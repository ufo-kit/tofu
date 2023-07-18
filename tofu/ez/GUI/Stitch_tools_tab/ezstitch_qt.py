import os
from PyQt5.QtWidgets import (
    QGroupBox,
    QPushButton,
    QCheckBox,
    QLabel,
    QLineEdit,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QRadioButton,
    QFileDialog,
    QMessageBox,
)
from shutil import rmtree
import logging
import getpass
import yaml
import tofu.ez.params as params
from tofu.ez.Helpers.stitch_funcs import main_sti_mp, main_conc_mp, main_360_mp_depth1
from tofu.ez.GUI.message_dialog import warning_message


LOG = logging.getLogger(__name__)

class EZStitchGroup(QGroupBox):
    def __init__(self):
        super().__init__()

        self.setTitle("EZ-STITCH")
        self.setToolTip("Reslicing and stitching tool")
        self.setStyleSheet('QGroupBox {color: purple;}')

        self.input_dir_button = QPushButton()
        self.input_dir_button.setText("Select input directory")
        self.input_dir_button.setToolTip("Normally contains a bunch of directories at the first depth level\n" \
                                "each of which has a subdirectory with the same name (second depth level). \n"
                                "Images with the same index in these second-level subdirectories will be stitched vertically.")
        self.input_dir_button.clicked.connect(self.input_button_pressed)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.editingFinished.connect(self.set_input_entry)

        self.tmp_dir_button = QPushButton()
        self.tmp_dir_button.setText("Select temporary directory")
        self.tmp_dir_button.clicked.connect(self.temp_button_pressed)

        self.tmp_dir_entry = QLineEdit()
        self.tmp_dir_entry.editingFinished.connect(self.set_temp_entry)

        self.output_dir_button = QPushButton()
        self.output_dir_button.setText("Directory to save stitched images")
        self.output_dir_button.clicked.connect(self.output_button_pressed)

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.editingFinished.connect(self.set_output_entry)

        self.types_of_images_label = QLabel()
        tmpstr = "Name of subdirectories which contain the same type of images in every directory in the input"
        self.types_of_images_label.setToolTip(tmpstr)
        self.types_of_images_label.setText("Name of subdirectory with the same type of images to stitch")
        self.types_of_images_label.setToolTip("e.g. sli, tomo, proj-pr, etc.")

        self.types_of_images_entry = QLineEdit()
        self.types_of_images_entry.setToolTip(tmpstr)
        self.types_of_images_entry.editingFinished.connect(self.set_type_images)

        self.orthogonal_checkbox = QCheckBox()
        self.orthogonal_checkbox.setText("Stitch orthogonal sections")
        self.orthogonal_checkbox.setToolTip("Will reslice images in every subdirectory and then stitch")
        self.orthogonal_checkbox.stateChanged.connect(self.set_stitch_checkbox)

        self.start_stop_step_label = QLabel()
        self.start_stop_step_label.setText("Which images to be stitched: start,stop,step:")
        self.start_stop_step_entry = QLineEdit()
        self.start_stop_step_entry.editingFinished.connect(self.set_start_stop_step)

        self.sample_moved_down_checkbox = QCheckBox()
        self.sample_moved_down_checkbox.setText("Flip images upside down before stitching")
        self.sample_moved_down_checkbox.stateChanged.connect(self.set_sample_moved_down)

        self.interpolate_regions_rButton = QRadioButton()
        self.interpolate_regions_rButton.setText("Interpolate overlapping regions and equalize intensity")
        self.interpolate_regions_rButton.clicked.connect(self.set_rButton)

        self.num_overlaps_label = QLabel()
        self.num_overlaps_label.setText("Number of overlapping rows")
        self.num_overlaps_entry = QLineEdit()
        self.num_overlaps_entry.editingFinished.connect(self.set_overlap)

        self.clip_histogram_checkbox = QCheckBox()
        self.clip_histogram_checkbox.setText("Clip histogram and convert slices to 8-bit before saving")
        self.clip_histogram_checkbox.stateChanged.connect(self.set_histogram_checkbox)

        self.min_value_label = QLabel()
        self.min_value_label.setText("Min value in 32-bit histogram")
        self.min_value_entry = QLineEdit()
        self.min_value_entry.editingFinished.connect(self.set_min_value)

        self.max_value_label = QLabel()
        self.max_value_label.setText("Max value in 32-bit histogram")
        self.max_value_entry = QLineEdit()
        self.max_value_entry.editingFinished.connect(self.set_max_value)

        self.concatenate_rButton = QRadioButton()
        self.concatenate_rButton.setText("Concatenate only")
        self.concatenate_rButton.clicked.connect(self.set_rButton)

        self.first_row_label = QLabel()
        self.first_row_label.setText("First row")
        self.first_row_entry = QLineEdit()
        self.first_row_entry.editingFinished.connect(self.set_first_row)

        self.last_row_label = QLabel()
        self.last_row_label.setText("Last row")
        self.last_row_entry = QLineEdit()
        self.last_row_entry.editingFinished.connect(self.set_last_row)

        self.half_acquisition_rButton = QRadioButton()
        self.half_acquisition_rButton.setText("Horizontal stitching of half-acq. mode data")
        self.half_acquisition_rButton.setToolTip("Applies to tif images in all depth-one subdirectories in the Input \n"
                                                 "unlike 360-MULTI-STITCH which search images at the depth two ")
        #self.half_acquisition_rButtonYfor a half-acqusition mode data (even number of tif files in the Input directory)")
        self.half_acquisition_rButton.clicked.connect(self.set_rButton)

        self.column_of_axis_label = QLabel()
        self.column_of_axis_label.setText("In which column the axis of rotation is")
        self.column_of_axis_entry = QLineEdit()
        self.column_of_axis_entry.editingFinished.connect(self.set_axis_column)

        self.help_button = QPushButton()
        self.help_button.setText("Help")
        self.help_button.clicked.connect(self.help_button_pressed)

        self.delete_button = QPushButton()
        self.delete_button.setText("Delete output dir")
        self.delete_button.clicked.connect(self.delete_button_pressed)

        self.stitch_button = QPushButton()
        self.stitch_button.setText("Stitch")
        self.stitch_button.clicked.connect(self.stitch_button_pressed)
        self.stitch_button.setStyleSheet("color:royalblue;font-weight:bold")

        self.import_parameters_button = QPushButton("Import Parameters from File")
        self.import_parameters_button.clicked.connect(self.import_parameters_button_pressed)

        self.save_parameters_button = QPushButton("Save Parameters to File")
        self.save_parameters_button.clicked.connect(self.save_parameters_button_pressed)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        vbox1 = QVBoxLayout()
        vbox1.addWidget(self.input_dir_button)
        vbox1.addWidget(self.input_dir_entry)
        vbox1.addWidget(self.tmp_dir_button)
        vbox1.addWidget(self.tmp_dir_entry)
        vbox1.addWidget(self.output_dir_button)
        vbox1.addWidget(self.output_dir_entry)
        layout.addItem(vbox1, 0, 0)

        grid = QGridLayout()
        grid.addWidget(self.types_of_images_label, 0, 0)
        grid.addWidget(self.types_of_images_entry, 0, 1)
        grid.addWidget(self.orthogonal_checkbox, 1, 0, 1, 2)
        grid.addWidget(self.start_stop_step_label, 2, 0)
        grid.addWidget(self.start_stop_step_entry, 2, 1)
        grid.addWidget(self.sample_moved_down_checkbox, 3, 0)
        grid.addWidget(self.interpolate_regions_rButton, 4, 0, 1, 2)
        grid.addWidget(self.num_overlaps_label, 5, 0)
        grid.addWidget(self.num_overlaps_entry, 5, 1)
        grid.addWidget(self.clip_histogram_checkbox, 6, 0)
        grid.addWidget(self.min_value_label, 7, 0)
        grid.addWidget(self.min_value_entry, 7, 1)
        grid.addWidget(self.max_value_label, 8, 0)
        grid.addWidget(self.max_value_entry, 8, 1)
        layout.addItem(grid, 1, 0)

        grid2 = QGridLayout()
        grid2.addWidget(self.concatenate_rButton, 0, 0, 1, 2)
        grid2.addWidget(self.first_row_label, 1, 0)
        grid2.addWidget(self.first_row_entry, 1, 1)
        grid2.addWidget(self.last_row_label, 1, 2)
        grid2.addWidget(self.last_row_entry, 1, 3)
        layout.addItem(grid2, 2, 0)

        grid3 = QGridLayout()
        grid3.addWidget(self.half_acquisition_rButton, 0, 0, 1, 2)
        grid3.addWidget(self.column_of_axis_label, 1, 0)
        grid3.addWidget(self.column_of_axis_entry, 1, 1)
        layout.addItem(grid3, 3, 0)

        grid4 = QGridLayout()
        grid4.addWidget(self.help_button, 0, 0)
        grid4.addWidget(self.delete_button, 0, 1)
        grid4.addWidget(self.stitch_button, 0, 2)
        grid4.addWidget(self.import_parameters_button, 1, 0, 1, 2)
        grid4.addWidget(self.save_parameters_button, 1, 2)
        layout.addItem(grid4, 4, 0)

        self.setLayout(layout)

    def init_values(self):
        self.parameters = {'parameters_type': 'ez_stitch'}
        self.parameters['ezstitch_input_dir'] = os.path.expanduser('~')
        self.input_dir_entry.setText(self.parameters['ezstitch_input_dir'])
        self.parameters['ezstitch_temp_dir'] = os.path.join(
                        os.path.expanduser('~'), "tmp-ezstitch")
        self.tmp_dir_entry.setText(self.parameters['ezstitch_temp_dir'])
        self.parameters['ezstitch_output_dir'] = os.path.join(
                        os.path.expanduser('~'), "ezufo-stitched-images")
        self.output_dir_entry.setText(self.parameters['ezstitch_output_dir'])
        self.parameters['ezstitch_type_image'] = "sli"
        self.types_of_images_entry.setText(self.parameters['ezstitch_type_image'])
        self.parameters['ezstitch_stitch_orthogonal'] = True
        self.orthogonal_checkbox.setChecked(self.parameters['ezstitch_stitch_orthogonal'])
        self.parameters['ezstitch_start_stop_step'] = "200,2000,200"
        self.start_stop_step_entry.setText(self.parameters['ezstitch_start_stop_step'])
        self.parameters['ezstitch_sample_moved_down'] = False
        self.sample_moved_down_checkbox.setChecked(self.parameters['ezstitch_sample_moved_down'])
        self.parameters['ezstitch_stitch_type'] = 0
        self.interpolate_regions_rButton.setChecked(True)
        self.concatenate_rButton.setChecked(False)
        self.half_acquisition_rButton.setChecked(False)
        self.parameters['ezstitch_num_overlap_rows'] = 60
        self.num_overlaps_entry.setText(str(self.parameters['ezstitch_num_overlap_rows']))
        self.parameters['ezstitch_clip_histo'] = False
        self.clip_histogram_checkbox.setChecked(self.parameters['ezstitch_clip_histo'])
        self.parameters['ezstitch_histo_min'] = -0.0003
        self.min_value_entry.setText(str(self.parameters['ezstitch_histo_min']))
        self.parameters['ezstitch_histo_max'] = 0.0002
        self.max_value_entry.setText(str(self.parameters['ezstitch_histo_max']))
        self.parameters['ezstitch_first_row'] = 40
        self.first_row_entry.setText(str(self.parameters['ezstitch_first_row']))
        self.parameters['ezstitch_last_row'] = 440
        self.last_row_entry.setText(str(self.parameters['ezstitch_last_row']))
        self.parameters['ezstitch_axis_of_rotation'] = 245
        self.column_of_axis_entry.setText(str(self.parameters['ezstitch_axis_of_rotation']))

    def update_parameters(self, new_parameters):
        LOG.debug("Update parameters")
        if new_parameters['parameters_type'] != 'ez_stitch':
            print("Error: Invalid parameter file type: " + str(new_parameters['parameters_type']))
            return -1
        # Update parameters dictionary (which is passed to auto_stitch_funcs)
        self.parameters = new_parameters
        # Update displayed parameters for GUI
        self.input_dir_entry.setText(self.parameters['ezstitch_input_dir'])
        self.tmp_dir_entry.setText(self.parameters['ezstitch_temp_dir'])
        self.output_dir_entry.setText(self.parameters['ezstitch_output_dir'])
        self.types_of_images_entry.setText(self.parameters['ezstitch_type_image'])
        self.orthogonal_checkbox.setChecked(self.parameters['ezstitch_stitch_orthogonal'])
        self.start_stop_step_entry.setText(self.parameters['ezstitch_start_stop_step'])
        self.sample_moved_down_checkbox.setChecked(self.parameters['ezstitch_sample_moved_down'])

        if self.parameters['ezstitch_stitch_type'] == 0:
            self.interpolate_regions_rButton.setChecked(True)
        elif self.parameters['ezstitch_stitch_type'] == 1:
            self.concatenate_rButton.setChecked(True)
        elif self.parameters['ezstitch_stitch_type'] == 2:
            self.half_acquisition_rButton.setChecked(True)

        self.num_overlaps_entry.setText(str(self.parameters['ezstitch_num_overlap_rows']))
        self.clip_histogram_checkbox.setChecked(self.parameters['ezstitch_clip_histo'])
        self.min_value_entry.setText(str(self.parameters['ezstitch_histo_min']))
        self.max_value_entry.setText(str(self.parameters['ezstitch_histo_max']))
        self.first_row_entry.setText(str(self.parameters['ezstitch_first_row']))
        self.last_row_entry.setText(str(self.parameters['ezstitch_last_row']))
        self.column_of_axis_entry.setText(str(self.parameters['ezstitch_axis_of_rotation']))

    def set_rButton(self):
        if self.interpolate_regions_rButton.isChecked():
            LOG.debug("Interpolate regions")
            self.parameters['ezstitch_stitch_type'] = 0
        elif self.concatenate_rButton.isChecked():
            LOG.debug("Concatenate only")
            self.parameters['ezstitch_stitch_type'] = 1
        elif self.half_acquisition_rButton.isChecked():
            LOG.debug("Half-acquisition mode")
            self.parameters['ezstitch_stitch_type'] = 2

    def input_button_pressed(self):
        LOG.debug("Input button pressed")
        dir_explore = QFileDialog(self)
        self.parameters['ezstitch_input_dir'] = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(self.parameters['ezstitch_input_dir'])

    def set_input_entry(self):
        LOG.debug("Input: " + str(self.input_dir_entry.text()))
        self.parameters['ezstitch_input_dir'] = str(self.input_dir_entry.text())

    def temp_button_pressed(self):
        LOG.debug("Temp button pressed")
        dir_explore = QFileDialog(self)
        self.parameters['ezstitch_temp_dir'] = dir_explore.getExistingDirectory()
        self.tmp_dir_entry.setText(self.parameters['ezstitch_temp_dir'])

    def set_temp_entry(self):
        LOG.debug("Temp: " + str(self.tmp_dir_entry.text()))
        self.parameters['ezstitch_temp_dir'] = str(self.tmp_dir_entry.text())

    def output_button_pressed(self):
        LOG.debug("Output button pressed")
        dir_explore = QFileDialog(self)
        self.parameters['ezstitch_output_dir'] = dir_explore.getExistingDirectory()
        self.output_dir_entry.setText(self.parameters['ezstitch_output_dir'])

    def set_output_entry(self):
        LOG.debug("Output: " + str(self.output_dir_entry.text()))
        self.parameters['ezstitch_output_dir'] = str(self.output_dir_entry.text())

    def set_type_images(self):
        LOG.debug("Type of images: " + str(self.types_of_images_entry.text()))
        self.parameters['ezstitch_type_image'] = str(self.types_of_images_entry.text())

    def set_stitch_checkbox(self):
        LOG.debug("Stitch orthogonal: " + str(self.orthogonal_checkbox.isChecked()))
        self.parameters['ezstitch_stitch_orthogonal'] = bool(self.orthogonal_checkbox.isChecked())

    def set_start_stop_step(self):
        LOG.debug("Images to be stitched: " + str(self.start_stop_step_entry.text()))
        self.parameters['ezstitch_start_stop_step'] = str(self.start_stop_step_entry.text())

    def set_sample_moved_down(self):
        LOG.debug("Sample moved down: " + str(self.sample_moved_down_checkbox.isChecked()))
        self.parameters['ezstitch_sample_moved_down'] = bool(self.sample_moved_down_checkbox.isChecked())

    def set_overlap(self):
        LOG.debug("Num overlapping rows: " + str(self.num_overlaps_entry.text()))
        self.parameters['ezstitch_num_overlap_rows'] = int(self.num_overlaps_entry.text())

    def set_histogram_checkbox(self):
        LOG.debug("Clip histogram:  " + str(self.clip_histogram_checkbox.isChecked()))
        self.parameters['ezstitch_clip_histo'] = bool(self.clip_histogram_checkbox.isChecked())

    def set_min_value(self):
        LOG.debug("Min value: " + str(self.min_value_entry.text()))
        self.parameters['ezstitch_histo_min'] = float(self.min_value_entry.text())

    def set_max_value(self):
        LOG.debug("Max value: " + str(self.max_value_entry.text()))
        self.parameters['ezstitch_histo_max'] = float(self.max_value_entry.text())

    def set_first_row(self):
        LOG.debug("First row: " + str(self.first_row_entry.text()))
        self.parameters['ezstitch_first_row'] = int(self.first_row_entry.text())

    def set_last_row(self):
        LOG.debug("Last row: " + str(self.last_row_entry.text()))
        self.parameters['ezstitch_last_row'] = int(self.last_row_entry.text())

    def set_axis_column(self):
        LOG.debug("Column of axis: " + str(self.column_of_axis_entry.text()))
        self.parameters['ezstitch_axis_of_rotation'] = int(self.column_of_axis_entry.text())

    def help_button_pressed(self):
        LOG.debug("Help button pressed")
        h = "Stitches images vertically\n"
        h += "Directory structure is, f.i., Input/000, Input/001,...Input/00N\n"
        h += "Each 000, 001, ... 00N directory must have identical subdirectory \"Type\"\n"
        h += "Selected range of images from \"Type\" directory will be stitched vertically\n"
        h += "across all subdirectories in the Input directory"
        h += "to be added as options:\n"
        h += "(1) orthogonal reslicing, (2) interpolation, (3) horizontal stitching"
        QMessageBox.information(self, "Help", h)

    def delete_button_pressed(self):
        LOG.debug("Delete button pressed")
        # if os.path.exists(self.parameters['ezstitch_output_dir']):
        #     os.system('rm -r {}'.format(self.parameters['ezstitch_output_dir']))
        #     print(" - Directory with reconstructed data was removed")
        if os.path.exists(self.parameters['ezstitch_output_dir']):
            qm = QMessageBox()
            rep = qm.question(self, '', f"{self.parameters['ezstitch_output_dir']} \n"
                                        "will be removed. Continue?", qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(self.parameters['ezstitch_output_dir'])
                except:
                    warning_message('Error while deleting directory')
                    return
            else:
                return

    def stitch_button_pressed(self):
        LOG.debug("Stitch button pressed")

        if os.path.exists(self.parameters['ezstitch_temp_dir']) and \
                len(os.listdir(self.parameters['ezstitch_temp_dir'])) > 0:
            qm = QMessageBox()
            rep = qm.question(self, '', "Temporary dir is not empty. Is it safe to delete it?", qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(self.parameters['ezstitch_temp_dir'])
                except:
                    warning_message('Error while deleting directory')
                    return
            else:
                return
        if os.path.exists(self.parameters['ezstitch_output_dir']) and \
                len(os.listdir(self.parameters['ezstitch_output_dir'])) > 0:
            qm = QMessageBox()
            rep = qm.question(self, '', "Output dir is not empty. Is it safe to delete it?", qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(self.parameters['ezstitch_output_dir'])
                except:
                    warning_message('Error while deleting directory')
                    return
            else:
                return

        print("======= Begin Stitching =======")
        # Interpolate overlapping regions and equalize intensity
        if self.parameters['ezstitch_stitch_type'] == 0:
            main_sti_mp(self.parameters)
        # Concatenate only
        elif self.parameters['ezstitch_stitch_type'] == 1:
            main_conc_mp(self.parameters)
        # Half acquisition mode
        elif self.parameters['ezstitch_stitch_type'] == 2:
            main_360_mp_depth1(self.parameters['ezstitch_input_dir'],
                               self.parameters['ezstitch_output_dir'],
                               self.parameters['ezstitch_axis_of_rotation'], 0)
        if os.path.isdir(self.parameters['ezstitch_output_dir']):
            params_file_path = os.path.join(self.parameters['ezstitch_output_dir'], 'ezmview_params.yaml')
            params.save_parameters(self.parameters, params_file_path)
        print("==== Waiting for Next Task ====")

    def import_parameters_button_pressed(self):
        LOG.debug("Import params button clicked")
        dir_explore = QFileDialog(self)
        params_file_path = dir_explore.getOpenFileName(filter="*.yaml")
        try:
            file_in = open(params_file_path[0], 'r')
            new_parameters = yaml.load(file_in, Loader=yaml.FullLoader)
            if self.update_parameters(new_parameters) == 0:
                print("Parameters file loaded from: " + str(params_file_path[0]))
        except FileNotFoundError:
            print("You need to select a valid input file")

    def save_parameters_button_pressed(self):
        LOG.debug("Save params button clicked")
        dir_explore = QFileDialog(self)
        params_file_path = dir_explore.getSaveFileName(filter="*.yaml")
        garbage, file_name = os.path.split(params_file_path[0])
        file_extension = os.path.splitext(file_name)
        # If the user doesn't enter the .yaml extension then append it to filepath
        if file_extension[-1] == "":
            file_path = params_file_path[0] + ".yaml"
        else:
            file_path = params_file_path[0]
        try:
            file_out = open(file_path, 'w')
            yaml.dump(self.parameters, file_out)
            print("Parameters file saved at: " + str(file_path))
        except FileNotFoundError:
            print("You need to select a directory and use a valid file name")

