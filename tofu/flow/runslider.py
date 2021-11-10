from functools import partial
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5 import QtGui
from PyQt5.QtWidgets import QGridLayout, QLineEdit, QWidget, QSlider
from tofu.flow.models import IntQLineEditViewItem, RangeQLineEditViewItem, UfoIntValidator
from tofu.flow.util import FlowError


class RunSlider(QWidget):
    value_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent=parent, flags=Qt.Window)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setMaximumHeight(20)
        self.setMinimumWidth(600)
        self.min_edit = QLineEdit()
        self.min_edit.setToolTip('Minimum')
        self.min_edit.setMaximumWidth(80)
        self.min_edit.editingFinished.connect(self.on_min_edit_editing_finished)
        self.current_edit = QLineEdit()
        self.current_edit.setToolTip('Current value')
        self.current_edit.editingFinished.connect(self.on_current_edit_editing_finished)
        self.max_edit = QLineEdit()
        self.max_edit.setToolTip('Maximum')
        self.max_edit.setMaximumWidth(80)
        self.max_edit.editingFinished.connect(self.on_max_edit_editing_finished)
        self.slider = QSlider(orientation=Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.valueChanged.connect(self.on_slider_value_changed)

        main_layout = QGridLayout()
        main_layout.addWidget(self.current_edit, 0, 0, 1, 3, Qt.AlignHCenter)
        main_layout.addWidget(self.min_edit, 1, 0)
        main_layout.addWidget(self.slider, 1, 1)
        main_layout.addWidget(self.max_edit, 1, 2)
        self.setLayout(main_layout)
        self.view_item = None
        self.real_minimum = 0
        self.real_maximum = 100
        self.real_span = 100
        self.type = None
        self._last_value = None
        self.setEnabled(False)

    def _update_range(self, current=None):
        self.real_span = self.real_maximum - self.real_minimum
        if current is not None:
            self.slider.blockSignals(True)
            self.slider.setValue(int(round((current - self.real_minimum) / self.real_span * 100)))
            self.slider.blockSignals(False)

    def get_real_value(self):
        # First convert possible exponents to float (in case UFO has huge defaults set)
        return self.type(float(self.current_edit.text()))

    def set_widget_value(self):
        value = self.get_real_value()
        self._last_value = value
        if isinstance(self.view_item, RangeQLineEditViewItem):
            value = [value]
        self.view_item.set(value)
        # Notify linked widgets
        self.view_item.property_changed.emit(self.view_item)

    def set_current_validator(self):
        if self.type == int:
            validator = UfoIntValidator(self.real_minimum, self.real_maximum)
        else:
            validator = QtGui.QDoubleValidator(self.real_minimum, self.real_maximum, 1000)
        self.current_edit.setValidator(validator)

    def setup(self, view_item):
        if self.view_item == view_item:
            return False

        current = view_item.get()
        if isinstance(view_item, RangeQLineEditViewItem):
            if len(current) > 1:
                return False
            self.type = float
            current = current[0]
            d_current = 0.1 * abs(current) if current else 100
            self.real_minimum = current - d_current
            self.real_maximum = current + d_current
        else:
            self.type = int if isinstance(view_item, IntQLineEditViewItem) else float
            self.real_minimum = view_item.widget.validator().bottom()
            self.real_maximum = view_item.widget.validator().top()

        self.view_item = view_item
        self._update_range(current=current)
        _set_number(self.min_edit, self.real_minimum)
        _set_number(self.max_edit, self.real_maximum)
        _set_number(self.current_edit, current)
        self._last_value = current
        self.setEnabled(True)
        self.set_current_validator()

        return True

    def reset(self):
        self.real_minimum = 0
        self.real_maximum = 100
        self.real_span = 100
        self._last_value = None
        self.type = None
        self.min_edit.setText('')
        self.max_edit.setText('')
        self.current_edit.setText('')
        self.setWindowTitle('')
        self.view_item = None
        self.setEnabled(False)

    def on_slider_value_changed(self, value):
        def delayed_update(init_value):
            current_value = self.slider.value()
            if init_value == current_value:
                self.set_widget_value()
                self.value_changed.emit(real_value)

        if self.view_item:
            real_value = self.slider.value() / 100 * self.real_span + self.real_minimum
            self.current_edit.setText('{:g}'.format(self.type(real_value)))
            func = partial(delayed_update, value)
            QTimer.singleShot(100, func)

    def on_current_edit_editing_finished(self):
        if not self.view_item:
            return

        try:
            value = self.type(self.current_edit.text())
        except ValueError:
            raise RunSliderError('Not a number')

        if value == self._last_value:
            # Nothing new, do not emit value_changed signal in case the app is closing
            return

        self.slider.blockSignals(True)
        self.slider.setValue(int(round((value - self.real_minimum) / self.real_span * 100)))
        self.slider.blockSignals(False)
        self.set_widget_value()
        self.value_changed.emit(value)

    def on_min_edit_editing_finished(self):
        if not self.view_item:
            return

        try:
            value = self.type(self.min_edit.text())
        except ValueError:
            raise RunSliderError('Not a number')
        if value >= self.real_maximum:
            raise RunSliderError('Minimum must be smaller than maximum')

        current = self.get_real_value()
        self.real_minimum = value
        if current < self.real_minimum:
            current = self.real_minimum
            self.current_edit.setText('{:g}'.format(current))
            self.set_widget_value()
            self.value_changed.emit(current)
        self._update_range(current=current)
        self.set_current_validator()

    def on_max_edit_editing_finished(self):
        if not self.view_item:
            return

        try:
            value = self.type(self.max_edit.text())
        except ValueError:
            raise RunSliderError('Not a number')
        if value <= self.real_minimum:
            raise RunSliderError('Maximum must be greater than minimum')

        current = self.get_real_value()
        self.real_maximum = value
        if current > self.real_maximum:
            current = self.real_maximum
            self.current_edit.setText('{:g}'.format(current))
            self.set_widget_value()
            self.value_changed.emit(current)
        self._update_range(current=current)
        self.set_current_validator()


def _set_number(edit, number):
    edit.setText('{:g}'.format(number))


class RunSliderError(FlowError):
    pass
