import sys
import os
import fabio
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
logging.getLogger('fabioutils').disabled = True
logging.getLogger('edfimage').disabled = True
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
        self.ui.axis_view_widget.setVisible(False)
        self.ui.axis_options.setVisible(False)
        self.ui.volume_params.setVisible(False)
        self.reco_images_layout = False
        self.volume_layout = False
        self.viewbox = False
        self.ext = tuple([".tif", ".edf"])
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
        self.ui.ip_box.setToolTip('Interpolate between two sets of flat fields')
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
        self.ui.show_2d_box.clicked.connect(self.on_hide_reco_images)
        self.ui.show_3d_box.clicked.connect(self.on_hide_volume)
        self.ui.percent_box.valueChanged.connect(self.on_percent_box)
        self.ui.percent_box2.valueChanged.connect(self.on_percent_box2)
        self.ui.volume_min_slider.valueChanged.connect(self.on_volume_sliders)
        self.ui.volume_max_slider.valueChanged.connect(self.on_volume_sliders)
        self.ui.crop_circle_box.clicked.connect(self.on_crop_circle)
        self.ui.crop_more_button.clicked.connect(self.on_crop_more_circle)
        self.ui.crop_less_button.clicked.connect(self.on_crop_less_circle)
        self.ui.make_contrast_button.clicked.connect(self.show_volume)
        self.ui.show_slices_button.clicked.connect(self.show_slices)
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
        self.ui.show_2d_box.clicked.connect(lambda value: self.change_value('show_2d', self.ui.show_2d_box.isChecked()))
        self.ui.show_3d_box.clicked.connect(lambda value: self.change_value('show_3d', self.ui.show_3d_box.isChecked()))

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

        if self.params.flats2 and self.proj_button.isChecked():
            self.ui.ip_box.setChecked(True)
        else:
            self.ui.ip_box.setChecked(False)
        self.on_ip_box_clicked()

        if self.params.reduction_mode.lower() == "average":
            self.ui.ffc_options.setCurrentIndex(0)
        else:
            self.ui.ffc_options.setCurrentIndex(1)

        if self.params.show_2d == "True":
            self.ui.show_2d_box.setChecked(True)
            self.params.show_2d = True
        else:
            self.ui.show_2d_box.setChecked(False)
            self.params.show_2d = False

        if self.params.show_3d == "True":
            self.ui.show_3d_box.setChecked(True)
            self.params.show_3d = True
            self.ui.volume_params.setVisible(True)
        else:
            self.ui.show_3d_box.setChecked(False)
            self.params.show_3d = False

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
                if find_file.endswith('.tif'):
                    crop_file = tifffile.TiffFile(find_file)
                    crop_arr = crop_file.asarray()
                    self.params.crop_width = crop_width = crop_arr.shape[1]
                else:
                    edf = fabio.edfimage.edfimage()
                    edf_cropfile = edf.read(find_file)
                    self.params.crop_width = int(edf_cropfile.header['Dim_1'])
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
        self.new_output = True

    def on_clear_output_dir_clicked(self):
        output_files = [f for f in os.listdir(str(self.ui.output_path_line.text())) if f.endswith(self.ext)]
        output_absfiles = [str(self.ui.output_path_line.text()) + '/' + name for name in output_files]
        for f in output_absfiles:
            os.remove(f)
        self.ui.reco_slider.setEnabled(False)

    def on_ffc_box_clicked(self):
        self.params.ffc_correction = self.ui.ffc_box.isChecked()
        self.ui.ffc_correction.setVisible(self.ui.ffc_box.isChecked())
        if self.ui.ffc_box.isChecked() == False:
            self.ip_box.setChecked(False)
            self.ui.ip_correction.setVisible(False)

    def on_ip_box_clicked(self):
        self.ui.ip_correction.setVisible(self.ui.ip_box.isChecked())
        if self.ui.ip_box.isChecked():
            self.ui.ffc_box.setChecked(True)
            self.params.ffc_correction = True
            self.ui.ffc_correction.setVisible(True)

    def change_ffc_options(self):
        self.params.reduction_mode = str(self.ui.ffc_options.currentText()).lower()

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
        self.ui.axis_view_widget.setVisible(False)
        self.ui.volume_params.setVisible(False)
        self.ui.axis_options.setVisible(False)
        self.on_tab_changed()

        self.ui.input_path_line.setText('.')
        self.ui.output_path_line.setText('.')
        self.ui.darks_path_line.setText('.')
        self.ui.flats_path_line.setText('.')
        self.ui.flats2_path_line.setText('.')
        self.ui.path_line_0.setText('.')
        self.ui.path_line_180.setText('.')

        self.ui.show_2d_box.setChecked(False)
        self.ui.show_3d_box.setchecked(False)
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
        self.params.reduction_mode = "average"
        self.params.crop_width = None
        self.params.show_2d = False
        self.params.show_3d = False
        self.params.angle = None
        self.params.axis = None
        self.on_region_box_clicked()
        self.on_ffc_box_clicked()
        self.on_ip_box_clicked()

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

        # TODO: Make this an option
        self.params.fix_nan_and_inf = True

        if self.ui.ip_box.isChecked():
            self.params.flats2 = self.ui.flats2_path_line.text()
        else:
            self.params.flats2 = ''

        if self.params.ffc_correction:
           flats_files = [f for f in os.listdir(str(self.ui.flats_path_line.text())) if f.endswith(self.ext)]
           self.params.num_flats = len(flats_files)
        else:
           self.params.num_flats = 0

        if self.ui.add_params.isChecked() == False and self.params.method == "dfi":
            self.params.oversampling = None
        elif self.ui.add_params.isChecked() and self.params.method == "dfi":
            self.params.oversampling = self.ui.oversampling.value()

        if self.params.method == "sart":
            input_images = [f for f in os.listdir(str(self.ui.input_path_line.text())) if f.endswith(self.ext)]
            if self.params.from_projections:
                self.params.num_angles = len(input_images)
            else:
                abs_sino = str(self.ui.input_path_line.text()) + '/' + str(input_images[0])
                if abs_sino.endswith('.tif'):
                    tif = tifffile.TiffFile(abs_sino)
                    array = tif.asarray()
                    self.params.num_angles = array.shape[0]
                else:
                    edf = fabio.edfimage.edfimage()
                    edf_sino = edf.read(abs_sino)
                    self.params.num_angles = int(edf_sino.header['Dim_2'])

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
                self.show_slices()

            except Exception as e:
                QtGui.QMessageBox.warning(self, "Warning", str(e))

        _disable_wait_cursor()
        self.ui.centralWidget.setEnabled(True)
        self.params.angle = self.ui.angle_step.value()

        log.seek(0)
        logtxt = open(log.name).read()
        self.ui.text_browser.setPlainText(logtxt)
        self.ui.text_browser.setLineWrapMode(QtGui.QTextEdit.NoWrap)

    def show_slices(self):
        if self.ui.show_2d_box.isChecked():
            if self.reco_images_layout == False:
                self.make_reco_layout()
            else:
                self.show_reco_images()

        elif self.ui.show_3d_box.isChecked():
            if self.volume_layout == False:
                self.make_volume_layout()
            else:
                self.show_volume()

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
        reco_files = [f for f in sorted(os.listdir(str(self.ui.output_path_line.text()))) if f.endswith(self.ext)]
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
        self.new_output = False
        self.scale_percent = self.ui.percent_box.value()
        self.reco_volume_view = gl.GLViewWidget()
        self.volume_img = None

        self.ui.volume_image.addWidget(self.reco_volume_view, 0, 0)
        self.get_slices()
        try:
            self.scale_data()
            self.show_volume()
        except ValueError as verror:
            LOG.debug(str(verror))
            log.seek(0)
            logtxt = open(log.name).read()
            self.ui.text_browser.setPlainText(logtxt)
            self.ui.text_browser.setLineWrapMode(QtGui.QTextEdit.NoWrap)

        _disable_wait_cursor()
        self.ui.centralWidget.setEnabled(True)

    def set_volume_to_center(self, volume_img, volume):
        volume_img.translate(-volume.shape[0]/2, -volume.shape[1]/2, -volume.shape[2]/2)

    def get_slices(self):
        reco_files = [f for f in sorted(os.listdir(str(self.ui.output_path_line.text()))) if f.endswith(self.ext)]
        self.reco_absfiles = [str(self.ui.output_path_line.text()) + '/' + name for name in reco_files]

    def scale_data(self):
        self.step = 1
        self.percent = 1.0

        if self.scale_percent < 100:
            self.percent = self.scale_percent / 100.0
            self.calculate_image_step()

        arr = self.convert_tif_to_smaller_img(self.reco_absfiles[0])
        self.len = len(self.reco_absfiles) / self.step
        self.scaled_data = np.empty((arr.shape[0], arr.shape[1], self.len), dtype=np.float32)

        for i in range(0, len(self.reco_absfiles)-1, self.step):
            self.scaled_data[0:arr.shape[0], 0:arr.shape[1], (self.len-1) - i/self.step] = self.convert_tif_to_smaller_img(self.reco_absfiles[i])

    def show_volume(self):
        _enable_wait_cursor()
        self.ui.centralWidget.setEnabled(False)
        self.repaint()
        self.app.processEvents()

        if self.new_output:
            self.get_slices()
            self.scale_data()

        if self.ui.volume_params.isVisible():
            self.scale_percent = self.ui.percent_box.value()
            self.ui.percent_box2.setValue(self.scale_percent)
        else:
            self.scale_percent = self.ui.percent_box2.value()

        if (int(self.percent * 100)) is not self.scale_percent:
            self.scale_data()

        data = np.copy(self.scaled_data)

        if self.ui.crop_circle_box.isChecked():
            lx = data.shape[0]
            ly = data.shape[1]
            X, Y = np.ogrid[0:lx, 0:ly]
            mask = (X - lx / 2) ** 2 + (Y - ly / 2) ** 2 > lx * ly / self.radius
            circle_array = np.copy(data)
            circle_array[mask] = 0.0
            data = circle_array

        if self.ui.make_contrast_button.isChecked():
            np.seterr(divide='ignore')
            negative = np.log(np.clip(-data, 0, -data.min())**2)
            np.seterr(divide='warn')
            data = negative * (255./negative.max())
            self.data_for_slider = np.copy(data)
            self.volume = self.get_volume(data)
            self.ui.volume_slider_widget.setVisible(False)
        else:
            data += np.abs(data.min())
            data = data / data.max() * 255
            self.data_for_slider = np.copy(data)
            self.volume = self.get_volume(data)
            self.ui.volume_slider_widget.setVisible(True)
            if self.ui.volume_min_slider.value() is not 0 or self.ui.volume_max_slider.value() is not 255:
                self.on_volume_sliders()

        if self.volume_img:
            self.volume_img = self.update_volume_img(self.volume_img, self.volume)
        else:
            self.volume_img = gl.GLVolumeItem(self.volume)
            self.reco_volume_view.addItem(self.volume_img)
            self.set_volume_to_center(self.volume_img, self.volume)

        if self.ui.reco_volume_widget.isVisible() == False:
            self.ui.reco_volume_widget.setVisible(True)
            self.ui.volume_params.setVisible(False)
            self.ui.resize(1500, 900)

        self.new_output = False
        _disable_wait_cursor()
        self.ui.centralWidget.setEnabled(True)

    def update_volume_img(self, old_volume_img, volume):
        new_volume_img = gl.GLVolumeItem(volume)
        self.reco_volume_view.removeItem(old_volume_img)
        self.reco_volume_view.addItem(new_volume_img)
        self.set_volume_to_center(new_volume_img, volume)
        return new_volume_img

    def calculate_image_step(self):
        images = len(self.reco_absfiles)
        self.step = float(images) / (self.scale_percent * images / 100.0)
        self.step = int(np.round(self.step))

    def convert_tif_to_smaller_img(self, tif_file):
        tif = tifffile.TiffFile(tif_file)
        array = tif.asarray()
        if self.scale_percent < 100:
            array = array[::self.step, ::self.step]
        return array

    def get_volume(self, data):
        volume = np.empty(data.shape + (4, ), dtype=np.ubyte)
        volume[..., 0] = data
        volume[..., 1] = data
        volume[..., 2] = data
        volume[..., 3] = ((volume[..., 0]*0.3 + volume[..., 1]*0.3).astype(float)/255.) **2 *255
        return volume

    def on_crop_circle(self):
        self.radius = 4
        self.ui.crop_more_button.setEnabled(True)
        self.ui.crop_less_button.setEnabled(True)
        self.show_volume()
        _disable_wait_cursor()

    def on_crop_more_circle(self):
        self.radius += 1
        self.show_volume()

    def on_crop_less_circle(self):
        if self.radius > 4:
            self.radius -= 1
            self.show_volume()

    def on_volume_sliders(self):
        _enable_wait_cursor()
        data = np.copy(self.data_for_slider)
        data[data < self.ui.volume_min_slider.value()] = 0
        data[data > self.ui.volume_max_slider.value()] = 0
        self.volume = self.get_volume(data)
        self.volume_img = self.update_volume_img(self.volume_img, self.volume)
        _disable_wait_cursor()

    def on_percent_box(self):
        self.ui.percent_box2.setValue(self.ui.percent_box.value())
        self.scale_percent = self.ui.percent_box.value()

    def on_percent_box2(self):
        self.ui.percent_box.setValue(self.ui.percent_box.value())
        self.scale_percent = self.ui.percent_box2.value()

    def on_hide_reco_images(self):
        if self.ui.show_2d_box.isChecked() == False:
            self.ui.reco_images_widget.setVisible(False)
        else:
            self.ui.show_3d_box.setChecked(False)
            self.ui.volume_params.setVisible(False)
            self.ui.reco_volume_widget.setVisible(False)
            self.params.show_3d = False

        if self.ui.tab_widget.currentIndex() == 0 and self.ui.reco_volume_widget.isVisible() == False and self.ui.reco_images_widget.isVisible() == False:
            self.ui.resize(585, 825)

    def on_hide_volume(self):
        if self.ui.show_3d_box.isChecked() == False:
            self.ui.reco_volume_widget.setVisible(False)
            self.ui.volume_params.setVisible(False)
        else:
            self.ui.show_2d_box.setChecked(False)
            self.ui.reco_images_widget.setVisible(False)
            self.ui.volume_params.setVisible(True)
            self.params.show_2d = False

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

def main(params):
    app = QtGui.QApplication(sys.argv)
    window = ApplicationWindow(app, params)
    sys.exit(app.exec_())
