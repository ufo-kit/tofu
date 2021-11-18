from PyQt5.QtWidgets import QGroupBox, QPushButton, QCheckBox, QLabel, QLineEdit, QGridLayout, QFileDialog, QMessageBox
import logging
import os
from tofu.ez.Helpers.find_360_overlap import find_overlap


LOG = logging.getLogger(__name__)


class Overlap360Group(QGroupBox):
    def __init__(self):
        super().__init__()

        self.args = {}
        self.e_root = ""
        self.e_proc = ""
        self.e_output = ""
        self.e_row_num = 0
        self.e_overlap_min = 0
        self.e_overlap_max = 0
        self.e_overlap_increment = 0
        self.e_axis_on_left = False

        self.setTitle("Find 360 Overlap")
        self.setStyleSheet('QGroupBox {color: Orange;}')

        self.input_dir_button = QPushButton("Select input directory")
        self.input_dir_button.clicked.connect(self.input_button_pressed)
        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.textChanged.connect(self.set_input_entry)

        self.temp_dir_button = QPushButton("Select temp directory")
        self.temp_dir_button.clicked.connect(self.temp_button_pressed)
        self.temp_dir_entry = QLineEdit()
        self.temp_dir_entry.textChanged.connect(self.set_temp_entry)

        self.output_dir_button = QPushButton("Select output directory")
        self.output_dir_button.clicked.connect(self.output_button_pressed)
        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.textChanged.connect(self.set_output_entry)

        self.pixel_row_label = QLabel("Pixel row to be used for sinogram")
        self.pixel_row_entry = QLineEdit()
        self.pixel_row_entry.textChanged.connect(self.set_pixel_row)

        self.min_label = QLabel("Lower limit of stitch/axis search range")
        self.min_entry = QLineEdit()
        self.min_entry.textChanged.connect(self.set_lower_limit)

        self.max_label = QLabel("Upper limit of stitch/axis search range")
        self.max_entry = QLineEdit()
        self.max_entry.textChanged.connect(self.set_upper_limit)

        self.step_label = QLabel("Value by which to increment through search range")
        self.step_entry = QLineEdit()
        self.step_entry.textChanged.connect(self.set_increment)

        self.axis_on_left = QCheckBox("Is the rotation axis on the left-hand side of the image?")
        self.axis_on_left.stateChanged.connect(self.set_axis_checkbox)

        self.find_overlap_button = QPushButton("Find Overlap")
        self.find_overlap_button.clicked.connect(self.overlap_button_pressed)
        self.find_overlap_button.setStyleSheet("color:royalblue;font-weight:bold")

        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.help_button_pressed)

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

        self.setLayout(layout)

    def init_values(self):
        indir = os.getcwd()
        self.input_dir_entry.setText(indir)
        self.e_root = indir
        tmpdir = "/data/tmp-stitch_search"
        self.temp_dir_entry.setText(tmpdir)
        self.e_proc = tmpdir
        outdir = os.getcwd() + '-overlap'
        self.output_dir_entry.setText(outdir)
        self.e_output = outdir
        self.e_row_num = 200
        self.pixel_row_entry.setText(str(self.e_row_num))
        self.e_overlap_min = 100
        self.min_entry.setText(str(self.e_overlap_min))
        self.e_overlap_max = 200
        self.max_entry.setText(str(self.e_overlap_max))
        self.e_overlap_increment = 2
        self.step_entry.setText(str(self.e_overlap_increment))
        self.e_axis_on_left = True
        self.axis_on_left.setChecked(bool(self.e_axis_on_left))

    def input_button_pressed(self):
        LOG.debug("Select input button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(directory)
        self.e_root = directory

    def set_input_entry(self):
        LOG.debug("Input: " + str(self.input_dir_entry.text()))
        self.e_root = str(self.input_dir_entry.text())

    def temp_button_pressed(self):
        LOG.debug("Select temp button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.temp_dir_entry.setText(directory)
        self.e_proc = directory

    def set_temp_entry(self):
        LOG.debug("Temp: " + str(self.temp_dir_entry.text()))
        self.e_proc = str(self.temp_dir_entry.text())

    def output_button_pressed(self):
        LOG.debug("Select output button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.output_dir_entry.setText(directory)
        self.e_output = directory

    def set_output_entry(self):
        LOG.debug("Output: " + str(self.output_dir_entry.text()))
        self.e_output = str(self.output_dir_entry.text())

    def set_pixel_row(self):
        LOG.debug("Pixel row: " + str(self.pixel_row_entry.text()))
        self.e_row_num = int(self.pixel_row_entry.text())

    def set_lower_limit(self):
        LOG.debug("Lower limit: " + str(self.min_entry.text()))
        self.e_overlap_min = int(self.min_entry.text())

    def set_upper_limit(self):
        LOG.debug("Upper limit: " + str(self.max_entry.text()))
        self.e_overlap_max = int(self.max_entry.text())

    def set_increment(self):
        LOG.debug("Value of increment: " + str(self.step_entry.text()))
        self.e_overlap_increment = int(self.step_entry.text())

    def set_axis_checkbox(self):
        LOG.debug("Is rotation axis on left-hand-side?: " + str(self.axis_on_left.isChecked()))
        self.e_axis_on_left = bool(self.axis_on_left.isChecked())

    def overlap_button_pressed(self):
        LOG.debug("Find overlap button pressed")

        args = qt_args(self.e_root, self.e_proc, self.e_output, self.e_row_num,
                self.e_overlap_min, self.e_overlap_max, self.e_overlap_increment, self.e_axis_on_left)
        find_overlap(args)

    def help_button_pressed(self):
        LOG.debug("Help button pressed")
        h = "This script takes as input a CT scan that has been collected in 'half-acquisition' mode"
        h += " and produces a series of reconstructed slices, each of which are generated by cropping and"
        h += " concatenating opposing projections together over a range of 'overlap' values (i.e. the pixel column"
        h += " at which the images are cropped and concatenated)."
        h += " The objective is to review this series of images to determine the pixel column at which the axis of rotation"
        h += " is located (much like the axis search function commonly used in reconstruction software)."
        QMessageBox.information(self, "Help", h)

class qt_args():
    def __init__(self, e_root, e_proc, e_output, e_row_num,
                 e_overlap_min, e_overlap_max, e_overlap_increment, e_axis_on_left):

        self.args = {}
        # Directories
        self.args['indir'] = str(e_root)
        setattr(self, 'indir', self.args['indir'])
        self.args['tmpdir'] = str(e_proc)
        setattr(self, 'tmpdir', self.args['tmpdir'])
        self.args['outdir'] = str(e_output)
        setattr(self, 'outdir', self.args['outdir'])
        # Values
        self.args['row_num'] = int(e_row_num)
        setattr(self, 'row_num', self.args['row_num'])
        self.args['overlap_min'] = int(e_overlap_min)
        setattr(self, 'overlap_min', self.args['overlap_min'])
        self.args['overlap_max'] = int(e_overlap_max)
        setattr(self, 'overlap_max', self.args['overlap_max'])
        self.args['overlap_increment'] = int(e_overlap_increment)
        setattr(self, 'overlap_increment', self.args['overlap_increment'])
        self.args['axis_on_left'] = bool(e_axis_on_left)
        setattr(self, 'axis_on_left', self.args['axis_on_left'])

