"""
All classes needed for :class:`qtpynodeeditor.NodeDataModel` implementation of UFO and
composite tasks.
"""
import gi
import glob
import json
import logging
import networkx as nx
import numpy as np
import pkg_resources
import os
import re
gi.require_version('Ufo', '0.0')
from gi.repository import Ufo
from PyQt5 import QtCore
from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QDoubleValidator, QValidator
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QInputDialog, QLabel, QLineEdit,
                             QScrollArea, QWidget, QFileDialog, QFormLayout, QVBoxLayout, QMenu)
from qtpynodeeditor import (NodeData, NodeDataModel, NodeDataType, FlowScene, FlowView, Port,
                            PortType, opposite_port)
from threading import Lock
from tofu.flow.util import (CompositeConnection, FlowError, get_config_key, MODEL_ROLE, NODE_ROLE,
                            PROPERTY_ROLE, saved_kwargs)
from tofu.flow.filedirdialog import FileDirDialog


LOG = logging.getLogger(__name__)
UFO_PLUGIN_MANAGER = Ufo.PluginManager()


UFO_DATA_TYPE = NodeDataType(id="UfoBuffer", name=None)
ARRAY_DATA_TYPE = NodeDataType(id="NumpyArray", name=None)


class UfoIntValidator(QValidator):

    """Combined int and unsigned int validator."""

    def __init__(self, minimum, maximum, parent=None):
        super().__init__(parent=parent)
        self.minimum = minimum
        self.maximum = maximum

    def bottom(self):
        return self.minimum

    def top(self):
        return self.maximum

    def validate(self, input_str, pos):
        try:
            if self.minimum <= int(input_str) <= self.maximum:
                result = (QValidator.Acceptable, input_str, pos)
            else:
                result = (QValidator.Intermediate, input_str, pos)
        except ValueError:
            if not input_str or input_str == '-' and self.minimum < 0:
                result = (QValidator.Intermediate, input_str, pos)
            else:
                result = (QValidator.Invalid, input_str, pos)

        return result


class UfoRangeValidator(QValidator):

    """
    Range separated by comma validator. *num_items* specifies how many numbers must be in the
    string. *is_float* specifies if the numbers are floating point (integer or unsigned integer
    otherwise).
    """

    def __init__(self, num_items=None, is_float=True, parent=None):
        super().__init__(parent=parent)
        self.num_items = num_items
        self.is_float = is_float

    def validate(self, input_str, pos):
        float_regexp = r'[+-]|[+-]?(\d+(\.\d*)?|\.\d*)([eE][+-]?\d*)?'
        numbers = input_str.split(',')
        intermediate = False

        if self.num_items is not None and len(numbers) > self.num_items:
            # Incorrect number of items
            return (QValidator.Invalid, input_str, pos)

        for (i, number) in enumerate(numbers):
            number = number.lower().strip()
            if ('e' in number or '.' in number) and not self.is_float:
                # Integer expected
                return (QValidator.Invalid, input_str, pos)
            if self.is_float:
                try:
                    float(number)
                except:
                    if (not number or re.fullmatch(float_regexp, number)):
                        # Partial floating point number (e.g. ends with "e")
                        intermediate = True
                        continue
                    else:
                        return (QValidator.Invalid, input_str, pos)
            else:
                try:
                    int(number)
                except:
                    if not number or number == '-':
                        intermediate = True
                        continue
                    else:
                        return (QValidator.Invalid, input_str, pos)

        if intermediate or (self.num_items is not None and len(numbers) < self.num_items):
            # Not enough arguments received or some numbers are incomplete
            return (QValidator.Intermediate, input_str, pos)

        return (QValidator.Acceptable, input_str, pos)


class ViewItem(QObject):
    property_changed = pyqtSignal(QObject)

    def __init__(self, widget, default_value=None, tooltip=''):
        super().__init__(parent=None)
        self.widget = widget
        self.focus_info = False
        if tooltip:
            self.widget.setToolTip(tooltip)
        if default_value is not None:
            self.set(default_value)

    def on_changed(self, *args):
        """
        Only user interaction must emit signals in the descendants. Signal is emitted only if the
        user input is valid.
        """
        try:
            self.get()
            self.property_changed.emit(self)
        except:
            LOG.debug(f'{self}: invalid input')

    def get(self):
        ...

    def set(self, value):
        ...


class CheckBoxViewItem(ViewItem):
    def __init__(self, checked=False, tooltip=''):
        widget = QCheckBox()
        super().__init__(widget, default_value=checked, tooltip=tooltip)
        widget.clicked.connect(self.on_changed)

    def get(self):
        return self.widget.isChecked()

    def set(self, value):
        self.widget.setChecked(value)


class ComboBoxViewItem(ViewItem):
    def __init__(self, items, default_value=None, tooltip=''):
        widget = QComboBox()
        for item in items:
            widget.addItem(item)
        super().__init__(widget, default_value=default_value, tooltip=tooltip)
        widget.activated.connect(self.on_changed)

    def get(self):
        return self.widget.currentText()

    def set(self, value):
        self.widget.setCurrentText(value)


class FocusInterceptQLineEdit(QLineEdit):
    focus_in = pyqtSignal(QObject)

    def focusInEvent(self, event):
        self.focus_in.emit(self)
        return super().focusInEvent(event)


class QLineEditViewItem(ViewItem):
    focus_in = pyqtSignal(QObject)

    def __init__(self, default_value=None, tooltip='', intercept_focus=False):
        if intercept_focus:
            widget = FocusInterceptQLineEdit()
            widget.focus_in.connect(self.on_focus_in)
        else:
            widget = QLineEdit()

        super().__init__(widget, default_value=default_value, tooltip=tooltip)

        if intercept_focus:
            self.focus_info = True
        widget.textEdited.connect(self.on_changed)

    def on_focus_in(self, widget):
        self.focus_in.emit(self)

    def get(self):
        return self.widget.text()

    def set(self, value):
        self.widget.setText(str(value))


class NumberQLineEditViewItem(QLineEditViewItem):
    def __init__(self, minimum, maximum, default_value=None, tooltip=''):
        if default_value < minimum or default_value > maximum:
            raise ValueError(f'default value {default_value} not in limits [{minimum}, {maximum}]')
        tooltip += ' (range: {} - {})'.format(minimum, maximum)
        super().__init__(default_value=default_value, tooltip=tooltip, intercept_focus=True)
        validator = QDoubleValidator(float(minimum), float(maximum), 100)
        self.widget.setValidator(validator)

    def get(self):
        return float(super().get())


class IntQLineEditViewItem(QLineEditViewItem):
    def __init__(self, minimum, maximum, default_value=None, tooltip=''):
        if default_value < minimum or default_value > maximum:
            raise ValueError(f'default value {default_value} not in limits [{minimum}, {maximum}]')
        tooltip += ' (range: {} - {})'.format(minimum, maximum)
        super().__init__(default_value=default_value, tooltip=tooltip, intercept_focus=True)
        validator = UfoIntValidator(minimum, maximum)
        self.widget.setValidator(validator)

    def get(self):
        return int(super().get())


class RangeQLineEditViewItem(QLineEditViewItem):
    def __init__(self, default_value='', tooltip='', num_items=None, is_float=True):
        super().__init__(default_value=default_value, tooltip=tooltip, intercept_focus=True)
        validator = UfoRangeValidator(num_items=num_items, is_float=is_float)
        self.widget.setValidator(validator)

    def set(self, values):
        text = ','.join([str(value) for value in values]) if values else ''
        self.widget.setText(text)

    def get(self):
        text = super().get()
        if text:
            values = [float(num) for num in text.split(',')]
        else:
            values = []

        return values


def get_ufo_qline_edit_item(glib_prop, default_value, range_num_items=None, range_is_float=True):
    if glib_prop.value_type.name == 'GValueArray':
        item = RangeQLineEditViewItem(tooltip=glib_prop.blurb, default_value=default_value,
                                      num_items=range_num_items, is_float=range_is_float)
    elif glib_prop.value_type.name in ['gdouble', 'gfloat']:
        item = NumberQLineEditViewItem(glib_prop.minimum, glib_prop.maximum,
                                       default_value=default_value,
                                       tooltip=glib_prop.blurb)
    elif hasattr(glib_prop, 'minimum') and hasattr(glib_prop, 'maximum'):
        item = IntQLineEditViewItem(glib_prop.minimum, glib_prop.maximum,
                                    default_value=default_value,
                                    tooltip=glib_prop.blurb)
    else:
        item = QLineEditViewItem(default_value=str(default_value),
                                 tooltip=glib_prop.blurb)

    return item


class PropertyViewRecord:

    """Attribute-access to a view's item."""

    def __init__(self, view_item, label, visible):
        self.view_item = view_item
        self.label = label
        self.visible = visible

    def __str__(self):
        return repr(self)

    def __repr__(self):
        fmt = 'PropertyViewRecord(widget={}, visible={})'

        return fmt.format(self.view_item.widget, self.visible)


class MultiPropertyViewRecord:

    """Attribute-access to a multiple property view's item."""

    def __init__(self, model, widget, visible):
        self.model = model
        self.widget = widget
        self.visible = visible

    def __str__(self):
        return repr(self)

    def __repr__(self):
        fmt = 'MultiPropertyViewRecord(model={}, widget={}, visible={})'

        return fmt.format(self.model, self.widget, self.visible)


class PropertyView(QWidget):
    property_changed = pyqtSignal(str, object)
    item_focus_in = pyqtSignal(ViewItem, str)

    def __init__(self, properties=None, parent=None, scrollable=True):
        super().__init__(parent=parent)
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(0)

        self._properties = {}
        if properties:
            for (name, (item, active)) in properties.items():
                if name in self._properties:
                    raise ValueError("Item '{}' already exists".format(name))
                # Set the parent properly, so that set_property_visible won't try to show the item
                # widget and the label in their own windows before the view is shown
                item.widget.setParent(self)
                label = QLabel(name, parent=self)
                form_layout.addRow(label, item.widget)
                self._properties[name] = PropertyViewRecord(item, label, active)
                self.set_property_visible(name, active)
                item.property_changed.connect(self.on_property_changed)
                if item.focus_info:
                    item.focus_in.connect(self.on_item_focus_in)

        if scrollable:
            widget = QWidget()
            widget.setLayout(form_layout)
            scroll = QScrollArea()
            scroll.setWidget(widget)
            scroll.setWidgetResizable(True)
            main_layout = QVBoxLayout()
            main_layout.addWidget(scroll)
            self.setLayout(main_layout)
        else:
            self.setLayout(form_layout)

    @property
    def property_names(self):
        return self._properties.keys()

    def get_property(self, name):
        return self._properties[name].view_item.get()

    def set_property(self, name, value):
        return self._properties[name].view_item.set(value)

    def get_record(self, name):
        return self._properties[name]

    def on_property_changed(self, item):
        # Get item's name
        for (name, record) in self._properties.items():
            if item == record.view_item:
                break

        self.property_changed.emit(name, item.get())

    def on_item_focus_in(self, view_item):
        for (name, it) in self._properties.items():
            if it.view_item.widget == view_item.widget:
                self.item_focus_in.emit(view_item, name)
                break

    def is_property_visible(self, name):
        return self._properties[name].visible

    def set_property_visible(self, name, visible):
        self._properties[name].view_item.widget.setVisible(visible)
        self._properties[name].label.setVisible(visible)
        self._properties[name].visible = visible

    def restore_properties(self, values):
        for prop in self._properties:
            if prop not in values:
                LOG.debug(f'Property {prop} not stored, using default')
                continue
            value, visible = values[prop]
            self.set_property(prop, value)
            self.set_property_visible(prop, visible)

    def export_properties(self):
        values = {}
        for prop in self._properties:
            values[prop] = [self.get_property(prop), self.is_property_visible(prop)]

        return values

    def contextMenuEvent(self, event):
        contextMenu = QMenu(self)
        actions = {}

        for name in list(self._properties.keys()):
            action = contextMenu.addAction(name)
            action.setCheckable(True)
            action.setChecked(self._properties[name].visible)
            actions[action] = name

        contextMenu.addSeparator()
        show_all_action = contextMenu.addAction('Show All')
        hide_all_action = contextMenu.addAction('Hide All')

        action = contextMenu.exec_(self.mapToGlobal(event.pos()))
        if action:
            if action in actions:
                name = actions[action]
                checked = action.isChecked()
                self.set_property_visible(name, checked)
            elif action == show_all_action:
                for name in self._properties.keys():
                    self.set_property_visible(name, True)
            elif action == hide_all_action:
                for name in self._properties.keys():
                    self.set_property_visible(name, False)


class MultiPropertyView(QWidget):
    def __init__(self, groups, parent=None):
        super().__init__(parent=parent)
        self._group_box_layout = QVBoxLayout()
        main_layout = QVBoxLayout()
        widget = QWidget()
        widget.setLayout(self._group_box_layout)

        scroll = QScrollArea()
        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        self.setLayout(main_layout)
        main_layout.addWidget(scroll)

        self._groups = {}
        for (model, visible) in groups.items():
            if isinstance(model, PropertyModel):
                model_widget = QGroupBox(model.caption)
                layout = QVBoxLayout()
                model_widget.setLayout(layout)
                layout.addWidget(model.embedded_widget())
            else:
                model_widget = QLabel(model.caption, parent=self)
            record = MultiPropertyViewRecord(model, model_widget, visible)
            self._groups[model.caption] = record
            self._group_box_layout.addWidget(model_widget)
            self.set_group_visible(model.caption, visible)

    def __getitem__(self, key):
        return self._groups[key].model

    def __contains__(self, key):
        return key in self._groups

    def __iter__(self):
        return iter(self._groups)

    def export_groups(self):
        values = {}
        for name in self._groups:
            state = self._groups[name].model.save()
            values[name] = {'model': state,
                            'visible': self._groups[name].visible}

        return values

    def restore_groups(self, values):
        for name in values:
            self[name].restore(values[name]['model'])
            self.set_group_visible(name, values[name]['visible'])

    def set_group_visible(self, name, visible):
        self._groups[name].widget.setVisible(visible)
        self._groups[name].visible = visible

    def is_group_visible(self, name):
        return self._groups[name].visible

    def contextMenuEvent(self, event):
        contextMenu = QMenu(self)
        actions = {}

        for name in list(self._groups.keys()):
            action = contextMenu.addAction(name)
            action.setCheckable(True)
            action.setChecked(self._groups[name].visible)
            actions[action] = name

        contextMenu.addSeparator()
        show_all_action = contextMenu.addAction('Show All')
        hide_all_action = contextMenu.addAction('Hide All')

        action = contextMenu.exec_(self.mapToGlobal(event.pos()))
        if action:
            if action in actions:
                name = actions[action]
                checked = action.isChecked()
                self.set_group_visible(name, checked)
            elif action == show_all_action:
                for name in self._groups.keys():
                    self.set_group_visible(name, True)
            elif action == hide_all_action:
                for name in self._groups.keys():
                    self.set_group_visible(name, False)


class UfoModel(NodeDataModel):

    """The root parent of all other models in tofu flow."""

    data_type = UFO_DATA_TYPE
    item_focus_in = pyqtSignal(QObject, str, str, NodeDataModel)

    def __init__(self, style=None, parent=None):
        super().__init__(style=style, parent=parent)
        # This is the caption model wants to have when it's instantiated, however, it might
        # get a different caption from the scene because the captions must be unique within
        self.base_caption = self.caption
        self.skip = False

    def restore(self, state, restore_caption=False):
        if restore_caption:
            self.caption = state.get('caption', self.caption)

    def save(self):
        return {'caption': self.caption}

    def double_clicked(self, parent):
        ...

    def __repr__(self):
        return f'UfoModel({self.caption})'

    def __str__(self):
        return repr(self)


class PropertyModel(UfoModel):
    property_changed = pyqtSignal(UfoModel, str, object)

    def __init__(self, style=None, parent=None, scrollable=True):
        """*properties* is a dictionary of name: ViewItem items."""
        super().__init__(style=style, parent=parent)
        properties = self.make_properties()
        if properties:
            self.properties = list(properties.keys())
            self._view = PropertyView(properties=properties, scrollable=scrollable)
            self._view.property_changed.connect(self.on_property_changed)
            self._view.item_focus_in.connect(self.on_item_focus_in)
        else:
            self.properties = []
            self._view = None

    def __getitem__(self, key):
        return self._view.get_property(key)

    def __setitem__(self, key, value):
        return self._view.set_property(key, value)

    def __contains__(self, key):
        return key in self.properties

    def __iter__(self):
        return iter(self.properties)

    def get_view_item(self, name):
        return self._view.get_record(name).view_item

    def on_property_changed(self, name, value):
        self.property_changed.emit(self, name, value)

    def on_item_focus_in(self, item, name):
        self.item_focus_in.emit(item, name, self.caption, self)

    def make_properties(self):
        """*properties* is a dictionary of name: ViewItem items."""
        return {}

    def copy_properties(self):
        properties = self.make_properties()
        for (name, (item, active)) in properties.items():
            item.set(self[name])
            properties[name][-1] = self._view.is_property_visible(name)

        return properties

    def auto_fill(self):
        """Automatically fill properties (e.g. number of files, etc.)"""
        ...

    def resizable(self):
        return True

    def embedded_widget(self) -> QWidget:
        return self._view if self._view else None

    def restore(self, state, restore_caption=True):
        self._view.restore_properties(state['properties'])
        super().restore(state, restore_caption=restore_caption)

    def save(self):
        state = super().save()
        state['properties'] = self._view.export_properties()

        return state


class UfoTaskModel(PropertyModel):
    caption_visible = True

    def __init__(self, task_name, style=None, parent=None, scrollable=True):
        self._task_name = task_name
        self.caption = ' '.join([item[0].upper() + item[1:] for item in self.name.split('_')])
        self.needs_fixed_scheduler = False
        self.can_split_gpu_work = False
        super().__init__(style=style, parent=parent, scrollable=scrollable)

    def make_properties(self):
        hidden_properties = get_config_key('models', self._task_name, 'hidden-properties')
        range_properties = get_config_key('models', self._task_name, 'range-properties', default={})
        properties = {}
        ufo_task = UFO_PLUGIN_MANAGER.get_task(self._task_name)
        for prop in ufo_task.list_properties():
            if prop.name == 'num-processed':
                continue
            default_value = getattr(ufo_task.props, prop.name)
            if prop.value_type.name == 'gboolean':
                item = CheckBoxViewItem(checked=default_value, tooltip=prop.blurb)
            elif hasattr(prop, 'enum_class'):
                items = [name.value_nick for name in default_value.__enum_values__.values()]
                item = ComboBoxViewItem(items, default_value=default_value.value_nick,
                                        tooltip=prop.blurb)
            else:
                range_num_items, range_is_float = range_properties.get(prop.name, (None, True))
                item = get_ufo_qline_edit_item(prop, default_value=default_value,
                                               range_num_items=range_num_items,
                                               range_is_float=range_is_float)
            visible = True
            if hidden_properties and prop.name in hidden_properties:
                visible = False
            properties[prop.name] = [item, visible]

        return properties

    def create_ufo_task(self, region=None):
        if self.expects_multiple_inputs and region is None:
            raise UfoModelError(f'{self.caption} expects multiple inputs '
                                'but there is no node with such capability in the flow')

        ufo_task = UFO_PLUGIN_MANAGER.get_task(self._task_name)
        self._setup_ufo_task(ufo_task, region=region)

        return ufo_task

    def _setup_ufo_task(self, ufo_task, region=None):
        for prop in self:
            setattr(ufo_task.props, prop, self[prop])

    def reset_batches(self):
        """
        In case the model can process batches and has internal state depending on them, this is
        where it can be re-set.
        """
        pass

    @property
    def uses_gpu(self):
        return UFO_PLUGIN_MANAGER.get_task(self._task_name).uses_gpu()

    @property
    def expects_multiple_inputs(self):
        return False


def get_ufo_model_class(ufo_task_name):
    # Use this to determine inputs and outputs but create a new object in the constructor in order
    # to enable multiple instances having different parameter values
    _ufo_task = UFO_PLUGIN_MANAGER.get_task(ufo_task_name)
    ufo_task_num_inputs = _ufo_task.get_num_inputs()
    ufo_task_num_outputs = int(_ufo_task.get_mode() & Ufo.TaskMode.SINK == 0)

    class UfoAutoModel(UfoTaskModel):
        name = ufo_task_name.replace('-', '_')

        def __init__(self, style=None, parent=None, scrollable=True):
            self.num_ports = {PortType.input: ufo_task_num_inputs,
                              PortType.output: ufo_task_num_outputs}
            self.data_type = {}
            self.port_caption = {}
            self.port_caption_visible = {}

            for port_type in (PortType.input, PortType.output):
                self.data_type[port_type] = {}
                self.port_caption[port_type] = {}
                self.port_caption_visible[port_type] = {}
                for i in range(self.num_ports[port_type]):
                    port_captions = get_config_key('models', ufo_task_name, 'port-captions')
                    if port_captions:
                        port_caption = port_captions[port_type][str(i)]
                        port_caption_visible = True if port_caption else False
                    else:
                        port_caption = ''
                        port_caption_visible = False
                    self.data_type[port_type][i] = UFO_DATA_TYPE
                    self.port_caption[port_type][i] = port_caption
                    self.port_caption_visible[port_type][i] = port_caption_visible

            self.ufo_task = None
            super().__init__(ufo_task_name, style=style, parent=parent, scrollable=scrollable)

    return UfoAutoModel


class BaseCompositeModel(UfoModel):
    # Move functionality which can go here from CompositeModel here
    data_type = UFO_DATA_TYPE

    def __init__(self, models, connections, links=None, registry=None, style=None, parent=None):
        if registry is None:
            # This has to be keyword argument because of the qtpynodeeditor's node creation
            # mechanism, but the argument is actually required
            raise AttributeError('registry must be provided')

        super().__init__(style=style, parent=parent)

        # Nodes in the edit pop-up window
        self.window_parent = None
        self._property_links_model = None
        self._links = [] if links is None else links
        self._slave_property_links = []
        self._window_nodes = {}
        self._other_scene = None
        self._other_view = None
        self.num_ports = {PortType.input: 0,
                          PortType.output: 0}
        self.data_type = {PortType.input: {}, PortType.output: {}}
        self.port_caption = {PortType.input: {}, PortType.output: {}}
        self.port_caption_visible = {PortType.input: {}, PortType.output: {}}

        groups = {}
        self._registry = registry
        self._models = {}
        # Internal connections
        self._connections = connections
        # Composite port to subnode port mapping
        self._inside_ports = {}
        # Subnode port to composite port mapping
        self._outside_ports = {}

        for (name, state, visible, position) in models:
            # Don't use the deafault registry creation because embedded PropertyModel must have
            # scrollable set to False
            cls, orig_kwargs = registry.registered_model_creators()[name]
            # Don't mess with the original dictionary
            kwargs = {orig_key: orig_value for (orig_key, orig_value) in orig_kwargs.items()}
            if issubclass(cls, PropertyModel):
                kwargs['scrollable'] = False
            if 'num-inputs' in state:
                kwargs['num_inputs'] = state['num-inputs']
            model = cls(**kwargs)
            model.restore(state)
            self._models[model] = position
            groups[model] = visible
            model.item_focus_in.connect(self.on_item_focus_in)
            for port_type in ['input', 'output']:
                for index in range(model.num_ports[port_type]):
                    side = (model.caption, port_type, index)
                    if not any([conn.contains(*side) for conn in connections]):
                        i = self.num_ports[port_type]
                        self.data_type[port_type][i] = UFO_DATA_TYPE
                        port_caption = model.caption
                        if model.port_caption[port_type][index]:
                            port_caption += ':' + model.port_caption[port_type][index]
                        self.port_caption[port_type][i] = port_caption
                        self.port_caption_visible[port_type][i] = True
                        self._inside_ports[(port_type, i)] = (model, port_type, index)
                        self._outside_ports[side] = (port_type, i)
                        self.num_ports[port_type] += 1

        self._view = MultiPropertyView(groups)

    def __getitem__(self, key):
        return self._view[key]

    def __contains__(self, key):
        return key in self._view

    def __iter__(self):
        return iter(self._view)

    def __repr__(self):
        return f'Composite(caption={self.caption}, models={sorted(list(iter(self._view)))})'

    def __str__(self):
        return repr(self)

    def get_outside_port(self, unique_name, port_type, port_index):
        return self._outside_ports[(unique_name, port_type, port_index)]

    def get_model_and_port_index(self, port_type, port_index):
        model, spt, index = self._inside_ports[(port_type, port_index)]

        return (model, index)

    def embedded_widget(self) -> QWidget:
        return self._view if self._view else None

    def resizable(self):
        return True

    def on_item_focus_in(self, item, name, caption, model):
        self.item_focus_in.emit(item, name, self.caption + '->' + caption, model)

    @property
    def is_editing(self):
        """Is wubwindow open."""
        return self._window_nodes != {}

    @property
    def property_links_model(self):
        return self._property_links_model

    @property_links_model.setter
    def property_links_model(self, plm):
        self._property_links_model = plm
        for model in self._models:
            if isinstance(model, BaseCompositeModel):
                model.property_links_model = plm

    def contains_path(self, path):
        """Is there a caption *path* inside this model."""
        model = self
        for caption in path:
            if caption in model:
                model = model[caption]
            else:
                return False

        return True

    def get_model_from_path(self, path):
        """*path* is caption path (str)."""
        model = self
        for caption in path:
            model = model[caption]

        return model

    def is_model_inside(self, model):
        """Return True if *model* is inside at any level."""
        paths = self.get_leaf_paths()
        for path in paths:
            for item in path:
                if item == model:
                    return True

        return False

    def get_path_from_model(self, model):
        """*model* must be inside this composite model."""
        paths = self.get_leaf_paths()
        for path in paths:
            for (i, item) in enumerate(path):
                if item == model:
                    return path[:i + 1]

        raise KeyError(f'{model} not inside')

    def get_descendant_graph(self, in_subwindow=False):
        """
        Get all descendant models recursively in case there are composite models inside this model.
        If *in_subwindow* is True, return models shown to the user in the subwindow, otherwise the
        ones created at class instantiation. For composites inside this one, if *in_subwindow* is
        True return the subwindow models, but if it's not being edited instead raising an exception,
        return the internal models.
        """
        if in_subwindow and not self.is_editing:
            raise ValueError('in_subwindow True but no subwindow open')

        graph = nx.DiGraph()

        def descend(parent):
            if in_subwindow and parent.is_editing:
                models = [node.model for node in parent._window_nodes.values()]
            else:
                models = [parent[key] for key in parent]
            for model in models:
                graph.add_edge(parent, model)
                if isinstance(model, BaseCompositeModel):
                    descend(model)

        descend(self)

        return graph

    def get_leaf_paths(self, in_subwindow=False):
        graph = self.get_descendant_graph(in_subwindow=in_subwindow)
        leaves = [node for node in graph.nodes if graph.out_degree(node) == 0]
        paths = []
        for leaf in leaves:
            paths.append(list(nx.simple_paths.all_simple_paths(graph, self, leaf))[0])

        return paths

    def restore(self, state, restore_caption=True):
        self._connections = [CompositeConnection(*args) for args in state['connections']]
        self._view.restore_groups(state['models'])
        super().restore(state, restore_caption=restore_caption)

    def restore_links(self, node):
        if self.property_links_model:
            row = self.property_links_model.rowCount()
            for items in self._links:
                # A row can be restored only if no property from the state is in the link model
                # yet
                row_ok = True
                for str_path in items:
                    prop_name = str_path[-1]
                    model = self.get_model_from_path(str_path[:-1])
                    if self.property_links_model.find_items([node, model, prop_name],
                                                            [NODE_ROLE, MODEL_ROLE, PROPERTY_ROLE]):
                        LOG.info(f'{str_path[-2]}->{prop_name} already in property links')
                        row_ok = False
                        break
                if row_ok:
                    for (i, str_path) in enumerate(items):
                        model = self.get_model_from_path(str_path[:-1])
                        self.property_links_model.add_item(node, model, str_path[-1], row, i)
                    row += 1

    def save(self):
        state = {'name': self.name, 'caption': self.caption}
        state['models'] = self._view.export_groups()

        for (model, position) in self._models.items():
            state['models'][model.caption]['position'] = position
            # This is necessary for creating models from saved files
            state['models'][model.caption]['name'] = model.name

        state['connections'] = [conn.save() for conn in self._connections]
        if self.property_links_model:
            state['links'] = []
            paths = self.get_leaf_paths()
            models = [path[-1] for path in paths]
            items = self.property_links_model.get_model_links(models)
            for row in items.values():
                # First item in the row is this model, skip it
                state['links'].append([str_path[1:] for str_path in row])

        return state

    def on_connection_created(self, connection):
        self._other_scene.connection_deleted.disconnect(self.on_connection_deleted)
        self._other_scene.delete_connection(connection)
        self._other_scene.connection_deleted.connect(self.on_connection_deleted)

    def on_connection_deleted(self, connection):
        self._other_scene.connection_created.disconnect(self.on_connection_created)
        self._other_scene.restore_connection(connection.__getstate__())
        self._other_scene.connection_created.connect(self.on_connection_created)

    def double_clicked(self, parent):
        self.edit_in_window(parent=parent)

    def on_other_scene_double_clicked(self, node):
        node.model.double_clicked(self._other_view)

    def expand_into_graph(self, graph):
        """Expand to submodels in a *graph*, which is a networkx.DiGraph instance."""
        name_to_model = {}

        for model in self._models:
            LOG.debug(f'Adding node {model.name}')
            graph.add_node(model)
            name_to_model[model.caption] = model

        for conn in self._connections:
            source = name_to_model[conn.from_unique_name]
            dest = name_to_model[conn.to_unique_name]
            LOG.debug(f'Adding edge {source.name}@{conn.from_port_index} -> '
                      f'{dest.name}@{conn.to_port_index}')
            graph.add_edge(source, dest, input=conn.to_port_index, output=conn.from_port_index)

    def _expand_into_scene(self, scene, original_nodes=None, restore_captions=False):
        # unique name to node instance mapping
        name_to_node = {}

        for model in self._models:
            if original_nodes and model.caption in original_nodes:
                node = scene.restore_node(original_nodes[model.caption])
            else:
                with saved_kwargs(scene.registry, model.__getstate__()):
                    if restore_captions:
                        node = scene.create_node(model.__class__)
                    else:
                        # This is the main scene, links restoration takes place in expand_into_scene
                        # for all nodes including composites
                        node = scene.create_node(model.__class__, restore_links=False)
            if isinstance(model, PropertyModel) or isinstance(model, BaseCompositeModel):
                node.model.restore(model.save(), restore_caption=restore_captions)
                if isinstance(node.model, BaseCompositeModel):
                    node.model.property_links_model = self.property_links_model
            else:
                node.model.restore(model.save())
            name_to_node[model.caption] = node
            if self._models[model] is not None:
                node.position = (self._models[model]['x'], self._models[model]['y'])

        for conn in self._connections:
            f_node = name_to_node[conn.from_unique_name]
            t_node = name_to_node[conn.to_unique_name]
            f_port = f_node[PortType.output][conn.from_port_index]
            t_port = t_node[PortType.input][conn.to_port_index]
            scene.create_connection(f_port, t_port, check_cycles=False)

        return name_to_node

    def add_slave_links(self):
        self._slave_property_links = []

        if not self.property_links_model:
            return

        for node in self._window_nodes.values():
            if isinstance(node.model, BaseCompositeModel):
                paths = node.model.get_leaf_paths(in_subwindow=node.model._window_nodes != {})
            else:
                paths = [[node.model]]
            # Propagate all signals from leaves to the original models
            for path in paths:
                str_path = [m.caption for m in path]
                new_model = path[-1]
                orig_model = self.get_model_from_path(str_path)
                # Create a link from this node's model instances to the original root
                # models in the link model (there can be other composites along the way to
                # the root
                root_model = self.property_links_model.get_root_model(orig_model)
                if root_model:
                    prop_names = self.property_links_model.get_model_properties(root_model)
                    for prop_name in prop_names:
                        if (new_model, prop_name) not in self._slave_property_links:
                            # In order to remove slaves when the subwindow is closed, register
                            # the slaves with respect to the most nested composite
                            registering_model = path[-2] if len(path) > 1 else self
                            if registering_model.is_editing:
                                registering_model._slave_property_links.append((new_model,
                                                                                prop_name))
                                registering_model.property_links_model.add_silent(new_model,
                                                                                  prop_name,
                                                                                  root_model,
                                                                                  prop_name)
                            if registering_model.window_parent:
                                # If the registering model has a parent, register also the
                                # models in it's internal model view
                                new_model = registering_model[path[-1].caption]
                                registering_model = registering_model.window_parent
                                registering_model._slave_property_links.append((new_model,
                                                                                prop_name))
                                registering_model.property_links_model.add_silent(new_model,
                                                                                  prop_name,
                                                                                  root_model,
                                                                                  prop_name)

    def edit_in_window(self, parent=None):
        self._other_scene = FlowScene(registry=self._registry)
        self._other_scene.node_double_clicked.connect(self.on_other_scene_double_clicked)
        self._window_nodes = self._expand_into_scene(self._other_scene, restore_captions=True)

        # Store references to parent composites
        for node in self._window_nodes.values():
            if isinstance(node.model, BaseCompositeModel):
                node.model.window_parent = self

        # Property links have to be registered with respect to the top composite model because
        # it's property model's property model is registered in property links
        window_parent = self
        while window_parent.window_parent:
            window_parent = window_parent.window_parent
        window_parent.add_slave_links()

        # Disable manipulation because the number of ports is fixed, so we can't e.g. internally
        # connect two nodes and delete the newly occupied port from the composite node
        self._other_scene.allow_node_creation = False
        self._other_scene.allow_node_deletion = False
        # There is no allow_connection_creation/deletion, so take care of it here
        self._other_scene.connection_created.connect(self.on_connection_created)
        self._other_scene.connection_deleted.connect(self.on_connection_deleted)
        self._other_view = FlowView(self._other_scene, parent=parent)
        self._other_view.setWindowFlag(Qt.Window, True)
        self._other_view.closeEvent = self.view_close_event
        self._other_view.setWindowTitle(self.name)
        self._other_view.resize(900, 600)
        self._other_view.show()

    def view_close_event(self, event):
        for node in self._window_nodes.values():
            # Clse all composite children recursively first
            if isinstance(node.model, BaseCompositeModel) and node.model.is_editing:
                node.model._other_view.close()
                node.model.window_parent = None

        for (unique_name, node) in self._window_nodes.items():
            self._view[unique_name].restore(node.model.save())
        if self.property_links_model:
            for (model, prop_name) in self._slave_property_links:
                self.property_links_model.remove_silent(model, prop_name)

        self._slave_property_links = []
        self._window_nodes = {}
        self._other_scene = None
        self._other_view = None

    def expand_into_scene(self, scene, composite_node, original_nodes=None):
        """
        Expand this node into *scene* and replace *composite_node*'s connections with
        connections going straight into its subnodes. Also create connections internal to this
        node and update property links. *original_nodes* is a dictionary in form {caption:
        node_state} which will be used for positioning of the replacing nodes
        (scene.restore_node instead of scene.create_node will be called).
        """
        assert self.property_links_model is not None
        # Connections to external nodes
        connections = []
        # name_to_node is in format caption: new node dictionary
        # Internal connections are handled in _expand_into_scene
        name_to_node = self._expand_into_scene(scene, original_nodes=original_nodes,
                                               restore_captions=False)

        for port_type in [PortType.input, PortType.output]:
            for index, port in composite_node[port_type].items():
                if port.connections:
                    connection = port.connections[0]
                    outside_port = connection.valid_ports[opposite_port(port_type)]
                    internal_model, pt, pi = self._inside_ports[(port_type, index)]
                    connections.append((outside_port,
                                        name_to_node[internal_model.caption][pt][pi]))

        # Update property links
        for (subcaption, subnode) in name_to_node.items():
            if isinstance(subnode.model, BaseCompositeModel):
                # Get all leaf PropertyModel instances
                paths = subnode.model.get_leaf_paths()
            else:
                paths = [[subnode.model]]
            # In case selected node is composite, replace all leaf node links
            for path in paths:
                str_path = [model.caption for model in path]
                # Captions might have changed if subnode captions were equal to other captions
                # in the scene and the composite node which is being replaced contains still the
                # old ones
                old_str_path = [subcaption] + str_path[1:]
                old_model = composite_node.model.get_model_from_path(old_str_path)
                self.property_links_model.replace_item(subnode, path[-1], old_model)

            subnode.graphics_object.setSelected(True)

        scene.remove_node(composite_node)

        # Create outside connections only after the composite node has been deleted to prevent
        # creating multiple connections per input port in the outside nodes
        for outside, inside in connections:
            scene.create_connection(outside, inside, check_cycles=False)

        return name_to_node, connections


def get_composite_model_class(composite_name, models, connections, links=None):
    if not composite_name:
        raise UfoModelError('composite name must be specified')

    class CompositeModel(BaseCompositeModel):
        name = composite_name
        data_type = UFO_DATA_TYPE

        def __init__(self, style=None, parent=None, registry=None):
            super().__init__(models, connections, links=links, registry=registry,
                             style=style, parent=parent)

    model = CompositeModel
    model.caption_visible = True
    model.caption = composite_name

    return model


class UfoGeneralBackprojectModel(UfoTaskModel):
    name = 'general_backproject'
    num_ports = {PortType.input: 1, PortType.output: 1}
    data_type = UFO_DATA_TYPE

    def __init__(self, style=None, parent=None, scrollable=True):
        super().__init__('general-backproject', style=style, parent=parent, scrollable=scrollable)
        self.needs_fixed_scheduler = True
        self.can_split_gpu_work = True

    def make_properties(self):
        properties = super().make_properties()
        slice_memory_coeff = NumberQLineEditViewItem(0.01, 1., default_value=0.8,
                                                     tooltip='Portion of used GPU memory')
        properties['slice-memory-coeff'] = [slice_memory_coeff, False]

        return properties

    def split_gpu_work(self, gpus):
        from tofu.genreco import make_runs, DTYPE_CL_SIZE

        def check_region(region):
            if not len(np.arange(*self[region])):
                raise UfoModelError(f'Invalid {region} {self[region]}')

        # Check if ranges are OK
        check_region('region')
        check_region('x-region')
        check_region('y-region')

        gpu_indices = range(len(gpus))
        bpp = DTYPE_CL_SIZE[self['store-type']]
        runs = make_runs(gpus, gpu_indices, self['x-region'], self['y-region'],
                         self['region'], bpp, slice_memory_coeff=self['slice-memory-coeff'])

        return runs

    def _setup_ufo_task(self, ufo_task, region=None):
        separate = ['region', 'slice-memory-coeff']
        task_props = [prop for prop in self if prop not in separate]
        for prop in task_props:
            setattr(ufo_task.props, prop, self[prop])

        # Set region separately in case there are multiple inputs
        current_region = self['region'] if region is None else region
        setattr(ufo_task.props, 'region', current_region)


class UfoVaryingInputModel(UfoTaskModel):

    """Base class for models which can have varying number if inputs."""

    def __init__(self, task_name, style=None, parent=None, scrollable=True, num_inputs=None,
                 dialog_title='Number of inputs', dialog_label='Number of inputs:'):
        if not num_inputs:
            num_inputs, ok = QInputDialog.getInt(parent,
                                                 dialog_title,
                                                 dialog_label,
                                                 value=1, minValue=1, maxValue=10, step=1)
            if not ok:
                raise UfoModelError('Number of inputs must be specified')
        self.num_ports = {PortType.input: num_inputs, PortType.output: 1}
        self.data_type = {PortType.output: {0: UFO_DATA_TYPE}}
        self.port_caption = {PortType.output: {0: ''}}
        self.port_caption_visible = {PortType.output: {0: False}}

        self.data_type[PortType.input] = {}
        self.port_caption[PortType.input] = {}
        self.port_caption_visible[PortType.input] = {}

        for i in range(num_inputs):
            self.data_type[PortType.input][i] = UFO_DATA_TYPE
            self.port_caption[PortType.input][i] = ''
            self.port_caption_visible[PortType.input][i] = False

        super().__init__(task_name, style=style, parent=parent, scrollable=scrollable)

    def save(self):
        state = super().save()
        state['num-inputs'] = self.num_ports['input']

        return state


class UfoOpenCLModel(UfoVaryingInputModel):
    name = 'opencl'

    def __init__(self, style=None, parent=None, scrollable=True, num_inputs=None):
        super().__init__('opencl', style=style, parent=parent, scrollable=scrollable,
                         num_inputs=num_inputs)

    def _setup_ufo_task(self, ufo_task, region=None):
        for prop in self:
            if prop in ['filename', 'source']:
                # opencl task really needs NULL
                value = self[prop] if self[prop] else None
            else:
                value = self[prop]
            setattr(ufo_task.props, prop, value)


class UfoReadModel(UfoTaskModel):
    name = 'read'
    num_ports = {PortType.input: 0, PortType.output: 1}
    data_type = UFO_DATA_TYPE

    def __init__(self, style=None, parent=None, scrollable=True):
        super().__init__('read', style=style, parent=parent, scrollable=scrollable)

    def auto_fill(self):
        import glob
        import imageio

        if os.path.isdir(self['path']):
            paths = sorted(glob.glob(os.path.join(self['path'], '*')))
        else:
            paths = [self['path']]

        num_images = 0
        for path in paths:
            try:
                num_images += len(imageio.get_reader(path))
            except:
                LOG.error(f"Error reading '{path}'")

        if not num_images:
            raise UfoModelError(f"No images found in {self['path']}")

        self['number'] = num_images

    def double_clicked(self, parent):
        current_path = self['path']
        if not os.path.isdir(current_path):
            current_path = os.path.dirname(current_path)
        if not current_path:
            current_path = QtCore.QDir.homePath()
        dialog = FileDirDialog()
        if dialog.exec_():
            self['path'] = dialog.selectedFiles()[0]

    def _setup_ufo_task(self, ufo_task, region=None):
        for prop in self:
            if prop != 'raw-bitdepth' or self['raw-bitdepth']:
                setattr(ufo_task.props, prop, self[prop])


class UfoRetrievePhaseModel(UfoVaryingInputModel):
    name = 'retrieve_phase'

    def __init__(self, style=None, parent=None, scrollable=True, num_inputs=None):
        super().__init__('retrieve-phase', style=style, parent=parent, scrollable=scrollable,
                         dialog_title='Multi-distance Setup', dialog_label='Number of distances:',
                         num_inputs=num_inputs)

    def make_properties(self):
        properties = super().make_properties()

        # Override distance property based on how many inputs we expect
        tooltip = properties['distance'][0].widget.toolTip()
        item = RangeQLineEditViewItem(tooltip=tooltip, default_value=[],
                                      num_items=self.num_ports['input'], is_float=True)
        properties['distance'] = [item, True]
        if self.num_ports['input'] > 1:
            properties['method'][0].set('ctf_multidistance')
            properties['method'][0].widget.setEnabled(False)
            properties['distance-x'][0].widget.setEnabled(False)
            properties['distance-y'][0].widget.setEnabled(False)

        return properties


class UfoWriteModel(UfoTaskModel):
    name = 'write'
    num_ports = {PortType.input: 1, PortType.output: 0}
    data_type = UFO_DATA_TYPE

    def __init__(self, style=None, parent=None, scrollable=True):
        super().__init__('write', style=style, parent=parent, scrollable=scrollable)

    def double_clicked(self, parent):
        current_path = os.path.dirname(self['filename'])
        if not current_path:
            current_path = QtCore.QDir.homePath()
        file_name, _ = QFileDialog.getSaveFileName(None, "Select File Name", current_path)
        if file_name:
            self['filename'] = file_name

    @property
    def expects_multiple_inputs(self):
        return '{region}' in self['filename']

    def _setup_ufo_task(self, ufo_task, region=None):
        if region is not None and not self.expects_multiple_inputs:
            raise UfoModelError('Write got region without enabling multiple inputs. '
                                'Add {region} somewhere in the "filename" field to enable it.')
        super()._setup_ufo_task(ufo_task, region=region)
        filename = self['filename']
        if region is not None and self.expects_multiple_inputs:
            filename = filename.format(region=region[0])
        setattr(ufo_task.props, 'filename', filename)


class _Batch(QObject):

    finished = pyqtSignal(int)

    def __init__(self, ufo_task, shape, batch_id):
        super().__init__(parent=None)
        self.batch_id = batch_id
        self.data = np.empty(shape, dtype=np.float32)
        ptr = self.data.__array_interface__['data'][0]
        ufo_task.props.pointer = ptr
        ufo_task.props.max_size = self.data.nbytes
        ufo_task.connect('processed', self._on_processed)
        self.num_processed = 0

    def _on_processed(self, ufo_task):
        self.num_processed += 1
        if self.num_processed == self.data.shape[0]:
            self.finished.emit(self.batch_id)


class UfoMemoryOutModel(UfoTaskModel):
    name = 'memory_out'
    num_ports = {PortType.input: 1, PortType.output: 1}
    data_type = {PortType.input: {0: UFO_DATA_TYPE},
                 PortType.output: {0: ARRAY_DATA_TYPE}}
    port_caption = {PortType.input: {0: ''},
                    PortType.output: {0: ''}}
    port_caption_visible = {PortType.input: {0: False},
                            PortType.output: {0: False}}

    def __init__(self, style=None, parent=None, scrollable=True):
        self._lock = Lock()
        self.reset_batches()
        super().__init__('memory-out', style=style, parent=parent, scrollable=scrollable)

    @property
    def expects_multiple_inputs(self):
        return self['number'] == '{region}'

    def make_properties(self):
        width_item = IntQLineEditViewItem(0, 1000000, default_value=0, tooltip='Input width')
        height_item = IntQLineEditViewItem(0, 1000000, default_value=0, tooltip='Input height')
        depth_item = IntQLineEditViewItem(0, 1000000, default_value=1,
                                          tooltip='Input depth (for 2D images should be 1)')
        number_item = QLineEditViewItem(default_value=1, tooltip='Number of inputs')
        properties = {'width': [width_item, True],
                      'height': [height_item, True],
                      'depth': [depth_item, True],
                      'number': [number_item, True]}

        return properties

    def consume_batch(self, batch_id):
        def consume(current_batch):
            LOG.debug(f'{self.caption}: consuming {current_batch.batch_id} (caller {batch_id})')
            self._current_data = current_batch.data
            self.data_updated.emit(0)
            # Free memory up
            self._batches[self._expecting_id] = None

        with self._lock:
            if self._expecting_id == batch_id:
                consume(self._batches[self._expecting_id])
                self._expecting_id += 1
                while self._expecting_id in self._waiting_list:
                    consume(self._batches[self._expecting_id])
                    del self._waiting_list[self._waiting_list.index(self._expecting_id)]
                    self._expecting_id += 1
            else:
                LOG.debug(f'{self.caption}: putting {batch_id} on waiting list')
                self._waiting_list.append(batch_id)

    def out_data(self, port: int) -> NodeData:
        LOG.debug(f'{self.caption}: out_data shape:'
                  f'{None if self._current_data is None else self._current_data.shape}')
        return self._current_data

    def reset_batches(self):
        self._batches = []
        self._waiting_list = []
        self._expecting_id = 0
        self._current_data = None

    def _setup_ufo_task(self, ufo_task, region=None):
        if region is not None and not self.expects_multiple_inputs:
            raise UfoModelError('Memory Out got region without enabling multiple inputs. '
                                'Type {region} in the "number" field to enable it.')
        number = int(self['number']) if region is None else len(np.arange(*region))
        shape = (number, self['height'], self['width'])
        with self._lock:
            batch = _Batch(ufo_task, shape, len(self._batches))
            self._batches.append(batch)
            batch.finished.connect(self.consume_batch)


class ImageViewerModel(UfoModel):
    name = 'image_viewer'
    caption = 'Image Viewer'
    num_ports = {PortType.input: 1,
                 PortType.output: 0,
                 }
    data_type = ARRAY_DATA_TYPE

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._node_data = None
        from tofu.flow.viewer import ImageViewer
        self._widget = ImageViewer()
        self._reset = True

    def embedded_widget(self):
        return self._widget

    def resizable(self):
        return True

    def double_clicked(self, parent):
        try:
            if self._widget.images is not None and not self._widget.popup_visible:
                import pyqtgraph
                self._widget.popup()
        except ImportError:
            LOG.debug('pyqtgraph not installed, not popping up')

    def set_in_data(self, data: NodeData, port: Port):
        if data is not None:
            if self._reset:
                self._widget.images = data
                self._reset = False
            else:
                self._widget.append(data)

    def reset_batches(self):
        self._reset = True

    def cleanup(self):
        self._widget.cleanup()


def get_ufo_model_classes(names=None):
    all_names = set(UFO_PLUGIN_MANAGER.get_all_task_names())
    # stamp causes a gobject unref warning
    blacklist = set(['general-backproject', 'memory-in', 'memory-out', 'opencl', 'read',
                     'retrieve-phase', 'stamp', 'write'])
    all_names = list(all_names - blacklist)

    return (get_ufo_model_class(name) for name in names or all_names)


def get_composite_model_classes_from_json(state):
    """
    Get composite model classes from their json representation. This is recursive in case a user
    creates a composite inside the scene, then adds nodes and creates another composite with the
    first one inside and doesn't export explicitly the first one. The order of returned classes is
    bottom -> up, i.e. first the classes which have striclty non-composite submodels are returned
    and the top level class is last.
    """
    classes = []

    def go_down(current):
        connections = [CompositeConnection(*args) for args in current['connections']]
        submodels = []
        for (key, model) in current['models'].items():
            if 'models' in model['model'] and 'connections' in model['model']:
                go_down(current['models'][key]['model'])
            # models are tuples (name, state, visible, position)
            submodels.append((model['name'],
                              model['model'],
                              model['visible'],
                              model['position']))
        classes.append(get_composite_model_class(current['name'], submodels, connections,
                                                 links=current.get('links', None)))

    go_down(state)

    return classes


def get_composite_model_classes():
    from xdg import xdg_data_home

    composite_lists = []
    paths = [pkg_resources.resource_filename(__name__, 'composites'),
             os.path.join(xdg_data_home(), 'tofu', 'flows', 'composites')]

    for path in paths:
        file_names = sorted(glob.glob(os.path.join(path, '*.cm')))
        for file_name in file_names:
            LOG.debug(f'Loading composite from {file_name}')
            try:
                with open(file_name, 'r') as f:
                    state = json.load(f)
                composite_lists.append(get_composite_model_classes_from_json(state))
            except Exception as e:
                LOG.error(e, exc_info=True)

    return composite_lists


class UfoModelError(FlowError):
    pass
