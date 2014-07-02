import sys
import os
import time
import logging
import tempfile
import threading
import subprocess
import numpy as np
import pyqtgraph as pg

from . import reco, config, tifffile
from PyQt4 import QtGui, QtCore
from scipy.signal import fftconvolve


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

def _set_line_edit_to_file(line_edit):
    file_name = QtGui.QFileDialog.getOpenFileName()
    line_edit.clear()
    line_edit.setText(file_name)

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
        self.setWindowTitle("Tomoviewer")

        self.main_widget = QtGui.QTabWidget(self)
        self.main_widget.setExpanding = True
        self.main_widget.setTabPosition(QtGui.QTabWidget.North)

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
        self.reco_button = button_group.addButton("Reconstruct", QtGui.QDialogButtonBox.AcceptRole)
        save_button = button_group.addButton("Save", QtGui.QDialogButtonBox.AcceptRole)

        # Log widget
        self.textWidget = QtGui.QTextBrowser(self)

        # Reconstruction group
        reconstruction_grid = QtGui.QGridLayout()
        reconstruction_group = QtGui.QGroupBox()
        reconstruction_group.setLayout(reconstruction_grid)
        reconstruction_group.setFlat(True)

        reconstruction_grid.addWidget(input_group, 0, 0)
        reconstruction_grid.addWidget(param_group, 1, 0)
        reconstruction_grid.addWidget(output_group, 2, 0)
        reconstruction_grid.addWidget(self.correction_group, 3, 0)
        reconstruction_grid.addWidget(button_group, 4, 0)
        reconstruction_grid.addWidget(self.textWidget, 5, 0)

        # Rotation axis options group
        self.do_axis_opts()

        # Rotation axis group
        self.axis_grid = QtGui.QGridLayout()
        axis_group = QtGui.QGroupBox()
        axis_group.setLayout(self.axis_grid)
        axis_group.setFlat(True)
        self.axis_grid.addWidget(self.axis_opts_group, 0, 0, QtCore.Qt.Alignment(QtCore.Qt.AlignTop))

        # Connect things
        input_path_button.clicked.connect(self.on_input_path_clicked)
        output_path_button.clicked.connect(self.on_output_path_clicked)
        close_button.clicked.connect(self.on_close)
        self.reco_button.clicked.connect(self.on_reconstruct)
        save_button.clicked.connect(self.on_save)
        self.proj_button.clicked.connect(self.on_proj_button_clicked)
        self.sino_button.clicked.connect(self.on_sino_button_clicked)
        self.correct_box.clicked.connect(self.on_correct_box_clicked)
        self.connect(self, QtCore.SIGNAL('triggered()'), self.closeEvent)
        self.darks_path_button.clicked.connect(self.on_darks_path_clicked)
        self.flats_path_button.clicked.connect(self.on_flats_path_clicked)
        self.main_widget.currentChanged.connect(self.on_tab_changed)

        self.main_widget.insertTab(0, reconstruction_group, "Reconstruction")
        self.main_widget.insertTab(1, axis_group, "Rotation Axis")

        self.setGeometry(100, 100, 575, 689)
        self.setMinimumSize(575, 689)
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)

    def do_axis_opts(self):
        self.axis_opts_grid = QtGui.QGridLayout()
        self.axis_opts_group = QtGui.QGroupBox()
        self.axis_opts_group.setLayout(self.axis_opts_grid)
        self.axis_opts_group.setFlat(True)

        self.path_line_0 = QtGui.QLineEdit()
        self.path_button_0 = QtGui.QPushButton("Browse ...")
        self.path_line_180 = QtGui.QLineEdit()
        self.path_button_180 = QtGui.QPushButton("Browse ...")
        self.run_button = QtGui.QPushButton("Run")
        self.absorptivity_checkbox = QtGui.QCheckBox('is absorptivity', self)

        self.axis_opts_grid.addWidget(QtGui.QLabel("0 deg projection:"), 0, 0)
        self.axis_opts_grid.addWidget(self.path_line_0, 0, 1)
        self.axis_opts_grid.addWidget(self.path_button_0, 0, 2)
        self.axis_opts_grid.addWidget(QtGui.QLabel("180 deg projection:"), 1, 0)
        self.axis_opts_grid.addWidget(self.path_line_180, 1, 1)
        self.axis_opts_grid.addWidget(self.path_button_180, 1, 2)
        self.axis_opts_grid.addWidget(self.absorptivity_checkbox, 2, 2)
        self.axis_opts_grid.addWidget(self.run_button, 3, 2)

        self.path_button_0.clicked.connect(self.on_path_0_clicked)
        self.path_button_180.clicked.connect(self.on_path_180_clicked)
        self.run_button.clicked.connect(self.on_run)

    def on_tab_changed(self):
        current_tab = self.main_widget.currentIndex()
        if current_tab == 0 and self.layout == True:
            self.geom = self.geometry()
            self.resize(575, 689)
        elif current_tab == 1 and self.layout == True:
            self.setGeometry(self.geom)

    def on_correct_box_clicked(self, checked):
        self.status = self.correct_box.isChecked()
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

    def on_path_0_clicked(self, checked):
        _set_line_edit_to_file(self.path_line_0)

    def on_path_180_clicked(self, checked):
        _set_line_edit_to_file(self.path_line_180)

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

    def on_run(self):
        try:
            self.init_axis()
            self.read_data()
            self.compute_axis()
            self.do_axis_layout()
            self.params.is_absorptivity = self.absorptivity_checkbox.isChecked()

        except Exception as e:
            QtGui.QMessageBox.warning(self, "Warning", str(e))

    def init_axis(self):
        self.layout = False
        self.axis_num = QtGui.QLabel()
        font = QtGui.QFont()
        font.setBold(True)
        self.axis_num.setFont(font)
        self.view = pg.ViewBox()
        self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 999)
        self.w_over = pg.ImageView(view=self.view)
        self.w_over.ui.roiBtn.hide()
        self.w_over.ui.normBtn.hide()
        self.overlap_opt = QtGui.QComboBox()
        self.overlap_opt.addItem("Subtraction overlap")
        self.overlap_opt.addItem("Addition overlap")
        self.overlap_opt.currentIndexChanged.connect(self.update_image)

    def read_data(self):
        tif_0 = tifffile.TiffFile(str(self.path_line_0.text()))
        tif_180 = tifffile.TiffFile(str(self.path_line_180.text()))

        self.arr_0 = tif_0.asarray()
        self.arr_180 = tif_180.asarray()
        self.arr_flip = np.fliplr(self.arr_0)

    def compute_axis(self):
        self.width = self.arr_0.shape[1]
        mean_0 = self.arr_0 - self.arr_0.mean()
        mean_180 = self.arr_180 - self.arr_180.mean()

        convolved = fftconvolve(mean_0, mean_180[::-1, :], mode='same')
        center = np.unravel_index(convolved.argmax(), convolved.shape)[1]

        self.axis = (self.width / 2.0 + center) / 2
        adj = (self.width / 2.0) - self.axis
        self.move = int(-adj)
        slider_val = int(adj) + 500
        self.slider.setValue(slider_val)

        self.update_image()

    def on_move_slider(self):
        pos = self.slider.value()
        if pos > 500:
            self.move = -1 * (pos - 500)
        elif pos < 500:
            self.move = 500 - pos
        else:
            self.move = 0

        self.update_axis()
        self.update_image()

    def on_overlap_opt_changed(self):
        current_overlap = self.overlap_opt.currentIndex()
        if current_overlap == 0:
            self.arr_over = self.arr_flip - arr_180
        elif current_overlap == 1:
            self.arr_over = self.arr_flip + arr_180

    def update_image(self):
        arr_180 = np.roll(self.arr_180, self.move, axis=1)
        self.arr_over = self.arr_flip - arr_180
        current_overlap = self.overlap_opt.currentIndex()
        if current_overlap == 0:
            self.arr_over = self.arr_flip - arr_180
        elif current_overlap == 1:
            self.arr_over = self.arr_flip + arr_180
        img = pg.ImageItem(self.arr_over.T)
        self.img_width = self.arr_over.T.shape[0]
        self.img_height = self.arr_over.T.shape[1]
        self.view.addItem(img)
        self.w_over.ui.histogram.setImageItem(img)

    def update_axis(self):
        if self.move > 0:
            self.axis = self.width / 2 + self.move
        elif self.move < 0:
            self.axis = self.width / 2 - self.move
        else:
            self.axis = self.width / 2

        self.axis_num.setText('center of rotation = %i px' % (self.axis))

    def on_remove_extrema(self):
        max_flip = np.percentile(self.arr_flip, 99)
        min_flip = np.percentile(self.arr_flip, 1)
        self.arr_flip = np.copy(self.arr_flip)
        self.arr_flip[self.arr_flip > max_flip] = max_flip
        self.arr_flip[self.arr_flip < min_flip] = min_flip

        max_180 = np.percentile(self.arr_180, 99)
        min_180 = np.percentile(self.arr_180, 1)
        self.arr_180 = np.copy(self.arr_180)
        self.arr_180[self.arr_180 > max_180] = max_180
        self.arr_180[self.arr_180 < min_180] = min_180

        self.update_image()
        self.extrema_checkbox.setEnabled(False)

    def on_choose_new(self):
        for i in reversed(range(self.axis_grid.count())):
            self.axis_grid.itemAt(i).widget().setParent(None)
        self.do_axis_opts()
        self.axis_grid.addWidget(self.axis_opts_group, 0, 0, QtCore.Qt.Alignment(QtCore.Qt.AlignTop))
        self.resize(575, 689)

    def do_axis_layout(self):
        self.layout = True
        self.resize(900, 900)

        for i in reversed(range(self.axis_grid.count())):
            self.axis_grid.itemAt(i).widget().setParent(None)

        self.axis_num.setText('center of rotation = %i px' % (self.axis))
        self.extrema_checkbox = QtGui.QCheckBox('remove extrema', self)
        img_size = QtGui.QLabel('width = %i | height = %i' % (self.img_width, self.img_height))
        self.new_button = QtGui.QPushButton("Choose new ...")
        self.absorptivity_checkbox.setEnabled(False)

        new_axis_grid = QtGui.QGridLayout()
        new_axis_group = QtGui.QGroupBox()
        new_axis_group.setLayout(new_axis_grid)
        new_axis_group.setFlat(True)

        new_axis_grid.addWidget(QtGui.QLabel("0 deg projection:"), 0, 0)
        new_axis_grid.addWidget(self.path_line_0, 0, 1)
        new_axis_grid.addWidget(self.extrema_checkbox, 0, 2)
        new_axis_grid.addWidget(img_size, 0, 3)
        new_axis_grid.addWidget(self.overlap_opt, 0, 4)
        new_axis_grid.addWidget(QtGui.QLabel("180 deg projection:"), 1, 0)
        new_axis_grid.addWidget(self.path_line_180, 1, 1)
        new_axis_grid.addWidget(self.absorptivity_checkbox, 1, 2)
        new_axis_grid.addWidget(self.axis_num, 1, 3)
        new_axis_grid.addWidget(self.new_button, 1, 4)

        self.axis_grid.addWidget(new_axis_group, 0, 0)
        self.axis_grid.addWidget(self.w_over, 1, 0)
        self.axis_grid.addWidget(self.slider, 2, 0)

        self.slider.valueChanged.connect(self.on_move_slider)
        self.extrema_checkbox.clicked.connect(self.on_remove_extrema)
        self.new_button.clicked.connect(self.on_choose_new)


def main(params):
    app = QtGui.QApplication(sys.argv)

    window = ApplicationWindow(app, params)
    window.show()
    sys.exit(app.exec_())
