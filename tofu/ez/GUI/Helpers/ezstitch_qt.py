import os
from PyQt5.QtWidgets import QGroupBox, QPushButton, QCheckBox, QLabel, QLineEdit, QGridLayout, QVBoxLayout, QHBoxLayout, QRadioButton, QFileDialog, QMessageBox
import logging
import getpass

from tofu.ez.Helpers.stitch_funcs import main_sti_mp, main_conc_mp, main_360_mp_depth1


LOG = logging.getLogger(__name__)


class EZStitchGroup(QGroupBox):
    def __init__(self):
        super().__init__()

        self.e_input = ""
        self.e_output = ""
        self.e_tmpdir = ""
        self.e_typ = ""
        self.e_ort = ""
        self.e_slices = ""
        self.e_flip = False
        self.e_ipol = 0
        self.e_ort = False
        self.e_reprows = 0
        self.e_gray256 = False
        self.e_hmin = 0
        self.e_hmax = 0
        self.e_r2 = 0
        self.e_r1 = 0
        self.e_ax = 0

        self.setTitle("EZ Stitch")
        self.setStyleSheet('QGroupBox {color: purple;}')

        self.input_dir_button = QPushButton()
        self.input_dir_button.setText("Select input directory")
        self.input_dir_button.clicked.connect(self.input_button_pressed)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.textChanged.connect(self.set_input_entry)

        self.tmp_dir_button = QPushButton()
        self.tmp_dir_button.setText("Select temporary directory - default value recommended")
        self.tmp_dir_button.clicked.connect(self.temp_button_pressed)

        self.tmp_dir_entry = QLineEdit()
        self.tmp_dir_entry.textChanged.connect(self.set_temp_entry)

        self.output_dir_button = QPushButton()
        self.output_dir_button.setText("Directory to save stitched images")
        self.output_dir_button.clicked.connect(self.output_button_pressed)

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.textChanged.connect(self.set_output_entry)

        self.types_of_images_label = QLabel()
        self.types_of_images_label.setText("Type of images to stitch (e.g. sli, tomo, proj-pr, etc.)")

        self.types_of_images_entry = QLineEdit()
        self.types_of_images_entry.textChanged.connect(self.set_type_images)

        self.orthogonal_checkbox = QCheckBox()
        self.orthogonal_checkbox.setText("Stitch orthogonal sections")
        self.orthogonal_checkbox.stateChanged.connect(self.set_stitch_checkbox)

        self.start_stop_step_label = QLabel()
        self.start_stop_step_label.setText("Which images to be stitched: start,stop,step:")
        self.start_stop_step_entry = QLineEdit()
        self.start_stop_step_entry.textChanged.connect(self.set_start_stop_step)

        self.sample_moved_down_checkbox = QCheckBox()
        self.sample_moved_down_checkbox.setText("Sample was moved downwards during scan")
        self.sample_moved_down_checkbox.stateChanged.connect(self.set_sample_moved_down)

        self.interpolate_regions_rButton = QRadioButton()
        self.interpolate_regions_rButton.setText("Interpolate overlapping regions and equalize intensity")
        self.interpolate_regions_rButton.clicked.connect(self.set_rButton)

        self.num_overlaps_label = QLabel()
        self.num_overlaps_label.setText("Number of overlapping rows")
        self.num_overlaps_entry = QLineEdit()
        self.num_overlaps_entry.textChanged.connect(self.set_overlap)

        self.clip_histogram_checkbox = QCheckBox()
        self.clip_histogram_checkbox.setText("Clip histogram and convert slices to 8-bit before saving")
        self.clip_histogram_checkbox.stateChanged.connect(self.set_histogram_checkbox)

        self.min_value_label = QLabel()
        self.min_value_label.setText("Min value in 32-bit histogram")
        self.min_value_entry = QLineEdit()
        self.min_value_entry.textChanged.connect(self.set_min_value)

        self.max_value_label = QLabel()
        self.max_value_label.setText("Max value in 32-bit histogram")
        self.max_value_entry = QLineEdit()
        self.max_value_entry.textChanged.connect(self.set_max_value)

        self.concatenate_rButton = QRadioButton()
        self.concatenate_rButton.setText("Concatenate only")
        self.concatenate_rButton.clicked.connect(self.set_rButton)

        self.first_row_label = QLabel()
        self.first_row_label.setText("First row")
        self.first_row_entry = QLineEdit()
        self.first_row_entry.textChanged.connect(self.set_first_row)

        self.last_row_label = QLabel()
        self.last_row_label.setText("Last row")
        self.last_row_entry = QLineEdit()
        self.last_row_entry.textChanged.connect(self.set_last_row)

        self.half_acquisition_rButton = QRadioButton()
        self.half_acquisition_rButton.setText("Half acquisition mode")
        self.half_acquisition_rButton.clicked.connect(self.set_rButton)

        self.column_of_axis_label = QLabel()
        self.column_of_axis_label.setText("In which column the axis of rotation is")
        self.column_of_axis_entry = QLineEdit()
        self.column_of_axis_entry.textChanged.connect(self.set_axis_column)

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
        '''
        layout.addWidget(self.input_dir_button, 0, 0, 1, 4)
        layout.addWidget(self.input_dir_entry, 1, 0, 1, 4)
        layout.addWidget(self.tmp_dir_button, 2, 0, 1, 4)
        layout.addWidget(self.tmp_dir_entry, 3, 0, 1, 4)
        layout.addWidget(self.output_dir_button, 4, 0, 1, 4)
        layout.addWidget(self.output_dir_entry, 5, 0, 1, 4)
        layout.addWidget(self.types_of_images_label, 6, 0, 1, 2)
        layout.addWidget(self.types_of_images_entry, 6, 2, 1, 2)
        layout.addWidget(self.orthogonal_checkbox, 7, 0, 1, 2)
        layout.addWidget(self.start_stop_step_label, 8, 0, 1, 2)
        layout.addWidget(self.start_stop_step_entry, 8, 2, 1, 2)
        layout.addWidget(self.sample_moved_down_checkbox, 9, 0, 1, 2)
        layout.addWidget(self.interpolate_regions_rButton, 10, 0, 1, 2)
        layout.addWidget(self.num_overlaps_label, 11, 0, 1, 2)
        layout.addWidget(self.num_overlaps_entry, 11, 2, 1, 2)
        layout.addWidget(self.clip_histogram_checkbox, 12, 0, 1, 2)
        layout.addWidget(self.min_value_label, 13, 0, 1, 2)
        layout.addWidget(self.min_value_entry, 13, 2, 1, 2)
        layout.addWidget(self.max_value_label, 14, 0, 1, 2)
        layout.addWidget(self.max_value_entry, 14, 2, 1, 2)
        layout.addWidget(self.concatenate_rButton, 15, 0, 1, 2)
        layout.addWidget(self.first_row_label, 16, 0, 1, 1)
        layout.addWidget(self.first_row_entry, 16, 1, 1, 1)
        layout.addWidget(self.last_row_label, 16, 2, 1, 1)
        layout.addWidget(self.last_row_entry, 16, 3, 1, 1)
        layout.addWidget(self.half_acquisition_rButton, 17, 0, 1, 2)
        layout.addWidget(self.column_of_axis_label, 18, 0, 1, 2)
        layout.addWidget(self.column_of_axis_entry, 18, 2, 1, 2)
        layout.addWidget(self.help_button, 19, 0, 1, 1)
        layout.addWidget(self.delete_button, 19, 1, 1, 1)
        layout.addWidget(self.stitch_button, 19, 2, 1, 2)

        '''
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
        grid.addWidget(self.orthogonal_checkbox, 1, 0)
        grid.addWidget(self.start_stop_step_label, 2, 0)
        grid.addWidget(self.start_stop_step_entry, 2, 1)
        grid.addWidget(self.sample_moved_down_checkbox, 3, 0)
        grid.addWidget(self.interpolate_regions_rButton, 4, 0)
        grid.addWidget(self.num_overlaps_label, 5, 0)
        grid.addWidget(self.num_overlaps_entry, 5, 1)
        grid.addWidget(self.clip_histogram_checkbox, 6, 0)
        grid.addWidget(self.min_value_label, 7, 0)
        grid.addWidget(self.min_value_entry, 7, 1)
        grid.addWidget(self.max_value_label, 8, 0)
        grid.addWidget(self.max_value_entry, 8, 1)
        layout.addItem(grid, 1, 0)

        grid2 = QGridLayout()
        grid2.addWidget(self.concatenate_rButton, 0, 0)
        grid2.addWidget(self.first_row_label, 1, 0)
        grid2.addWidget(self.first_row_entry, 1, 1)
        grid2.addWidget(self.last_row_label, 1, 2)
        grid2.addWidget(self.last_row_entry, 1, 3)
        layout.addItem(grid2, 2, 0)

        grid3 = QGridLayout()
        grid3.addWidget(self.half_acquisition_rButton, 0, 0)
        grid3.addWidget(self.column_of_axis_label, 1, 0)
        grid3.addWidget(self.column_of_axis_entry, 1, 1)
        layout.addItem(grid3, 3, 0)

        hbox = QHBoxLayout()
        hbox.addWidget(self.help_button)
        hbox.addWidget(self.delete_button)
        hbox.addWidget(self.stitch_button)
        layout.addItem(hbox, 4, 0)

        self.setLayout(layout)

    def init_values(self):
        indir = os.getcwd()
        self.input_dir_entry.setText(indir)
        self.e_input = indir
        tmpdir = os.path.join("/data", "tmp-ezstitch-" + getpass.getuser())
        self.tmp_dir_entry.setText(tmpdir)
        outdir = os.getcwd() + '-stitched'
        self.output_dir_entry.setText(outdir)
        self.e_output = outdir
        self.types_of_images_entry.setText("sli")
        self.e_typ = "sli"
        self.orthogonal_checkbox.setChecked(True)
        self.e_ort = True
        self.start_stop_step_entry.setText("200,2000,200")
        self.e_slices = "200,2000,200"
        self.sample_moved_down_checkbox.setChecked(False)
        self.e_flip = False
        self.interpolate_regions_rButton.setChecked(True)
        self.e_ipol = 0
        self.num_overlaps_entry.setText("60")
        self.e_reprows = "60"
        self.clip_histogram_checkbox.setChecked(False)
        self.e_gray256 = False
        self.min_value_entry.setText("-0.0003")
        self.e_hmin = "-0.0003"
        self.max_value_entry.setText("0.0002")
        self.e_hmax = "0.0002"
        self.concatenate_rButton.setChecked(False)
        self.first_row_entry.setText("40")
        self.e_r1 = "40"
        self.last_row_entry.setText("440")
        self.e_r2 = "440"
        self.half_acquisition_rButton.setChecked(False)
        self.column_of_axis_entry.setText("245")
        self.e_ax = "245"

    def set_rButton(self):
        if self.interpolate_regions_rButton.isChecked():
            LOG.debug("Interpolate regions")
            self.e_ipol = 0
        elif self.concatenate_rButton.isChecked():
            LOG.debug("Concatenate only")
            self.e_ipol = 1
        elif self.half_acquisition_rButton.isChecked():
            LOG.debug("Half-acquisition mode")
            self.e_ipol = 2

    def input_button_pressed(self):
        LOG.debug("Input button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(directory)
        self.e_input = directory

    def set_input_entry(self):
        LOG.debug("Input: " + str(self.input_dir_entry.text()))
        self.e_input = str(self.input_dir_entry.text())

    def temp_button_pressed(self):
        LOG.debug("Temp button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.tmp_dir_entry.setText(directory)
        self.e_tmpdir = directory

    def set_temp_entry(self):
        LOG.debug("Temp: " + str(self.tmp_dir_entry.text()))
        self.e_tmpdir = str(self.tmp_dir_entry.text())

    def output_button_pressed(self):
        LOG.debug("Output button pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        self.output_dir_entry.setText(directory)
        self.e_output = directory

    def set_output_entry(self):
        LOG.debug("Output: " + str(self.output_dir_entry.text()))
        self.e_output = str(self.output_dir_entry.text())

    def set_type_images(self):
        LOG.debug("Type of images: " + str(self.types_of_images_entry.text()))
        self.e_typ = str(self.types_of_images_entry.text())

    def set_stitch_checkbox(self):
        LOG.debug("Stitch orthogonal: " + str(self.orthogonal_checkbox.isChecked()))
        self.e_ort = bool(self.orthogonal_checkbox.isChecked())

    def set_start_stop_step(self):
        LOG.debug("Images to be stitched: " + str(self.start_stop_step_entry.text()))
        self.e_slices = str(self.start_stop_step_entry.text())

    def set_sample_moved_down(self):
        LOG.debug("Sample moved down: " + str(self.sample_moved_down_checkbox.isChecked()))
        self.e_flip = bool(self.sample_moved_down_checkbox.isChecked())

    def set_overlap(self):
        LOG.debug("Num overlapping rows: " + str(self.num_overlaps_entry.text()))
        self.e_reprows = int(self.num_overlaps_entry.text())

    def set_histogram_checkbox(self):
        LOG.debug("Clip histogram:  " + str(self.clip_histogram_checkbox.isChecked()))
        self.e_gray256 = bool(self.clip_histogram_checkbox.isChecked())

    def set_min_value(self):
        LOG.debug("Min value: " + str(self.min_value_entry.text()))
        self.e_hmin = float(self.min_value_entry.text())

    def set_max_value(self):
        LOG.debug("Max value: " + str(self.max_value_entry.text()))
        self.e_hmax = float(self.max_value_entry.text())

    def set_first_row(self):
        LOG.debug("First row: " + str(self.first_row_entry.text()))
        self.e_r1 = int(self.first_row_entry.text())

    def set_last_row(self):
        LOG.debug("Last row: " + str(self.last_row_entry.text()))
        self.e_r2 = int(self.last_row_entry.text())

    def set_axis_column(self):
        LOG.debug("Column of axis: " + str(self.column_of_axis_entry.text()))
        self.e_ax = int(self.column_of_axis_entry.text())

    def stitch_button_pressed(self):
        LOG.debug("Stitch button pressed")
        args = tk_args(self.e_input, self.e_output, self.e_tmpdir,
                       self.e_typ, self.e_ort, self.e_slices, self.e_flip, self.e_ipol,
                       self.e_reprows, self.e_gray256, self.e_hmin, self.e_hmax,
                       self.e_r1, self.e_r2, self.e_ax)
        LOG.debug(args)

        if os.path.exists(self.e_tmpdir):
            os.system('rm -r {}'.format(self.e_tmpdir))

        if os.path.exists(self.e_output):
            raise ValueError('Output directory exists')

        print("======= Begin Stitching =======")
        # Interpolate overlapping regions and equalize intensity
        if self.e_ipol == 0:
            main_sti_mp(args)
        # Concatenate only
        elif self.e_ipol == 1:
            main_conc_mp(args)
        # Half acquisition mode
        else:
            main_360_mp_depth1(args)
        print("==== Waiting for Next Task ====")

    def delete_button_pressed(self):
        LOG.debug("Delete button pressed")
        if os.path.exists(self.e_output):
            os.system('rm -r {}'.format(self.e_output))
            print(" - Directory with reconstructed data was removed")

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

        #TODO CLEAN and quit when app closed

class tk_args():
    def __init__(self, e_input, e_output, e_tmpdir,
                    e_typ, e_ort, e_slices, e_flip, e_ipol,
                    e_reprows, e_gray256, e_hmin, e_hmax,
                    e_r1, e_r2, e_ax):

        self.args={}
        # directories
        self.args['input'] = str(e_input)
        setattr(self, 'input', self.args['input'])
        self.args['output'] = str(e_output)
        setattr(self, 'output', self.args['output'])
        self.args['tmpdir'] = str(e_tmpdir)
        setattr(self, 'tmpdir', self.args['tmpdir'])
        # parameters
        self.args['typ'] = str(e_typ)
        setattr(self, 'typ', self.args['typ'])
        self.args['slices'] = str(e_slices)
        setattr(self, 'slices', self.args['slices'])
        self.args['flip'] = bool(int(e_flip))
        setattr(self, 'flip', self.args['flip'])
        self.args['ipol'] = int(e_ipol)
        setattr(self, 'ipol', self.args['ipol'])
        self.args['ort'] = bool(int(e_ort))
        setattr(self, 'ort', self.args['ort'])
        # vert stitch with interp and normalization
        self.args['reprows'] = int(e_reprows)
        setattr(self, 'reprows', self.args['reprows'])
        self.args['gray256'] = bool(int(e_gray256))
        setattr(self, 'gray256', self.args['gray256'])
        self.args['hmin'] = float(e_hmin)
        setattr(self, 'hmin', self.args['hmin'])
        self.args['hmax'] = float(e_hmax)
        setattr(self, 'hmax', self.args['hmax'])
        #simple vert stitch
        self.args['r2'] = int(e_r2)
        setattr(self, 'r2', self.args['r2'])
        self.args['r1'] = int(e_r1)
        setattr(self, 'r1', self.args['r1'])
        #hor stitch half acq mode
        self.args['ax'] = int(e_ax)
        setattr(self, 'ax', self.args['ax'])
