from functools import partial

from PyQt5.QtWidgets import (
    QGroupBox,
    QPushButton,
    QCheckBox,
    QLabel,
    QLineEdit,
    QGridLayout,
    QFileDialog,
    QMessageBox,
    QRadioButton
)
from PyQt5.QtCore import pyqtSignal
import logging
from shutil import rmtree
import os
import yaml
from tofu.ez.Helpers.stitch_funcs import main_360_mp_depth2
from tofu.ez.GUI.message_dialog import warning_message
# Params
from tofu.ez.params import EZVARS_aux
from tofu.ez.util import add_value_to_dict_entry, get_int_validator
from tofu.ez.util import import_values, export_values

LOG = logging.getLogger(__name__)

class MultiStitch360Group(QGroupBox):
    get_fdt_names_on_stitch_pressed = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.setTitle("360-MULTI-STITCH: convert half-acqusition mode CT sets to ordinary CT sets. "
                      "Not recursive.")
        self.setToolTip("Converts half-acquistion data sets to ordinary projections \n"
                      "and crops all images to the same size.")
        self.setStyleSheet('QGroupBox {color: red;}')

        self.input_dir_button = QPushButton("Select input directory")
        self.input_dir_button.setToolTip("Contains one layer of CT directories with flats/darks/tomo subdirectories. \n"
                                         "Images in each will be stitched pair-wise [x and x+180 deg]. \n"
                                         "Doesn't work recursively")
        self.input_dir_button.clicked.connect(self.input_button_pressed)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.editingFinished.connect(self.set_input_entry)

        self.output_dir_button = QPushButton("Directory to save stitched images")
        self.output_dir_button.clicked.connect(self.output_button_pressed)

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.editingFinished.connect(self.set_output_entry)

        self.crop_checkbox = QCheckBox("Crop all projections to match the width of smallest stitched projection")
        self.crop_checkbox.clicked.connect(self.set_crop_projections_checkbox)

        self.olap_val_switch_label = QLabel()
        self.olap_val_switch_label.setText('Define overlaps as')

        self.olap_val_int_rButton = QRadioButton()
        self.olap_val_int_rButton.setText('Min/max and interpolate between')
        self.olap_val_int_rButton.clicked.connect(self.set_rButton)
        self.olap_val_int_rButton.setChecked(True)


        self.olap_val_dict_rButton = QRadioButton()
        self.olap_val_dict_rButton.setText('Table')
        self.olap_val_dict_rButton.clicked.connect(self.set_rButton)

        self.olap_val_list_rButton = QRadioButton()
        self.olap_val_list_rButton.setText('List')
        self.olap_val_list_rButton.clicked.connect(self.set_rButton)



        self.oval_val_switch_group = QGroupBox()

        self.axis_bottom_label = QLabel()
        self.axis_bottom_label.setText("Overlap for first directory:")
        self.axis_bottom_entry = QLineEdit()
        self.axis_bottom_entry.editingFinished.connect(self.set_axis_bottom)
        self.axis_bottom_entry.setValidator(get_int_validator())

        self.axis_top_label = QLabel("For last directory:")
        self.axis_top_entry = QLineEdit()
        self.axis_top_entry.editingFinished.connect(self.set_axis_top)
        self.axis_top_entry.setValidator(get_int_validator())

        #### MANUAL ENTRY OF OVERLAPS
        self.axis_group = QGroupBox("Enter overlaps manually")
        self.axis_group.clicked.connect(self.set_axis_group)

        self.num_subdirs = 24
        for i in range(self.num_subdirs):
            setattr(self, f"axis_z{i:03d}_label", QLabel(f"Dir {i:02d}:"))
            entry = QLineEdit()
            setattr(self, f"axis_z{i:03d}_entry", entry)
            entry.editingFinished.connect(partial(self.set_z_by_index, i))
            getattr(self, f"axis_z{i:03d}_entry").setValidator(get_int_validator())

        self.olap_list_label = QLabel()
        self.olap_list_label.setText("List of values comma separated")
        self.olap_list_entry = QLineEdit()
        self.olap_list_entry.setToolTip('Example: 48,50,5')
        self.olap_list_entry.editingFinished.connect(self.set_olap_list)

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
        self.set_rButton()

    def set_layout(self):
        layout = QGridLayout()

        # layout.addWidget(self.input_dir_button, 0, 0, 1, 4)
        # layout.addWidget(self.input_dir_entry, 1, 0, 1, 4)
        # layout.addWidget(self.output_dir_button, 4, 0, 1, 4)
        # layout.addWidget(self.output_dir_entry, 5, 0, 1, 4)
        # layout.addWidget(self.crop_checkbox, 6, 0, 1, 4)

        layout.addWidget(self.input_dir_button, 0, 0, 1, 1)
        layout.addWidget(self.input_dir_entry, 0, 1, 1, 7)
        layout.addWidget(self.output_dir_button, 1, 0, 1, 1)
        layout.addWidget(self.output_dir_entry, 1, 1, 1, 7)
        layout.addWidget(self.crop_checkbox, 2, 0, 1, 4)
        l=3
        olap_switch_layout = QGridLayout()
        olap_switch_layout.addWidget(self.olap_val_switch_label, 0, 0)
        olap_switch_layout.addWidget(self.olap_val_int_rButton, 0, 1)
        olap_switch_layout.addWidget(self.olap_val_dict_rButton, 0, 2)
        olap_switch_layout.addWidget(self.olap_val_list_rButton, 0, 3)
        self.oval_val_switch_group.setLayout(olap_switch_layout)
        layout.addWidget(self.oval_val_switch_group, l, 0, 1, 8)
        l= 4
        # Interpolate overlaps
        layout.addWidget(self.axis_bottom_label, l, 0)
        layout.addWidget(self.axis_bottom_entry, l, 1)
        layout.addWidget(self.axis_top_label, l, 2)
        layout.addWidget(self.axis_top_entry, l, 3)

        # self.axis_group.setCheckable(True)
        # self.axis_group.setChecked(False)

        # Table of overlaps
        l=5
        axis_layout = QGridLayout()
        ncols = 6
        for i in range(self.num_subdirs):
            axis_layout.addWidget(getattr(self, f"axis_z{i:03d}_label"), 
                                  i % ncols, i // ncols * 2)
            axis_layout.addWidget(getattr(self, f"axis_z{i:03d}_entry"), 
                                  i % ncols, i // ncols * 2 + 1)
        self.axis_group.setLayout(axis_layout)
        layout.addWidget(self.axis_group, l, 0, 1, 8)
        l = 6
        layout.addWidget(self.olap_list_label, l, 0)
        layout.addWidget(self.olap_list_entry, l, 1, 1, 7)

        # layout.addWidget(self.help_button, 11, 0)
        # layout.addWidget(self.delete_button, 11, 1)
        # layout.addWidget(self.stitch_button, 11, 2, 1, 2)
        #
        # layout.addWidget(self.import_parameters_button, 12, 0, 1, 2)
        # layout.addWidget(self.save_parameters_button, 12, 2, 1, 2)
        l = 7
        layout.addWidget(self.delete_button, l, 0)
        layout.addWidget(self.help_button, l, 1)
        layout.addWidget(self.import_parameters_button, l, 2)
        layout.addWidget(self.save_parameters_button, l, 3)
        layout.addWidget(self.stitch_button, l, 4)



        self.setLayout(layout)

    def load_values(self):
        self.input_dir_entry.setText(str(EZVARS_aux['stitch360']['input-dir']['value']))
        self.output_dir_entry.setText(str(EZVARS_aux['stitch360']['output-dir']['value']))
        self.crop_checkbox.setChecked(EZVARS_aux['stitch360']['crop']['value'])
        self.axis_bottom_entry.setText(str(EZVARS_aux['stitch360']['olap_min']['value']))
        self.axis_top_entry.setText(str(EZVARS_aux['stitch360']['olap_max']['value']))
        self.set_rButton_from_params()

    def set_rButton_from_params(self):
        t = "One of the imported overlaps is not a number"
        if EZVARS_aux['stitch360']['olap_switch']['value'] == 0:
            self.olap_val_int_rButton.setChecked(True)
            self.olap_val_dict_rButton.setChecked(False)
            self.olap_val_list_rButton.setChecked(False)
        elif EZVARS_aux['stitch360']['olap_switch']['value'] == 1:
            self.olap_val_int_rButton.setChecked(False)
            self.olap_val_dict_rButton.setChecked(True)
            self.olap_val_list_rButton.setChecked(False)
            vals = EZVARS_aux['stitch360']['olap_list']['value'].split(',')
            if self.check_that_int_failed(vals, t):
                return
            else:
                self.set_table_vals(vals)
        elif EZVARS_aux['stitch360']['olap_switch']['value'] == 2:
            self.olap_val_int_rButton.setChecked(False)
            self.olap_val_dict_rButton.setChecked(False)
            self.olap_val_list_rButton.setChecked(True)
            self.olap_list_entry.setText(EZVARS_aux['stitch360']['olap_list']['value'])
            vals = EZVARS_aux['stitch360']['olap_list']['value'].split(',')
            if self.check_that_int_failed(vals, t):
                return
            else:
                self.set_table_vals(vals)

    def check_that_int_failed(self, vals, t):
        for i in range(len(vals)):
            try:
                int(vals[i])
            except:
                qm = QMessageBox()
                qm.warning(self, '', t)
                return 1
        return 0

    def set_table_vals(self, vals):
        for i in range(len(vals)):
            try:
                getattr(self, f"axis_z{i:03d}_entry").setText(str(vals[i]))
            except:
                continue

    def set_rButton(self):
        dict_entry = EZVARS_aux['stitch360']['olap_switch']
        if self.olap_val_int_rButton.isChecked():
            add_value_to_dict_entry(dict_entry, 0)
            self.axis_bottom_entry.setEnabled(True)
            self.axis_top_entry.setEnabled(True)
            self.olap_list_entry.setEnabled(False)
            self.axis_group.setEnabled(False)
        elif self.olap_val_dict_rButton.isChecked():
            add_value_to_dict_entry(dict_entry, 1)
            self.axis_bottom_entry.setEnabled(False)
            self.axis_top_entry.setEnabled(False)
            self.olap_list_entry.setEnabled(False)
            self.axis_group.setEnabled(True)
        elif self.olap_val_list_rButton.isChecked():
            add_value_to_dict_entry(dict_entry, 2)
#            self.axis_bottom_label.setEnabled(False)
            self.axis_bottom_entry.setEnabled(False)
#            self.axis_top_label.setEnabled(False)
            self.axis_top_entry.setEnabled(False)
            self.olap_list_entry.setEnabled(True)
            self.axis_group.setEnabled(False)

    def input_button_pressed(self):
        LOG.debug("Input button pressed")
        dir_explore = QFileDialog(self)
        self.input_dir_entry.setText(dir_explore.getExistingDirectory())
        self.set_input_entry()

    def set_input_entry(self):
        add_value_to_dict_entry(EZVARS_aux['stitch360']['input-dir'], str(self.input_dir_entry.text()))

    def output_button_pressed(self):
        LOG.debug("Output button pressed")
        dir_explore = QFileDialog(self)
        self.output_dir_entry.setText(dir_explore.getExistingDirectory())
        self.set_output_entry()

    def set_output_entry(self):
        add_value_to_dict_entry(EZVARS_aux['stitch360']['output-dir'], str(self.output_dir_entry.text()))

    def set_crop_projections_checkbox(self):
        add_value_to_dict_entry(EZVARS_aux['stitch360']['crop'], self.crop_checkbox.isChecked())

    def set_axis_bottom(self):
        add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_min'], int(self.axis_bottom_entry.text()))

    def set_axis_top(self):
        add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_max'], int(self.axis_top_entry.text()))

    def set_olap_type(self):
        add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_switch'], 0)

    def set_olap_list(self):
        vals = self.olap_list_entry.text().split(',')
        if self.check_that_int_failed(vals):
            return
        else:
            add_value_to_dict_entry(EZVARS_aux['stitch360']['olap_list'],
                                    self.olap_list_entry.text())


    def set_axis_group(self):
        if self.axis_group.isChecked():
            self.axis_bottom_label.setEnabled(False)
            self.axis_bottom_entry.setEnabled(False)
            self.axis_top_label.setEnabled(False)
            self.axis_top_entry.setEnabled(False)
        else:
            self.axis_bottom_label.setEnabled(True)
            self.axis_bottom_entry.setEnabled(True)
            self.axis_top_label.setEnabled(True)
            self.axis_top_entry.setEnabled(True)

    def set_z_by_index(self, index):
        entry: QLineEdit = getattr(self, f"axis_z{index:03d}_entry")
        key = f"z{index:03d}"
        LOG.debug(f"{key} axis: {entry.text()}")
        self.update_olap_list()

    def update_olap_list(self):
        EZVARS_aux['stitch360']['olap_list']['value'] = ''
        for i in range(self.num_subdirs):
            try:
                EZVARS_aux['stitch360']['olap_list']['value'] += \
                     (str(int(getattr(self, f"axis_z{i:03d}_entry").text())) + ",")
            except:
                EZVARS_aux['stitch360']['olap_list']['value']=\
                    EZVARS_aux['stitch360']['olap_list']['value'][:-1]
                return

    def stitch_button_pressed(self):
        LOG.debug("Stitch button pressed")
        self.get_fdt_names_on_stitch_pressed.emit()
        if os.path.exists(EZVARS_aux['stitch360']['output-dir']['value']) and \
                    len(os.listdir(EZVARS_aux['stitch360']['output-dir']['value'])) > 0:
            qm = QMessageBox()
            rep = qm.warning(self, '', "Output directory exists and is not empty.")            
            return

        print("======= Begin 360 Multi-Stitch =======")
        main_360_mp_depth2()

        params_file_path = os.path.join(EZVARS_aux['stitch360']['output-dir']['value'],
                                        'ezvars_aux_from_multistitch.yaml')
        export_values(params_file_path, ['ezvars_aux'])

        print("==== Waiting for Next Task ====")
        QMessageBox.information(self, "Finished", "Finished stitching")

    def delete_button_pressed(self):
        LOG.debug("Delete button pressed")
        qm = QMessageBox()
        rep = qm.question(self, '', "Is it safe to delete the output directory?", qm.Yes | qm.No)
        
        if not os.path.exists(EZVARS_aux['stitch360']['output-dir']['value']):
            warning_message("Output directory does not exist")
        elif rep == qm.Yes:
            print("---- Deleting Data From Output Directory ----")
            try:
                rmtree(EZVARS_aux['stitch360']['output-dir']['value'])
            except:
                warning_message("Problems with deleting output directory")
        else:
            return
        
    def help_button_pressed(self):
        LOG.debug("Help button pressed")
        h = "Stitches images horizontally\n"
        h += "Directory structure is, f.i., Input/000, Input/001,...Input/00N\n"
        h += "Each 000, 001, ... 00N directory must have subdirectory(ies) with camera frames\n"
        h += "Frames in each subdirectory will be stitched horizontally in pairs\n"
        h += "and cropped to the same horizontal size of the subdirectory with the largest overlap"
        QMessageBox.information(self, "Help", h)

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

