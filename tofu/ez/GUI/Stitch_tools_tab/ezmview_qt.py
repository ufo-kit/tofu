import os
import logging
from PyQt5.QtWidgets import (
    QGroupBox,
    QPushButton,
    QLineEdit,
    QLabel,
    QCheckBox,
    QGridLayout,
    QFileDialog,
    QMessageBox,
)
import yaml
from tofu.ez.Helpers.mview_main import main_prep


LOG = logging.getLogger(__name__)


class EZMViewGroup(QGroupBox):
    def __init__(self):
        super().__init__()

        self.args = {}
        self.e_indir = ""
        self.e_nproj = 0
        self.e_nflats = 0
        self.e_ndarks = 0
        self.e_nviews = 0
        self.e_noflats2 = False
        self.e_Andor = False

        self.setTitle("Split a sequence of tif files over flats/darks/tomo directories")
        self.setStyleSheet("QGroupBox {color: green;}")

        self.input_dir_button = QPushButton()
        self.input_dir_button.setText("Select directory with a CT sequence")
        self.input_dir_button.clicked.connect(self.select_directory)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.editingFinished.connect(self.set_directory_entry)

        self.num_projections_label = QLabel()
        self.num_projections_label.setText("Number of projections")

        self.num_projections_entry = QLineEdit()
        self.num_projections_entry.editingFinished.connect(self.set_num_projections)

        self.num_flats_label = QLabel()
        self.num_flats_label.setText("Number of flats")

        self.num_flats_entry = QLineEdit()
        self.num_flats_entry.editingFinished.connect(self.set_num_flats)

        self.num_darks_label = QLabel()
        self.num_darks_label.setText("Number of darks")

        self.num_darks_entry = QLineEdit()
        self.num_darks_entry.editingFinished.connect(self.set_num_darks)

        self.num_vert_steps_label = QLabel()
        self.num_vert_steps_label.setText("Number of CT sets in the sequence")

        self.num_vert_steps_entry = QLineEdit()
        self.num_vert_steps_entry.editingFinished.connect(self.set_num_steps)

        self.no_trailing_flats_darks_checkbox = QCheckBox()
        self.no_trailing_flats_darks_checkbox.setText("No trailing flats/darks")
        self.no_trailing_flats_darks_checkbox.stateChanged.connect(self.set_trailing_checkbox)

        self.filenames_without_padding_checkbox = QCheckBox()
        self.filenames_without_padding_checkbox.setText("File names without zero padding")
        self.filenames_without_padding_checkbox.stateChanged.connect(self.set_file_names_checkbox)

        self.help_button = QPushButton()
        self.help_button.setText("Help")
        self.help_button.clicked.connect(self.help_button_pressed)

        self.undo_button = QPushButton()
        self.undo_button.setText("Undo")
        self.undo_button.clicked.connect(self.undo_button_pressed)

        self.convert_button = QPushButton()
        self.convert_button.setText("Convert")
        self.convert_button.clicked.connect(self.convert_button_pressed)
        self.convert_button.setStyleSheet("color:royalblue;font-weight:bold")

        self.save_parameters_button = QPushButton("Save Parameters to File")
        self.save_parameters_button.clicked.connect(self.save_parameters_button_pressed)

        self.import_parameters_button = QPushButton("Import Parameters from File")
        self.import_parameters_button.clicked.connect(self.import_parameters_button_pressed)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.input_dir_button, 0, 0, 1, 3)
        layout.addWidget(self.input_dir_entry, 1, 0, 1, 3)
        layout.addWidget(self.num_projections_label, 2, 0)
        layout.addWidget(self.num_projections_entry, 2, 1, 1, 2)
        layout.addWidget(self.num_flats_label, 3, 0)
        layout.addWidget(self.num_flats_entry, 3, 1, 1, 2)
        layout.addWidget(self.num_darks_label, 4, 0)
        layout.addWidget(self.num_darks_entry, 4, 1, 1, 2)
        layout.addWidget(self.num_vert_steps_label, 5, 0)
        layout.addWidget(self.num_vert_steps_entry, 5, 1, 1, 2)
        layout.addWidget(self.no_trailing_flats_darks_checkbox, 6, 0)
        layout.addWidget(self.filenames_without_padding_checkbox, 6, 1, 1, 2)
        layout.addWidget(self.help_button, 7, 0, 1, 1)
        layout.addWidget(self.undo_button, 7, 1, 1, 1)
        layout.addWidget(self.convert_button, 7, 2, 1, 1)
        layout.addWidget(self.import_parameters_button, 8, 0, 1, 2)
        layout.addWidget(self.save_parameters_button, 8, 2, 1, 1)

        self.setLayout(layout)

    def init_values(self):
        self.parameters = {'parameters_type': 'ez_mview'}
        self.input_dir_entry.setText(os.getcwd())
        self.parameters['ezmview_input_dir'] = os.getcwd()
        self.num_projections_entry.setText("3000")
        self.parameters['ezmview_num_projections'] = 3000
        self.num_flats_entry.setText("10")
        self.parameters['ezmview_num_flats'] = 10
        self.num_darks_entry.setText("10")
        self.parameters['ezmview_num_darks'] = 10
        self.num_vert_steps_entry.setText("1")
        self.parameters['ezmview_num_vertical_steps'] = 1
        self.no_trailing_flats_darks_checkbox.setChecked(False)
        self.parameters['ezmview_flats2'] = False
        self.filenames_without_padding_checkbox.setChecked(False)
        self.parameters['ezmview_zero_padding'] = False

    def update_parameters(self, new_parameters):
        LOG.debug("Update parameters")
        if new_parameters['parameters_type'] != 'ez_mview':
            print("Error: Invalid parameter file type: " + str(new_parameters['parameters_type']))
            return -1
        # Update parameters dictionary (which is passed to auto_stitch_funcs)
        self.parameters = new_parameters
        # Update displayed parameters for GUI
        self.input_dir_entry.setText(str(self.parameters['ezmview_input_dir']))
        self.num_projections_entry.setText(str(self.parameters['ezmview_num_projections']))
        self.num_flats_entry.setText(str(self.parameters['ezmview_num_flats']))
        self.num_darks_entry.setText(str(self.parameters['ezmview_num_darks']))
        self.num_vert_steps_entry.setText(str(self.parameters['ezmview_num_vertical_steps']))
        self.no_trailing_flats_darks_checkbox.setChecked(bool(self.parameters['ezmview_flats2']))
        self.filenames_without_padding_checkbox.setChecked(bool(self.parameters['ezmview_zero_padding']))

    def select_directory(self):
        LOG.debug("Select directory button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(directory)
        self.parameters['ezmview_input_dir'] = directory

    def set_directory_entry(self):
        LOG.debug("Directory entry: " + str(self.input_dir_entry.text()))
        self.parameters['ezmview_input_dir'] = str(self.input_dir_entry.text())

    def set_num_projections(self):
        LOG.debug("Num projections: " + str(self.num_projections_entry.text()))
        self.parameters['ezmview_num_projections'] = int(self.num_projections_entry.text())

    def set_num_flats(self):
        LOG.debug("Num flats: " + str(self.num_flats_entry.text()))
        self.parameters['ezmview_num_flats'] = int(self.num_flats_entry.text())

    def set_num_darks(self):
        LOG.debug("Num darks: " + str(self.num_darks_entry.text()))
        self.parameters['ezmview_num_darks'] = int(self.num_darks_entry.text())

    def set_num_steps(self):
        LOG.debug("Num steps: " + str(self.num_vert_steps_entry.text()))
        self.parameters['ezmview_num_vertical_steps'] = int(self.num_vert_steps_entry.text())

    def set_trailing_checkbox(self):
        LOG.debug("No trailing: " + str(self.no_trailing_flats_darks_checkbox.isChecked()))
        self.parameters['ezmview_flats2'] = bool(self.no_trailing_flats_darks_checkbox.isChecked())

    def set_file_names_checkbox(self):
        LOG.debug("File names without zero padding: " +
                      str(self.filenames_without_padding_checkbox.isChecked()))
        self.parameters['ezmview_zero_padding'] = \
            bool(self.filenames_without_padding_checkbox.isChecked())

    def convert_button_pressed(self):
        LOG.debug("Convert button pressed")
        LOG.debug(self.parameters)
        main_prep(self.parameters)

    def undo_button_pressed(self):
        LOG.debug("Undo button pressed")
        cmd = "find {} -type f -name \"*.tif\" -exec mv -t {} {{}} +"
        cmd = cmd.format(str(self.parameters['ezmview_input_dir']), str(self.parameters['ezmview_input_dir']))
        os.system(cmd)

    def help_button_pressed(self):
        LOG.debug("Help button pressed")
        h = "Distributes a sequence of CT frames in flats/darks/tomo/flats2 directories\n"
        h += "assuming that acqusition sequence is flats->darks->tomo->flats2\n"
        h += 'Use only for sequences with flat fields acquired at 0 and 180!\n'
        h += "Conversions happens in-place but can be undone"
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


