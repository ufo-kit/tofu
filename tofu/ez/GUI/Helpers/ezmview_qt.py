import os
import logging
from PyQt5.QtWidgets import QGroupBox, QPushButton, QLineEdit, QLabel, QCheckBox, QGridLayout, QFileDialog, QMessageBox
from tofu.ez.Helpers.mview_main import main_prep

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

        self.setTitle("EZMView")
        self.setStyleSheet('QGroupBox {color: green;}')

        self.input_dir_button = QPushButton()
        self.input_dir_button.setText("Select directory with a CT sequence")
        self.input_dir_button.clicked.connect(self.select_directory)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.textChanged.connect(self.set_directory_entry)

        self.num_projections_label = QLabel()
        self.num_projections_label.setText("Number of projections")

        self.num_projections_entry = QLineEdit()
        self.num_projections_entry.textChanged.connect(self.set_num_projections)

        self.num_flats_label = QLabel()
        self.num_flats_label.setText("Number of flats")

        self.num_flats_entry = QLineEdit()
        self.num_flats_entry.textChanged.connect(self.set_num_flats)

        self.num_darks_label = QLabel()
        self.num_darks_label.setText("Number of darks")

        self.num_darks_entry = QLineEdit()
        self.num_darks_entry.textChanged.connect(self.set_num_darks)

        self.num_vert_steps_label = QLabel()
        self.num_vert_steps_label.setText("Number of vertical steps")

        self.num_vert_steps_entry = QLineEdit()
        self.num_vert_steps_entry.textChanged.connect(self.set_num_steps)

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
        self.setLayout(layout)

    def init_values(self):
        self.input_dir_entry.setText(os.getcwd())
        self.e_indir = os.getcwd()
        self.num_projections_entry.setText("3000")
        self.e_nproj = 3000
        self.num_flats_entry.setText("10")
        self.e_nflats = 10
        self.num_darks_entry.setText("10")
        self.e_ndarks = 10
        self.num_vert_steps_entry.setText("1")
        self.e_nviews = 1
        self.no_trailing_flats_darks_checkbox.setChecked(False)
        self.e_noflats2 = False
        self.filenames_without_padding_checkbox.setChecked(False)
        self.e_Andor = False

    def select_directory(self):
        logging.debug("Select directory button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(directory)
        self.e_indir = directory

    def set_directory_entry(self):
        logging.debug("Directory entry: " + str(self.input_dir_entry.text()))
        self.e_indir = str(self.input_dir_entry.text())

    def set_num_projections(self):
        logging.debug("Num projections: " + str(self.num_projections_entry.text()))
        self.e_nproj = int(self.num_projections_entry.text())

    def set_num_flats(self):
        logging.debug("Num flats: " + str(self.num_flats_entry.text()))
        self.e_nflats = int(self.num_flats_entry.text())

    def set_num_darks(self):
        logging.debug("Num darks: " + str(self.num_darks_entry.text()))
        self.e_ndarks = int(self.num_darks_entry.text())

    def set_num_steps(self):
        logging.debug("Num steps: " + str(self.num_vert_steps_entry.text()))
        self.e_nviews = int(self.num_vert_steps_entry.text())

    def set_trailing_checkbox(self):
        logging.debug("No trailing: " + str(self.no_trailing_flats_darks_checkbox.isChecked()))
        self.e_noflats2 = bool(self.no_trailing_flats_darks_checkbox.isChecked())

    def set_file_names_checkbox(self):
        logging.debug("File names without zero padding: " + str(self.filenames_without_padding_checkbox.isChecked()))
        self.e_Andor = bool(self.filenames_without_padding_checkbox.isChecked())

    def convert_button_pressed(self):
        logging.debug("Convert button pressed")
        self.args['input'] = str(self.e_indir)
        setattr(self, 'input', self.args['input'])
        self.args['output'] = str(self.e_indir)
        setattr(self, 'output', self.args['output'])
        self.args['nproj'] = int(self.e_nproj)
        setattr(self, 'nproj', self.args['nproj'])
        self.args['nflats'] = int(self.e_nflats)
        setattr(self, 'nflats', self.args['nflats'])
        self.args['ndarks'] = int(self.e_ndarks)
        setattr(self, 'ndarks', self.args['ndarks'])
        self.args['nviews'] = int(self.e_nviews)
        setattr(self, 'nviews', self.args['nviews'])
        self.args['noflats2'] = bool(int(self.e_noflats2))
        setattr(self, 'noflats2', self.args['noflats2'])
        self.args['Andor'] = bool(int(self.e_Andor))
        setattr(self, 'Andor', self.args['Andor'])

        logging.debug(self.args)
        main_prep(self)

    def undo_button_pressed(self):
        logging.debug("Undo button pressed")
        cmd = "find {} -type f -name \"*.tif\" -exec mv -t {} {{}} +"
        cmd = cmd.format(str(self.e_indir), str(self.e_indir))
        os.system(cmd)

    def help_button_pressed(self):
        logging.debug("Help button pressed")
        h = "Distributes a sequence of CT frames in flats/darks/tomo/flats2 directories\n"
        h += "assuming that acqusition sequence is flats->darks->tomo->flats2\n"
        h += 'Use only for sequences with flat fields acquired at 0 and 180!\n'
        h += "Conversions happens in-place but can be undone"
        QMessageBox.information(self, "Help", h)

class tk_args():
    def __init__(self, e_input, e_output, e_tmpdir, e_ax1, e_ax2, e_ax, e_crop):

        self.args={}
        # directories
        self.args['input']=str(e_input.get())
        setattr(self, 'input', self.args['input'])
        self.args['output'] = str(e_output.get())
        setattr(self, 'output', self.args['output'])
        self.args['tmpdir'] = str(e_tmpdir.get())
        setattr(self, 'tmpdir', self.args['tmpdir'])
        #hor stitch half acq mode
        self.args['ax1'] = int(e_ax1.get())
        setattr(self, 'ax1', self.args['ax1'])
        self.args['ax2'] = int(e_ax2.get())
        setattr(self, 'ax2', self.args['ax2'])
        self.args['ax'] = int(e_ax.get())
        setattr(self, 'ax', self.args['ax'])
        self.args['crop'] = int(e_crop.get())
        setattr(self, 'crop', self.args['crop'])


