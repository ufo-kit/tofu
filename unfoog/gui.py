import sys
import os
import time
import logging
import tempfile
import threading
import subprocess
from PyQt4 import QtGui, QtCore
from . import reco, config


LOG = logging.getLogger(__name__)
log = tempfile.NamedTemporaryFile(delete = False, suffix = '.txt')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
    filename=log.name,
    filemode='a'
)


def _set_line_edit_to_path(line_edit):
    path = QtGui.QFileDialog.getExistingDirectory()
    line_edit.clear()
    line_edit.setText(path)


def _new_path_line_edit(text):
    line_edit = QtGui.QLineEdit()
    line_edit.setText(text)
    return line_edit


def _enable_wait_cursor():
    QtGui.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))


def _disable_wait_cursor():
    QtGui.QApplication.restoreOverrideCursor()


class Bunch(object):
  def __init__(self, adict):
      self.__dict__.update(adict)


class ApplicationWindow(QtGui.QMainWindow):
    def __init__(self, app, params):
        QtGui.QMainWindow.__init__(self)
        self.params = params
        self.app = app
        self.imagej_available = any([os.path.exists(os.path.join(p,"imagej")) for p in os.environ["PATH"].split(os.pathsep)])
        self.do_layout()

    def do_layout(self):
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("Reconstruction")

        file_menu = QtGui.QMenu('&File', self)
        file_menu.addAction('&Quit', self.on_close,
                            QtCore.Qt.CTRL + QtCore.Qt.Key_Q)
        self.menuBar().addMenu(file_menu)

        self.main_widget = QtGui.QWidget(self)
        main_vbox = QtGui.QVBoxLayout()

        self.setGeometry(300, 200, 200, 200)
        self.resize(575, 520)

        # Input group
        input_group = QtGui.QGroupBox("Input")
        input_grid = QtGui.QGridLayout()
        input_group.setLayout(input_grid)
        input_group.setFlat(True)

        self.sino_button = QtGui.QRadioButton("Sinograms")
        self.proj_button = QtGui.QRadioButton("Projections")
        input_path_button = QtGui.QPushButton("Browse ...")
        self.input_path_line = _new_path_line_edit(self.params.input)

        self.sino_button.setChecked(True)
        self.proj_button.setChecked(False)

        input_grid.addWidget(self.sino_button, 0, 0)
        input_grid.addWidget(self.proj_button, 1, 0)
        input_grid.addWidget(self.input_path_line, 2, 0)
        input_grid.addWidget(input_path_button, 2, 1)

        # Parameters group
        param_grid = QtGui.QGridLayout()
        param_group = QtGui.QGroupBox("Parameters")
        param_group.setLayout(param_grid)
        param_group.setFlat(True)

        self.axis_spin = QtGui.QDoubleSpinBox()
        self.axis_spin.setDecimals(2)
        self.axis_spin.setMaximum(8192.0)
        self.axis_spin.setValue(self.params.axis if self.params.axis else 0.0)

        self.angle_step = QtGui.QDoubleSpinBox()
        self.angle_step.setDecimals(10)
        self.angle_step.setValue(self.params.angle if self.params.angle else 0.0)

        param_grid.addWidget(QtGui.QLabel('Axis (pixel):'), 0, 0)
        param_grid.addWidget(self.axis_spin, 0, 1)
        param_grid.addWidget(QtGui.QLabel('Angle step (rad):'), 1, 0)
        param_grid.addWidget(self.angle_step, 1, 1)

        # Output group
        output_grid = QtGui.QGridLayout()
        output_group = QtGui.QGroupBox("Output")
        output_group.setLayout(output_grid)
        output_group.setFlat(True)

        self.output_path_line = _new_path_line_edit(self.params.output)
        output_path_button = QtGui.QPushButton("Browse ...")
        self.imagej_checkbox = QtGui.QCheckBox("Show Images after Reconstruction", self)

        if self.imagej_available == False:
            self.imagej_checkbox.setEnabled(False)
            LOG.debug("ImageJ is not installed")

        output_grid.addWidget(QtGui.QLabel("Path:"), 0, 0)
        output_grid.addWidget(self.output_path_line, 0, 1)
        output_grid.addWidget(output_path_button, 0, 2)
        output_grid.addWidget(self.imagej_checkbox, 1, 0)

        # Darks & Flats Group
        correction_grid = QtGui.QGridLayout()
        self.correction_group = QtGui.QGroupBox("Correction for Projections")
        self.correction_group.setLayout(correction_grid)
        self.correction_group.setFlat(True)

        self.correct_box = QtGui.QCheckBox("Use Correction", self)
        self.darks_path_line = QtGui.QLineEdit()
        self.darks_path_button = QtGui.QPushButton("Browse...")
        self.darks_label = QtGui.QLabel("Dark-field:")
        self.flats_path_line = QtGui.QLineEdit()
        self.flats_path_button = QtGui.QPushButton("Browse...")
        self.flats_label = QtGui.QLabel("Flat-field:")

        correction_grid.addWidget(self.correct_box, 0, 0)
        correction_grid.addWidget(self.darks_label, 1, 0)
        correction_grid.addWidget(self.darks_path_line, 1, 1)
        correction_grid.addWidget(self.darks_path_button, 1, 2)
        correction_grid.addWidget(self.flats_label, 2, 0)
        correction_grid.addWidget(self.flats_path_line, 2, 1)
        correction_grid.addWidget(self.flats_path_button, 2, 2)

        self.correct_box.setEnabled(False)
        self.status = False
        self.change_status()

        # Button group
        button_group = QtGui.QDialogButtonBox()

        close_button = button_group.addButton(QtGui.QDialogButtonBox.Close)
        reco_button = button_group.addButton("Reconstruct", QtGui.QDialogButtonBox.AcceptRole)
        save_button = button_group.addButton("Save", QtGui.QDialogButtonBox.AcceptRole)

        # Log widget
        self.textWidget = QtGui.QTextBrowser(self)

        main_vbox.addWidget(input_group)
        main_vbox.addWidget(param_group)
        main_vbox.addWidget(output_group)
        main_vbox.addWidget(self.correction_group)
        main_vbox.addWidget(button_group)
        main_vbox.addWidget(self.textWidget)

        # Connect things
        input_path_button.clicked.connect(self.on_input_path_clicked)
        output_path_button.clicked.connect(self.on_output_path_clicked)
        close_button.clicked.connect(self.on_close)
        reco_button.clicked.connect(self.on_reconstruct)
        save_button.clicked.connect(self.on_save)
        self.proj_button.clicked.connect(self.on_proj_button_clicked)
        self.sino_button.clicked.connect(self.on_sino_button_clicked)
        self.correct_box.clicked.connect(self.on_correct_box_clicked)
        self.connect(self, QtCore.SIGNAL('triggered()'), self.closeEvent)
        self.darks_path_button.clicked.connect(self.on_darks_path_clicked)
        self.flats_path_button.clicked.connect(self.on_flats_path_clicked)

        self.main_widget.setLayout(main_vbox)
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)

    def on_correct_box_clicked(self, checked):
        if self.correct_box.isChecked():
            self.status = True
            self.change_status()
        else:
            self.status = False
            self.change_status()

    def change_status(self):
        self.darks_path_line.setEnabled(self.status)
        self.darks_path_button.setEnabled(self.status)
        self.darks_label.setEnabled(self.status)
        self.flats_path_line.setEnabled(self.status)
        self.flats_path_button.setEnabled(self.status)
        self.flats_label.setEnabled(self.status)

    def on_proj_button_clicked(self, checked):
        if self.proj_button.isChecked():
            self.correct_box.setEnabled(True)

    def on_sino_button_clicked(self, checked):
        if self.sino_button.isChecked():
            self.correct_box.setEnabled(False)
            self.status = False
            self.change_status()

    def on_input_path_clicked(self, checked):
        _set_line_edit_to_path(self.input_path_line)
        if "sinogram" in str(self.input_path_line.text()):
            self.sino_button.setChecked(True)
            self.proj_button.setChecked(False)
            self.correct_box.setEnabled(False)
            self.status = False
            self.change_status()
        elif "projection" in str(self.input_path_line.text()):
            self.sino_button.setChecked(False)
            self.proj_button.setChecked(True)
            self.correct_box.setEnabled(True)

    def on_output_path_clicked(self, checked):
        _set_line_edit_to_path(self.output_path_line)

    def on_darks_path_clicked(self, checked):
        _set_line_edit_to_path(self.darks_path_line)

    def on_flats_path_clicked(self, checked):
        _set_line_edit_to_path(self.flats_path_line)

    def on_close(self):
        self.close()

    def closeEvent(self, event):
        try:
            os.remove(log.name)
        except OSError as e:
            pass

    def on_save(self):
        d = self.param_dict()
        d['disable'] = ''
        config.write(**d)

    def on_reconstruct(self):
        _enable_wait_cursor()
        self.main_widget.setEnabled(False)
        self.repaint()
        self.app.processEvents()

        self.params.axis = self.axis_spin.value()
        self.params.angle = self.angle_step.value()
        self.params.input = str(self.input_path_line.text())
        self.params.output = str(self.output_path_line.text())
        self.params.from_projections = self.proj_button.isChecked()

        if self.correct_box.isChecked():
            self.params.darks = str(self.darks_path_line.text())
            self.params.flats = str(self.flats_path_line.text())
        else:
            self.params.darks = None
            self.params.flats = None

        try:
            reco.tomo(self.params)

        except Exception as e:
            QtGui.QMessageBox.warning(self, "Warning", str(e))

        if self.imagej_checkbox.isChecked():

            output_path = str(self.output_path_line.text())
            if output_path == ".":
                output_path = str(os.getcwd())

            tif = tempfile.NamedTemporaryFile(delete = False, suffix = '.ijm')
            tif.write('run("Image Sequence...", "open=')
            tif.write(output_path)
            tif.write(' number=-1 starting=1 increment=1 scale=100 file=[] sort use");')
            tif.seek(0)

            def call_imagej():
                subprocess.call(["imagej -macro " + tif.name], shell = True)

            process = threading.Thread(target = call_imagej)
            process.start()

        _disable_wait_cursor()
        self.main_widget.setEnabled(True)
        log.seek(0)
        logtxt = open(log.name).read()
        self.textWidget.setPlainText(logtxt)


def main(params):
    app = QtGui.QApplication(sys.argv)

    window = ApplicationWindow(app, params)
    window.show()
    sys.exit(app.exec_())
