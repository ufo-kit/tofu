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
from tofu.ez.Helpers.find_360_overlap import find_overlap
from tofu.ez.params import EZVARS_aux
from tofu.ez.util import add_value_to_dict_entry
from tofu.ez.util import import_values, export_values
import yaml

#TODO Make all stitching tools compatible with the bigtiffs


LOG = logging.getLogger(__name__)

class Overlap360Group(QGroupBox):
    get_fdt_names_on_stitch_pressed = pyqtSignal()
    get_RR_params_on_start_pressed = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.setTitle("360-AXIS-SEARCH: find overlap in half acq. mode CT sets. Finds all CT sets in Input recursively.")
        self.setToolTip("Stitches and reconstructs one slice with different axis of rotation positions for half-acqusition mode data set(s)")
        self.setStyleSheet('QGroupBox {color: Orange;}')

        self.input_dir_button = QPushButton("Select input directory")
        self.input_dir_button.clicked.connect(self.input_button_pressed)
        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.editingFinished.connect(self.set_input_entry)

        self.temp_dir_button = QPushButton("Select temp directory")
        self.temp_dir_button.clicked.connect(self.temp_button_pressed)
        self.temp_dir_entry = QLineEdit()
        self.temp_dir_entry.editingFinished.connect(self.set_temp_entry)

        self.output_dir_button = QPushButton("Select output directory")
        self.output_dir_button.clicked.connect(self.output_button_pressed)
        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.editingFinished.connect(self.set_output_entry)

        self.pixel_row_label = QLabel("Row to be reconstructed")
        self.pixel_row_label.setToolTip("TEST")
        self.pixel_row_entry = QLineEdit()
        self.pixel_row_entry.editingFinished.connect(self.set_pixel_row)

        self.patch_size_label = QLabel("Patch size")
        self.patch_size_label.setToolTip(EZVARS_aux['find360olap']['patch-size']['help'])
        self.patch_size_entry = QLineEdit()
        self.patch_size_entry.editingFinished.connect(self.set_patch_size)
        self.patch_size_entry.setToolTip(EZVARS_aux['find360olap']['patch-size']['help'])

        self.row1_dummy_label1 = QLabel("\t")
        self.row1_dummy_label2 = QLabel("\t")
        
        self.doRR = QCheckBox("Apply ring removal")
        #self.doRR.setEnabled(False)
        self.doRR.stateChanged.connect(self.set_RR_checkbox)

        self.range_label = QLabel("Overlap range for axis search:")

        self.min_label = QLabel("\tStart")
        self.min_entry = QLineEdit()
        self.min_entry.editingFinished.connect(self.set_lower_limit)

        self.max_label = QLabel("Stop")
        self.max_entry = QLineEdit()
        self.max_entry.editingFinished.connect(self.set_upper_limit)

        self.step_label = QLabel("Step")
        self.step_entry = QLineEdit()
        self.step_entry.editingFinished.connect(self.set_increment)

        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.help_button_pressed)

        self.find_overlap_button = QPushButton("Generate slices")
        self.find_overlap_button.clicked.connect(self.overlap_button_pressed)
        self.find_overlap_button.setStyleSheet("color:royalblue;font-weight:bold")

        self.import_parameters_button = QPushButton("Import Parameters from File")
        self.import_parameters_button.clicked.connect(self.import_parameters_button_pressed)

        self.save_parameters_button = QPushButton("Save Parameters to File")
        self.save_parameters_button.clicked.connect(self.save_parameters_button_pressed)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        # layout.addWidget(self.input_dir_button, 0, 0, 1, 2)
        # layout.addWidget(self.input_dir_entry, 1, 0, 1, 2)
        # layout.addWidget(self.temp_dir_button, 2, 0, 1, 2)
        # layout.addWidget(self.temp_dir_entry, 3, 0, 1, 2)
        # layout.addWidget(self.output_dir_button, 4, 0, 1, 2)
        # layout.addWidget(self.output_dir_entry, 5, 0, 1, 2)
        # layout.addWidget(self.pixel_row_label, 6, 0)
        # layout.addWidget(self.pixel_row_entry, 6, 1)
        # layout.addWidget(self.min_label, 7, 0)
        # layout.addWidget(self.min_entry, 7, 1)
        # layout.addWidget(self.max_label, 8, 0)
        # layout.addWidget(self.max_entry, 8, 1)
        # layout.addWidget(self.step_label, 9, 0)
        # layout.addWidget(self.step_entry, 9, 1)
        # layout.addWidget(self.patch_size_label, 10, 0)
        # layout.addWidget(self.patch_size_entry, 10, 1)
        # layout.addWidget(self.doRR, 11, 0)
        # layout.addWidget(self.help_button, 12, 0)
        # layout.addWidget(self.find_overlap_button, 12, 1)
        # layout.addWidget(self.import_parameters_button, 13, 0)
        # layout.addWidget(self.save_parameters_button, 13, 1)
        
        layout.addWidget(self.input_dir_button, 0, 0, 1, 1)
        layout.addWidget(self.input_dir_entry, 0, 1, 1, 6)
        layout.addWidget(self.temp_dir_button, 1, 0, 1, 1)
        layout.addWidget(self.temp_dir_entry, 1, 1, 1, 6)
        layout.addWidget(self.output_dir_button, 2, 0, 1, 1)
        layout.addWidget(self.output_dir_entry, 2, 1, 1, 6)
        # 
        l = 3
        layout.addWidget(self.range_label, l, 0)
        layout.addWidget(self.min_label, l, 1)
        layout.addWidget(self.min_entry, l, 2)
        layout.addWidget(self.max_label, l, 3)
        layout.addWidget(self.max_entry, l, 4)
        layout.addWidget(self.step_label, l, 5)
        layout.addWidget(self.step_entry, l, 6)
        #
        l = 4
        layout.addWidget(self.pixel_row_label, l, 0)
        layout.addWidget(self.pixel_row_entry, l, 1)
        layout.addWidget(self.row1_dummy_label1, l, 2)
        layout.addWidget(self.patch_size_label, l, 3)
        layout.addWidget(self.patch_size_entry, l, 4)
        layout.addWidget(self.row1_dummy_label2, l, 5)
        layout.addWidget(self.doRR, l, 6)
        #
        l = 5
        layout.addWidget(self.help_button, l, 0, 1, 1)
        layout.addWidget(self.import_parameters_button, l, 1, 1, 2)
        layout.addWidget(self.save_parameters_button, l, 3, 1, 2)
        layout.addWidget(self.find_overlap_button, l, 5, 1, 2)
        self.setLayout(layout)

    def load_values(self):
        self.input_dir_entry.setText(str(EZVARS_aux['find360olap']['input-dir']['value']))
        self.temp_dir_entry.setText(str(EZVARS_aux['find360olap']['tmp-dir']['value']))
        self.output_dir_entry.setText(str(EZVARS_aux['find360olap']['output-dir']['value']))
        self.pixel_row_entry.setText(str(EZVARS_aux['find360olap']['row']['value']))
        self.min_entry.setText(str(EZVARS_aux['find360olap']['start']['value']))
        self.max_entry.setText(str(EZVARS_aux['find360olap']['stop']['value']))
        self.step_entry.setText(str(EZVARS_aux['find360olap']['step']['value']))
        self.patch_size_entry.setText(str(EZVARS_aux['find360olap']['patch-size']['value']))
        self.doRR.setChecked(EZVARS_aux['find360olap']['doRR']['value'])

    def input_button_pressed(self):
        LOG.debug("Select input button pressed")
        dir_explore = QFileDialog(self)
        tmp = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(tmp)
        add_value_to_dict_entry(EZVARS_aux['find360olap']['input-dir'], tmp)

    def set_input_entry(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['input-dir'], str(self.input_dir_entry.text()))

    def temp_button_pressed(self):
        dir_explore = QFileDialog(self)
        tmp = dir_explore.getExistingDirectory()
        self.temp_dir_entry.setText(tmp)
        add_value_to_dict_entry(EZVARS_aux['find360olap']['tmp-dir'], tmp)

    def set_temp_entry(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['tmp-dir'], str(self.temp_dir_entry.text()))

    def output_button_pressed(self):
        LOG.debug("Select output button pressed")
        dir_explore = QFileDialog(self)
        tmp = dir_explore.getExistingDirectory()
        self.output_dir_entry.setText(tmp)
        add_value_to_dict_entry(EZVARS_aux['find360olap']['output-dir'], tmp)

    def set_output_entry(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['output-dir'], str(self.output_dir_entry.text()))

    def set_pixel_row(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['row'], int(self.pixel_row_entry.text()))

    def set_lower_limit(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['start'], int(self.min_entry.text()))

    def set_upper_limit(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['stop'], int(self.max_entry.text()))

    def set_increment(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['step'], int(self.step_entry.text()))

    def set_patch_size(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['patch-size'],
                                int(self.patch_size_entry.text()))
    def set_RR_checkbox(self):
        add_value_to_dict_entry(EZVARS_aux['find360olap']['doRR'], self.doRR.isChecked())

    def overlap_button_pressed(self):
        LOG.debug("Find overlap button pressed")
        print("Find overlap button pressed")
        self.get_fdt_names_on_stitch_pressed.emit()
        self.get_RR_params_on_start_pressed.emit()
        if os.path.exists(EZVARS_aux['find360olap']['output-dir']['value']) and \
                    len(os.listdir(EZVARS_aux['find360olap']['output-dir']['value'])) > 0:
            qm = QMessageBox()
            rep = qm.question(self, 'WARNING',
                              "Output directory exists and not empty. Is it SAFE to delete it?",
                              qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(EZVARS_aux['find360olap']['output-dir']['value'])
                except:
                    QMessageBox.information(self, "Problem", "Cannot delete existing output dir")
                    return
            else:
                return
        if os.path.exists(EZVARS_aux['find360olap']['tmp-dir']['value']) and \
                len(os.listdir(EZVARS_aux['find360olap']['tmp-dir']['value'])) > 0:
            qm = QMessageBox()
            rep = qm.question(self, 'WARNING', "Temporary dir exist and not empty. Is it SAFE to delete it?", qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(EZVARS_aux['find360olap']['tmp-dir']['value'])
                except:
                    QMessageBox.information(self, "Problem", "Cannot delete existing tmp dir")
                    return
            else:
                return
        if not os.path.exists(EZVARS_aux['find360olap']['tmp-dir']['value']):
            os.makedirs(EZVARS_aux['find360olap']['tmp-dir']['value'])
        if not os.path.exists(EZVARS_aux['find360olap']['output-dir']['value']):
            os.makedirs(EZVARS_aux['find360olap']['output-dir']['value'])
        find_overlap()
        params_file_path = os.path.join(EZVARS_aux['find360olap']['output-dir']['value'],
                                            'ezvars_aux_from_overlap_search.yaml')
        if export_values(params_file_path, ['ezvars_aux']):
            QMessageBox.information(self, "Problem", "Cannot export to yaml file")
        else:
            QMessageBox.information(self, "Done", "List of processed directories and "
                                                  "overlap estimates saved in \n"
                                                  f"{params_file_path}")


    def help_button_pressed(self):
        LOG.debug("Help button pressed")
        h = "This script helps to find the index of detector column in with tomographic axis of rotation "
        h += "situated during half acq. mode scan (or overlap between pairs of images separate by 180 deg)"
        h += "Input can be a bunch of CT scans that has been collected in 'half-acquisition' mode"
        h += "For each CT set for selected detector row this script will reconstruct a bunch of slices"
        h += "each for different amount of overlap in the user defined range."
        h += "The objective is to review this series of images and find the best looking slice"
        h += "in the very much the same way as it is done when you search for axis of rotation in normal scans"
        h += "The overlap can be computed by adding the index of the right slice (times the search step)"
        h += "to the first overlap value in the search range."
        h += "Script attempts to estimate the overlap and saves the value for each data set in the"
        h += "360_overlap_params.yaml in the ezvars_aux section. They can be used as an input for"
        h += "batch stitching of the half acq mode data. User can edit the values directly in the"
        h += "yaml file if needed."
        QMessageBox.information(self, "Help", h)

    def import_parameters_button_pressed(self):
        LOG.debug("Import params button clicked")
        dir_explore = QFileDialog(self)
        params_file_path = dir_explore.getOpenFileName(filter="*.yaml")
        try:
            import_values(params_file_path[0], ['ezvars_aux'])
            self.load_values()
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
            export_values(file_path, ['ezvars_aux'])
            print("Parameters file saved at: " + str(file_path))
        except FileNotFoundError:
            print("You need to select a directory and use a valid file name")

