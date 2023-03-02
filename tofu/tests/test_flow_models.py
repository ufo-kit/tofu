import pytest
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QValidator
from PyQt5.QtWidgets import QFileDialog, QInputDialog, QLineEdit
from tofu.flow.main import get_filled_registry
from tofu.flow.models import (CheckBoxViewItem, ComboBoxViewItem, get_composite_model_class,
                              get_composite_model_classes, get_composite_model_classes_from_json,
                              get_ufo_model_class, get_ufo_model_classes, ImageViewerModel,
                              IntQLineEditViewItem, MultiPropertyView, NumberQLineEditViewItem,
                              PropertyModel, PropertyView, QLineEditViewItem,
                              RangeQLineEditViewItem, UfoGeneralBackprojectModel, UfoIntValidator,
                              UfoMemoryOutModel, UfoModelError, UfoRangeValidator, UfoReadModel,
                              UfoRetrievePhaseModel, UfoModel, UfoTaskModel,
                              UfoVaryingInputModel, UfoWriteModel, ViewItem)
from tofu.flow.scene import UfoScene
from tofu.flow.util import CompositeConnection, MODEL_ROLE, PROPERTY_ROLE
from tofu.tests.flow_util import populate_link_model


def check_property_changed_emit(qtbot, view_item, expected, gui_func, gui_args, gui_kwargs=None,
                                show=False):
    if gui_kwargs is None:
        gui_kwargs = {}

    def on_changed(vit):
        vit.change_called = True

    view_item.change_called = False
    view_item.property_changed.connect(on_changed)
    qtbot.addWidget(view_item.widget)

    if show:
        # without show the mouse click for QCheckBox doesn't happen, bug in pytest-qt?
        view_item.widget.show()

    # Store old value for later check of programmatic change
    old_value = view_item.get()

    # Simulate user interaction
    gui_func(*gui_args, **gui_kwargs)

    # Value must have been set
    assert view_item.get() == expected
    # Signal must have been emitted
    assert view_item.change_called

    view_item.change_called = False
    view_item.set(old_value)
    # Signal must be emitted only on user interacion, not programmatic access
    assert not view_item.change_called


def make_properties():
    return {
        'int': [IntQLineEditViewItem(0, 100, default_value=10), True],
        'float': [NumberQLineEditViewItem(0, 100, default_value=0), True],
        'string': [QLineEditViewItem(default_value='foo'), True],
        'range': [RangeQLineEditViewItem(default_value=[1, 2, 3], num_items=3, is_float=True),
                  True],
        'choices': [ComboBoxViewItem(['a', 'b', 'c']), True],
        'check': [CheckBoxViewItem(checked=True), True]
    }


class DummyPropertyModel(PropertyModel):
    def make_properties(self):
        return make_properties()


@pytest.fixture(scope='function')
def property_view():
    return PropertyView(properties=make_properties(), scrollable=False)


@pytest.fixture(scope='function')
def multi_property_view(nodes):
    groups = {nodes['cpm'].model: True, nodes['read'].model: False}

    return MultiPropertyView(groups=groups)


def make_composite_model_class(nodes, name='foobar'):
    # We want to connect cpm:Pad to average, thus we need to get the outside port of the cpm
    # composite which corresponds to the pad model
    pad_index = nodes['cpm'].model.get_outside_port('Pad', 'output', 0)[1]
    connections = [CompositeConnection('cpm', pad_index, 'Average', 0)]
    state = [('cpm', nodes['cpm'].model.save(), True, None),
             ('average', nodes['average'].model.save(), True, None)]

    return get_composite_model_class(name, state, connections)


def create_scene(qtbot, registry):
    scene = UfoScene(registry=registry)
    if scene.views():
        for view in scene.views():
            qtbot.addWidget(view)

    return scene


def make_composite_node_in_scene(qtbot, nodes):
    model_cls = make_composite_model_class(nodes)
    registry = get_filled_registry()
    # Register both composites so that we can create them
    registry.register_model(nodes['cpm'].model.__class__,
                            category='Composite', registry=registry)
    registry.register_model(model_cls, category='Composite', registry=registry)
    scene = create_scene(qtbot, registry)
    node = scene.create_node(model_cls)

    return (scene, node)


@pytest.fixture(scope='function')
def composite_model(nodes):
    # Make sure 'cpm', which is inside this composite model, has been registered
    registry = nodes['cpm'].model._registry
    model_cls = make_composite_model_class(nodes)
    registry.register_model(model_cls, category='Composite', registry=registry)

    return model_cls(registry=registry)


@pytest.fixture(scope='function')
def general_backproject(qtbot):
    model = UfoGeneralBackprojectModel()
    qtbot.addWidget(model.embedded_widget())

    return model


@pytest.fixture(scope='function')
def read_model(qtbot):
    model = UfoReadModel()
    qtbot.addWidget(model.embedded_widget())

    return model


@pytest.fixture(scope='function')
def write_model(qtbot):
    model = UfoWriteModel()
    qtbot.addWidget(model.embedded_widget())

    return model


@pytest.fixture(scope='function')
def memory_out_model(qtbot):
    model = UfoMemoryOutModel()
    model['width'] = 100
    model['height'] = 100
    qtbot.addWidget(model.embedded_widget())

    return model


@pytest.fixture(scope='function')
def image_viewer_model(qtbot):
    model = ImageViewerModel()
    qtbot.addWidget(model.embedded_widget())

    return model


def test_ufo_int_validator():
    validator = UfoIntValidator(-10, 10)

    def check(input_str, expected):
        assert validator.validate(input_str, -1)[0] == expected

    check('0', QValidator.Acceptable)
    check('1', QValidator.Acceptable)
    check('-1', QValidator.Acceptable)
    check('101', QValidator.Intermediate)
    check('-101', QValidator.Intermediate)
    check('-', QValidator.Intermediate)
    check('1.', QValidator.Invalid)
    check('1.0', QValidator.Invalid)
    check('asdf', QValidator.Invalid)

    validator = UfoIntValidator(3, 10)
    check('1', QValidator.Intermediate)


def test_ufo_range_validator():
    def check(validator, input_str, expected):
        assert validator.validate(input_str, len(input_str))[0] == expected

    # Integer
    validator = UfoRangeValidator(num_items=3, is_float=False)
    check(validator, ',,', QValidator.Intermediate)
    check(validator, ' ,,', QValidator.Intermediate)
    check(validator, '1,1,', QValidator.Intermediate)
    check(validator, ',1,', QValidator.Intermediate)
    check(validator, '1,-2,3', QValidator.Acceptable)
    check(validator, '1,1.0,1', QValidator.Invalid)
    check(validator, '-1,s,-1', QValidator.Invalid)
    check(validator, '1,1,1,1', QValidator.Invalid)
    check(validator, '1,1,1,', QValidator.Invalid)

    # Float
    validator = UfoRangeValidator(num_items=3, is_float=True)
    check(validator, ',,', QValidator.Intermediate)
    check(validator, ' ,,', QValidator.Intermediate)
    check(validator, '.,,', QValidator.Intermediate)
    check(validator, '.e,,', QValidator.Intermediate)
    check(validator, '.e-,,', QValidator.Intermediate)
    check(validator, '.e+,,', QValidator.Intermediate)
    check(validator, '1.0e,,', QValidator.Intermediate)
    check(validator, '1.0e+,,', QValidator.Intermediate)
    check(validator, '1.0e-,,', QValidator.Intermediate)
    check(validator, '1e,,', QValidator.Intermediate)
    check(validator, '1e+,,', QValidator.Intermediate)
    check(validator, '1e-,,', QValidator.Intermediate)
    check(validator, '.1e,,', QValidator.Intermediate)
    check(validator, '.1e+,,', QValidator.Intermediate)
    check(validator, '.1e-,,', QValidator.Intermediate)

    check(validator, '1,1,1', QValidator.Acceptable)
    check(validator, '-1,1,1', QValidator.Acceptable)
    check(validator, '1.,1.,1', QValidator.Acceptable)
    check(validator, '-1.,1.,1', QValidator.Acceptable)
    check(validator, '1.0e1,1.0,1', QValidator.Acceptable)
    check(validator, '1.0e+1,1.0,1', QValidator.Acceptable)
    check(validator, '1.0e-1,1.0,1', QValidator.Acceptable)
    check(validator, '.1,1.0,1', QValidator.Acceptable)
    check(validator, '.1e-1,1.0,1', QValidator.Acceptable)
    check(validator, '.1e+1,1.0,1', QValidator.Acceptable)
    check(validator, '.1e1,1.0,1', QValidator.Acceptable)

    check(validator, 'e,,', QValidator.Invalid)
    check(validator, 'e.,,', QValidator.Invalid)
    check(validator, '+e,,', QValidator.Invalid)
    check(validator, '-e,,', QValidator.Invalid)
    check(validator, '+e.,,', QValidator.Invalid)
    check(validator, '-e.,,', QValidator.Invalid)
    check(validator, '1+,,', QValidator.Invalid)
    check(validator, '1-,,', QValidator.Invalid)
    check(validator, 'gfd,1,3', QValidator.Invalid)


def test_view_item_init(qtbot):
    def get(inst):
        return inst.widget.text()

    def set(inst, value):
        inst.widget.setText(value)

    def on_changed(vit):
        vit.change_called = True

    ViewItem.get = get
    ViewItem.set = set
    edit = QLineEdit()
    qtbot.addWidget(edit)
    vit = ViewItem(edit, default_value='foo', tooltip='tooltip')
    edit.textEdited.connect(vit.on_changed)
    assert vit.widget.toolTip() == 'tooltip'
    assert vit.widget.text() == 'foo'

    check_property_changed_emit(qtbot, vit, 'fooa', qtbot.keyClick, (edit, 'a'))


def test_check_box_view_item(qtbot):
    assert CheckBoxViewItem(checked=True).get()
    vit = CheckBoxViewItem(checked=False, tooltip='tooltip')
    assert vit.widget.toolTip() == 'tooltip'
    assert not vit.get()

    check_property_changed_emit(qtbot, vit, True, qtbot.mouseClick,
                                (vit.widget, Qt.LeftButton), show=True)


def test_combo_box_view_item(qtbot):
    items = ['a', 'b', 'c']
    vit = ComboBoxViewItem(items, default_value='b', tooltip='tooltip')
    assert vit.widget.toolTip() == 'tooltip'
    assert vit.get() == 'b'
    check_property_changed_emit(qtbot, vit, 'c', qtbot.keyClick, (vit.widget, 'c'))


def test_qline_edit_view_item(qtbot):
    vit = QLineEditViewItem(default_value='foo', tooltip='tooltip')
    assert vit.widget.toolTip() == 'tooltip'
    assert vit.get() == 'foo'
    check_property_changed_emit(qtbot, vit, 'fooc', qtbot.keyClick, (vit.widget, 'c'))


def test_number_qline_edit_view_item(qtbot):
    with pytest.raises(ValueError):
        NumberQLineEditViewItem(-100, 100, default_value=1000)
    with pytest.raises(ValueError):
        NumberQLineEditViewItem(-100, 100, default_value=-1000)

    vit = NumberQLineEditViewItem(-100., 100., default_value=0., tooltip='tooltip')
    assert vit.widget.toolTip().startswith('tooltip')
    assert vit.get() == 0
    # is 0.0, after key click "1" will be 0.01
    check_property_changed_emit(qtbot, vit, 0.01, qtbot.keyClick, (vit.widget, '1'))


def test_int_qline_edit_view_item(qtbot):
    with pytest.raises(ValueError):
        IntQLineEditViewItem(-100, 100, default_value=1000)
    with pytest.raises(ValueError):
        IntQLineEditViewItem(-100, 100, default_value=-1000)

    vit = IntQLineEditViewItem(-100, 100, default_value=0, tooltip='tooltip')
    assert vit.widget.toolTip().startswith('tooltip')
    assert vit.get() == 0
    # is 0, after key click "1" will be 01, thus 1
    check_property_changed_emit(qtbot, vit, 1, qtbot.keyClick, (vit.widget, '1'))


def test_range_edit_view_item(qtbot):
    vit = RangeQLineEditViewItem(default_value=[1.0, 2.0, 3.0], tooltip='tooltip')
    assert vit.widget.toolTip().startswith('tooltip')
    assert vit.get() == [1.0, 2.0, 3.0]
    # Last is 3.0, after key click "1" will be 3.01
    check_property_changed_emit(qtbot, vit, [1.0, 2.0, 3.01], qtbot.keyClick, (vit.widget, '1'))


class TestPropertyView:
    def test_init(self, qtbot, property_view):
        assert len(property_view.property_names) > 0

        # Defaults must pass
        PropertyView()

    def test_get_property(self, qtbot, property_view):
        assert property_view.get_property('int') == 10

    def test_set_property(self, qtbot, property_view):
        property_view.set_property('int', 50)
        assert property_view.get_property('int') == 50

    def test_on_property_changed(self, qtbot, property_view):
        widget = property_view._properties['int'].view_item.widget
        qtbot.addWidget(widget)
        qtbot.keyClick(widget, '0')
        assert property_view.get_property('int') == 100

    def test_is_property_visible(self, qtbot, property_view):
        assert property_view.is_property_visible('int')

    def test_set_property_visible(self, qtbot, property_view):
        visible = not property_view.is_property_visible('int')
        property_view.set_property_visible('int', visible)
        assert property_view.is_property_visible('int') == visible

    def test_restore_properties(self, qtbot, property_view):
        props = property_view.export_properties()
        property_view.set_property('int', props['int'][0] + 1)
        property_view.restore_properties(props)
        assert property_view.get_property('int') == props['int'][0]

    def test_export_properties(self, qtbot, property_view):
        props = property_view.export_properties()
        assert 'int' in props
        assert props['int'][0] == property_view.get_property('int')
        assert props['int'][1] == property_view.is_property_visible('int')


class TestMultiPropertyView:
    def test_init(self, qtbot, multi_property_view):
        assert len(list(iter(multi_property_view))) == 2

    def test_getitem(self, qtbot, multi_property_view, nodes):
        assert multi_property_view['cpm'] == nodes['cpm'].model

    def test_contains(self, qtbot, multi_property_view):
        assert 'cpm' in multi_property_view
        assert 'foo' not in multi_property_view

    def test_iter(self, qtbot, multi_property_view):
        assert set(list(iter(multi_property_view))) == set(['cpm', 'Read'])

    def test_export_groups(self, qtbot, multi_property_view):
        state = multi_property_view.export_groups()
        multi_property_view.set_group_visible('Read', False)

        assert state['Read']['model']['caption'] == 'Read'
        assert not state['Read']['visible']

    def test_restore_groups(self, qtbot, multi_property_view, nodes):
        multi_property_view['Read']['number'] = 100
        state = multi_property_view.export_groups()
        multi_property_view['Read']['number'] = 1000
        multi_property_view.restore_groups(state)
        assert multi_property_view['Read']['number']

    def test_set_group_visible(self, qtbot, multi_property_view):
        visible = not multi_property_view.is_group_visible('cpm')
        multi_property_view.set_group_visible('cpm', visible)
        assert multi_property_view.is_group_visible('cpm') == visible

    def test_is_group_visible(self, qtbot, multi_property_view):
        assert multi_property_view.is_group_visible('cpm')
        assert not multi_property_view.is_group_visible('Read')


class TestUfoModel:
    def test_init(self):
        model = UfoModel()
        assert model.caption == model.base_caption

    def test_restore(self):
        model = UfoModel()
        state = {'caption': 'foo'}
        old_caption = model.caption

        model.restore(state, restore_caption=False)
        assert model.caption == old_caption

        model.restore(state, restore_caption=True)
        assert model.caption == 'foo'

        # 'caption' not in state, the old one must be preserved
        model = UfoModel()
        old_caption = model.caption
        model.restore({}, restore_caption=True)

        assert model.caption == old_caption

    def save(self):
        model = UfoModel()
        model.caption = 'foo'

        assert model.save()['caption'] == 'foo'


class TestPropertyModel:
    def test_init(self, qtbot):
        PropertyModel()
        model = DummyPropertyModel()
        # make_properties must be called
        assert set(model.properties) == set(make_properties().keys())

    def test_getitem(self, qtbot):
        model = DummyPropertyModel()
        model['int']
        with pytest.raises(KeyError):
            model['foo']

    def test_setitem(self, qtbot):
        model = DummyPropertyModel()
        model['int'] = 132
        assert model['int'] == 132

    def test_contains(self, qtbot):
        model = DummyPropertyModel()
        assert 'int' in model
        assert 'foo' not in model

    def test_iter(self, qtbot):
        model = DummyPropertyModel()
        assert set(iter(model)) == set(make_properties().keys())

    def test_on_property_changed(self, qtbot):
        def callback(model, name, value):
            self.called_name = name
            self.called_value = value

        model = DummyPropertyModel()
        model.property_changed.connect(callback)
        widget = model._view._properties['int'].view_item.widget
        qtbot.addWidget(widget)
        qtbot.keyClick(widget, '0')

        assert self.called_value == model['int']
        assert self.called_name == 'int'

    def test_make_properties(self, qtbot):
        props = DummyPropertyModel().make_properties()
        assert props.keys() == make_properties().keys()
        assert PropertyModel().make_properties() == {}

    def test_copy_properties(self, qtbot):
        model = DummyPropertyModel()
        model['int'] = 123
        visible = not model._view.is_property_visible('int')
        model._view.set_property_visible('int', visible)
        properties = model.copy_properties()
        # It has to be a deep copy, so changing the model properties cannot affect the copy
        model['int'] = 12
        model._view.set_property_visible('int', not visible)

        assert properties['int'][0].get() == 123
        assert properties['int'][1] == visible

    def test_embedded_widget(self, qtbot):
        assert PropertyModel().embedded_widget() is None
        assert isinstance(DummyPropertyModel().embedded_widget(), PropertyView)

    def test_restore(self, qtbot):
        model = DummyPropertyModel()
        state = model.save()
        old_value = model['int']
        old_caption = model.caption
        visible = not model._view.is_property_visible('int')

        model['int'] = old_value + 1
        model._view.set_property_visible('int', visible)
        model.caption = 'Foo'

        model.restore(state, restore_caption=False)
        assert model['int'] == old_value
        assert model._view.is_property_visible('int') == (not visible)
        assert model.caption == 'Foo'

        model.restore(state, restore_caption=True)
        assert model.caption == old_caption

    def test_save(self, qtbot):
        model = DummyPropertyModel()
        old_value = model['int']
        visible = not model._view.is_property_visible('int')

        model['int'] = old_value + 1
        model._view.set_property_visible('int', visible)
        model.caption = 'Foo'

        state = model.save()
        assert state['properties']['int'][0] == old_value + 1
        assert state['properties']['int'][1] == visible
        assert state['caption'] == 'Foo'


class TestUfoTaskModel:
    def test_init(self, qtbot):
        model = UfoTaskModel('flat-field-correct')
        assert model.properties
        # A task doesn't need any special treatment by default
        assert not model.expects_multiple_inputs
        assert not model.can_split_gpu_work
        assert not model.needs_fixed_scheduler

    def test_make_properties(self, qtbot):
        model = UfoTaskModel('flat-field-correct')
        # Config takes effect
        assert not model._view.is_property_visible('dark-scale')

    def test_create_ufo_task(self, qtbot):
        model = UfoTaskModel('flat-field-correct')
        model['dark-scale'] = 12.3
        task = model.create_ufo_task()
        assert task.props.dark_scale == pytest.approx(12.3)

    def test_uses_gpu(self, qtbot):
        model = UfoTaskModel('flat-field-correct')
        assert model.uses_gpu

        model = UfoTaskModel('read')
        assert not model.uses_gpu


def test_get_ufo_model_class(qtbot):
    # flat correction is a fairly complicated task to test
    task_name = 'flat-field-correct'
    model_cls = get_ufo_model_class(task_name)
    # Model class attributes
    assert model_cls.name == 'flat_field_correct'

    model = model_cls()
    # Model instance attributes
    assert model.num_ports['input'] == 3
    assert model.num_ports['output'] == 1
    assert model.port_caption['input'][0] == 'radios'
    assert model.port_caption['input'][1] == 'darks'
    assert model.port_caption['input'][2] == 'flats'
    assert model.port_caption['output'][0] == ''


class TestBaseCompositeModel:
    def test_init(self, qtbot, monkeypatch, composite_model, scene):
        # cpm has 1 input and 2 outputs (read and pad are not connected) and average has 1 input and
        # 1 output, but cpm is connected with average, which reduces both port types by 1
        assert composite_model.num_ports['input'] == 1
        assert composite_model.num_ports['output'] == 2

        for port_type in ['input', 'output']:
            for i in range(composite_model.num_ports[port_type]):
                submodel, j = composite_model.get_model_and_port_index(port_type, i)
                subcaption = submodel.port_caption[port_type][j]
                if subcaption:
                    subcaption = ':' + subcaption
                assert (composite_model.port_caption[port_type][i] == submodel.caption + subcaption)

        assert composite_model._view

        # num-inputs must take effect
        monkeypatch.setattr(QInputDialog, "getInt", lambda *args, **kwargs: (2, True))
        monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: ('with-pr', True))
        node = scene.create_node(scene.registry.create('retrieve_phase'))
        node.graphics_object.setSelected(True)
        node = scene.create_composite()
        assert node.model.get_model_from_path(['Retrieve Phase']).num_ports['input'] == 2
        # and it must not affect default registry creators
        kwargs = scene.registry.registered_model_creators()['retrieve_phase'][1]
        assert 'num_inputs' not in kwargs

    def test_getitem(self, qtbot, composite_model, nodes):
        assert composite_model['cpm']
        assert composite_model['Average']

        with pytest.raises(KeyError):
            composite_model['foo']

    def test_contains(self, qtbot, composite_model, nodes):
        assert 'cpm' in composite_model
        assert 'foo' not in composite_model

    def test_iter(self, qtbot, composite_model):
        assert set(list(iter(composite_model))) == set(['cpm', 'Average'])

    def test_get_descendant_graph(self, qtbot, monkeypatch, composite_model, nodes):
        graph = composite_model.get_descendant_graph()

        cpm = composite_model['cpm']
        assert (composite_model, cpm) in graph.edges
        assert (composite_model, composite_model['Average']) in graph.edges
        assert (cpm, cpm['Read']) in graph.edges
        assert (cpm, cpm['Pad']) in graph.edges

        with pytest.raises(ValueError):
            composite_model.get_descendant_graph(in_subwindow=True)

        # Subwindow editing
        composite_model.edit_in_window()
        qtbot.addWidget(composite_model._other_view)
        graph = composite_model.get_descendant_graph(in_subwindow=True)

        cpm = composite_model._window_nodes['cpm'].model
        average = composite_model._window_nodes['Average'].model
        assert (composite_model, cpm) in graph.edges
        assert (composite_model, average) in graph.edges
        assert (cpm, cpm['Read']) in graph.edges
        assert (cpm, cpm['Pad']) in graph.edges
        composite_model._other_view.close()

        # Create outer composite with foobar inside, get_descendant_graph with in_subwindow=True
        # when outer is being edited and foobar not must return outer subwindow models and foobar's
        # internal models
        scene = create_scene(qtbot, composite_model._registry)
        inner = scene.create_node(composite_model.__class__)
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('outer', True))
        inner.graphics_object.setSelected(True)
        outer = scene.create_composite().model

        outer.edit_in_window()
        qtbot.addWidget(outer._other_view)
        graph = outer.get_descendant_graph(in_subwindow=True)
        inner = outer._window_nodes['foobar'].model
        assert (outer, inner) in graph.edges
        assert (inner, inner['Average']) in graph.edges
        assert (inner['cpm'], inner['cpm']['Read']) in graph.edges
        outer._other_view.close()

    def test_contains_path(self, qtbot, composite_model, nodes):
        assert composite_model.contains_path(['Average'])
        assert composite_model.contains_path(['cpm'])
        assert composite_model.contains_path(['cpm', 'Read'])
        assert not composite_model.contains_path(['cpm', 'Read 2'])
        assert not composite_model.contains_path(['foo'])

    def test_get_model_from_path(self, qtbot, composite_model, nodes):
        assert composite_model.get_model_from_path(['cpm', 'Read'])

        with pytest.raises(KeyError):
            composite_model.get_model_from_path(['foo'])

    def test_is_model_inside(self, qtbot, composite_model, nodes):
        model = composite_model.get_model_from_path(['cpm'])
        assert composite_model.is_model_inside(model)
        model = composite_model.get_model_from_path(['cpm', 'Read'])
        assert composite_model.is_model_inside(model)
        assert not composite_model.is_model_inside(nodes['read_2'].model)

    def test_get_path_from_model(self, qtbot, composite_model, nodes):
        cpm = composite_model['cpm']

        path = composite_model.get_path_from_model(cpm)
        assert path == [composite_model, cpm]

        path = composite_model.get_path_from_model(cpm['Read'])
        assert path == [composite_model, cpm, cpm['Read']]

        model = composite_model['cpm']['Read']
        path = composite_model.get_path_from_model(model)
        assert path == [composite_model, cpm, model]

        with pytest.raises(KeyError):
            composite_model.get_path_from_model(nodes['read_2'].model)

    def test_leaf_paths(self, qtbot, composite_model, nodes):
        leaves = composite_model.get_leaf_paths(in_subwindow=False)
        cpm = composite_model['cpm']
        assert len(leaves) == 3
        assert [composite_model, cpm, cpm['Read']] in leaves
        assert [composite_model, cpm, cpm['Pad']] in leaves
        assert [composite_model, composite_model['Average']] in leaves

    def test_set_property_links_model(self, qtbot, link_model, composite_model):
        composite_model.property_links_model = link_model
        assert composite_model.property_links_model == link_model
        # The property links model must be set also for children
        assert composite_model['cpm'].property_links_model == link_model

    def test_get_outside_port(self, qtbot, composite_model):
        # There is one input corresponding to cpm's pad model
        cpm = composite_model.get_model_from_path(['cpm'])
        pad_index = cpm.get_outside_port('Pad', 'input', 0)[1]
        composite_model.get_outside_port('cpm', 'input', pad_index)

        # and two outputs: cpm's read and average
        read_index = cpm.get_outside_port('Read', 'output', 0)[1]
        composite_model.get_outside_port('cpm', 'output', read_index)
        composite_model.get_outside_port('Average', 'output', 0)

    def test_get_model_and_port_index(self, qtbot, composite_model):
        model, index = composite_model.get_model_and_port_index('input', 0)
        cpm = composite_model.get_model_from_path(['cpm'])
        # There is only one input: Pad. Get it's internal cpm's index and compare with what the
        # outer composite object gives.
        pad_index = cpm.get_outside_port('Pad', 'input', 0)[1]
        assert model == cpm
        assert index == pad_index

        # There are two output ports, one from cpm's read model and one from average
        average = composite_model.get_model_from_path(['Average'])
        # Get read index from the cpm inside the composite_model and not from the cpm in the 'nodes'
        # fixsture because those are not the same instance and the read output index might be
        # different in those two instances because the ports are dictionaries
        read_index = cpm.get_outside_port('Read', 'output', 0)[1]
        outputs = [composite_model.get_model_and_port_index('output', 0)]
        outputs.append(composite_model.get_model_and_port_index('output', 1))
        assert (cpm, read_index) in outputs
        assert (average, 0) in outputs

    def test_embedded_widget(self, qtbot, composite_model):
        assert isinstance(composite_model.embedded_widget(), MultiPropertyView)

    def test_restore(self, qtbot, composite_model):
        state = composite_model.save()
        old_value = composite_model['cpm']['Pad']['width']
        old_caption = composite_model.caption
        visible = not composite_model._view.is_group_visible('cpm')

        composite_model['cpm']['Pad']['width'] = old_value + 1
        composite_model._view.set_group_visible('cpm', visible)
        composite_model.caption = 'Foo'

        composite_model.restore(state, restore_caption=False)
        assert composite_model['cpm']['Pad']['width'] == old_value
        assert composite_model._view.is_group_visible('cpm') == (not visible)
        assert composite_model.caption == 'Foo'

        composite_model.restore(state, restore_caption=True)
        assert composite_model.caption == old_caption
        conn = composite_model._connections[0]
        assert [[conn.from_unique_name, conn.from_port_index,
                 conn.to_unique_name, conn.to_port_index]] == state['connections']

    def test_restore_links(self, qtbot, nodes):
        def check_links(node, link_model):
            assert link_model.rowCount() == 1
            assert link_model.columnCount() == 3
            assert link_model.find_items((node.model['cpm']['Read'], 'number'),
                                         (MODEL_ROLE, PROPERTY_ROLE))
            assert link_model.find_items((node.model['cpm']['Pad'], 'height'),
                                         (MODEL_ROLE, PROPERTY_ROLE))
            assert link_model.find_items((node.model['Average'], 'number'),
                                         (MODEL_ROLE, PROPERTY_ROLE))
            assert not link_model.find_items((node.model['cpm']['Read'], 'height'),
                                             (MODEL_ROLE, PROPERTY_ROLE))

        scene, node = make_composite_node_in_scene(qtbot, nodes)
        link_model = scene.property_links_model
        link_model.add_item(node, node.model['cpm']['Read'], 'number', 0, 0)
        link_model.add_item(node, node.model['cpm']['Pad'], 'height', 0, 1)
        link_model.add_item(node, node.model['Average'], 'number', 0, 2)

        # Set links to the newly created links
        node.model._links = node.model.save()['links']

        # Link model has to have the exact same entries as before
        link_model.clear()
        node.model.restore_links(node)
        check_links(node, link_model)

        # Second time doesn't add the same links twice
        node.model.restore_links(node)
        check_links(node, link_model)

    def test_save(self, qtbot, nodes):
        scene, node = make_composite_node_in_scene(qtbot, nodes)
        link_model = scene.property_links_model
        cpm = node.model['cpm']
        link_model.add_item(node, node.model['cpm']['Read'], 'number', 0, 0)
        link_model.add_item(node, node.model['cpm']['Pad'], 'height', 0, 1)
        link_model.add_item(node, node.model['Average'], 'number', 0, 2)
        old_value = node.model['cpm']['Pad']['width']
        visible = not node.model._view.is_group_visible('cpm')

        node.model['cpm']['Pad']['width'] = old_value + 1
        node.model._view.set_group_visible('cpm', visible)
        node.model.caption = 'Foo'

        state = node.model.save()
        cpm_models_state = state['models']['cpm']['model']['models']

        assert state['models']['cpm']['visible'] == visible
        assert cpm_models_state['Pad']['model']['properties']['width'][0] == old_value + 1
        assert state['caption'] == 'Foo'

        cpm = node.model.get_model_from_path(['cpm'])
        pad_index = cpm.get_outside_port('Pad', 'output', 0)[1]
        assert state['connections'] == [['cpm', pad_index, 'Average', 0]]

        # Property links
        links = link_model.get_model_links([path[-1] for path in node.model.get_leaf_paths()])
        links = [[str_path[1:] for str_path in row] for row in links.values()]
        saved = node.model.save()['links']

        # One row
        assert len(saved) == len(links) == 1
        # All linked paths must be saved
        for str_path in saved[0]:
            assert str_path in links[0]

    def test_on_connection_created(self, qtbot, composite_model):
        composite_model.edit_in_window()
        qtbot.addWidget(composite_model._other_view)
        for node in composite_model._other_scene.nodes.values():
            if node.model.caption == 'cpm':
                read_index = node.model.get_outside_port('Read', 'output', 0)[1]
                pad_index = node.model.get_outside_port('Pad', 'input', 0)[1]
                output_port = node['output'][read_index]
                input_port = node['input'][pad_index]

        num_connections = len(composite_model._other_scene.connections)
        composite_model._other_scene.create_connection(output_port, input_port)

        # No new connections allowed
        assert len(composite_model._other_scene.connections) == num_connections
        composite_model._other_view.close()

    def test_on_connection_deleted(self, qtbot, composite_model):
        composite_model.edit_in_window()
        qtbot.addWidget(composite_model._other_view)
        num_connections = len(composite_model._other_scene.connections)
        composite_model._other_scene.delete_connection(composite_model._other_scene.connections[0])

        # No connection deletions
        assert len(composite_model._other_scene.connections) == num_connections
        composite_model._other_view.close()

    def test_double_clicked(self, qtbot, composite_model):
        composite_model.double_clicked(None)
        qtbot.addWidget(composite_model._other_view)
        assert composite_model.is_editing and composite_model._other_view is not None

    def test_on_other_scene_double_clicked(self, qtbot, composite_model):
        composite_model.double_clicked(None)
        qtbot.addWidget(composite_model._other_view)
        for node in composite_model._other_scene.nodes.values():
            if node.model.caption == 'cpm':
                node.model.double_clicked(composite_model._other_view)
                qtbot.addWidget(node.model._other_view)
                assert composite_model.is_editing and composite_model._other_view is not None
                break

    def test_expand_into_graph(self, qtbot, composite_model):
        import networkx as nx
        graph = nx.MultiDiGraph()
        composite_model.expand_into_graph(graph)
        src, dst, ports = list(graph.edges.data())[0]
        conn = composite_model._connections[0]
        gt = [conn.from_unique_name, conn.from_port_index, conn.to_unique_name, conn.to_port_index]
        conn_graph = [src.caption, ports['output'], dst.caption, ports['input']]

        assert conn_graph == gt

    def test_add_slave_links(self, qtbot, monkeypatch, nodes):
        def crosscheck(model, root_model, property_name, link_model):
            key = (model, property_name)
            root_key = (root_model, property_name)

            assert link_model._silent[key] == root_key
            assert key in link_model._slaves[root_key]

        scene, node = make_composite_node_in_scene(qtbot, nodes)
        link_model = scene.property_links_model
        link_model.add_item(node, node.model['cpm']['Read'], 'number', 0, 0)
        link_model.add_item(node, node.model['cpm']['Pad'], 'height', 0, 1)
        link_model.add_item(node, node.model['Average'], 'number', 0, 2)

        # Not being edited, nothing registered
        node.model.add_slave_links()
        assert link_model._silent == {}

        node.model.edit_in_window()
        qtbot.addWidget(node.model._other_view)
        # Standard editing setup
        assert hasattr(node.model, '_other_scene')
        assert hasattr(node.model, '_other_view')
        assert not node.model._other_scene.allow_node_creation
        assert not node.model._other_scene.allow_node_deletion
        # Test foobar's subwindow, registering model is cpm and its internal models must be linked
        crosscheck(node.model._window_nodes['cpm'].model['Read'],
                   node.model['cpm']['Read'], 'number', link_model)
        crosscheck(node.model._window_nodes['cpm'].model['Pad'],
                   node.model['cpm']['Pad'], 'height', link_model)
        crosscheck(node.model._window_nodes['Average'].model,
                   node.model['Average'], 'number', link_model)

        # Test foobar's subwindow and cpm's subwindow, cpm and also its models in the subwindow must
        # be linked
        cpm = node.model._window_nodes['cpm'].model
        cpm.edit_in_window()
        qtbot.addWidget(cpm._other_view)
        assert cpm.window_parent == node.model
        crosscheck(cpm._window_nodes['Read'].model,
                   node.model['cpm']['Read'], 'number', link_model)
        crosscheck(cpm._window_nodes['Pad'].model,
                   node.model['cpm']['Pad'], 'height', link_model)

        # Add one more composite layer, outer->foobar->cpm->Model, both registering model and its
        # window_parent must be jinked
        node.model._other_view.close()
        assert cpm._other_view is None

        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('outermost', True))
        node.graphics_object.setSelected(True)

        outer = scene.create_composite()
        outer.model.edit_in_window()
        qtbot.addWidget(outer.model._other_view)
        node_sub = outer.model._window_nodes['foobar']

        node_sub.model.edit_in_window()
        qtbot.addWidget(node_sub.model._other_view)
        cpm = node_sub.model._window_nodes['cpm'].model
        cpm.edit_in_window()
        qtbot.addWidget(cpm._other_view)
        crosscheck(node_sub.model._window_nodes['cpm'].model['Read'],
                   outer.model['foobar']['cpm']['Read'], 'number', link_model)
        crosscheck(node_sub.model._window_nodes['cpm'].model['Pad'],
                   outer.model['foobar']['cpm']['Pad'], 'height', link_model)
        crosscheck(node_sub.model._window_nodes['Average'].model,
                   outer.model['foobar']['Average'], 'number', link_model)
        crosscheck(cpm._window_nodes['Read'].model,
                   outer.model['foobar']['cpm']['Read'], 'number', link_model)
        crosscheck(cpm._window_nodes['Pad'].model,
                   outer.model['foobar']['cpm']['Pad'], 'height', link_model)
        cpm._other_view.close()
        node_sub.model._other_view.close()
        outer.model._other_view.close()

    def test_edit_in_window(self, qtbot, nodes):
        composite_model = nodes['cpm'].model
        link_model = composite_model.property_links_model
        populate_link_model(link_model, nodes)

        composite_model.edit_in_window()
        qtbot.addWidget(composite_model._other_view)
        assert hasattr(composite_model, '_other_scene')
        assert hasattr(composite_model, '_other_view')
        assert not composite_model._other_scene.allow_node_creation
        assert not composite_model._other_scene.allow_node_deletion

        # Silent must have been added with root cpm's read model
        assert (list(link_model._slaves.keys())[0]
                == (composite_model.get_model_from_path(['Read']), 'y'))

        # Subcomposites must link to their parent models
        scene, node = make_composite_node_in_scene(qtbot, nodes)
        node.model.edit_in_window()
        qtbot.addWidget(node.model._other_view)
        assert node.model._window_nodes['cpm'].model.window_parent == node.model
        node.model._other_view.close()
        composite_model._other_view.close()

    def test_view_close_event(self, qtbot, nodes):
        composite_model = nodes['cpm'].model
        link_model = composite_model.property_links_model
        populate_link_model(link_model, nodes)
        composite_model.edit_in_window()
        qtbot.addWidget(composite_model._other_view)

        for node in composite_model._other_scene.nodes.values():
            if node.model.caption == 'Read':
                widget = node.model.embedded_widget()._properties['y'].view_item.widget
                qtbot.addWidget(node.model.embedded_widget())
                qtbot.keyClicks(widget, '11')
            else:
                # Pad
                node.model['width'] += 10

        # Linked models must be updated immediately
        assert composite_model['Read']['y'] == 11
        assert nodes['read'].model['number'] == 11
        assert nodes['read_2'].model['height'] == 11

        composite_model._other_view.close()

        # Original models in the composite must be updated after close
        assert composite_model['Pad']['width'] == 10

        # Silent model must be removed (it was the only one, so test for {} is sufficient)
        assert link_model._slaves == {}
        assert link_model._silent == {}

    def test_expand_into_scene(self, qtbot, monkeypatch):
        def get_int(*args, **kwargs):
            return self.get_int_return

        monkeypatch.setattr(QInputDialog, "getInt", get_int)
        nodes = {}
        registry = get_filled_registry()
        scene = create_scene(qtbot, registry)

        # Composite node
        for name in ['read', 'pad']:
            model_cls = registry.create(name)
            node = scene.create_node(model_cls)
            node.graphics_object.setSelected(True)

        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        nodes['cpm'] = scene.create_composite()
        nodes['cpm'].graphics_object.setSelected(False)

        model_cls = registry.create('average')
        nodes['average'] = scene.create_node(model_cls)

        self.get_int_return = (2, True)
        model_cls = registry.create('retrieve_phase')
        nodes['retrieve_phase'] = scene.create_node(model_cls)

        # Add null node to create an outside connection
        null_cls = registry.create('null')
        null_node = scene.create_node(null_cls)

        # Make a property link
        scene.property_links_model.add_item(nodes['cpm'], nodes['cpm'].model['Read'],
                                            'number', 0, 0)
        scene.property_links_model.add_item(nodes['cpm'], nodes['cpm'].model['Pad'], 'width', 0, 1)
        # Export composite and reload it so that it remembers the links (important for testing of
        # adding property link duplicates)
        cpm_cls_with_links = get_composite_model_classes_from_json(nodes['cpm'].model.save())[0]
        registry.register_model(cpm_cls_with_links, category='Composites', registry=registry)
        scene.remove_node(nodes['cpm'])
        nodes['cpm'] = scene.create_node(registry.create('cpm'))

        # Outer composite node has inside: read, pad, average; pad and average are connected
        # read and pad are encapsulated in an internal composite cpm
        pad_index = nodes['cpm'].model.get_outside_port('Pad', 'output', 0)[1]
        scene.create_connection(nodes['cpm']['output'][pad_index], nodes['average']['input'][0])
        nodes['cpm'].graphics_object.setSelected(True)
        nodes['average'].graphics_object.setSelected(True)
        nodes['retrieve_phase'].graphics_object.setSelected(True)
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('foobar', True))
        scene.create_composite()
        composite_node = scene.selected_nodes()[0]
        composite_model = composite_node.model

        # Create outside connection from outer composite's average to null
        port_null = null_node['input'][0]
        # average_index = nodes['cpm'].model.get_outside_port('Pad', 'output', 0)[1]
        # Get the average index dynamically because it might be mapped to a different output port
        # every time (reader in cpm makes another output)
        average_index = composite_model.get_outside_port('Average', 'output', 0)[1]
        port_composite = composite_node['output'][average_index]
        scene.create_connection(port_composite, port_null)

        # Change some property to see if it persists after expansion
        composite_model['cpm']['Read']['number'] = 123

        # Make sure the nested num-inputs takes effect, i.e. QInputDialog.getInt invocation must
        # fail the test
        self.get_int_return = (None, False)

        composite_model.expand_into_scene(scene, composite_node)

        # Nodes must be there
        assert (set([node.model.caption for node in scene.nodes.values()])
                == set(['Null', 'Average', 'Retrieve Phase', 'cpm']))

        # num-inputs took effect
        for node in scene.nodes.values():
            if node.model.caption == 'Retrieve Phase':
                assert node.model.num_ports['input'] == 2
                break

        # Changed properties must be there
        for node in scene.nodes.values():
            if node.model.caption == 'cpm':
                assert node.model['Read']['number'] == 123
                break

        # Connections must be preserved
        for connection in scene.connections:
            if connection.get_node('output').model.caption == 'cpm':
                # Internal composite connection Pad -> Average must be there
                assert connection.get_node('input').model.caption == 'Average'
                cpm_index = connection.get_port_index('output')
                cpm_model = connection.get_node('output').model
                assert cpm_model.get_model_and_port_index('output', cpm_index)[0].caption == 'Pad'
            else:
                # Outside connection Average -> Null must be there
                assert connection.get_node('input').model.caption == 'Null'

        # Property links must be there
        assert scene.property_links_model.rowCount() == 1

        # Original composite node must be gone
        assert composite_node not in scene.nodes.values()


def test_get_composite_model_class(qtbot, nodes):
    model_cls = make_composite_model_class(nodes)

    with pytest.raises(AttributeError):
        # Registry must be provided
        model_cls()

    # Name must be provided
    with pytest.raises(UfoModelError):
        make_composite_model_class(nodes, name='')

    with pytest.raises(UfoModelError):
        make_composite_model_class(nodes, name=None)


class TestUfoGeneralBackprojectModel:
    def test_init(self, general_backproject):
        assert general_backproject.num_ports['input'] == 1
        assert general_backproject.num_ports['output'] == 1
        assert general_backproject.needs_fixed_scheduler is True
        assert general_backproject.can_split_gpu_work is True

    def test_make_properties(self, general_backproject):
        props = general_backproject.make_properties()
        assert 'slice-memory-coeff' in props

    def test_split_gpu_work(self, general_backproject):
        from gi.repository import Ufo
        resources = Ufo.Resources()
        gpus = resources.get_gpu_nodes()
        general_backproject['x-region'] = [-100., 100., 1.]
        general_backproject['y-region'] = [-100., 100., 1.]
        general_backproject['region'] = [-100., 100., 1.]
        if gpus:
            # Normal operation
            assert general_backproject.split_gpu_work(gpus)

            # Wrong input
            general_backproject['x-region'] = [-100., -200., 1.]
            with pytest.raises(UfoModelError):
                general_backproject.split_gpu_work(gpus)
            general_backproject['x-region'] = [-100., 100., 1.]

            general_backproject['y-region'] = [-100., -200., 1.]
            with pytest.raises(UfoModelError):
                general_backproject.split_gpu_work(gpus)
            general_backproject['y-region'] = [-100., 100., 1.]

            general_backproject['region'] = [-100., -200., 1.]
            with pytest.raises(UfoModelError):
                general_backproject.split_gpu_work(gpus)
            general_backproject['region'] = [-100., 100., 1.]

    def test_create_ufo_task(self, general_backproject):
        general_backproject['region'] = [-100., 100., 1.]
        ufo_task = general_backproject.create_ufo_task(region=None)
        assert ufo_task.props.region == pytest.approx(general_backproject['region'])

        ufo_task = general_backproject.create_ufo_task(region=[-10., 10., 1.])
        assert ufo_task.props.region == pytest.approx([-10., 10., 1.])


class TestUfoReadModel:
    def test_init(self, read_model):
        assert read_model.num_ports['input'] == 0
        assert read_model.num_ports['output'] == 1

    def test_double_clicked(self, qtbot, monkeypatch, read_model):
        from tofu.flow.filedirdialog import FileDirDialog

        monkeypatch.setattr(FileDirDialog, "exec_", lambda *args: 1)
        monkeypatch.setattr(FileDirDialog, "selectedFiles", lambda *args: ['foobarbaz'])
        read_model.double_clicked(None)
        assert read_model['path'] == 'foobarbaz'


class TestUfoVaryingInputModel:
    def test_init(self, qtbot, monkeypatch):
        def get_int(*args, **kwargs):
            self.called = True
            return (1, True)

        # No number of inputs specified, dialog needs to pop up
        self.called = False
        monkeypatch.setattr(QInputDialog, 'getInt', get_int)
        model = UfoVaryingInputModel('opencl', num_inputs=None)
        qtbot.addWidget(model.embedded_widget())
        assert self.called
        assert model.num_ports['input'] == 1

        # e.g. opencl task can have multiple inputs
        model = UfoVaryingInputModel('opencl', num_inputs=4)
        qtbot.addWidget(model.embedded_widget())
        assert model.num_ports['input'] == 4
        assert len(model.data_type['input']) == 4
        assert len(model.port_caption['input']) == 4
        assert len(model.port_caption_visible['input']) == 4

    def test_save(self, qtbot):
        model = UfoVaryingInputModel('opencl', num_inputs=4)
        qtbot.addWidget(model.embedded_widget())

        assert model.save()['num-inputs'] == 4


class TestUfoRetrievePhaseModel:
    def test_distance_input(self, qtbot):
        model = UfoRetrievePhaseModel(num_inputs=4)
        qtbot.addWidget(model.embedded_widget())
        validator = model._view._properties['distance'].view_item.widget.validator()

        # Validator accepts only 4 values
        assert validator.validate('1,2,3,4', 0)[0] == QValidator.Acceptable
        assert validator.validate('1,2,3', 0)[0] == QValidator.Intermediate
        assert validator.validate('1,2,3,4,5', 0)[0] == QValidator.Invalid

    def test_multidistance_fixed_method(self, qtbot):
        def check(num_inputs):
            model = UfoRetrievePhaseModel(num_inputs=num_inputs)
            qtbot.addWidget(model.embedded_widget())
            enabled = num_inputs == 1

            assert model._view._properties['method'].view_item.widget.isEnabled() == enabled
            if not enabled:
                assert model['method'] == 'ctf_multidistance'
            assert model._view._properties['distance-x'].view_item.widget.isEnabled() == enabled
            assert model._view._properties['distance-y'].view_item.widget.isEnabled() == enabled

        check(1)
        check(2)


class TestUfoWriteModel:
    def test_init(self, write_model):
        assert write_model.num_ports['input'] == 1
        assert write_model.num_ports['output'] == 0

    def test_double_clicked(self, monkeypatch, write_model):
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: ('foobarbaz', None))
        write_model.double_clicked(None)
        assert write_model['filename'] == 'foobarbaz'

    def test_expects_multiple_inputs(self, write_model):
        write_model['filename'] = 'foo{region}bar'
        assert write_model.expects_multiple_inputs
        write_model['filename'] = 'foobar'
        assert not write_model.expects_multiple_inputs

    def test_setup_ufo_task(self, write_model):
        write_model['filename'] = '{region}'
        # Must pass
        ufo_task = write_model.create_ufo_task(region=[0, 1, 1])
        # Must fail
        with pytest.raises(UfoModelError):
            write_model.create_ufo_task(region=None)

        assert ufo_task.props.filename == '0'

        write_model['filename'] = 'foo.tif'
        # Must pass
        ufo_task = write_model.create_ufo_task(region=None)
        # Must fail
        with pytest.raises(UfoModelError):
            write_model.create_ufo_task(region=[0, 1, 1])

        assert ufo_task.props.filename == 'foo.tif'


class TestUfoMemoryOutModel:
    def test_init(self, memory_out_model):
        assert memory_out_model.num_ports['input'] == 1
        assert memory_out_model.num_ports['output'] == 1

    def test_expects_multiple_inputs(self, memory_out_model):
        memory_out_model['number'] = '{region}'
        assert memory_out_model.expects_multiple_inputs
        memory_out_model['number'] = '1'
        assert not memory_out_model.expects_multiple_inputs

    def test_make_properties(self, memory_out_model):
        prop_names = {'width', 'height', 'depth', 'number'}
        assert prop_names == memory_out_model.make_properties().keys()

    def test_out_data(self, monkeypatch, memory_out_model):
        def slot(port_index):
            self.num_called += 1
            self.data = memory_out_model.out_data(port_index)

        self.num_called = 0
        memory_out_model['number'] = 10
        shape = (int(memory_out_model['number']),
                 memory_out_model['height'],
                 memory_out_model['width'])
        memory_out_model.create_ufo_task()
        batch = memory_out_model._batches[0]
        memory_out_model.data_updated.connect(slot)
        batch.data[:] = 3
        assert len(memory_out_model._batches) == 1
        assert batch.data.shape == shape
        for i in range(shape[0]):
            batch._on_processed(None)
        # Called once per 3D array
        assert self.num_called == 1
        # out_data has been set to the batch ouput
        np.testing.assert_almost_equal(self.data, 3)
        # Original data must have been freed
        assert memory_out_model._batches == [None]

        memory_out_model.reset_batches()

        # Multiple inputs
        def slot(port_index):
            # Append the first item in the current result
            self.called.append(memory_out_model.out_data(port_index)[0, 0, 0])

        self.called = []
        memory_out_model.data_updated.connect(slot)
        memory_out_model['number'] = '{region}'
        # Two parallel batches of four regions each
        for j in range(2):
            for i in range(4):
                memory_out_model.create_ufo_task(region=[0, 10, 1])
                # Set batch data to its linearized index to make checking easy
                memory_out_model._batches[4 * j + i].data[:] = 4 * j + i
            # Out of order processing
            for batch_id in np.array([2, 0, 1, 3], dtype=int) + (4 * j):
                for e in range(10):
                    memory_out_model._batches[batch_id]._on_processed(None)
            # All regions in the current paralell batch must have been processed
            assert memory_out_model._waiting_list == []

        # Result must be in order
        np.testing.assert_almost_equal(self.called, np.arange(8))
        # Original data must have been freed
        assert memory_out_model._batches == [None] * 8

    def test_reset_batches(self, memory_out_model):
        memory_out_model.reset_batches()
        assert memory_out_model._batches == []
        assert memory_out_model._waiting_list == []
        assert memory_out_model._expecting_id == 0
        assert memory_out_model._current_data is None

    def test_setup_ufo_task(self, memory_out_model):
        memory_out_model['number'] = '{region}'
        # Must pass
        memory_out_model.create_ufo_task(region=[0, 100, 1])
        memory_out_model.create_ufo_task(region=[100, 200, 1])
        assert len(memory_out_model._batches) == 2
        # Must fail
        with pytest.raises(UfoModelError):
            memory_out_model.create_ufo_task(region=None)

        memory_out_model.reset_batches()
        memory_out_model['number'] = '100'
        # Must pass
        memory_out_model.create_ufo_task(region=None)
        # Must fail
        with pytest.raises(UfoModelError):
            memory_out_model.create_ufo_task(region=[0, 100, 1])
        assert len(memory_out_model._batches) == 1


class TestImageViewerModel:
    def test_init(self, image_viewer_model):
        assert image_viewer_model.num_ports['input'] == 1
        assert image_viewer_model.num_ports['output'] == 0

    def test_double_clicked(self, qtbot, image_viewer_model):
        image_viewer_model.double_clicked(None)
        # No images, no pop up
        assert image_viewer_model._widget._pg_window is None

        image_viewer_model._widget.images = np.arange(1000).reshape(10, 10, 10)
        image_viewer_model.double_clicked(None)
        assert image_viewer_model._widget._pg_window.isVisible()
        qtbot.addWidget(image_viewer_model._widget._pg_window)

        # User closes, must re-open
        image_viewer_model._widget._pg_window.close()
        image_viewer_model.double_clicked(None)
        assert image_viewer_model._widget._pg_window.isVisible()

    def test_set_in_data(self, image_viewer_model):
        images = np.arange(1000).reshape(10, 10, 10)
        image_viewer_model.set_in_data(images, None)
        assert image_viewer_model._widget.images.shape == images.shape
        image_viewer_model.set_in_data(images, None)
        assert image_viewer_model._widget.images.shape == (20,) + images.shape[1:]

        # Images cannot be appended after reset is called, they must be set
        image_viewer_model.reset_batches()
        image_viewer_model.set_in_data(images, None)
        assert image_viewer_model._widget.images.shape == images.shape

    def test_reset_batches(self, image_viewer_model):
        image_viewer_model.reset_batches()
        assert image_viewer_model._reset


def test_get_ufo_model_classes():
    # All
    classes = list(get_ufo_model_classes())
    assert classes
    # Blacklist
    assert 'read' not in [cls.name for cls in classes]
    # Selection
    assert len(list(get_ufo_model_classes(names=['pad']))) == 1


def test_get_composite_model_classes_from_json(qtbot, composite_model):
    classes = get_composite_model_classes_from_json(composite_model.save())
    # First must be the bottom class, top class comes last
    assert [cls.name for cls in classes] == ['cpm', 'foobar']


def test_get_composite_model_classes():
    # Just make sure this runs and the result is not empty
    assert get_composite_model_classes()
