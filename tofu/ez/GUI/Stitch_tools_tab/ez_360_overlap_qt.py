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
import yaml
import os
from tofu.ez.Helpers.find_360_overlap import find_overlap
import tofu.ez.params as params
import getpass

#TODO Make all stitching tools compatible with the bigtiffs


LOG = logging.getLogger(__name__)

class Overlap360Group(QGroupBox):
    get_fdt_names_on_stitch_pressed = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.setTitle("Reconstruct one slice with different axis of rotation positions for half-acqusition mode data set(s)")
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

        self.pixel_row_label = QLabel("Pixel row to be used for sinogram")
        self.pixel_row_entry = QLineEdit()
        self.pixel_row_entry.editingFinished.connect(self.set_pixel_row)

        self.min_label = QLabel("Lower limit of stitch/axis search range")
        self.min_entry = QLineEdit()
        self.min_entry.editingFinished.connect(self.set_lower_limit)

        self.max_label = QLabel("Upper limit of stitch/axis search range")
        self.max_entry = QLineEdit()
        self.max_entry.editingFinished.connect(self.set_upper_limit)

        self.step_label = QLabel("Value by which to increment through search range")
        self.step_entry = QLineEdit()
        self.step_entry.editingFinished.connect(self.set_increment)

        self.axis_on_left = QCheckBox("Apply ring removal")
        self.axis_on_left.setEnabled(False)
        self.axis_on_left.stateChanged.connect(self.set_axis_checkbox)

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
        layout.addWidget(self.input_dir_button, 0, 0, 1, 2)
        layout.addWidget(self.input_dir_entry, 1, 0, 1, 2)
        layout.addWidget(self.temp_dir_button, 2, 0, 1, 2)
        layout.addWidget(self.temp_dir_entry, 3, 0, 1, 2)
        layout.addWidget(self.output_dir_button, 4, 0, 1, 2)
        layout.addWidget(self.output_dir_entry, 5, 0, 1, 2)
        layout.addWidget(self.pixel_row_label, 6, 0)
        layout.addWidget(self.pixel_row_entry, 6, 1)
        layout.addWidget(self.min_label, 7, 0)
        layout.addWidget(self.min_entry, 7, 1)
        layout.addWidget(self.max_label, 8, 0)
        layout.addWidget(self.max_entry, 8, 1)
        layout.addWidget(self.step_label, 9, 0)
        layout.addWidget(self.step_entry, 9, 1)
        layout.addWidget(self.axis_on_left, 10, 0)
        layout.addWidget(self.help_button, 11, 0)
        layout.addWidget(self.find_overlap_button, 11, 1)
        layout.addWidget(self.import_parameters_button, 12, 0)
        layout.addWidget(self.save_parameters_button, 12, 1)
        self.setLayout(layout)

    def init_values(self):
        self.parameters = {'parameters_type': '360_overlap'}
        self.parameters['360overlap_input_dir'] = os.path.expanduser('~')
        self.input_dir_entry.setText(self.parameters['360overlap_input_dir'])
        self.parameters['360overlap_temp_dir'] = os.path.join(
                        os.path.expanduser('~'), "tmp-360axis-search")
        self.temp_dir_entry.setText(self.parameters['360overlap_temp_dir'])
        self.parameters['360overlap_output_dir'] = os.path.join(
                        os.path.expanduser('~'), "ezufo-360axis-search")
        self.output_dir_entry.setText(self.parameters['360overlap_output_dir'])
        self.parameters['360overlap_row'] = 200
        self.pixel_row_entry.setText(str(self.parameters['360overlap_row']))
        self.parameters['360overlap_lower_limit'] = 100
        self.min_entry.setText(str(self.parameters['360overlap_lower_limit']))
        self.parameters['360overlap_upper_limit'] = 200
        self.max_entry.setText(str(self.parameters['360overlap_upper_limit']))
        self.parameters['360overlap_increment'] = 1
        self.step_entry.setText(str(self.parameters['360overlap_increment']))
        self.parameters['360overlap_axis_on_left'] = True
        self.axis_on_left.setChecked(bool(self.parameters['360overlap_axis_on_left']))

    def update_parameters(self, new_parameters):
        LOG.debug("Update parameters")
        if new_parameters['parameters_type'] != '360_overlap':
            print("Error: Invalid parameter file type: " + str(new_parameters['parameters_type']))
            return -1
        # Update parameters dictionary (which is passed to auto_stitch_funcs)
        self.parameters = new_parameters
        # Update displayed parameters for GUI
        self.input_dir_entry.setText(self.parameters['360overlap_input_dir'])
        self.temp_dir_entry.setText(self.parameters['360overlap_temp_dir'])
        self.output_dir_entry.setText(self.parameters['360overlap_output_dir'])
        self.pixel_row_entry.setText(str(self.parameters['360overlap_row']))
        self.min_entry.setText(str(self.parameters['360overlap_lower_limit']))
        self.max_entry.setText(str(self.parameters['360overlap_upper_limit']))
        self.step_entry.setText(str(self.parameters['360overlap_increment']))
        self.axis_on_left.setChecked(bool(self.parameters['360overlap_axis_on_left']))

    def input_button_pressed(self):
        LOG.debug("Select input button pressed")
        dir_explore = QFileDialog(self)
        self.parameters['360overlap_input_dir'] = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(self.parameters['360overlap_input_dir'])

    def set_input_entry(self):
        LOG.debug("Input: " + str(self.input_dir_entry.text()))
        self.parameters['360overlap_input_dir'] = str(self.input_dir_entry.text())

    def temp_button_pressed(self):
        LOG.debug("Select temp button pressed")
        dir_explore = QFileDialog(self)
        self.parameters['360overlap_temp_dir'] = dir_explore.getExistingDirectory()
        self.temp_dir_entry.setText(self.parameters['360overlap_temp_dir'])

    def set_temp_entry(self):
        LOG.debug("Temp: " + str(self.temp_dir_entry.text()))
        self.parameters['360overlap_temp_dir'] = str(self.temp_dir_entry.text())

    def output_button_pressed(self):
        LOG.debug("Select output button pressed")
        dir_explore = QFileDialog(self)
        self.parameters['360overlap_output_dir'] = dir_explore.getExistingDirectory()
        self.output_dir_entry.setText(self.parameters['360overlap_output_dir'])

    def set_output_entry(self):
        LOG.debug("Output: " + str(self.output_dir_entry.text()))
        self.parameters['360overlap_output_dir'] = str(self.output_dir_entry.text())

    def set_pixel_row(self):
        LOG.debug("Pixel row: " + str(self.pixel_row_entry.text()))
        self.parameters['360overlap_row'] = int(self.pixel_row_entry.text())

    def set_lower_limit(self):
        LOG.debug("Lower limit: " + str(self.min_entry.text()))
        self.parameters['360overlap_lower_limit'] = int(self.min_entry.text())

    def set_upper_limit(self):
        LOG.debug("Upper limit: " + str(self.max_entry.text()))
        self.parameters['360overlap_upper_limit'] = int(self.max_entry.text())

    def set_increment(self):
        LOG.debug("Value of increment: " + str(self.step_entry.text()))
        self.parameters['360overlap_increment'] = int(self.step_entry.text())

    def set_axis_checkbox(self):
        LOG.debug("Is rotation axis on left-hand-side?: " + str(self.axis_on_left.isChecked()))
        self.parameters['360overlap_axis_on_left'] = bool(self.axis_on_left.isChecked())

    def overlap_button_pressed(self):
        LOG.debug("Find overlap button pressed")
        if os.path.exists(self.parameters['360overlap_output_dir']) or \
                os.path.exists(self.parameters['360overlap_temp_dir']):
            qm = QMessageBox()
            rep = qm.question(self, '', "Output directory or(and) temporary dir exist. Can I delete both?", qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(self.parameters['360overlap_output_dir'])
                    rmtree(self.parameters['360overlap_temp_dir'])
                except:
                    pass
            else:
                return
        os.makedirs(self.parameters['360overlap_temp_dir'])
        os.makedirs(self.parameters['360overlap_output_dir'])
        find_overlap(self.parameters)
        if os.path.exists(self.parameters['360overlap_output_dir']):
            params_file_path = os.path.join(self.parameters['360overlap_output_dir'], '360_overlap_params.yaml')
            params.save_parameters(self.parameters, params_file_path)


    def help_button_pressed(self):
        LOG.debug("Help button pressed")
        h = "This script takes as input a CT scan that has been collected in 'half-acquisition' mode"
        h += " and produces a series of reconstructed slices, each of which are generated by cropping and"
        h += " concatenating opposing projections together over a range of 'overlap' values (i.e. the pixel column"
        h += " at which the images are cropped and concatenated)."
        h += " The objective is to review this series of images to determine the pixel column at which the axis of rotation"
        h += " is located (much like the axis search function commonly used in reconstruction software)."
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

