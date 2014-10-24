import sys
import os
import time
import logging
import tempfile
import threading
import subprocess
import numpy as np
import pyqtgraph as pg
import pkg_resources

from . import reco, config, tifffile
from PyQt4 import QtGui, QtCore, uic
from scipy.signal import fftconvolve


LOG = logging.getLogger(__name__)
log = tempfile.NamedTemporaryFile(delete = False, suffix = '.txt')
logging.getLogger('PyQt4.uic.uiparser').disabled = True
logging.getLogger('PyQt4.uic.properties').disabled = True

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
    filename=log.name,
    filemode='a'
)


def _set_line_edit_to_path(parent, line_edit, directory, last_dir):
    if last_dir is not None:
        directory = last_dir
    path = QtGui.QFileDialog.getExistingDirectory(parent, '.', directory)
    line_edit.clear()
    line_edit.setText(path)

def _set_line_edit_to_file(parent, line_edit, directory, last_dir):
    if last_dir is not None:
        directory = last_dir
    file_name = QtGui.QFileDialog.getOpenFileName(parent, '.', directory)
    line_edit.clear()
    line_edit.setText(file_name)

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
        ui_file = pkg_resources.resource_filename(__name__, 'gui.ui')
        self.ui = uic.loadUi(ui_file, self)
        self.ui.show()
        self.ui.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.ui.setGeometry(100, 100, 585, 825)
        self.ui.tab_widget.setCurrentIndex(0)
        self.ui.reco_images_widget.setVisible(False)
        self.ui.phgen_images_widget.setVisible(False)
        self.ui.axis_view_widget.setVisible(False)
        self.ui.axis_options.setVisible(False)
        self.get_values_from_params()

        self.ui.region_box.setToolTip(self.get_help('general', 'region'))
        self.ui.input_path_button.setToolTip(self.get_help('general', 'input'))
        self.ui.proj_button.setToolTip(self.get_help('fbp', 'from_projections'))
        self.ui.method_box.setToolTip(self.get_help('general', 'method'))
        self.ui.axis_spin.setToolTip(self.get_help('general', 'axis'))
        self.ui.angle_step.setToolTip(self.get_help('general', 'angle'))
        self.ui.angle_offset.setToolTip(self.get_help('general', 'offset'))
        self.ui.oversampling.setToolTip(self.get_help('dfi', 'oversampling'))
        self.ui.output_path_button.setToolTip(self.get_help('general', 'output'))
        self.ui.correct_box.setToolTip(self.get_help('general', 'correction'))
        self.ui.darks_path_button.setToolTip(self.get_help('general', 'darks'))
        self.ui.flats_path_button.setToolTip(self.get_help('general', 'flats'))
        self.ui.path_button_0.setToolTip(self.get_help('general', 'deg0'))
        self.ui.path_button_180.setToolTip(self.get_help('general', 'deg180'))
        self.ui.absorptivity_checkbox.setToolTip(self.get_help('general', 'absorptivity'))

        self.ui.input_path_button.clicked.connect(self.on_input_path_clicked)
        self.ui.sino_button.clicked.connect(self.on_sino_button_clicked)
        self.ui.proj_button.clicked.connect(self.on_proj_button_clicked)
        self.ui.region_box.clicked.connect(self.on_region)
        self.ui.from_region.valueChanged.connect(self.concatenate_region)
        self.ui.to_region.valueChanged.connect(self.concatenate_region)
        self.ui.step_region.valueChanged.connect(self.concatenate_region)
        self.ui.method_box.currentIndexChanged.connect(self.change_method)
        self.ui.axis_spin.valueChanged.connect(self.change_axis_spin)
        self.ui.angle_step.valueChanged.connect(self.change_angle_step)
        self.ui.crop_box.clicked.connect(self.on_crop_width)
        self.ui.output_path_button.clicked.connect(self.on_output_path_clicked)
        self.ui.correct_box.clicked.connect(self.on_correct_box_clicked)
        self.ui.darks_path_button.clicked.connect(self.on_darks_path_clicked)
        self.ui.flats_path_button.clicked.connect(self.on_flats_path_clicked)
        self.ui.reco_button.clicked.connect(self.on_reconstruct)
        self.ui.reco_slider.valueChanged.connect(self.move_reco_slider)
        self.ui.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.ui.path_button_0.clicked.connect(self.on_path_0_clicked)
        self.ui.path_button_180.clicked.connect(self.on_path_180_clicked)
        self.ui.show_reco_images_box.clicked.connect(self.on_hide_reco_images)
        self.ui.run_button.clicked.connect(self.on_run)
        self.ui.save_action.triggered.connect(self.on_save_as)
        self.ui.clear_action.triggered.connect(self.on_clear)
        self.ui.open_action.triggered.connect(self.on_open_from)
        self.ui.close_action.triggered.connect(self.close)
        self.ui.add_params.clicked.connect(self.change_method)
        self.ui.axis_slider.valueChanged.connect(self.move_axis_slider)
        self.ui.extrema_checkbox.clicked.connect(self.on_remove_extrema)
        self.ui.overlap_opt.currentIndexChanged.connect(self.update_image)
        self.ui.generate_button.clicked.connect(self.on_generate)
        self.ui.generate_phantom.clicked.connect(self.on_generate_phantom)
        self.ui.generate_sinogram.clicked.connect(self.on_generate_sinogram)
        self.ui.phgen_width.valueChanged.connect(self.on_phgen_width_changed)
        self.ui.phgen_height.valueChanged.connect(self.on_phgen_height_changed)
        self.ui.phgen_slider.valueChanged.connect(self.move_phgen_slider)
        self.ui.reco_sino_phgen.clicked.connect(self.on_reco_sino)

        self.ui.input_path_line.textChanged.connect(lambda value: self.change_value('input', str(self.ui.input_path_line.text())))
        self.ui.sino_button.clicked.connect(lambda value: self.change_value('from_projections', False))
        self.ui.proj_button.clicked.connect(lambda value: self.change_value('from_projections', True))
        self.ui.region_box.clicked.connect(lambda value: self.change_value('enable_region', self.ui.region_box.isChecked()))
        self.ui.angle_offset.valueChanged.connect(lambda value: self.change_value('offset', value))
        if self.add_params.isChecked():
            self.ui.method_box.currentIndexChanged.connect(lambda value: self.change_value('method', self.method))
        self.ui.oversampling.valueChanged.connect(lambda value: self.change_value('oversampling', value))
        self.ui.output_path_line.textChanged.connect(lambda value: self.change_value('output', str(self.ui.output_path_line.text())))
        self.ui.darks_path_line.textChanged.connect(lambda value: self.change_value('darks', str(self.ui.darks_path_line.text())))
        self.ui.flats_path_line.textChanged.connect(lambda value: self.change_value('flats', str(self.ui.flats_path_line.text())))
        self.ui.path_line_0.textChanged.connect(lambda value: self.change_value('deg0', str(self.ui.path_line_0.text())))
        self.ui.path_line_180.textChanged.connect(lambda value: self.change_value('deg180', str(self.ui.path_line_180.text())))
        self.ui.absorptivity_checkbox.clicked.connect(lambda value: self.change_value('absorptivity', self.ui.absorptivity_checkbox.isChecked()))
        self.ui.gpu_box.clicked.connect(lambda value: self.change_value('use_gpu', self.ui.gpu_box.isChecked()))

    def get_values_from_params(self):
        self.ui.input_path_line.setText(self.params.input)
        self.ui.output_path_line.setText(self.params.output)
        self.ui.darks_path_line.setText(self.params.darks)
        self.ui.flats_path_line.setText(self.params.flats)
        self.ui.path_line_0.setText(self.params.deg0)
        self.ui.path_line_180.setText(self.params.deg180)

        self.ui.axis_spin.setValue(self.params.axis if self.params.axis else 0.0)
        self.ui.angle_step.setValue(self.params.angle if self.params.angle else 0.0)
        self.ui.angle_offset.setValue(self.params.offset if self.params.offset else 0.0)
        self.ui.oversampling.setValue(self.params.oversampling if self.params.oversampling else 0)

        if self.params.method == "fbp":
            self.ui.method_box.setCurrentIndex(0)
        elif self.params.method == "dfi":
            self.ui.method_box.setCurrentIndex(1)
        self.change_method()

        if self.params.enable_region == "True":
            self.params.enable_region = True
            self.ui.region_box.setChecked(True)
        else:
            self.params.enable_region = False
            self.ui.region_box.setChecked(False)

        region = [int(x) for x in self.params.region.split(':')]
        self.ui.from_region.setValue(region[0])
        self.ui.to_region.setValue(region[1])
        self.ui.step_region.setValue(region[2])
        self.ui.from_region.setEnabled(self.ui.region_box.isChecked())
        self.ui.to_region.setEnabled(self.ui.region_box.isChecked())
        self.ui.step_region.setEnabled(self.ui.region_box.isChecked())

        if self.params.enable_cropping == "True":
            self.ui.crop_box.setChecked(True)
            self.params.enable_cropping = True
        else:
            self.ui.crop_box.setChecked(False)
            self.params.enable_cropping = False

        if self.params.from_projections == "True":
            self.params.from_projections = True
            self.ui.proj_button.setChecked(True)
            self.ui.sino_button.setChecked(False)
            self.ui.correct_box.setEnabled(True)
        else:
            self.params.from_projections = False
            self.ui.proj_button.setChecked(False)
            self.ui.sino_button.setChecked(True)

        if self.params.correction == "True" and self.proj_button.isChecked():
            self.ui.correct_box.setChecked(True)
            self.params.correction = True
        else:
            self.ui.correct_box.setChecked(False)
            self.params.correction = False
        self.on_correction()

        if self.params.use_gpu == "True":
            self.ui.gpu_box.setChecked(True)
            self.params.use_gpu = True
        else:
            self.ui.gpu_box.setChecked(False)
            self.params.use_gpu = False

        if self.params.absorptivity == "True":
            self.ui.absorptivity_checkbox.setChecked(True)
            self.params.absorptivity = True
        else:
            self.ui.absorptivity_checkbox.setChecked(False)
            self.params.absorptivity = False

    def on_tab_changed(self):
        current_tab = self.ui.tab_widget.currentIndex()
        if current_tab == 0 and self.ui.reco_images_widget.isVisible() == False:
            self.ui.resize(585, 825)
        elif current_tab == 0 and self.ui.reco_images_widget.isVisible() == True:
            self.ui.resize(1500, 900)
        elif current_tab == 1 and self.ui.axis_view_widget.isVisible() == False:
            self.ui.resize(585, 825)
        elif current_tab == 1 and self.ui.axis_view_widget.isVisible() == True:
            self.ui.resize(1500, 900)
        elif current_tab == 2 and self.ui.phgen_images_widget.isVisible() == False:
            self.on_phantom_generator()
            self.ui.resize(585, 825)
        elif current_tab == 2 and self.ui.phgen_images_widget.isVisible() == True:
            self.ui.resize(1500, 900)

    def change_method(self):
        if self.ui.method_box.currentIndex() == 0:
            self.ui.add_params.setVisible(False)
            self.ui.dfi_params.setVisible(False)
            self.params.method = "fbp"

        elif self.ui.method_box.currentIndex() == 1:
            self.ui.add_params.setVisible(True)
            self.ui.dfi_params.setVisible(self.ui.add_params.isChecked())
            self.params.method = "dfi"

    def get_help(self, section, name):
        help = config.SECTIONS[section][name]['help']
        return help

    def change_value(self, name, value):
        setattr(self.params, name, value)

    def on_sino_button_clicked(self):
        if self.ui.sino_button.isChecked():
            self.ui.correct_box.setEnabled(False)
            self.params.correction = False
            self.on_correction()

    def on_proj_button_clicked(self):
        if self.ui.proj_button.isChecked():
            self.ui.correct_box.setEnabled(True)
            if self.ui.correct_box.isChecked() == True:
                self.params.correction = True
                self.on_correction()

    def on_region(self):
        self.ui.from_region.setEnabled(self.ui.region_box.isChecked())
        self.ui.to_region.setEnabled(self.ui.region_box.isChecked())
        self.ui.step_region.setEnabled(self.ui.region_box.isChecked())
        if self.ui.region_box.isChecked() == False:
            self.params.enable_region = False

    def concatenate_region(self):
        self.params.region = str(int(self.ui.from_region.value())) + ":" + str(int(self.ui.to_region.value())) + ":" + str(int(self.ui.step_region.value()))

    def on_input_path_clicked(self, checked):
        _set_line_edit_to_path(self, self.ui.input_path_line, self.params.input, self.params.last_dir)
        if os.path.exists(str(self.ui.input_path_line.text())):
            self.params.last_dir = str(self.ui.input_path_line.text())

        if "sinogram" in str(self.ui.input_path_line.text()):
            self.ui.sino_button.setChecked(True)
            self.ui.proj_button.setChecked(False)
            self.ui.correct_box.setEnabled(False)
            self.ui.params.from_projections = False
            self.params.correction = False
            self.on_correction()
        elif "projection" in str(self.ui.input_path_line.text()):
            self.ui.sino_button.setChecked(False)
            self.ui.proj_button.setChecked(True)
            self.ui.correct_box.setEnabled(True)
            self.params.from_projections = True
        if self.ui.crop_box.isChecked() == True:
            self.on_crop_width()

    def change_axis_spin(self):
        if self.ui.axis_spin.value() == 0:
            self.params.axis = None
        else:
            self.params.axis = self.ui.axis_spin.value()

    def change_angle_step(self):
        if self.ui.angle_step.value() == 0:
            self.params.angle = None
        else:
            self.params.angle = self.ui.angle_step.value()

    def on_crop_width(self):
        if self.ui.crop_box.isChecked() == True:
            try:
                find_file = os.path.join(str(self.ui.input_path_line.text()), os.listdir(str(self.ui.input_path_line.text()))[0])
                crop_file = tifffile.TiffFile(find_file)
                crop_arr = crop_file.asarray()
                crop_width = crop_arr.shape[1]
                self.params.crop_width = crop_width
                self.params.enable_cropping = True
            except Exception as e:
                QtGui.QMessageBox.warning(self, "Warning", "Choose input path first \n" + str(e))
                self.params.enable_cropping = False
                self.ui.crop_box.setChecked(False)
        else:
            self.params.enable_cropping = False

    def on_output_path_clicked(self, checked):
        _set_line_edit_to_path(self, self.ui.output_path_line, self.params.output, self.params.last_dir)
        if os.path.exists(str(self.ui.output_path_line.text())):
            self.params.last_dir = str(self.ui.output_path_line.text())

    def on_correct_box_clicked(self):
        self.params.correction = self.ui.correct_box.isChecked()
        self.on_correction()

    def on_correction(self):
        self.ui.darks_path_line.setVisible(self.params.correction)
        self.ui.darks_path_button.setVisible(self.params.correction)
        self.ui.darks_label.setVisible(self.params.correction)
        self.ui.flats_path_line.setVisible(self.params.correction)
        self.ui.flats_path_button.setVisible(self.params.correction)
        self.ui.flats_label.setVisible(self.params.correction)

    def on_darks_path_clicked(self, checked):
        _set_line_edit_to_path(self, self.ui.darks_path_line, self.params.darks, self.params.last_dir)
        if os.path.exists(str(self.ui.darks_path_line.text())):
            self.params.last_dir = str(self.ui.darks_path_line.text())

    def on_flats_path_clicked(self, checked):
        _set_line_edit_to_path(self, self.ui.flats_path_line, self.params.flats, self.params.last_dir)
        if os.path.exists(str(self.ui.flats_path_line.text())):
            self.params.last_dir = str(self.ui.flats_path_line.text())

    def on_path_0_clicked(self, checked):
        _set_line_edit_to_file(self, self.ui.path_line_0, str(self.ui.path_line_0.text()), self.params.last_dir)
        if os.path.exists(str(self.ui.path_line_0.text())):
            self.params.last_dir = str(self.ui.path_line_0.text())

    def on_path_180_clicked(self, checked):
        _set_line_edit_to_file(self, self.ui.path_line_180, str(self.ui.path_line_180.text()), self.params.last_dir)
        if os.path.exists(str(self.ui.path_line_180.text())):
             self.params.last_dir = str(self.ui.path_line_180.text())

    def on_open_from(self):
        config_file = QtGui.QFileDialog.getOpenFileName(self, 'Open ...', self.params.last_dir)
        self.params = config.TomoParams(config_file)
        self.get_values_from_params()

    def on_save_as(self):
        if os.path.exists(self.params.last_dir):
            config_file = str(self.params.last_dir + "/reco.conf")
        else:
            config_file = str(os.getenv('HOME') + "reco.conf")
        save_config = QtGui.QFileDialog.getSaveFileName(self, 'Save as ...', config_file)
        if save_config:
            self.params.config = save_config
            self.params.write(self.params.config)

    def on_clear(self):
        self.ui.reco_images_widget.setVisible(False)
        self.ui.phgen_images_widget.setVisible(False)
        self.ui.axis_view_widget.setVisible(False)
        self.ui.axis_options.setVisible(False)
        self.on_tab_changed()

        self.ui.input_path_line.setText('.')
        self.ui.output_path_line.setText('.')
        self.ui.darks_path_line.setText('.')
        self.ui.flats_path_line.setText('.')
        self.ui.path_line_0.setText('.')
        self.ui.path_line_180.setText('.')

        self.ui.sino_button.setChecked(True)
        self.ui.proj_button.setChecked(False)
        self.ui.region_box.setChecked(False)
        self.ui.crop_box.setChecked(False)
        self.ui.correct_box.setChecked(False)
        self.ui.absorptivity_checkbox.setChecked(False)
        self.ui.gpu_box.setChecked(False)

        self.ui.from_region.setValue(0)
        self.ui.to_region.setValue(1)
        self.ui.step_region.setValue(1)
        self.ui.axis_spin.setValue(0)
        self.ui.angle_step.setValue(0)
        self.ui.angle_offset.setValue(0)
        self.ui.oversampling.setValue(0)

        self.ui.from_region.setEnabled(False)
        self.ui.to_region.setEnabled(False)
        self.ui.step_region.setEnabled(False)
        self.ui.correct_box.setEnabled(False)
        self.ui.text_browser.clear()
        self.ui.method_box.setCurrentIndex(0)

        self.params.from_projections = False
        self.params.enable_cropping = False
        self.params.enable_region = False
        self.params.absorptivity = False
        self.params.correction = False
        self.params.crop_width = None
        self.params.use_gpu = False
        self.params.angle = None
        self.params.axis = None
        self.on_correction()

        self.ui.phgen_width.setValue(512)
        self.ui.phgen_height.setValue(512)
        self.ui.sum_abs_diff.setText('')
        self.ui.reco_sino_phgen.setChecked(False)
        self.ui.generate_phantom.setChecked(True)
        self.ui.generate_sinogram.setChecked(True)

    def closeEvent(self, event):
        self.params.config = "reco.conf"
        try:
            self.params.write(self.params.config)
        except IOError as e:
            QtGui.QMessageBox.warning(self, "Warning", str(e))
            self.on_save_as()
        try:
            os.remove(log.name)
        except OSError as e:
            pass

    def on_reconstruct(self):
        _enable_wait_cursor()
        self.ui.centralWidget.setEnabled(False)
        self.repaint()
        self.app.processEvents()

        try:
            reco.tomo(self.params)

        except Exception as e:
            QtGui.QMessageBox.warning(self, "Warning", str(e))

        if self.ui.show_reco_images_box.isChecked() :
            try:
                if self.ui.reco_sino_phgen.isChecked() == False:
                    output_path = str(self.ui.output_path_line.text())
                    if output_path == ".":
                        output_path = str(os.getcwd())
                    self.show_reco_images()
                else:
                    self.show_phgen_images()

            except Exception as e:
                QtGui.QMessageBox.warning(self, "Warning", str(e))

        _disable_wait_cursor()
        self.ui.centralWidget.setEnabled(True)

        if self.ui.reco_sino_phgen.isChecked():
            self.ui.reco_sino_phgen.setChecked(False)
            self.on_sum_absolute_differences()
            self.params.enable_cropping = False
            self.ui.crop_box.setChecked(False)
            self.ui.tab_widget.setCurrentIndex(2)

        log.seek(0)
        logtxt = open(log.name).read()
        self.ui.text_browser.setPlainText(logtxt)

    def show_reco_images(self):
        self.reco_graphics_view = pg.GraphicsView()
        self.reco_viewbox = pg.ViewBox(invertY=True)
        self.reco_viewbox.setAspectLocked(True)
        self.reco_histogram = pg.HistogramLUTWidget()
        self.reco_graphics_view.setCentralItem(self.reco_viewbox)
        reco_files = [f for f in sorted(os.listdir(str(self.ui.output_path_line.text()))) if f.endswith('.tif')]
        self.reco_absfiles = [str(self.ui.output_path_line.text()) + '/' + name for name in reco_files]
        self.ui.reco_slider.setMaximum(len(self.reco_absfiles) - 1)
        self.move_reco_slider()
        self.ui.reco_images.addWidget(self.reco_graphics_view, 0, 0)
        self.ui.reco_images.addWidget(self.reco_histogram, 0, 1)
        self.ui.reco_images_widget.setVisible(True)
        self.ui.resize(1500, 900)

    def move_reco_slider(self):
        pos = self.ui.reco_slider.value()
        img = self.convert_tif_to_img(self.reco_absfiles[pos])
        self.reco_viewbox.clear()
        self.reco_viewbox.addItem(img)
        self.reco_histogram.setImageItem(img)

    def convert_tif_to_img(self, tif_file):
        tif = tifffile.TiffFile(tif_file)
        array = tif.asarray()
        image = pg.ImageItem(array.T)
        return image

    def on_hide_reco_images(self):
        if self.ui.show_reco_images_box.isChecked() == False:
            self.ui.reco_images_widget.setVisible(False)

    def on_run(self):
        _enable_wait_cursor()
        try:
            self.init_axis()
            self.read_data()
            self.compute_axis()
            self.do_axis_layout()

        except Exception as e:
            _disable_wait_cursor()
            QtGui.QMessageBox.warning(self, "Warning", str(e))

    def init_axis(self):
        self.w_over = pg.GraphicsView()
        self.viewbox = pg.ViewBox()
        self.w_over.setCentralItem(self.viewbox)
        self.histogram = pg.HistogramLUTWidget()

    def read_data(self):
        tif_0 = tifffile.TiffFile(str(self.ui.path_line_0.text()))
        tif_180 = tifffile.TiffFile(str(self.ui.path_line_180.text()))

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
        self.ui.axis_slider.setValue(slider_val)

        self.params.axis = self.axis
        self.ui.axis_spin.setValue(self.axis)
        self.update_image()

    def update_image(self):
        arr_180 = np.roll(self.arr_180, self.move, axis=1)
        self.arr_over = self.arr_flip - arr_180
        current_overlap = self.ui.overlap_opt.currentIndex()
        if current_overlap == 0:
            self.arr_over = self.arr_flip - arr_180
        elif current_overlap == 1:
            self.arr_over = self.arr_flip + arr_180
        img = pg.ImageItem(self.arr_over.T)
        self.img_width = self.arr_over.T.shape[0]
        self.img_height = self.arr_over.T.shape[1]
        self.viewbox.clear()
        self.viewbox.addItem(img)
        self.viewbox.setAspectLocked(True)
        self.histogram.setImageItem(img)

    def do_axis_layout(self):
        self.extrema_checkbox.setChecked(False)
        self.extrema_checkbox.setEnabled(True)
        self.ui.axis_num.setText('center of rotation = %i px' % (self.axis))
        self.ui.img_size.setText('width = %i | height = %i' % (self.img_width, self.img_height))
        self.ui.axis_view_layout.addWidget(self.w_over, 0, 0)
        self.ui.axis_view_layout.addWidget(self.histogram, 0, 1)
        self.axis_view_widget.setVisible(True)
        self.axis_options.setVisible(True)
        self.ui.resize(1500, 900)
        _disable_wait_cursor()

    def keyPressEvent(self, event):
        if self.ui.tab_widget.currentIndex() == 0 and self.ui.reco_images_widget.isVisible() == True:
            if event.key() == QtCore.Qt.Key_Right:
                self.ui.reco_slider.setValue(self.ui.reco_slider.value() + 1)
            elif event.key() == QtCore.Qt.Key_Left:
                self.ui.reco_slider.setValue(self.ui.reco_slider.value() - 1)
            else:
                QtGui.QMainWindow.keyPressEvent(self, event)

        elif self.ui.tab_widget.currentIndex() == 1 and self.ui.axis_view_widget.isVisible() == True:
            if event.key() == QtCore.Qt.Key_Right:
                self.ui.axis_slider.setValue(self.ui.axis_slider.value() + 1)
            elif event.key() == QtCore.Qt.Key_Left:
                self.ui.axis_slider.setValue(self.ui.axis_slider.value() - 1)
            else:
                QtGui.QMainWindow.keyPressEvent(self, event)

        elif self.ui.tab_widget.currentIndex() == 2 and self.ui.phgen_images_widget.isVisible() == True:
            if event.key() == QtCore.Qt.Key_Right:
                self.ui.phgen_slider.setValue(self.ui.phgen_slider.value() + 1)
            elif event.key() == QtCore.Qt.Key_Left:
                self.ui.phgen_slider.setValue(self.ui.phgen_slider.value() - 1)
            else:
                QtGui.QMainWindow.keyPressEvent(self.event)

    def wheelEvent(self, event):
        wheel = 0
        if self.ui.tab_widget.currentIndex() == 0 and self.ui.reco_images_widget.isVisible() == True:
            delta = event.delta()
            wheel += (delta and delta // abs(delta))
            self.ui.reco_slider.setValue(self.ui.reco_slider.value() - wheel)

        if self.ui.tab_widget.currentIndex() == 1 and self.ui.axis_view_widget.isVisible() == True:
            delta = event.delta()
            wheel += (delta and delta // abs(delta))
            self.ui.axis_slider.setValue(self.ui.axis_slider.value() - wheel)

        if self.ui.tab_widget.currentIndex() == 2 and self.ui.phgen_images_widget.isVisible() == True:
            delta = event.delta()
            wheel += (delta and delta // abs(delta))
            self.ui.phgen_slider.setValue(self.ui.phgen_slider.value() - wheel)

    def move_axis_slider(self):
        pos = self.ui.axis_slider.value()
        if pos > 500:
            self.move = -1 * (pos - 500)
        elif pos < 500:
            self.move = 500 - pos
        else:
            self.move = 0

        self.update_axis()
        self.update_image()

    def on_overlap_opt_changed(self):
        current_overlap = self.ui.overlap_opt.currentIndex()
        if current_overlap == 0:
            self.arr_over = self.arr_flip - arr_180
        elif current_overlap == 1:
            self.arr_over = self.arr_flip + arr_180

    def update_axis(self):
        self.axis = self.width / 2 + self.move
        self.ui.axis_num.setText('center of rotation = %s px' % str(self.axis))

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
        self.ui.extrema_checkbox.setEnabled(False)

    def on_phantom_generator(self):
        self.phantom = ''
        self.sino = ''
        if self.ui.generate_phantom.isChecked():
            self.phantom = '-p '
        if self.ui.generate_sinogram.isChecked():
            self.sino = '-s '
        self.width = '-w ' + str(self.ui.phgen_width.value())
        self.height = ' -h ' + str(self.ui.phgen_height.value())

    def on_generate_phantom(self):
        if self.ui.generate_phantom.isChecked() == True:
            self.phantom = '-p '
        else:
            self.phantom = ''
            self.sino = '-s '
            self.ui.generate_sinogram.setChecked(True)

    def on_generate_sinogram(self):
        if self.ui.generate_sinogram.isChecked() == True:
            self.sino = '-s '
        else:
            self.sino = ''
            self.phantom = '-p '
            self.ui.generate_phantom.setChecked(True)

    def on_phgen_width_changed(self):
        self.width = '-w ' + str(self.ui.phgen_width.value())

    def on_phgen_height_changed(self):
        self.height = ' -h ' + str(self.ui.phgen_height.value())

    def on_generate(self):
        _enable_wait_cursor()
        run_phgen = "generate " + str(self.sino) + str(self.phantom) + str(self.width) + str(self.height)
        subprocess.call([run_phgen], shell = True)
        for sino in os.listdir(os.getcwd()):
            if os.path.isfile(os.path.join(os.getcwd(), sino)) and 'sinogram' in sino:
                self.generated_sinogram = sino
        _disable_wait_cursor()

    def on_reco_sino(self):
        if self.ui.reco_sino_phgen.isChecked():
            self.ui.sino_button.setChecked(True)
            self.params.from_projections = False

            try:
                self.ui.input_path_line.setText(self.generated_sinogram)
                self.ui.output_path_line.setText(os.getcwd())
                if self.ui.phgen_width.value() == self.ui.phgen_height.value() and self.params.method == 'fbp':
                    self.params.enable_cropping = True
                    self.ui.crop_box.setChecked(True)
                    self.params.crop_width = self.ui.phgen_width.value()
                    self.axis_spin.setValue(0)
                self.ui.tab_widget.setCurrentIndex(0)

            except Exception as e:
                self.ui.reco_sino_phgen.setChecked(False)
                QtGui.QMessageBox.warning(self, "Warning", str(e))

    def show_phgen_images(self):
        self.phgen_graphics_view = pg.GraphicsView()
        self.phgen_viewbox = pg.ViewBox(invertY=True)
        self.phgen_viewbox.setAspectLocked(True)
        self.phgen_histogram = pg.HistogramLUTWidget()
        self.phgen_graphics_view.setCentralItem(self.phgen_viewbox)

        try:
            self.phgen_files = [f for f in sorted(os.listdir(os.getcwd())) if f.endswith('.tif')]
            self.ui.phgen_slider.setMaximum(len(self.phgen_files) - 1)
            self.move_phgen_slider()
            self.ui.phgen_images_layout.addWidget(self.phgen_graphics_view, 0, 0)
            self.ui.phgen_images_layout.addWidget(self.phgen_histogram, 0, 1)
            self.ui.phgen_images_widget.setVisible(True)
            if self.ui.tab_widget.currentIndex() == 2:
                self.ui.resize(1500, 900)

        except Exception as e:
            QtGui.QMessageBox.warning(self, "Warning", str(e))

    def move_phgen_slider(self):
        pos = self.ui.phgen_slider.value()
        img = self.convert_tif_to_img(self.phgen_files[pos])
        self.phgen_viewbox.clear()
        self.phgen_viewbox.addItem(img)
        self.phgen_histogram.setImageItem(img)

    def on_sum_absolute_differences(self):
        _enable_wait_cursor()
        for slice_file in os.listdir(os.getcwd()):
            if os.path.isfile(os.path.join(os.getcwd(), slice_file)) and 'slice' in slice_file:
                reco_slice = slice_file
        for phantom_file in os.listdir(os.getcwd()):
            if os.path.isfile(os.path.join(os.getcwd(), phantom_file)) and 'phantom' in phantom_file:
                phantom = phantom_file

        slice_tif = tifffile.TiffFile(reco_slice)
        phantom_tif = tifffile.TiffFile(phantom)
        slice_array = slice_tif.asarray()
        phantom_array = phantom_tif.asarray()
        slice_shape = slice_array.shape
        phantom_shape = phantom_array.shape

        if slice_shape[0] > phantom_shape[0]:
            height = phantom_shape[0] - 1
        else:
            height = slice_shape[0] - 1
        if slice_shape[1] > phantom_shape[1]:
            width = phantom_shape[1] - 1
        else:
            width = slice_shape[1] - 1

        sum_abs_diff = 0
        try:
            for x in range (0, height):
                for y in range(0, width):
                    sum_abs_diff += abs(slice_array[x][y] - phantom_array[x][y])

            self.ui.sum_abs_diff.setText(str(sum_abs_diff))
        except Exception as e:
            QtGui.QMessageBox.warning(self, "Warning", str(e))
        _disable_wait_cursor()


def main(params):
    app = QtGui.QApplication(sys.argv)
    window = ApplicationWindow(app, params)
    sys.exit(app.exec_())
