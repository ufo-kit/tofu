import sys
import os
import logging
import tempfile
import subprocess
import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl
import pkg_resources

from . import reco, config, tifffile
from PyQt4 import QtGui, QtCore, uic
from scipy.signal import fftconvolve


logging.getLogger('').handlers = []
LOG = logging.getLogger(__name__)
logging.getLogger('PyQt4.uic.uiparser').disabled = True
logging.getLogger('PyQt4.uic.properties').disabled = True
log = tempfile.NamedTemporaryFile(delete = False, suffix = '.txt')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s:%(levelname)s:%(name)s:%(message)s',
    filename=log.name,
    filemode='a'
)

def _set_line_edit_to_path(parent, directory, last_dir):
    if last_dir is not None:
        directory = last_dir
    path = QtGui.QFileDialog.getExistingDirectory(parent, '.', directory)
    return path

def _set_line_edit_to_file(parent, directory, last_dir):
    if last_dir is not None:
        directory = last_dir
    file_name = QtGui.QFileDialog.getOpenFileName(parent, '.', directory)
    return file_name

def _set_last_dir(parent, path, line_edit, last_dir):
    if os.path.exists(str(path)):
        line_edit.clear()
        line_edit.setText(path)
        last_dir = str(line_edit.text())
    return last_dir

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
        self.ui.reco_volume_widget.setVisible(False)
        self.ui.volume_min_slider.setTracking(False)
        self.ui.volume_max_slider.setTracking(False)
        self.ui.phgen_images_widget.setVisible(False)
        self.ui.axis_view_widget.setVisible(False)
        self.ui.axis_options.setVisible(False)
        self.ui.volume_params.setVisible(False)
        self.phgen_graphics_view = False
        self.reco_images_layout = False
        self.volume_layout = False
        self.viewbox = False
        self.get_values_from_params()

        self.ui.input_path_button.setToolTip(self.get_help('general', 'input'))
        self.ui.proj_button.setToolTip(self.get_help('fbp', 'from_projections'))
        self.ui.y_step.setToolTip(self.get_help('general', 'y_step'))
        self.ui.method_box.setToolTip(self.get_help('general', 'method'))
        self.ui.axis_spin.setToolTip(self.get_help('general', 'axis'))
        self.ui.angle_step.setToolTip(self.get_help('general', 'angle'))
        self.ui.angle_offset.setToolTip(self.get_help('general', 'offset'))
        self.ui.oversampling.setToolTip(self.get_help('dfi', 'oversampling'))
        self.ui.iterations_sart.setToolTip(self.get_help('sart', 'max_iterations'))
        self.ui.relaxation.setToolTip(self.get_help('sart', 'relaxation_factor'))
        self.ui.output_path_button.setToolTip(self.get_help('general', 'output'))
        self.ui.ffc_box.setToolTip(self.get_help('general', 'ffc_correction'))
        self.ui.ip_box.setToolTip(self.get_help('general', 'ip_correction'))
        self.ui.darks_path_button.setToolTip(self.get_help('general', 'darks'))
        self.ui.flats_path_button.setToolTip(self.get_help('general', 'flats'))
        self.ui.flats2_path_button.setToolTip(self.get_help('general', 'flats2'))
        self.ui.path_button_0.setToolTip(self.get_help('general', 'deg0'))
        self.ui.path_button_180.setToolTip(self.get_help('general', 'deg180'))

        self.ui.input_path_button.clicked.connect(self.on_input_path_clicked)
        self.ui.sino_button.clicked.connect(self.on_sino_button_clicked)
        self.ui.proj_button.clicked.connect(self.on_proj_button_clicked)
        self.ui.region_box.clicked.connect(self.on_region_box_clicked)
        self.ui.method_box.currentIndexChanged.connect(self.change_method)
        self.ui.axis_spin.valueChanged.connect(self.change_axis_spin)
        self.ui.angle_step.valueChanged.connect(self.change_angle_step)
        self.ui.crop_box.clicked.connect(self.on_crop_width)
        self.ui.output_path_button.clicked.connect(self.on_output_path_clicked)
        self.ui.ffc_box.clicked.connect(self.on_ffc_box_clicked)
        self.ui.ip_box.clicked.connect(self.on_ip_box_clicked)
        self.ui.darks_path_button.clicked.connect(self.on_darks_path_clicked)
        self.ui.flats_path_button.clicked.connect(self.on_flats_path_clicked)
        self.ui.flats2_path_button.clicked.connect(self.on_flats2_path_clicked)
        self.ui.ffc_options.currentIndexChanged.connect(self.change_ffc_options)
        self.ui.reco_button.clicked.connect(self.on_reconstruct)
        self.ui.reco_slider.valueChanged.connect(self.move_reco_slider)
        self.ui.tab_widget.currentChanged.connect(self.on_tab_changed)
        self.ui.path_button_0.clicked.connect(self.on_path_0_clicked)
        self.ui.path_button_180.clicked.connect(self.on_path_180_clicked)
        self.ui.show_reco_images_box.clicked.connect(self.on_hide_reco_images)
        self.ui.show_volume_box.clicked.connect(self.on_hide_volume)
        self.ui.gloptions.currentIndexChanged.connect(self.change_gloptions)
        self.ui.gloptions2.currentIndexChanged.connect(self.change_gloptions)
        self.ui.percent_box.valueChanged.connect(self.on_percent_box)
        self.ui.percent_box2.valueChanged.connect(self.on_percent_box2)
        self.ui.volume_min_slider.valueChanged.connect(self.on_volume_sliders)
        self.ui.volume_max_slider.valueChanged.connect(self.on_volume_sliders)
        self.ui.crop_circle_box.clicked.connect(self.on_crop_circle)
        self.ui.crop_more_button.clicked.connect(self.on_crop_more_circle)
        self.ui.crop_less_button.clicked.connect(self.on_crop_less_circle)
        self.ui.make_contrast_button.clicked.connect(self.on_make_contrast)
        self.ui.update_volume_button.clicked.connect(self.update_volume)
        self.ui.update_volume_button2.clicked.connect(self.make_volume_layout)
        self.ui.run_button.clicked.connect(self.on_run)
        self.ui.save_action.triggered.connect(self.on_save_as)
        self.ui.clear_action.triggered.connect(self.on_clear)
        self.ui.clear_output_dir_action.triggered.connect(self.on_clear_output_dir_clicked)
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
        self.ui.y_step.valueChanged.connect(lambda value: self.change_value('y_step', value))
        self.ui.angle_offset.valueChanged.connect(lambda value: self.change_value('offset', value))
        if self.add_params.isChecked():
            self.ui.method_box.currentIndexChanged.connect(lambda value: self.change_value('method', self.method))
        self.ui.oversampling.valueChanged.connect(lambda value: self.change_value('oversampling', value))
        self.ui.iterations_sart.valueChanged.connect(lambda value: self.change_value('max_iterations', value))
        self.ui.relaxation.valueChanged.connect(lambda value: self.change_value('relaxation_factor', value))
        self.ui.output_path_line.textChanged.connect(lambda value: self.change_value('output', str(self.ui.output_path_line.text())))
        self.ui.darks_path_line.textChanged.connect(lambda value: self.change_value('darks', str(self.ui.darks_path_line.text())))
        self.ui.flats_path_line.textChanged.connect(lambda value: self.change_value('flats', str(self.ui.flats_path_line.text())))
        self.ui.flats2_path_line.textChanged.connect(lambda value: self.change_value('flats2', str(self.ui.flats2_path_line.text())))
        self.ui.path_line_0.textChanged.connect(lambda value: self.change_value('deg0', str(self.ui.path_line_0.text())))
        self.ui.path_line_180.textChanged.connect(lambda value: self.change_value('deg180', str(self.ui.path_line_180.text())))
        self.ui.gpu_box.clicked.connect(lambda value: self.change_value('use_gpu', self.ui.gpu_box.isChecked()))

    def get_values_from_params(self):
        self.ui.input_path_line.setText(self.params.input)
        self.ui.output_path_line.setText(self.params.output)
        self.ui.darks_path_line.setText(self.params.darks)
        self.ui.flats_path_line.setText(self.params.flats)
        self.ui.flats2_path_line.setText(self.params.flats2)
        self.ui.path_line_0.setText(self.params.deg0)
        self.ui.path_line_180.setText(self.params.deg180)

        self.ui.y_step.setValue(self.params.y_step if self.params.y_step else 1)
        self.ui.axis_spin.setValue(self.params.axis if self.params.axis else 0.0)
        self.ui.angle_step.setValue(self.params.angle if self.params.angle else 0.0)
        self.ui.angle_offset.setValue(self.params.offset if self.params.offset else 0.0)
        self.ui.oversampling.setValue(self.params.oversampling if self.params.oversampling else 0)
        self.ui.iterations_sart.setValue(self.params.max_iterations if self.params.max_iterations else 0)
        self.ui.relaxation.setValue(self.params.relaxation_factor if self.params.relaxation_factor else 0.0)

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
            self.on_proj_button_clicked()
        else:
            self.params.from_projections = False
            self.ui.proj_button.setChecked(False)
            self.ui.sino_button.setChecked(True)
            self.on_sino_button_clicked()

        if self.params.method == "fbp":
            self.ui.method_box.setCurrentIndex(0)
        elif self.params.method == "dfi":
            self.ui.method_box.setCurrentIndex(1)
        elif self.params.method == "sart":
            self.ui.method_box.setCurrentIndex(2)
            self.ui.sino_button.setChecked(True)
            self.params.from_projections = False

        self.change_method()

        if self.params.y_step > 1 and self.sino_button.isChecked():
            self.ui.region_box.setChecked(True)
        else:
            self.ui.region_box.setChecked(False)
        self.ui.on_region_box_clicked()

        if self.params.ffc_correction == "True" and self.proj_button.isChecked():
            self.ui.ffc_box.setChecked(True)
        else:
            self.ui.ffc_box.setChecked(False)
        self.on_ffc_box_clicked()

        if self.params.ip_correction == "True" and self.proj_button.isChecked():
            self.ui.ip_box.setChecked(True)
        else:
            self.ui.ip_box.setChecked(False)
        self.on_ip_box_clicked()

        if self.params.ffc_options == "Average":
            self.ui.ffc_options.setCurrentIndex(0)
        else:
            self.ui.ffc_options.setCurrentIndex(1)

        if self.params.use_gpu == "True":
            self.ui.gpu_box.setChecked(True)
            self.params.use_gpu = True
        else:
            self.ui.gpu_box.setChecked(False)
            self.params.use_gpu = False

    def on_tab_changed(self):
        current_tab = self.ui.tab_widget.currentIndex()
        if current_tab == 0 and self.ui.reco_images_widget.isVisible() == False and self.ui.reco_volume_widget.isVisible() == False:
            self.ui.resize(585, 825)
        elif current_tab == 0 and (self.ui.reco_images_widget.isVisible() == True or self.ui.reco_volume_widget.isVisible() == True):
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
            self.ui.sart_params.setVisible(False)
            self.params.method = "fbp"

        elif self.ui.method_box.currentIndex() == 1:
            self.ui.add_params.setVisible(True)
            self.ui.sart_params.setVisible(False)
            self.ui.dfi_params.setVisible(self.ui.add_params.isChecked())
            self.params.method = "dfi"

        elif self.ui.method_box.currentIndex() == 2:
            self.ui.add_params.setVisible(True)
            self.ui.dfi_params.setVisible(False)
            self.ui.sart_params.setVisible(self.ui.add_params.isChecked())
            self.params.method = "sart"
            self.ui.sino_button.setChecked(True)
            self.on_sino_button_clicked()
            self.params.from_projections = False

    def get_help(self, section, name):
        help = config.SECTIONS[section][name]['help']
        return help

    def change_value(self, name, value):
        setattr(self.params, name, value)

    def on_sino_button_clicked(self):
        if self.ui.sino_button.isChecked():
            self.ui.ffc_box.setEnabled(False)
            self.ui.ffc_box.setChecked(False)
            self.ui.ip_box.setEnabled(False)
            self.ui.ip_box.setChecked(False)
            self.on_ffc_box_clicked()
            self.on_ip_box_clicked()
            self.ui.region_box.setEnabled(True)

    def on_proj_button_clicked(self):
        if self.ui.proj_button.isChecked():
            self.ui.ffc_box.setEnabled(True)
            self.ui.ip_box.setEnabled(True)
            self.ui.region_box.setEnabled(False)
            self.ui.region_box.setChecked(False)
            self.on_region_box_clicked()

    def on_region_box_clicked(self):
        self.ui.y_step.setEnabled(self.ui.region_box.isChecked())
        if self.ui.region_box.isChecked():
            self.params.y_step = self.ui.y_step.value()
        else:
            self.params.y_step = 1

    def on_input_path_clicked(self, checked):
        path = _set_line_edit_to_path(self, self.params.input, self.params.last_dir)
        self.params.last_dir = _set_last_dir(self, path, self.ui.input_path_line, self.params.last_dir)

        if "sinogram" in str(self.ui.input_path_line.text()):
            self.ui.sino_button.setChecked(True)
            self.ui.proj_button.setChecked(False)
            self.params.from_projections = False
            self.on_sino_button_clicked()
        elif "projection" in str(self.ui.input_path_line.text()):
            self.ui.sino_button.setChecked(False)
            self.ui.proj_button.setChecked(True)
            self.params.from_projections = True
            self.on_proj_button_clicked()
        if self.ui.crop_box.isChecked():
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
        if self.ui.crop_box.isChecked():
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
        path = _set_line_edit_to_path(self, self.params.output, self.params.last_dir)
        self.params.last_dir = _set_last_dir(self, path, self.ui.output_path_line, self.params.last_dir)
        self.output = "new"

    def on_clear_output_dir_clicked(self):
        output_files = [f for f in os.listdir(str(self.ui.output_path_line.text())) if f.endswith('.tif')]
        output_absfiles = [str(self.ui.output_path_line.text()) + '/' + name for name in output_files]
        for f in output_absfiles:
            os.remove(f)
        self.ui.reco_slider.setEnabled(False)

    def on_ffc_box_clicked(self):
        self.params.ffc_correction = self.ui.ffc_box.isChecked()
        self.ui.ffc_correction.setVisible(self.ui.ffc_box.isChecked())
        if self.ui.ffc_box.isChecked() == False:
            self.ip_box.setChecked(False)
            self.params.ip_correction = False
            self.ui.ip_correction.setVisible(False)

    def on_ip_box_clicked(self):
        self.params.ip_correction = self.ui.ip_box.isChecked()
        self.ui.ip_correction.setVisible(self.ui.ip_box.isChecked())
        if self.ui.ip_box.isChecked():
            self.ui.ffc_box.setChecked(True)
            self.params.ffc_correction = True
            self.ui.ffc_correction.setVisible(True)

    def change_ffc_options(self):
        self.params.ffc_options = str(self.ui.ffc_options.currentText())

    def on_darks_path_clicked(self, checked):
        path = _set_line_edit_to_path(self, self.params.darks, self.params.last_dir)
        self.params.last_dir = _set_last_dir(self, path, self.ui.darks_path_line, self.params.last_dir)

    def on_flats_path_clicked(self, checked):
        path = _set_line_edit_to_path(self, self.params.flats, self.params.last_dir)
        self.params.last_dir = _set_last_dir(self, path, self.ui.flats_path_line, self.params.last_dir)

    def on_flats2_path_clicked(self, checked):
        path = _set_line_edit_to_path(self, self.params.flats2, self.params.last_dir)
        self.params.last_dir = _set_last_dir(self, path, self.ui.flats2_path_line, self.params.last_dir)

    def on_path_0_clicked(self, checked):
        path = _set_line_edit_to_file(self, self.params.deg0, self.params.last_dir)
        self.params.last_dir = _set_last_dir(self, path, self.ui.path_line_0, self.params.last_dir)

    def on_path_180_clicked(self, checked):
        path = _set_line_edit_to_file(self, self.params.deg180, self.params.last_dir)
        self.params.last_dir = _set_last_dir(self, path, self.ui.path_line_180, self.params.last_dir)

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
        self.ui.reco_volume_widget.setVisible(False)
        self.ui.phgen_images_widget.setVisible(False)
        self.ui.axis_view_widget.setVisible(False)
        self.ui.axis_options.setVisible(False)
        self.on_tab_changed()

        self.ui.input_path_line.setText('.')
        self.ui.output_path_line.setText('.')
        self.ui.darks_path_line.setText('.')
        self.ui.flats_path_line.setText('.')
        self.ui.flats2_path_line.setText('.')
        self.ui.path_line_0.setText('.')
        self.ui.path_line_180.setText('.')

        self.ui.sino_button.setChecked(True)
        self.ui.proj_button.setChecked(False)
        self.ui.region_box.setChecked(False)
        self.ui.crop_box.setChecked(False)
        self.ui.ffc_box.setChecked(False)
        self.ui.ip_box.setChecked(False)
        self.ui.gpu_box.setChecked(False)

        self.ui.y_step.setValue(1)
        self.ui.axis_spin.setValue(0)
        self.ui.angle_step.setValue(0)
        self.ui.angle_offset.setValue(0)
        self.ui.oversampling.setValue(0)
        self.ui.ffc_options.setCurrentIndex(0)

        self.ui.text_browser.clear()
        self.ui.method_box.setCurrentIndex(0)

        self.params.from_projections = False
        self.params.enable_cropping = False
        self.params.ffc_options = "Average"
        self.params.crop_width = None
        self.params.use_gpu = False
        self.params.angle = None
        self.params.axis = None
        self.on_region_box_clicked()
        self.on_ffc_box_clicked()
        self.on_ip_box_clicked()

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

        if self.params.y_step > 1:
            self.params.angle *= self.params.y_step

        if self.params.ffc_correction:
           flats_files = [f for f in os.listdir(str(self.ui.flats_path_line.text())) if f.endswith('.tif')]
           self.params.num_flats = len(flats_files)
        else:
           self.params.num_flats = 0

        if self.ui.add_params.isChecked() == False and self.params.method == "dfi":
            self.params.oversampling = None
        elif self.ui.add_params.isChecked() and self.params.method == "dfi":
            self.params.oversampling = self.ui.oversampling.value()

        if self.params.method == "sart":
            input_sinos = [f for f in os.listdir(str(self.ui.input_path_line.text())) if f.endswith('.tif')]
            abs_sino = str(self.ui.input_path_line.text()) + '/' + str(input_sinos[0])
            tif = tifffile.TiffFile(abs_sino)
            array = tif.asarray()
            self.params.num_angles = array.shape[0]

            if self.ui.add_params.isChecked():
                self.params.max_iterations = self.ui.iterations_sart.value()
                self.params.relaxation_factor = self.ui.relaxation.value()
            else:
                self.params.max_iterations = 0
                self.params.relaxation_factor = 0.0

        if self.params.method == "sart" and self.params.angle == None:
            QtGui.QMessageBox.warning(self,"Warning", "Missing argument for Angle step (rad)")

        else:
            try:
                reco.tomo(self.params)

                if self.ui.show_reco_images_box.isChecked():
                    if self.ui.reco_sino_phgen.isChecked() == False:
                        output_path = str(self.ui.output_path_line.text())
                        if output_path == ".":
                            output_path = str(os.getcwd())

                        if self.reco_images_layout == False:
                            self.make_reco_layout()
                        else:
                            self.show_reco_images()

                    else:
                        if self.phgen_graphics_view == False:
                            self.show_phgen_images()
                        else:
                            self.update_phgen_images()

                if self.ui.show_volume_box.isChecked():
                    if self.volume_layout == False:
                        self.make_volume_layout()
                    else:
                        self.output = "new"
                        self.update_volume()

            except Exception as e:
                QtGui.QMessageBox.warning(self, "Warning", str(e))

        _disable_wait_cursor()
        self.ui.centralWidget.setEnabled(True)
        self.params.angle = self.ui.angle_step.value()

        if self.ui.reco_sino_phgen.isChecked():
            self.ui.reco_sino_phgen.setChecked(False)
            self.on_sum_absolute_differences()
            self.params.enable_cropping = False
            self.ui.crop_box.setChecked(False)
            self.ui.tab_widget.setCurrentIndex(2)

            if self.ui.phgen_images_widget.isVisible() == False:
                self.ui.phgen_images_widget.setVisible(True)
                self.ui.resize(1500, 900)

        log.seek(0)
        logtxt = open(log.name).read()
        self.ui.text_browser.setPlainText(logtxt)

    def make_reco_layout(self):
        self.reco_images_layout = True
        self.reco_graphics_view = pg.GraphicsView()
        self.reco_viewbox = pg.ViewBox(lockAspect=True, invertY=True)
        self.reco_histogram = pg.HistogramLUTWidget()
        self.reco_graphics_view.setCentralItem(self.reco_viewbox)
        self.show_reco_images()
        self.ui.reco_images.addWidget(self.reco_graphics_view, 0, 0)
        self.ui.reco_images.addWidget(self.reco_histogram, 0, 1)

    def show_reco_images(self):
        self.levels = None
        reco_files = [f for f in sorted(os.listdir(str(self.ui.output_path_line.text()))) if f.endswith('.tif')]
        self.reco_absfiles = [str(self.ui.output_path_line.text()) + '/' + name for name in reco_files]
        self.ui.reco_slider.setMaximum(len(self.reco_absfiles) - 1)
        self.ui.reco_slider.setEnabled(True)
        self.move_reco_slider()
        self.levels = self.reco_histogram.getLevels()
        if self.ui.reco_images_widget.isVisible() == False:
            self.ui.reco_images_widget.setVisible(True)
            self.ui.resize(1500, 900)

    def move_reco_slider(self):
        new_levels = self.reco_histogram.getLevels()
        pos = self.ui.reco_slider.value()
        img = self.convert_tif_to_img(self.reco_absfiles[pos])
        self.reco_viewbox.clear()
        self.reco_viewbox.addItem(img)
        self.reco_histogram.setImageItem(img)
        if self.levels is not None:
            if new_levels == self.levels:
                self.reco_histogram.setLevels(self.levels[0], self.levels[1])
            else:
                self.reco_histogram.setLevels(new_levels[0], new_levels[1])

    def convert_tif_to_img(self, tif_file):
        tif = tifffile.TiffFile(tif_file)
        array = tif.asarray()
        image = pg.ImageItem(array.T)
        return image

    def make_volume_layout(self):
        _enable_wait_cursor()
        self.ui.centralWidget.setEnabled(False)
        self.repaint()
        self.app.processEvents()
        self.volume_layout = True
        self.scale_percent = self.ui.percent_box.value()
        self.reco_volume_view = gl.GLViewWidget()
        self.ui.volume_image.addWidget(self.reco_volume_view, 0, 0)
        self.volume_img = gl.GLVolumeItem(None)
        self.reco_volume_view.addItem(self.volume_img)
        self.get_slices()
        try:
            self.show_volume()
            self.set_volume_to_center()
            self.on_volume_sliders()
        except ValueError as verror:
            LOG.debug(str(verror))
            log.seek(0)
            logtxt = open(log.name).read()
            self.ui.text_browser.setPlainText(logtxt)

        _disable_wait_cursor()
        self.ui.centralWidget.setEnabled(True)

    def undo_translation(self):
        self.volume_img.translate(self.volume.shape[0]/2, self.volume.shape[1]/2, self.volume.shape[2]/2)

    def set_volume_to_center(self):
        self.volume_img.translate(-self.volume.shape[0]/2, -self.volume.shape[1]/2, -self.volume.shape[2]/2)

    def get_slices(self):
        reco_files = [f for f in sorted(os.listdir(str(self.ui.output_path_line.text()))) if f.endswith('.tif')]
        self.reco_absfiles = [str(self.ui.output_path_line.text()) + '/' + name for name in reco_files]
        self.changed_data = None

    def show_volume(self):
        self.step = 1
        self.percent = 1.0

        if self.scale_percent < 100:
            self.percent = self.scale_percent / 100.0
            self.calculate_image_step()

        test_arr = self.convert_tif_to_smaller_img(self.reco_absfiles[0])
        tif_width = test_arr.shape[1]
        tif_height = test_arr.shape[0]
        length = len(self.reco_absfiles) / self.step
        data = np.empty((tif_width, tif_height, length), dtype=np.float32)

        for i in range(0, len(self.reco_absfiles)-1, self.step):
            data[0:tif_width, 0:tif_height, (length-1) - i/self.step] = self.convert_tif_to_smaller_img(self.reco_absfiles[i])

        self.data_for_contrast = np.copy(data)
        self.change_gloptions()

        if self.ui.make_contrast_button.isChecked() == False:
            data += np.abs(data.min())
            data = data / data.max() * 255
            self.data = np.copy(data)
            self.volume = self.get_volume(data)

            self.change_gloptions()
            self.volume_img.setData(self.volume)
            self.volume_img.setGLOptions(self.options)
            self.volume_img.update()
            self.data_max = int(data.max())
            self.data_min = int(data.min())
            self.ui.volume_min_slider.setMinimum(self.data_min)
            self.ui.volume_min_slider.setMinimum(self.data_min)
            self.ui.volume_max_slider.setMaximum(self.data_max)
            self.ui.volume_max_slider.setMaximum(self.data_max)

            if self.ui.crop_circle_box.isChecked():
                self.ui.volume_min_slider.setValue(self.volume_min_slider_pos)
                self.ui.volume_max_slider.setValue(self.volume_max_slider_pos)
                self.on_volume_sliders()
            else:
                self.ui.volume_min_slider.setValue(self.data_min)
                self.ui.volume_max_slider.setValue(self.data_max)
        else:
            self.on_make_contrast(self.data_for_contrast)

        if self.ui.reco_volume_widget.isVisible() == False:
            self.ui.reco_volume_widget.setVisible(True)
            self.ui.volume_params.setVisible(False)
            self.ui.resize(1500, 900)

        self.output = "old"

    def get_volume(self, data):
        volume = np.empty(data.shape + (4, ), dtype=np.ubyte)
        volume[..., 0] = data
        volume[..., 1] = data
        volume[..., 2] = data
        volume[..., 3] = ((volume[..., 0]*0.3 + volume[..., 1]*0.3).astype(float)/255.) **2 *255
        return volume

    def on_make_contrast(self, data):
        _enable_wait_cursor()
        if self.ui.make_contrast_button.isChecked():
            np.seterr(divide='ignore')
            negative = np.log(np.clip(-self.data_for_contrast, 0, -self.data_for_contrast.min())**2)
            np.seterr(divide='warn')
            volume = np.empty(self.data_for_contrast.shape + (4, ), dtype=np.ubyte)
            volume[..., 0] = negative * (255./negative.max())
            volume[..., 1] = negative * (255./negative.max())
            volume[..., 2] = negative * (255./negative.max())
            volume[..., 3] = ((volume[..., 0]*0.3 + volume[..., 1]*0.3).astype(float)/255.) **2 *255
            self.volume_img.setData(volume)
            self.volume_img.update()
            self.ui.volume_slider_widget.setVisible(False)
        else:
            self.volume_img.setData(self.volume)
            self.volume_img.update()
            self.ui.volume_slider_widget.setVisible(True)
        _disable_wait_cursor()

    def update_volume(self):
        _enable_wait_cursor()
        self.ui.centralWidget.setEnabled(False)
        self.repaint()
        self.app.processEvents()
        if self.output == "new":
            self.undo_translation()
            self.get_slices()
            try:
                self.show_volume()
                self.set_volume_to_center()
            except ValueError as verror:
                LOG.debug(str(verror))
                log.seek(0)
                logtxt = open(log.name).read()
                self.ui.text_browser.setPlainText(logtxt)

        else:
            pos_min = self.ui.volume_min_slider.value()
            pos_max = self.ui.volume_max_slider.value()
            if (int(self.percent * 100)) is not self.ui.percent_box2.value():
                if self.ui.make_contrast_button.isChecked():
                    self.ui.make_contrast_button.setChecked(False)
                    self.on_make_contrast(None)
                    self.undo_translation()
                    self.show_volume()
                    self.set_volume_to_center()
                    self.ui.make_contrast_button.setChecked(True)
                    self.on_make_contrast(self.data_for_contrast)
                else:
                    self.undo_translation()
                    self.show_volume()
                    self.set_volume_to_center()
            self.ui.volume_min_slider.setValue(pos_min)
            self.ui.volume_max_slider.setValue(pos_max)
            self.on_volume_sliders()

        _disable_wait_cursor()
        self.ui.centralWidget.setEnabled(True)

    def calculate_image_step(self):
        images = len(self.reco_absfiles)
        self.step = float(images) / (self.scale_percent * images / 100.0)
        self.step = int(np.round(self.step))

    def convert_tif_to_smaller_img(self, tif_file):
        tif = tifffile.TiffFile(tif_file)
        array = tif.asarray()

        if self.scale_percent < 100:
            array = array[::self.step, ::self.step]

        if self.ui.crop_circle_box.isChecked():
            lx, ly = array.shape
            X, Y = np.ogrid[0:lx, 0:ly]
            mask = (X - lx / 2) ** 2 + (Y - ly / 2) ** 2 > lx * ly / self.radius
            circle_array = np.copy(array)
            circle_array[mask] = 0.0
            array = circle_array

        return array

    def on_crop_circle(self):
        if self.ui.crop_circle_box.isChecked():
            _enable_wait_cursor()
            self.radius = 4
            self.show_volume()
            self.ui.crop_more_button.setEnabled(True)
            self.ui.crop_less_button.setEnabled(True)
            _disable_wait_cursor()
        else:
            _enable_wait_cursor()
            self.show_volume()
            self.ui.crop_more_button.setEnabled(False)
            self.ui.crop_less_button.setEnabled(False)
            self.ui.volume_min_slider.setValue(self.volume_min_slider_pos)
            self.ui.volume_max_slider.setValue(self.volume_max_slider_pos)
            self.on_volume_sliders()
            if self.ui.make_contrast_button.isChecked():
                self.on_make_contrast(self.data_for_contrast)
            _disable_wait_cursor()

    def on_crop_more_circle(self):
        _enable_wait_cursor()
        self.radius += 1
        self.show_volume()
        _disable_wait_cursor()

    def on_crop_less_circle(self):
        if self.radius > 4:
            _enable_wait_cursor()
            self.radius -= 1
            self.show_volume()
            _disable_wait_cursor()

    def change_gloptions(self):
        if self.ui.volume_params.isVisible() == True:
            self.options = str(self.ui.gloptions.currentText())
        else:
            self.options = str(self.ui.gloptions2.currentText())
            self.volume_img.setGLOptions(self.options)
            self.volume_img.update()

    def on_volume_sliders(self):
        _enable_wait_cursor()
        self.changed_data = np.copy(self.data)
        self.changed_data[self.changed_data < self.ui.volume_min_slider.value()] = 0
        self.changed_data[self.changed_data > self.ui.volume_max_slider.value()] = 0
        volume = self.get_volume(self.changed_data)
        self.volume_img.setData(volume)
        self.volume_img.update()
        _disable_wait_cursor()
        self.volume_min_slider_pos = self.ui.volume_min_slider.value()
        self.volume_max_slider_pos = self.ui.volume_max_slider.value()

    def on_percent_box(self):
        self.ui.percent_box2.setValue(self.ui.percent_box.value())
        self.scale_percent = self.ui.percent_box.value()

    def on_percent_box2(self):
        self.ui.percent_box.setValue(self.ui.percent_box.value())
        self.scale_percent = self.ui.percent_box2.value()

    def on_hide_reco_images(self):
        if self.ui.show_reco_images_box.isChecked() == False:
            self.ui.reco_images_widget.setVisible(False)
        else:
            self.ui.show_volume_box.setChecked(False)
            self.ui.volume_params.setVisible(False)
            self.ui.reco_volume_widget.setVisible(False)

        if self.ui.tab_widget.currentIndex() == 0 and self.ui.reco_volume_widget.isVisible() == False and self.ui.reco_images_widget.isVisible() == False:
            self.ui.resize(585, 825)

    def on_hide_volume(self):
        if self.ui.show_volume_box.isChecked() == False:
            self.ui.reco_volume_widget.setVisible(False)
            self.ui.volume_params.setVisible(False)
        else:
            self.ui.show_reco_images_box.setChecked(False)
            self.ui.reco_images_widget.setVisible(False)
            self.ui.volume_params.setVisible(True)

        if self.ui.tab_widget.currentIndex() == 0 and self.ui.reco_volume_widget.isVisible() == False and self.ui.reco_images_widget.isVisible() == False:
            self.ui.resize(585, 825)

    def on_run(self):
        _enable_wait_cursor()
        if self.viewbox == False:
            self.viewbox = pg.ViewBox()
            self.histogram = pg.HistogramLUTWidget()
            self.w_over = pg.GraphicsView()
            self.w_over.setCentralItem(self.viewbox)
            self.ui.axis_view_layout.addWidget(self.w_over, 0, 0)
            self.ui.axis_view_layout.addWidget(self.histogram, 0, 1)

        self.extrema_checkbox.setChecked(False)
        self.extrema_checkbox.setEnabled(True)
        try:
            self.read_data()
            self.compute_axis()
            if self.axis_view_widget.isVisible() == False:
                self.axis_view_widget.setVisible(True)
                self.axis_options.setVisible(True)
                self.ui.resize(1500, 900)

        except Exception as e:
            _disable_wait_cursor()
            QtGui.QMessageBox.warning(self, "Warning", str(e))

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
        self.ui.axis_num.setText('center of rotation = %i px' % (self.axis))
        self.ui.img_size.setText('width = %i | height = %i' % (self.img_width, self.img_height))
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

        elif self.ui.tab_widget.currentIndex() == 1 and self.ui.axis_view_widget.isVisible() == True:
            delta = event.delta()
            wheel += (delta and delta // abs(delta))
            self.ui.axis_slider.setValue(self.ui.axis_slider.value() - wheel)

        elif self.ui.tab_widget.currentIndex() == 2 and self.ui.phgen_images_widget.isVisible() == True:
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
        if self.ui.extrema_checkbox.isChecked():
            self.original_flip = np.copy(self.arr_flip)
            self.original_arr_180 = np.copy(self.arr_180)

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

        else:
            self.arr_flip = self.original_flip
            self.arr_180 = self.original_arr_180
            self.update_image()

    def on_phantom_generator(self):
        self.phantom = ''
        self.sino = ''
        if self.ui.generate_phantom.isChecked():
            self.phantom = '-p '
        if self.ui.generate_sinogram.isChecked():
            self.sino = '-s '
        self.ph_width = '-w ' + str(self.ui.phgen_width.value())
        self.height = ' -h ' + str(self.ui.phgen_height.value())

    def on_generate_phantom(self):
        if self.ui.generate_phantom.isChecked():
            self.phantom = '-p '
        else:
            self.phantom = ''
            self.sino = '-s '
            self.ui.generate_sinogram.setChecked(True)

    def on_generate_sinogram(self):
        if self.ui.generate_sinogram.isChecked():
            self.sino = '-s '
        else:
            self.sino = ''
            self.phantom = '-p '
            self.ui.generate_phantom.setChecked(True)

    def on_phgen_width_changed(self):
        self.ph_width = '-w ' + str(self.ui.phgen_width.value())

    def on_phgen_height_changed(self):
        self.height = ' -h ' + str(self.ui.phgen_height.value())

    def on_generate(self):
        _enable_wait_cursor()
        run_phgen = "generate " + str(self.sino) + str(self.phantom) + str(self.ph_width) + str(self.height)
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
        self.ui.phgen_images_layout.addWidget(self.phgen_graphics_view, 0, 0)
        self.ui.phgen_images_layout.addWidget(self.phgen_histogram, 0, 1)
        self.update_phgen_images()

    def update_phgen_images(self):
        try:
            self.phgen_files = [f for f in sorted(os.listdir(os.getcwd())) if f.endswith('.tif')]
            self.ui.phgen_slider.setMaximum(len(self.phgen_files) - 1)
            self.move_phgen_slider()

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
