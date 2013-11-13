import sys
import time
from PyQt4 import QtGui, QtCore
from . import reco


def _set_line_edit_to_path(line_edit):
    path = QtGui.QFileDialog.getExistingDirectory()
    line_edit.clear()
    line_edit.setText(path)


def _new_path_line_edit(cfg_parser, cfg_key, default=''):
    line_edit = QtGui.QLineEdit()
    line_edit.setText(cfg_parser.get_config('general', cfg_key, default=default))
    return line_edit


def _enable_wait_cursor():
    QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))


def _disable_wait_cursor():
    QtGui.QApplication.restoreOverrideCursor()


class Bunch(object):
  def __init__(self, adict):
      self.__dict__.update(adict)


class ApplicationWindow(QtGui.QMainWindow):
    def __init__(self, app, args, cfg_parser):
        QtGui.QMainWindow.__init__(self)
        self.args = args
        self.app = app
        self.cfg_parser = cfg_parser
        self.do_layout()

    def do_layout(self):
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("application main window")

        file_menu = QtGui.QMenu('&File', self)
        file_menu.addAction('&Quit', self.on_close,
                            QtCore.Qt.CTRL + QtCore.Qt.Key_Q)
        self.menuBar().addMenu(file_menu)

        self.main_widget = QtGui.QWidget(self)
        main_vbox = QtGui.QVBoxLayout()

        # Input group
        input_group = QtGui.QGroupBox("Input")
        input_grid = QtGui.QGridLayout()
        input_group.setLayout(input_grid)
        input_group.setFlat(True)

        sino_button = QtGui.QRadioButton("Sinograms")
        self.proj_button = QtGui.QRadioButton("Projections")
        input_path_button = QtGui.QPushButton("Browse ...")
        self.input_path_line = _new_path_line_edit(self.cfg_parser, 'input')

        from_projections = self.cfg_parser.get_config('general',
                                                      'from_projections',
                                                       default=None)

        sino_button.setChecked(not from_projections)
        self.proj_button.setChecked(from_projections is not None)

        input_grid.addWidget(sino_button, 0, 0)
        input_grid.addWidget(self.proj_button, 1, 0)
        input_grid.addWidget(self.input_path_line, 2, 0)
        input_grid.addWidget(input_path_button, 2, 1)

        # Parameters group
        param_grid = QtGui.QGridLayout()
        param_group = QtGui.QGroupBox("param")
        param_group.setLayout(param_grid)
        param_group.setFlat(True)

        self.axis_spin = QtGui.QDoubleSpinBox()
        self.axis_spin.setDecimals(10)
        self.axis_spin.setValue(float(self.cfg_parser.get_config('general', 'axis', default=0.0)))

        self.angle_step = QtGui.QDoubleSpinBox()
        self.angle_step.setDecimals(10)
        self.angle_step.setValue(float(self.cfg_parser.get_config('general', 'angle_step', default=0.0)))

        param_grid.addWidget(QtGui.QLabel('Axis:'), 0, 0)
        param_grid.addWidget(self.axis_spin, 0, 1)
        param_grid.addWidget(QtGui.QLabel('Angle step:'), 1, 0)
        param_grid.addWidget(self.angle_step, 1, 1)

        # Output group
        output_grid = QtGui.QGridLayout()
        output_group = QtGui.QGroupBox("Output")
        output_group.setLayout(output_grid)
        output_group.setFlat(True)

        self.output_path_line = _new_path_line_edit(self.cfg_parser, 'output', default='./slice-%05i.tif')
        output_path_button = QtGui.QPushButton("Browse ...")

        output_grid.addWidget(QtGui.QLabel("Path:"), 0, 0)
        output_grid.addWidget(self.output_path_line, 0, 1)
        output_grid.addWidget(output_path_button, 0, 2)

        # Button group
        button_group = QtGui.QDialogButtonBox()

        close_button = button_group.addButton(QtGui.QDialogButtonBox.Close)
        reco_button = button_group.addButton("Reconstruct", QtGui.QDialogButtonBox.AcceptRole)

        main_vbox.addWidget(input_group)
        main_vbox.addWidget(param_group)
        main_vbox.addWidget(output_group)
        main_vbox.addStretch()
        main_vbox.addWidget(button_group)

        # Connect things
        input_path_button.clicked.connect(self.on_input_path_clicked)
        output_path_button.clicked.connect(self.on_output_path_clicked)
        close_button.clicked.connect(self.on_close)
        reco_button.clicked.connect(self.on_reconstruct)

        self.main_widget.setLayout(main_vbox)
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)

    def on_input_path_clicked(self, checked):
        _set_line_edit_to_path(self.input_path_line)

    def on_output_path_clicked(self, checked):
        _set_line_edit_to_path(self.output_path_line)

    def on_close(self):
        self.close()

    def on_reconstruct(self):
        _enable_wait_cursor()
        self.main_widget.setEnabled(False)
        self.repaint()
        self.app.processEvents()

        try:
            reco.run(self.cfg_parser,
                     str(self.input_path_line.text()),
                     str(self.output_path_line.text()),
                     axis=self.axis_spin.value(),
                     angle_step=self.angle_step.value(),
                     from_projections=self.proj_button.isChecked())

        except Exception as e:
            QtGui.QMessageBox.warning(self, "Warning", str(e))

        _disable_wait_cursor()
        self.main_widget.setEnabled(True)


def main(args, cfg_parser):
    app = QtGui.QApplication(sys.argv)

    window = ApplicationWindow(app, args, cfg_parser)
    window.show()
    sys.exit(app.exec_())
