from PyQt5.QtWidgets import (
    QGroupBox,
    QPushButton,
    QCheckBox,
    QLabel,
    QLineEdit,
    QGridLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSignal
import logging
from shutil import rmtree
import os
import yaml
from tofu.ez.Helpers.stitch_funcs import main_360_mp_depth2
from tofu.ez.GUI.message_dialog import warning_message
# Params
import tofu.ez.params as params

LOG = logging.getLogger(__name__)

class MultiStitch360Group(QGroupBox):
    get_fdt_names_on_stitch_pressed = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.setTitle("360-MULTI-STITCH")
        self.setToolTip("Converts half-acquistion data sets to ordinary projections \n"
                      "and crops all images to the same size.")
        self.setStyleSheet('QGroupBox {color: red;}')

        self.input_dir_button = QPushButton("Select input directory")
        self.input_dir_button.setToolTip("Contains multiple CT directories with flats/darks/tomo subdirectories. \n"
                                         "Images in each will be stitched pair-wise [x and x+180 deg]")
        self.input_dir_button.clicked.connect(self.input_button_pressed)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.editingFinished.connect(self.set_input_entry)

        self.temp_dir_button = QPushButton("Select temporary directory - default value recommended")
        self.temp_dir_button.clicked.connect(self.temp_button_pressed)

        self.temp_dir_entry = QLineEdit()
        self.temp_dir_entry.editingFinished.connect(self.set_temp_entry)

        self.output_dir_button = QPushButton("Directory to save stitched images")
        self.output_dir_button.clicked.connect(self.output_button_pressed)

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.editingFinished.connect(self.set_output_entry)

        self.crop_checkbox = QCheckBox("Crop all projections to match the width of smallest stitched projection")
        self.crop_checkbox.clicked.connect(self.set_crop_projections_checkbox)

        self.axis_bottom_label = QLabel()
        self.axis_bottom_label.setText("Axis of Rotation (Dir 00):")

        self.axis_bottom_entry = QLineEdit()
        self.axis_bottom_entry.editingFinished.connect(self.set_axis_bottom)

        self.axis_top_label = QLabel("Axis of Rotation (Dir 0N):")

        self.axis_group = QGroupBox("Enter axis of rotation manually")
        self.axis_group.clicked.connect(self.set_axis_group)

        self.axis_top_entry = QLineEdit()
        self.axis_top_entry.editingFinished.connect(self.set_axis_top)

        self.axis_z000_label = QLabel("Axis of Rotation (Dir 00):")
        self.axis_z000_entry = QLineEdit()
        self.axis_z000_entry.editingFinished.connect(self.set_z000)

        self.axis_z001_label = QLabel("Axis of Rotation (Dir 01):")
        self.axis_z001_entry = QLineEdit()
        self.axis_z001_entry.editingFinished.connect(self.set_z001)

        self.axis_z002_label = QLabel("Axis of Rotation (Dir 02):")
        self.axis_z002_entry = QLineEdit()
        self.axis_z002_entry.editingFinished.connect(self.set_z002)

        self.axis_z003_label = QLabel("Axis of Rotation (Dir 03):")
        self.axis_z003_entry = QLineEdit()
        self.axis_z003_entry.editingFinished.connect(self.set_z003)

        self.axis_z004_label = QLabel("Axis of Rotation (Dir 04):")
        self.axis_z004_entry = QLineEdit()
        self.axis_z004_entry.editingFinished.connect(self.set_z004)

        self.axis_z005_label = QLabel("Axis of Rotation (Dir 05):")
        self.axis_z005_entry = QLineEdit()
        self.axis_z005_entry.editingFinished.connect(self.set_z005)

        self.axis_z006_label = QLabel("Axis of Rotation (Dir 06):")
        self.axis_z006_entry = QLineEdit()
        self.axis_z006_entry.editingFinished.connect(self.set_z006)

        self.axis_z007_label = QLabel("Axis of Rotation (Dir 07):")
        self.axis_z007_entry = QLineEdit()
        self.axis_z007_entry.editingFinished.connect(self.set_z007)

        self.axis_z008_label = QLabel("Axis of Rotation (Dir 08):")
        self.axis_z008_entry = QLineEdit()
        self.axis_z008_entry.editingFinished.connect(self.set_z008)

        self.axis_z009_label = QLabel("Axis of Rotation (Dir 09):")
        self.axis_z009_entry = QLineEdit()
        self.axis_z009_entry.editingFinished.connect(self.set_z009)

        self.axis_z010_label = QLabel("Axis of Rotation (Dir 10):")
        self.axis_z010_entry = QLineEdit()
        self.axis_z010_entry.editingFinished.connect(self.set_z010)

        self.axis_z011_label = QLabel("Axis of Rotation (Dir 11):")
        self.axis_z011_entry = QLineEdit()
        self.axis_z011_entry.editingFinished.connect(self.set_z011)

        self.stitch_button = QPushButton("Stitch")
        self.stitch_button.clicked.connect(self.stitch_button_pressed)
        self.stitch_button.setStyleSheet("color:royalblue;font-weight:bold")

        self.delete_button = QPushButton("Delete output dir")
        self.delete_button.clicked.connect(self.delete_button_pressed)

        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.help_button_pressed)

        self.import_parameters_button = QPushButton("Import Parameters from File")
        self.import_parameters_button.clicked.connect(self.import_parameters_button_pressed)

        self.save_parameters_button = QPushButton("Save Parameters to File")
        self.save_parameters_button.clicked.connect(self.save_parameters_button_pressed)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.input_dir_button, 0, 0, 1, 4)
        layout.addWidget(self.input_dir_entry, 1, 0, 1, 4)
        layout.addWidget(self.temp_dir_button, 2, 0, 1, 4)
        layout.addWidget(self.temp_dir_entry, 3, 0, 1, 4)
        layout.addWidget(self.output_dir_button, 4, 0, 1, 4)
        layout.addWidget(self.output_dir_entry, 5, 0, 1, 4)
        layout.addWidget(self.crop_checkbox, 6, 0, 1, 4)

        layout.addWidget(self.axis_bottom_label, 7, 0)
        layout.addWidget(self.axis_bottom_entry, 7, 1)
        layout.addWidget(self.axis_top_label, 7, 2)
        layout.addWidget(self.axis_top_entry, 7, 3)

        self.axis_group.setCheckable(True)
        self.axis_group.setChecked(False)
        axis_layout = QGridLayout()

        axis_layout.addWidget(self.axis_z000_label, 0, 0)
        axis_layout.addWidget(self.axis_z000_entry, 0, 1)
        axis_layout.addWidget(self.axis_z006_label, 0, 2)
        axis_layout.addWidget(self.axis_z006_entry, 0, 3)

        axis_layout.addWidget(self.axis_z001_label, 1, 0)
        axis_layout.addWidget(self.axis_z001_entry, 1, 1)
        axis_layout.addWidget(self.axis_z007_label, 1, 2)
        axis_layout.addWidget(self.axis_z007_entry, 1, 3)

        axis_layout.addWidget(self.axis_z002_label, 2, 0)
        axis_layout.addWidget(self.axis_z002_entry, 2, 1)
        axis_layout.addWidget(self.axis_z008_label, 2, 2)
        axis_layout.addWidget(self.axis_z008_entry, 2, 3)

        axis_layout.addWidget(self.axis_z003_label, 3, 0)
        axis_layout.addWidget(self.axis_z003_entry, 3, 1)
        axis_layout.addWidget(self.axis_z009_label, 3, 2)
        axis_layout.addWidget(self.axis_z009_entry, 3, 3)

        axis_layout.addWidget(self.axis_z004_label, 4, 0)
        axis_layout.addWidget(self.axis_z004_entry, 4, 1)
        axis_layout.addWidget(self.axis_z010_label, 4, 2)
        axis_layout.addWidget(self.axis_z010_entry, 4, 3)

        axis_layout.addWidget(self.axis_z005_label, 5, 0)
        axis_layout.addWidget(self.axis_z005_entry, 5, 1)
        axis_layout.addWidget(self.axis_z011_label, 5, 2)
        axis_layout.addWidget(self.axis_z011_entry, 5, 3)
        self.axis_group.setLayout(axis_layout)

        self.axis_group.setTabOrder(self.axis_z000_entry, self.axis_z001_entry)
        self.axis_group.setTabOrder(self.axis_z001_entry, self.axis_z002_entry)
        self.axis_group.setTabOrder(self.axis_z002_entry, self.axis_z003_entry)
        self.axis_group.setTabOrder(self.axis_z003_entry, self.axis_z004_entry)
        self.axis_group.setTabOrder(self.axis_z004_entry, self.axis_z005_entry)
        self.axis_group.setTabOrder(self.axis_z005_entry, self.axis_z006_entry)
        self.axis_group.setTabOrder(self.axis_z006_entry, self.axis_z007_entry)
        self.axis_group.setTabOrder(self.axis_z007_entry, self.axis_z008_entry)
        self.axis_group.setTabOrder(self.axis_z008_entry, self.axis_z009_entry)
        self.axis_group.setTabOrder(self.axis_z009_entry, self.axis_z010_entry)
        self.axis_group.setTabOrder(self.axis_z010_entry, self.axis_z011_entry)

        layout.addWidget(self.axis_group, 8, 0, 1, 4)

        layout.addWidget(self.help_button, 9, 0)
        layout.addWidget(self.delete_button, 9, 1)
        layout.addWidget(self.stitch_button, 9, 2, 1, 2)

        layout.addWidget(self.import_parameters_button, 10, 0, 1, 2)
        layout.addWidget(self.save_parameters_button, 10, 2, 1, 2)

        self.setLayout(layout)

    def init_values(self):
        self.parameters = {'parameters_type': '360_multi_stitch'}
        self.parameters['360multi_input_dir'] = os.path.expanduser('~')# #EZVARS['360-batch-stitch']['indir']
        self.input_dir_entry.setText(self.parameters['360multi_input_dir'])
        self.parameters['360multi_temp_dir'] = os.path.join(  #EZVARS['360-batch-stitch']['tmpdir']
                        os.path.expanduser('~'), "tmp-batch360stitch")
        self.temp_dir_entry.setText(self.parameters['360multi_temp_dir'])
        self.parameters['360multi_output_dir'] = os.path.join(os.path.expanduser('~'),'stitched360') #EZVARS['360-batch-stitch']['outdir']
        self.output_dir_entry.setText(self.parameters['360multi_output_dir'])
        self.parameters['360multi_crop_projections'] = True   #EZVARS['360-batch-stitch']['crop']
        self.crop_checkbox.setChecked(self.parameters['360multi_crop_projections'])
        self.parameters['360multi_bottom_axis'] = 245  #EZVARS['360-batch-stitch']['COR-in-first-set']
        self.axis_bottom_entry.setText(str(self.parameters['360multi_bottom_axis']))
        self.parameters['360multi_top_axis'] = 245  #EZVARS['360-batch-stitch']['COR-in-last-set']
        self.axis_top_entry.setText(str(self.parameters['360multi_top_axis']))
        self.parameters['360multi_axis'] = self.parameters['360multi_bottom_axis']
        self.parameters['360multi_manual_axis'] = False   #EZVARS['360-batch-stitch']['COR-user-defined']
        self.parameters['360multi_axis_dict'] = dict.fromkeys(['z000', 'z001', 'z002', 'z003', 'z004', 'z005',
                                                               'z006', 'z007', 'z008', 'z009', 'z010', 'z011'], 200)
        # EZVARS['360-batch-stitch']['COR-dict']

    def update_parameters(self, new_parameters):
        LOG.debug("Update parameters")
        if new_parameters['parameters_type'] != '360_multi_stitch':
            print("Error: Invalid parameter file type: " + str(new_parameters['parameters_type']))
            return -1
        # Update parameters dictionary (which is passed to auto_stitch_funcs)
        self.parameters = new_parameters
        # Update displayed parameters for GUI
        self.input_dir_entry.setText(self.parameters['360multi_input_dir'])
        self.temp_dir_entry.setText(self.parameters['360multi_temp_dir'])
        self.output_dir_entry.setText(self.parameters['360multi_output_dir'])
        self.crop_checkbox.setChecked(self.parameters['360multi_crop_projections'])
        self.axis_bottom_entry.setText(str(self.parameters['360multi_bottom_axis']))
        self.axis_top_entry.setText(str(self.parameters['360multi_top_axis']))
        self.axis_group.setChecked(bool(self.parameters['360multi_manual_axis']))
        self.axis_z000_entry.setText(str(self.parameters['360multi_axis_dict']['z000']))
        self.axis_z001_entry.setText(str(self.parameters['360multi_axis_dict']['z001']))
        self.axis_z002_entry.setText(str(self.parameters['360multi_axis_dict']['z002']))
        self.axis_z003_entry.setText(str(self.parameters['360multi_axis_dict']['z003']))
        self.axis_z004_entry.setText(str(self.parameters['360multi_axis_dict']['z004']))
        self.axis_z005_entry.setText(str(self.parameters['360multi_axis_dict']['z005']))
        self.axis_z006_entry.setText(str(self.parameters['360multi_axis_dict']['z006']))
        self.axis_z007_entry.setText(str(self.parameters['360multi_axis_dict']['z007']))
        self.axis_z008_entry.setText(str(self.parameters['360multi_axis_dict']['z008']))
        self.axis_z009_entry.setText(str(self.parameters['360multi_axis_dict']['z009']))
        self.axis_z010_entry.setText(str(self.parameters['360multi_axis_dict']['z010']))
        self.axis_z011_entry.setText(str(self.parameters['360multi_axis_dict']['z011']))
        return 0

    def input_button_pressed(self):
        LOG.debug("Input button pressed")
        dir_explore = QFileDialog(self)
        self.input_dir_entry.setText(dir_explore.getExistingDirectory())
        self.set_input_entry()

    def set_input_entry(self):
        LOG.debug("Input directory: " + str(self.input_dir_entry.text()))
        self.parameters['360multi_input_dir'] = str(self.input_dir_entry.text())
        
        # Set output directory to automatically follow the input directory structure
        self.output_dir_entry.setText(self.parameters['360multi_input_dir'] + "/hor-search")
        self.set_output_entry()

    def temp_button_pressed(self):
        LOG.debug("Temp button pressed")
        dir_explore = QFileDialog(self)
        self.temp_dir_entry.setText(dir_explore.getExistingDirectory())
        self.set_temp_entry()

    def set_temp_entry(self):
        LOG.debug("Temp directory: " + str(self.temp_dir_entry.text()))
        self.parameters['360multi_temp_dir'] = str(self.temp_dir_entry.text())

    def output_button_pressed(self):
        LOG.debug("Output button pressed")
        dir_explore = QFileDialog(self)
        self.output_dir_entry.setText(dir_explore.getExistingDirectory())
        self.set_output_entry()

    def set_output_entry(self):
        LOG.debug("Output directory: " + str(self.output_dir_entry.text()))
        self.parameters['360multi_output_dir'] = str(self.output_dir_entry.text())

    def set_crop_projections_checkbox(self):
        LOG.debug("Crop projections: " + str(self.crop_checkbox.isChecked()))
        self.parameters['360multi_crop_projections'] = bool(self.crop_checkbox.isChecked())

    def set_axis_bottom(self):
        LOG.debug("Axis Bottom : " + str(self.axis_bottom_entry.text()))
        self.parameters['360multi_bottom_axis'] = int(self.axis_bottom_entry.text())

    def set_axis_top(self):
        LOG.debug("Axis Top: " + str(self.axis_top_entry.text()))
        self.parameters['360multi_top_axis'] = int(self.axis_top_entry.text())

    def set_axis_group(self):
        if self.axis_group.isChecked():
            self.axis_bottom_label.setEnabled(False)
            self.axis_bottom_entry.setEnabled(False)
            self.axis_top_label.setEnabled(False)
            self.axis_top_entry.setEnabled(False)
            self.parameters['360multi_manual_axis'] = True
            LOG.debug("Enter axis of rotation manually: " + str(self.parameters['360multi_manual_axis']))
        else:
            self.axis_bottom_label.setEnabled(True)
            self.axis_bottom_entry.setEnabled(True)
            self.axis_top_label.setEnabled(True)
            self.axis_top_entry.setEnabled(True)
            self.parameters['360multi_manual_axis'] = False
            LOG.debug("Enter axis of rotation manually: " + str(self.parameters['360multi_manual_axis']))

    def set_z000(self):
        LOG.debug("z000 axis: " + str(self.axis_z000_entry.text()))
        self.parameters['360multi_axis_dict']['z000'] = int(self.axis_z000_entry.text())

    def set_z001(self):
        LOG.debug("z001 axis: " + str(self.axis_z001_entry.text()))
        self.parameters['360multi_axis_dict']['z001'] = int(self.axis_z001_entry.text())

    def set_z002(self):
        LOG.debug("z002 axis: " + str(self.axis_z002_entry.text()))
        self.parameters['360multi_axis_dict']['z002'] = int(self.axis_z002_entry.text())

    def set_z003(self):
        LOG.debug("z003 axis: " + str(self.axis_z003_entry.text()))
        self.parameters['360multi_axis_dict']['z003'] = int(self.axis_z003_entry.text())

    def set_z004(self):
        LOG.debug("z004 axis: " + str(self.axis_z004_entry.text()))
        self.parameters['360multi_axis_dict']['z004'] = int(self.axis_z004_entry.text())

    def set_z005(self):
        LOG.debug("z005 axis: " + str(self.axis_z005_entry.text()))
        self.parameters['360multi_axis_dict']['z005'] = int(self.axis_z005_entry.text())

    def set_z006(self):
        LOG.debug("z006 axis: " + str(self.axis_z006_entry.text()))
        self.parameters['360multi_axis_dict']['z006'] = int(self.axis_z006_entry.text())

    def set_z007(self):
        LOG.debug("z007 axis: " + str(self.axis_z007_entry.text()))
        self.parameters['360multi_axis_dict']['z007'] = int(self.axis_z007_entry.text())

    def set_z008(self):
        LOG.debug("z008 axis: " + str(self.axis_z008_entry.text()))
        self.parameters['360multi_axis_dict']['z008'] = int(self.axis_z008_entry.text())

    def set_z009(self):
        LOG.debug("z009 axis: " + str(self.axis_z009_entry.text()))
        self.parameters['360multi_axis_dict']['z009'] = int(self.axis_z009_entry.text())

    def set_z010(self):
        LOG.debug("z010 axis: " + str(self.axis_z010_entry.text()))
        self.parameters['360multi_axis_dict']['z010'] = int(self.axis_z010_entry.text())

    def set_z011(self):
        LOG.debug("z011 axis: " + str(self.axis_z011_entry.text()))
        self.parameters['360multi_axis_dict']['z011'] = int(self.axis_z011_entry.text())

    def stitch_button_pressed(self):
        LOG.debug("Stitch button pressed")
        self.get_fdt_names_on_stitch_pressed.emit()
        if os.path.exists(self.parameters['360multi_temp_dir']) and \
                    len(os.listdir(self.parameters['360multi_temp_dir'])) > 0:
            qm = QMessageBox()
            rep = qm.warning(self, '', "Temp directory exists and is not empty.")            
            return

        if os.path.exists(self.parameters['360multi_output_dir']) and \
                    len(os.listdir(self.parameters['360multi_output_dir'])) > 0:
            qm = QMessageBox()
            rep = qm.warning(self, '', "Output directory exists and is not empty.")            
            return

        print("======= Begin 360 Multi-Stitch =======")
        main_360_mp_depth2(self.parameters)

        if os.path.isdir(self.parameters['360multi_output_dir']):
            params_file_path = os.path.join(self.parameters['360multi_output_dir'], '360_multi_stitch_params.yaml')
            params.save_parameters(self.parameters, params_file_path)

        print("==== Waiting for Next Task ====")

    def delete_button_pressed(self):
        print("---- Deleting Data From Output Directory ----")
        LOG.debug("Delete button pressed")
        qm = QMessageBox()
        rep = qm.question(self, '', "Is it safe to delete the output directory?", qm.Yes | qm.No)
        
        if not os.path.exists(self.parameters['360multi_output_dir']):
            warning_message("Output directory does not exist")
        elif rep == qm.Yes:
            try:
                rmtree(self.parameters['360multi_output_dir'])
            except:
                warning_message("Problems with deleting output directory")
        else:
            return
        
        rep = qm.question(self, '', "Is it safe to delete the temp directory?", qm.Yes | qm.No)
        if not os.path.exists(self.parameters['360multi_temp_dir']):
            warning_message("Temp directory does not exist")
        elif rep == qm.Yes:
            try:
                rmtree(self.parameters['360multi_temp_dir'])
            except:
                warning_message("Problems with deleting temp directory")
        else:
            return
        

    def help_button_pressed(self):
        LOG.debug("Help button pressed")
        h = "Stitches images horizontally\n"
        h += "Directory structure is, f.i., Input/000, Input/001,...Input/00N\n"
        h += "Each 000, 001, ... 00N directory must have identical subdirectory \"Type\"\n"
        h += "Selected range of images from \"Type\" directory will be stitched vertically\n"
        h += "across all subdirectories in the Input directory"
        h += "to be added as options:\n"
        h += "(1) orthogonal reslicing, (2) interpolation, (3) horizontal stitching"
        QMessageBox.information(self, "Help", h)

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

