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
from tofu.ez.params import EZVARS_aux, EZVARS
from tofu.ez.Helpers.stitch_funcs import main_sti_mp, main_360sti_ufol_depth1, main_360_mp_depth1
from tofu.ez.GUI.message_dialog import warning_message
from tofu.ez.util import add_value_to_dict_entry, get_int_validator, get_double_validator
from tofu.ez.util import import_values, export_values


LOG = logging.getLogger(__name__)

class EZStitchGroup(QGroupBox):
    def __init__(self):
        super().__init__()

        self.setTitle("EZ-STITCH")
        self.setToolTip("Reslicing and stitching tool")
        self.setStyleSheet('QGroupBox {color: purple;}')

        self.invoke_after_reco_checkbox = QCheckBox("Automatically produce stitched orthogonal sections")
        self.invoke_after_reco_checkbox.stateChanged.connect(self.conf_auto_stitch)
        #self.invoke_after_reco_checkbox.setToolTip("Only works for batch reconstructions with ")

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
        self.orthogonal_checkbox.stateChanged.connect(self.set_ort_checkbox)

        self.start_stop_step_label = QLabel()
        self.start_stop_step_label.setText("Which images to be stitched: start,stop,step:")
        self.start_stop_step_entry = QLineEdit()
        self.start_stop_step_entry.editingFinished.connect(self.get_start_stop_step)

        self.flipud_checkbox = QCheckBox()
        self.flipud_checkbox.setText("Flip images upside down before stitching")
        self.flipud_checkbox.stateChanged.connect(self.set_flipud)

        self.interpolate_regions_rButton = QRadioButton()
        self.interpolate_regions_rButton.setText("Interpolate overlapping regions and equalize intensity")
        self.interpolate_regions_rButton.clicked.connect(self.set_rButton)

        self.num_overlaps_label = QLabel()
        self.num_overlaps_label.setText("Number of overlapping rows")
        self.num_overlaps_entry = QLineEdit()
        self.num_overlaps_entry.editingFinished.connect(self.set_overlap)

        self.est_olap_checkbox = QCheckBox()
        self.est_olap_checkbox.setText("Estimate vertical overlap automatically. Will take a slice from z00 directory "
                              "and compare it with selected slices in z01 directory")
        #self.est_olap_checkbox.stateChanged.connect(self.set_est_olap)

        self.ind_z00_label = QLabel()
        self.ind_z00_label.setText("Index of slice in z00 directory")
        self.ind_z00_entry = QLineEdit()

        self.slice_range_label = QLabel()
        self.slice_range_label.setText("Range of slices in z01 directory")

        self.ind_start_z01_label = QLabel()
        self.ind_start_z01_label.setText("First slice")
        self.ind_start_z01_entry = QLineEdit()

        self.ind_stop_z01_label = QLabel()
        self.ind_stop_z01_label.setText("Last slice")
        self.ind_stop_z01_entry = QLineEdit()

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
        vbox1.addWidget(self.invoke_after_reco_checkbox)
        vbox1.addWidget(self.input_dir_button)
        vbox1.addWidget(self.input_dir_entry)
        vbox1.addWidget(self.tmp_dir_button)
        vbox1.addWidget(self.tmp_dir_entry)
        vbox1.addWidget(self.output_dir_button)
        vbox1.addWidget(self.output_dir_entry)
        layout.addItem(vbox1, 0, 0)

        grid0 = QGridLayout()
        grid0.addWidget(self.types_of_images_label, 0, 0)
        grid0.addWidget(self.types_of_images_entry, 0, 1)
        grid0.addWidget(self.orthogonal_checkbox, 1, 0, 1, 2)
        grid0.addWidget(self.start_stop_step_label, 2, 0)
        grid0.addWidget(self.start_stop_step_entry, 2, 1)
        grid0.addWidget(self.flipud_checkbox, 3, 0)
        layout.addItem(grid0, 1, 0)

        grid1 = QGridLayout()
        grid1.addWidget(self.interpolate_regions_rButton, 0, 0, 1, 2)
        grid1.addWidget(self.num_overlaps_label, 1, 0)
        grid1.addWidget(self.num_overlaps_entry, 1, 1)
        grid1.addWidget(self.est_olap_checkbox,2, 0, 1, 2)
        layout.addItem(grid1, 2, 0)

        grid1_b = QGridLayout()
        grid1_b.addWidget(self.clip_histogram_checkbox, 0, 0)
        grid1_b.addWidget(self.min_value_label, 1, 0)
        grid1_b.addWidget(self.min_value_entry, 1, 1)
        grid1_b.addWidget(self.max_value_label, 2, 0)
        grid1_b.addWidget(self.max_value_entry, 2, 1)
        layout.addItem(grid1_b, 3, 0)

        grid2 = QGridLayout()
        grid2.addWidget(self.concatenate_rButton, 0, 0, 1, 2)
        grid2.addWidget(self.first_row_label, 1, 0)
        grid2.addWidget(self.first_row_entry, 1, 1)
        grid2.addWidget(self.last_row_label, 1, 2)
        grid2.addWidget(self.last_row_entry, 1, 3)
        layout.addItem(grid2, 4, 0)

        grid3 = QGridLayout()
        grid3.addWidget(self.half_acquisition_rButton, 0, 0, 1, 2)
        grid3.addWidget(self.column_of_axis_label, 1, 0)
        grid3.addWidget(self.column_of_axis_entry, 1, 1)
        layout.addItem(grid3, 5, 0)

        grid4 = QGridLayout()
        grid4.addWidget(self.help_button, 0, 0)
        grid4.addWidget(self.delete_button, 0, 1)
        grid4.addWidget(self.stitch_button, 0, 2)
        grid4.addWidget(self.import_parameters_button, 1, 0, 1, 2)
        grid4.addWidget(self.save_parameters_button, 1, 2)
        layout.addItem(grid4, 6, 0)

        self.setLayout(layout)

    def load_values(self):
        self.invoke_after_reco_checkbox.setChecked(EZVARS_aux['vert-sti']['dovertsti']['value'])
        self.input_dir_entry.setText(str(EZVARS_aux['vert-sti']['input-dir']['value']))
        self.tmp_dir_entry.setText(str(EZVARS_aux['vert-sti']['tmp-dir']['value']))
        self.output_dir_entry.setText(str(EZVARS_aux['vert-sti']['output-dir']['value']))
        self.types_of_images_entry.setText(str(EZVARS_aux['vert-sti']['subdir-name']['value']))
        self.orthogonal_checkbox.setChecked(EZVARS_aux['vert-sti']['ort']['value'])
        self.start_stop_step_entry.setText(f"{EZVARS_aux['vert-sti']['start']['value']},"
                                           f"{EZVARS_aux['vert-sti']['stop']['value']},"
                                           f"{EZVARS_aux['vert-sti']['step']['value']}")
        self.flipud_checkbox.setChecked(EZVARS_aux['vert-sti']['flipud']['value'])

        if EZVARS_aux['vert-sti']['task_type']['value'] == 0:
            self.interpolate_regions_rButton.setChecked(True)
        elif EZVARS_aux['vert-sti']['task_type']['value'] == 1:
            self.concatenate_rButton.setChecked(True)
        elif EZVARS_aux['vert-sti']['task_type']['value'] == 2:
            self.half_acquisition_rButton.setChecked(True)

        self.num_overlaps_entry.setText(str(EZVARS_aux['vert-sti']['num_olap_rows']['value']))
        self.clip_histogram_checkbox.setChecked(EZVARS_aux['vert-sti']['clip_hist']['value'])
        self.min_value_entry.setText(str(EZVARS_aux['vert-sti']['min_int_val']['value']))
        self.max_value_entry.setText(str(EZVARS_aux['vert-sti']['max_int_val']['value']))
        self.first_row_entry.setText(str(EZVARS_aux['vert-sti']['conc_row_top']['value']))
        self.last_row_entry.setText(str(EZVARS_aux['vert-sti']['conc_row_bottom']['value']))
        self.column_of_axis_entry.setText(str(EZVARS_aux['vert-sti']['cor']['value']))
        self.conf_auto_stitch()
    
    #TODO: change output/tmp on signal from the main tab if auto sttiched is requested
    # and respective entries are modified in the main tab
    def conf_auto_stitch(self):
        if self.invoke_after_reco_checkbox.isChecked():
            add_value_to_dict_entry(EZVARS_aux['vert-sti']['dovertsti'], True)
            self.input_dir_entry.setEnabled(False)
            self.output_dir_entry.setEnabled(f"{EZVARS['inout']['output-dir']}-ort-stitched")
            self.tmp_dir_entry.setEnabled(EZVARS['inout']['tmp-dir'])
            self.types_of_images_entry.setText('sli')
            self.types_of_images_entry.setEnabled(False)
            self.half_acquisition_rButton.setEnabled(False)
            self.column_of_axis_entry.setEnabled(False)
        else:
            add_value_to_dict_entry(EZVARS_aux['vert-sti']['dovertsti'], False)
            self.input_dir_entry.setEnabled(True)
            self.types_of_images_entry.setEnabled(True)
            self.half_acquisition_rButton.setEnabled(True)
            self.column_of_axis_entry.setEnabled(True)

    def set_rButton(self):
        if self.interpolate_regions_rButton.isChecked():
            LOG.debug("Interpolate regions")
            add_value_to_dict_entry(EZVARS_aux['vert-sti']['task_type'], 0)
        elif self.concatenate_rButton.isChecked():
            LOG.debug("Concatenate only")
            add_value_to_dict_entry(EZVARS_aux['vert-sti']['task_type'], 1)
        elif self.half_acquisition_rButton.isChecked():
            LOG.debug("Half-acquisition mode")
            add_value_to_dict_entry(EZVARS_aux['vert-sti']['task_type'], 2)

    def input_button_pressed(self):
        LOG.debug("Input button pressed")
        dir_explore = QFileDialog(self)
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['input-dir'], dir_explore.getExistingDirectory())
        self.input_dir_entry.setText(EZVARS_aux['vert-sti']['input-dir']['value'])

    def set_input_entry(self):
        LOG.debug("Input: " + str(self.input_dir_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['input-dir'], str(self.input_dir_entry.text()))

    def temp_button_pressed(self):
        LOG.debug("Temp button pressed")
        dir_explore = QFileDialog(self)
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['tmp-dir'], dir_explore.getExistingDirectory())
        self.tmp_dir_entry.setText(EZVARS_aux['vert-sti']['tmp-dir']['value'])

    def set_temp_entry(self):
        LOG.debug("Temp: " + str(self.tmp_dir_entry.text()))
        EZVARS_aux['vert-sti']['tmp-dir']['value'] = str(self.tmp_dir_entry.text())
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['tmp-dir'], str(self.tmp_dir_entry.text()))

    def output_button_pressed(self):
        LOG.debug("Output button pressed")
        dir_explore = QFileDialog(self)
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['output-dir'], dir_explore.getExistingDirectory())
        self.output_dir_entry.setText(EZVARS_aux['vert-sti']['output-dir']['value'])

    def set_output_entry(self):
        LOG.debug("Output: " + str(self.output_dir_entry.text()))
        EZVARS_aux['vert-sti']['output-dir']['value'] = str(self.output_dir_entry.text())
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['output-dir'], str(self.output_dir_entry.text()))

    def set_type_images(self):
        LOG.debug("Type of images: " + str(self.types_of_images_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['subdir-name'], str(self.types_of_images_entry.text()))

    def set_ort_checkbox(self):
        LOG.debug("Stitch orthogonal: " + str(self.orthogonal_checkbox.isChecked()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['ort'], bool(self.orthogonal_checkbox.isChecked()))

    def get_start_stop_step(self):
        LOG.debug("Images to be stitched: " + str(self.start_stop_step_entry.text()))
        sli_range = str(self.start_stop_step_entry.text()).split(",")
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['start'], sli_range[0])
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['stop'], sli_range[1])
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['step'], sli_range[2])
        
    def set_flipud(self):
        LOG.debug("Sample moved down: " + str(self.flipud_checkbox.isChecked()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['flipud'], bool(self.flipud_checkbox.isChecked()))

    def set_overlap(self):
        LOG.debug("Num overlapping rows: " + str(self.num_overlaps_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['num_olap_rows'], int(self.num_overlaps_entry.text()))

    def set_histogram_checkbox(self):
        LOG.debug("Clip histogram:  " + str(self.clip_histogram_checkbox.isChecked()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['clip_hist'], bool(self.clip_histogram_checkbox.isChecked()))

    def set_min_value(self):
        LOG.debug("Min value: " + str(self.min_value_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['min_int_val'], float(self.min_value_entry.text()))

    def set_max_value(self):
        LOG.debug("Max value: " + str(self.max_value_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['max_int_val'], float(self.max_value_entry.text()))

    def set_first_row(self):
        LOG.debug("First row: " + str(self.first_row_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['conc_row_top'], int(self.first_row_entry.text()))

    def set_last_row(self):
        LOG.debug("Last row: " + str(self.last_row_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['conc_row_bottom'], int(self.last_row_entry.text()))

    def set_axis_column(self):
        LOG.debug("Column of axis: " + str(self.column_of_axis_entry.text()))
        add_value_to_dict_entry(EZVARS_aux['vert-sti']['cor'], int(self.column_of_axis_entry.text()))
        
    

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
        # if os.path.exists(EZVARS_aux['vert-sti']['output-dir']['value']):
        #     os.system('rm -r {}'.format(EZVARS_aux['vert-sti']['output-dir']['value']))
        #     print(" - Directory with reconstructed data was removed")
        if os.path.exists(EZVARS_aux['vert-sti']['output-dir']['value']):
            qm = QMessageBox()
            rep = qm.question(self, '', f"{EZVARS_aux['vert-sti']['output-dir']['value']} \n"
                                        "will be removed. Continue?", qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(EZVARS_aux['vert-sti']['output-dir']['value'])
                except:
                    warning_message('Error while deleting directory')
                    return
            else:
                return

    def stitch_button_pressed(self):
        LOG.debug("Stitch button pressed")

        if os.path.exists(EZVARS_aux['vert-sti']['tmp-dir']['value']) and \
                len(os.listdir(EZVARS_aux['vert-sti']['tmp-dir']['value'])) > 0:
            qm = QMessageBox()
            rep = qm.question(self, '', "Temporary dir is not empty. Is it safe to delete it?", 
                              qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(EZVARS_aux['vert-sti']['tmp-dir']['value'])
                except:
                    warning_message('Error while deleting directory')
                    return
            else:
                return
        if os.path.exists(EZVARS_aux['vert-sti']['output-dir']['value']) and \
                len(os.listdir(EZVARS_aux['vert-sti']['output-dir']['value'])) > 0:
            qm = QMessageBox()
            rep = qm.question(self, '', "Output dir is not empty. Is it safe to delete it?", 
                              qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(EZVARS_aux['vert-sti']['output-dir']['value'])
                except:
                    warning_message('Error while deleting directory')
                    return
            else:
                return

        print("======= Begin Stitching =======")
        # Interpolate overlapping regions and equalize intensity
        if EZVARS_aux['vert-sti']['task_type']['value'] == 0 or \
                EZVARS_aux['vert-sti']['task_type']['value'] == 1:
            main_sti_mp()
        else: 
            # main_360_mp_depth1(self.parameters['ezstitch_input_dir'],
            #                     EZVARS_aux['vert-sti']['output-dir']['value'],
            #                     self.parameters['ezstitch_axis_of_rotation'], 0)
            main_360sti_ufol_depth1(EZVARS_aux['vert-sti']['input-dir']['value'],
                               EZVARS_aux['vert-sti']['output-dir']['value'],
                               EZVARS_aux['vert-sti']['cor']['value'], 0)
        if os.path.isdir(EZVARS_aux['vert-sti']['output-dir']['value']):
            params_file_path = os.path.join(EZVARS_aux['vert-sti']['output-dir']['value'], 
                                            'ezmview_params.yaml')
            export_values(params_file_path, ['ezvars_aux'])
        print("==== Waiting for Next Task ====")

    def import_parameters_button_pressed(self):
        LOG.debug("Import params button clicked")
        dir_explore = QFileDialog(self)
        params_file_path = dir_explore.getOpenFileName(filter="*.yaml")
        import_values(params_file_path[0], ['ezvars_aux'])
        self.load_values()

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
            export_values(file_path, ['ezvars_aux'])
            print("Parameters file saved at: " + str(file_path))
        except FileNotFoundError:
            print("You need to select a directory and use a valid file name")

