from PyQt5.QtWidgets import QGroupBox, QPushButton, QCheckBox, QLabel, QLineEdit, QGridLayout, QFileDialog, QMessageBox
import logging
import os
import getpass
from tofu.ez.Helpers.stitch_funcs import main_360_mp_depth2

class MultiStitch360Group(QGroupBox):

    def __init__(self):
        super().__init__()

        self.args = {}
        self.e_input = ""
        self.e_output = ""
        self.e_tmpdir = ""
        self.e_ax1 = 0
        self.e_ax2 = 0
        self.e_ax = 0
        self.e_ax = 0
        self.e_crop = 0

        self.setTitle("360 Multi Stitch")
        self.setStyleSheet('QGroupBox {color: red;}')

        self.input_dir_button = QPushButton()
        self.input_dir_button.setText("Select input directory")
        self.input_dir_button.clicked.connect(self.input_button_pressed)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.textChanged.connect(self.set_input_entry)

        self.temp_dir_button = QPushButton()
        self.temp_dir_button.setText("Select temporary directory - default value recommended")
        self.temp_dir_button.clicked.connect(self.temp_button_pressed)

        self.temp_dir_entry = QLineEdit()
        self.temp_dir_entry.textChanged.connect(self.set_temp_entry)

        self.output_dir_button = QPushButton()
        self.output_dir_button.setText("Directory to save stitched images")
        self.output_dir_button.clicked.connect(self.output_button_pressed)

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.textChanged.connect(self.set_output_entry)

        self.crop_checkbox = QCheckBox()
        self.crop_checkbox.setText("Crop all projections to match the width of smallest stitched projection")
        self.crop_checkbox.clicked.connect(self.set_crop_projections_checkbox)

        self.axis_bottom_label = QLabel()
        self.axis_bottom_label.setText("Axis of Rotation at bottom (z00):")

        self.axis_bottom_entry = QLineEdit()
        self.axis_bottom_entry.textChanged.connect(self.set_axis_bottom)

        self.axis_top_label = QLabel()
        self.axis_top_label.setText("Axis of Rotation at top (ignored if not multi-slice):")

        self.axis_top_entry = QLineEdit()
        self.axis_top_entry.textChanged.connect(self.set_axis_top)

        self.stitch_button = QPushButton()
        self.stitch_button.setText("Stitch")
        self.stitch_button.clicked.connect(self.stitch_button_pressed)
        self.stitch_button.setStyleSheet("color:royalblue;font-weight:bold")

        self.delete_button = QPushButton()
        self.delete_button.setText("Delete output dir")
        self.delete_button.clicked.connect(self.delete_button_pressed)

        self.help_button = QPushButton()
        self.help_button.setText("Help")
        self.help_button.clicked.connect(self.help_button_pressed)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.input_dir_button, 0, 0, 1, 3)
        layout.addWidget(self.input_dir_entry, 1, 0, 1, 3)
        layout.addWidget(self.temp_dir_button, 2, 0, 1, 3)
        layout.addWidget(self.temp_dir_entry, 3, 0, 1, 3)
        layout.addWidget(self.output_dir_button, 4, 0, 1, 3)
        layout.addWidget(self.output_dir_entry, 5, 0, 1, 3)
        layout.addWidget(self.crop_checkbox, 6, 0, 1, 3)
        layout.addWidget(self.axis_bottom_label, 7, 0, 1, 2)
        layout.addWidget(self.axis_bottom_entry, 7, 2, 1, 1)
        layout.addWidget(self.axis_top_label, 8, 0, 1, 2)
        layout.addWidget(self.axis_top_entry, 8, 2, 1, 1)
        layout.addWidget(self.help_button, 9, 0)
        layout.addWidget(self.delete_button, 9, 1)
        layout.addWidget(self.stitch_button, 9, 2)

        self.setLayout(layout)

    def init_values(self):
        self.input_dir_entry.setText(os.getcwd())
        self.e_input = os.getcwd()
        tmp = os.path.join("/data", "tmp-ezstitch-" + getpass.getuser())
        self.temp_dir_entry.setText(tmp)
        self.e_tmpdir = tmp
        self.output_dir_entry.setText(os.getcwd() + '-stitched')
        self.e_output = os.getcwd() + '-stitched'
        self.crop_checkbox.setChecked(True)
        self.e_crop = True
        self.axis_bottom_entry.setText("245")
        self.e_ax1 = 245
        self.axis_top_entry.setText("245")
        self.e_ax2 = 245
        self.e_ax = self.e_ax1

    def input_button_pressed(self):
        logging.debug("Input button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(directory)
        self.e_input = directory

    def set_input_entry(self):
        logging.debug("Input directory: " + str(self.input_dir_entry.text()))
        self.e_input = str(self.input_dir_entry.text())

    def temp_button_pressed(self):
        logging.debug("Temp button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.temp_dir_entry.setText(directory)
        self.e_tmpdir = directory

    def set_temp_entry(self):
        logging.debug("Temp directory: " + str(self.temp_dir_entry.text()))
        self.e_tmpdir = str(self.temp_dir_entry.text())

    def output_button_pressed(self):
        logging.debug("Output button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.output_dir_entry.setText(directory)
        self.e_output = directory

    def set_output_entry(self):
        logging.debug("Output directory: " + str(self.output_dir_entry.text()))
        self.e_output = str(self.output_dir_entry.text())

    def set_crop_projections_checkbox(self):
        logging.debug("Crop projections: " + str(self.crop_checkbox.isChecked()))
        self.e_crop = bool(self.crop_checkbox.isChecked())

    def set_axis_bottom(self):
        logging.debug("Axis Bottom : " + str(self.axis_bottom_entry.text()))
        self.e_ax1 = int(self.axis_bottom_entry.text())

    def set_axis_top(self):
        logging.debug("Axis Top: " + str(self.axis_top_entry.text()))
        self.e_ax2 = int(self.axis_top_entry.text())

    def stitch_button_pressed(self):
        logging.debug("Stitch button pressed")
        args = tk_args(self.e_input, self.e_output, self.e_tmpdir, self.e_ax1, self.e_ax2, self.e_ax, self.e_crop)

        if os.path.exists(self.e_tmpdir):
            os.system('rm -r {}'.format(self.e_tmpdir))

        if os.path.exists(self.e_output):
            raise ValueError('Output directory exists')

        print("")
        print("======= Begin 360 Multi-Stitch =======")
        main_360_mp_depth2(args)
        print("==== Waiting for Next Task ====")

    #TODO Call cleanup function if application is closed

    #TODO Add JRavs dropdown menu option

    def delete_button_pressed(self):
        logging.debug("Delete button pressed")
        if os.path.exists(self.e_output):
            os.system('rm -r {}'.format(self.e_output))
            print(" - Directory with reconstructed data was removed")

    def help_button_pressed(self):
        logging.debug("Help button pressed")
        h = "Stitches images horizontally\n"
        h += "Directory structure is, f.i., Input/000, Input/001,...Input/00N\n"
        h += "Each 000, 001, ... 00N directory must have identical subdirectory \"Type\"\n"
        h += "Selected range of images from \"Type\" directory will be stitched vertically\n"
        h += "across all subdirectories in the Input directory"
        h += "to be added as options:\n"
        h += "(1) orthogonal reslicing, (2) interpolation, (3) horizontal stitching"
        QMessageBox.information(self, "Help", h)

class tk_args():
    def __init__(self, e_input, e_output, e_tmpdir, e_ax1, e_ax2, e_ax, e_crop):

        self.args={}
        # directories
        self.args['input'] = str(e_input)
        setattr(self, 'input', self.args['input'])
        self.args['output'] = str(e_output)
        setattr(self, 'output', self.args['output'])
        self.args['tmpdir'] = str(e_tmpdir)
        setattr(self, 'tmpdir', self.args['tmpdir'])
        #hor stitch half acq mode
        self.args['ax1'] = int(e_ax1)
        setattr(self, 'ax1', self.args['ax1'])
        self.args['ax2'] = int(e_ax2)
        setattr(self, 'ax2', self.args['ax2'])
        self.args['ax'] = int(e_ax)
        setattr(self, 'ax', self.args['ax'])
        self.args['crop'] = int(e_crop)
        setattr(self, 'crop', self.args['crop'])