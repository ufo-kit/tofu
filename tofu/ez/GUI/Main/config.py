import os
import logging
import numpy as np

from PyQt5.QtWidgets import QMessageBox, QFileDialog, QCheckBox, QPushButton, QGridLayout, QLabel, QGroupBox, QLineEdit, QHBoxLayout
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import Qt
from tofu.ez.main import main_tk, clean_tmp_dirs
from tofu.ez.GUI.yaml_in_out import Yaml_IO

import tofu.ez.GUI.params as parameters

class ConfigGroup(QGroupBox):
    """
    Setup and configuration settings
    """
    # Used to send signal to ezufo_launcher when settings are imported https://stackoverflow.com/questions/2970312/pyqt4-qtcore-pyqtsignal-object-has-no-attribute-connect
    signal_update_vals_from_params = pyqtSignal(dict)
    # Used to send signal when reconstruction is done
    signal_reco_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        self.setTitle("Configuration")
        self.setStyleSheet('QGroupBox {color: purple;}')

        self.yaml_io = Yaml_IO()

        #Select input directory
        self.input_dir_select = QPushButton("Select input directory (or paste abs. path)")
        self.input_dir_select.setStyleSheet("background-color:lightgrey; font: 12pt;")

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.textChanged.connect(self.set_input_dir)
        self.input_dir_select.pressed.connect(self.select_input_dir)

        #Save .params checkbox
        self.save_params_checkbox = QCheckBox("Save args in .params file")
        self.save_params_checkbox.stateChanged.connect(self.set_save_args)

        #Select output directory
        self.output_dir_select = QPushButton()
        self.output_dir_select.setText("Select output directory (or paste abs. path)")
        self.output_dir_select.setStyleSheet("background-color:lightgrey; font: 12pt;")

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.textChanged.connect(self.set_output_dir)
        self.output_dir_select.pressed.connect(self.select_output_dir)

        #Save in separate files or in one huge tiff file
        self.bigtiff_checkbox = QCheckBox()
        self.bigtiff_checkbox.setText("Save slices in multipage tiffs")
        self.bigtiff_checkbox.setToolTip("Will save images in bigtiff containers. \n"
                                         "Note that some temporary data is always saved in bigtiffs.\n"
                                         "Use bio-formats importer plugin for imagej or fiji to open the bigtiffs.")
        self.bigtiff_checkbox.stateChanged.connect(self.set_big_tiff)

        #Crop in the reconstruction plane
        self.preproc_checkbox = QCheckBox()
        self.preproc_checkbox.setText("Preprocess with a generic ufo-launch pipeline, f.i.")
        self.preproc_checkbox.setToolTip("Selected ufo filters will be applied to each "
                                         "image before reconstruction begins. \n"
                                         "To print the list of filters use \"ufo-query -l\" command. \n"
                                         "Parameters of each filter can be seen with \"ufo-query -p filtername\".")
        self.preproc_checkbox.stateChanged.connect(self.set_preproc)

        self.preproc_entry = QLineEdit()
        self.preproc_entry.textChanged.connect(self.set_preproc_entry)

        #Names of directories with flats/darks/projections frames
        self.e_DIRTYP = ["darks", "flats", "tomo", "flats2"]
        self.dir_name_label = QLabel()
        self.dir_name_label.setText("Name of flats/darks/tomo subdirectories in each CT data set")
        self.darks_entry = QLineEdit()
        self.darks_entry.textChanged.connect(self.set_darks)
        self.flats_entry = QLineEdit()
        self.flats_entry.textChanged.connect(self.set_flats)
        self.tomo_entry = QLineEdit()
        self.tomo_entry.textChanged.connect(self.set_tomo)
        self.flats2_entry = QLineEdit()
        self.flats2_entry.textChanged.connect(self.set_flats2)

        #Select flats/darks/flats2 for use in multiple reconstructions
        self.use_common_flats_darks_checkbox = QCheckBox()
        self.use_common_flats_darks_checkbox.setText("Use common flats/darks across multiple experiments")
        self.use_common_flats_darks_checkbox.stateChanged.connect(self.set_flats_darks_checkbox)

        self.select_darks_button = QPushButton("Select path to darks (or paste abs. path)")
        self.select_darks_button.setToolTip("Background detector noise")
        self.select_darks_button.clicked.connect(self.select_darks_button_pressed)

        self.select_flats_button = QPushButton("Select path to flats (or paste abs. path)")
        self.select_flats_button.setToolTip("Images without sample in the beam")
        self.select_flats_button.clicked.connect(self.select_flats_button_pressed)

        self.select_flats2_button = QPushButton("Select path to flats2 (or paste abs. path)")
        self.select_flats2_button.setToolTip("If selected, it will be assumed that flats were \n"
                                             "acquired before projections while flats2 after \n"
                                             "and interpolation will be used to compute intensity of flat image \n"
                                             "for each projection between flats and flats2")
        self.select_flats2_button.clicked.connect(self.select_flats2_button_pressed)

        self.darks_absolute_entry = QLineEdit()
        self.darks_absolute_entry.setText("Absolute path to darks")
        self.darks_absolute_entry.textChanged.connect(self.set_common_darks)

        self.flats_absolute_entry = QLineEdit()
        self.flats_absolute_entry.setText("Absolute path to flats")
        self.flats_absolute_entry.textChanged.connect(self.set_common_flats)

        self.use_flats2_checkbox = QCheckBox("Use common flats2")
        self.use_flats2_checkbox.clicked.connect(self.set_use_flats2)

        self.flats2_absolute_entry = QLineEdit()
        self.flats2_absolute_entry.textChanged.connect(self.set_common_flats2)
        self.flats2_absolute_entry.setText("Absolute path to flats2")

        #Select temporary directory
        self.temp_dir_select = QPushButton()
        self.temp_dir_select.setText("Select temporary directory (or paste abs. path)")
        self.temp_dir_select.setToolTip("Temporary data will be saved there.\n"
                                        "note that the size of temporary data can exceed 300 GB in some cases.")
        self.temp_dir_select.pressed.connect(self.select_temp_dir)
        self.temp_dir_select.setStyleSheet("background-color:lightgrey; font: 12pt;")
        self.temp_dir_entry = QLineEdit()
        self.temp_dir_entry.textChanged.connect(self.set_temp_dir)

        #Keep temp data selection
        self.keep_tmp_data_checkbox = QCheckBox()
        self.keep_tmp_data_checkbox.setText("Keep all temp data till the end of reconstruction")
        self.keep_tmp_data_checkbox.setToolTip("Useful option to inspect how images change at each step")
        self.keep_tmp_data_checkbox.stateChanged.connect(self.set_keep_tmp_data)

        #IMPORT SETTINGS FROM FILE
        self.open_settings_file = QPushButton()
        self.open_settings_file.setText("Import parameters from file")
        self.open_settings_file.setStyleSheet("background-color:lightgrey; font: 12pt;")
        self.open_settings_file.pressed.connect(self.import_settings_button_pressed)

        #EXPORT SETTINGS TO FILE
        self.save_settings_file = QPushButton()
        self.save_settings_file.setText("Export parameters to file")
        self.save_settings_file.setStyleSheet("background-color:lightgrey; font: 12pt;")
        self.save_settings_file.pressed.connect(self.export_settings_button_pressed)

        #QUIT
        self.quit_button = QPushButton()
        self.quit_button.setText("Quit")
        self.quit_button.setStyleSheet("background-color:lightgrey; font: 13pt; font-weight: bold;")
        self.quit_button.clicked.connect(self.quit_button_pressed)

        #HELP
        self.help_button = QPushButton()
        self.help_button.setText("Help")
        self.help_button.setStyleSheet("background-color:lightgrey; font: 13pt; font-weight: bold")
        self.help_button.clicked.connect(self.help_button_pressed)

        #DELETE
        self.delete_reco_dir_button = QPushButton()
        self.delete_reco_dir_button.setText("Delete reco dir")
        self.delete_reco_dir_button.setStyleSheet("background-color:lightgrey; font: 13pt; font-weight: bold")
        self.delete_reco_dir_button.clicked.connect(self.delete_button_pressed)

        #DRY RUN
        self.dry_run_button = QPushButton()
        self.dry_run_button.setText("Dry run")
        self.dry_run_button.setStyleSheet("background-color:lightgrey; font: 13pt; font-weight: bold")
        self.dry_run_button.clicked.connect(self.dryrun_button_pressed)

        #RECONSTRUCT
        self.reco_button = QPushButton()
        self.reco_button.setText("Reconstruct")
        self.reco_button.setStyleSheet("background-color:lightgrey;color:royalblue; font: 14pt; font-weight: bold;")
        self.reco_button.clicked.connect(self.reco_button_pressed)

        #OPEN IMAGE AFTER RECONSTRUCT
        self.open_image_after_reco_checkbox = QCheckBox()
        self.open_image_after_reco_checkbox.setText("Load images and open viewer after reconstruction")
        self.open_image_after_reco_checkbox.clicked.connect(self.set_open_image_after_reco)

        self.set_layout()

    def set_layout(self):
        """
        Sets the layout of buttons, labels, etc. for config group
        """
        layout = QGridLayout()

        checkbox_groupbox = QGroupBox()
        checkbox_layout = QGridLayout()
        checkbox_layout.addWidget(self.save_params_checkbox, 0, 0)
        checkbox_layout.addWidget(self.bigtiff_checkbox, 1, 0)
        checkbox_layout.addWidget(self.open_image_after_reco_checkbox, 2, 0)
        checkbox_layout.addWidget(self.keep_tmp_data_checkbox, 3, 0)
        checkbox_groupbox.setLayout(checkbox_layout)
        layout.addWidget(checkbox_groupbox, 0, 4, 4, 1)

        layout.addWidget(self.input_dir_select, 0, 0)
        layout.addWidget(self.input_dir_entry, 0, 1, 1, 3)
        layout.addWidget(self.output_dir_select, 1, 0)
        layout.addWidget(self.output_dir_entry, 1, 1, 1, 3)
        layout.addWidget(self.temp_dir_select, 2, 0)
        layout.addWidget(self.temp_dir_entry, 2, 1, 1, 3)
        layout.addWidget(self.preproc_checkbox, 3, 0)
        layout.addWidget(self.preproc_entry, 3, 1, 1, 3)

        fdt_groupbox = QGroupBox()
        fdt_layout = QGridLayout()
        fdt_layout.addWidget(self.dir_name_label, 0, 0)
        fdt_layout.addWidget(self.darks_entry, 0, 1)
        fdt_layout.addWidget(self.flats_entry, 0, 2)
        fdt_layout.addWidget(self.tomo_entry, 0, 3)
        fdt_layout.addWidget(self.flats2_entry, 0, 4)
        fdt_layout.addWidget(self.use_common_flats_darks_checkbox, 1, 0)
        fdt_layout.addWidget(self.select_darks_button, 1, 1)
        fdt_layout.addWidget(self.select_flats_button, 1, 2)
        fdt_layout.addWidget(self.select_flats2_button, 1, 4)
        fdt_layout.addWidget(self.darks_absolute_entry, 2, 1)
        fdt_layout.addWidget(self.flats_absolute_entry, 2, 2)
        fdt_layout.addWidget(self.use_flats2_checkbox, 2, 3, Qt.AlignRight)
        fdt_layout.addWidget(self.flats2_absolute_entry, 2, 4)
        fdt_groupbox.setLayout(fdt_layout)
        layout.addWidget(fdt_groupbox, 4, 0, 1, 5)

        layout.addWidget(self.open_settings_file, 5, 0, 1, 3)
        layout.addWidget(self.save_settings_file, 5, 3, 1, 2)
        layout.addWidget(self.quit_button, 6, 0)
        layout.addWidget(self.help_button, 6, 1)
        layout.addWidget(self.delete_reco_dir_button, 6, 2)
        layout.addWidget(self.dry_run_button, 6, 3)
        layout.addWidget(self.reco_button, 6, 4)

        self.setLayout(layout)

    def init_values(self):
        """
        Sets the initial default values of config group
        """
        # If we're on a computer with access to network
        indir = "/beamlinedata/BMIT/projects/"
        if os.path.isdir(indir):
            self.input_dir_entry.setText(indir)
            outdir = os.path.abspath(indir + "/rec")
            self.output_dir_entry.setText(outdir)
        # Otherwise use this as default
        else:
            indir = "/"
            self.input_dir_entry.setText(indir)
            outdir = os.path.abspath(indir + "rec")
            self.output_dir_entry.setText(outdir)
        self.save_params_checkbox.setChecked(True)
        parameters.params['e_parfile'] = True
        parameters.params['e_bigtif'] = False
        self.preproc_checkbox.setChecked(False)
        self.set_preproc()
        parameters.params['e_pre'] = False
        self.preproc_entry.setText("remove-outliers size=3 threshold=500 sign=1")
        self.darks_entry.setText("darks")
        self.flats_entry.setText("flats")
        self.tomo_entry.setText("tomo")
        self.flats2_entry.setText("flats2")
        self.use_common_flats_darks_checkbox.setChecked(False)
        self.darks_absolute_entry.setText("Absolute path to darks")
        self.flats_absolute_entry.setText("Absolute path to flats")
        self.use_common_flats_darks_checkbox.setChecked(False)
        self.flats2_absolute_entry.setText("Absolute path to flats2")
        self.temp_dir_entry.setText("/data/tmp-ezufo")
        self.keep_tmp_data_checkbox.setChecked(False)
        parameters.params['e_keep_tmp'] = False
        self.set_temp_dir()
        self.dry_run_button.setChecked(False)
        parameters.params['e_dryrun'] = False
        parameters.params['e_openIV'] = False
        self.open_image_after_reco_checkbox.setChecked(False)

    def set_values_from_params(self):
        """
        Updates displayed values for config group
        Called when .yaml file of params is loaded
        """
        self.input_dir_entry.setText(parameters.params['e_indir'])
        self.save_params_checkbox.setChecked(parameters.params['e_parfile'])
        self.output_dir_entry.setText(parameters.params['e_outdir'])
        self.bigtiff_checkbox.setChecked(parameters.params['e_bigtif'])
        self.preproc_checkbox.setChecked(parameters.params['e_pre'])
        self.preproc_entry.setText(parameters.params['e_pre_cmd'])
        self.darks_entry.setText(parameters.params['e_darks'])
        self.flats_entry.setText(parameters.params['e_flats'])
        self.tomo_entry.setText(parameters.params['e_tomo'])
        self.flats2_entry.setText(parameters.params['e_flats2'])
        self.temp_dir_entry.setText(parameters.params['e_tmpdir'])
        self.keep_tmp_data_checkbox.setChecked(parameters.params['e_keep_tmp'])
        self.dry_run_button.setChecked(parameters.params['e_dryrun'])
        self.open_image_after_reco_checkbox.setChecked(parameters.params['e_openIV'])
        self.darks_absolute_entry.setText(parameters.params['e_common_darks'])
        self.flats_absolute_entry.setText(parameters.params['e_common_flats'])
        self.use_flats2_checkbox.setChecked(parameters.params['e_use_common_flats2'])
        self.flats2_absolute_entry.setText(parameters.params['e_common_flats2'])

    def select_input_dir(self):
        """
        Saves directory specified by user in file-dialog for input tomographic data
        """
        if os.path.isdir("/beamlinedata/BMIT/projects"):
            indir = "/beamlinedata/BMIT/projects"
        else:
            indir = "/"
        dir_explore = QFileDialog(self)
        dir = dir_explore.getExistingDirectory(directory=indir)
        self.input_dir_entry.setText(dir)
        parameters.params['e_indir'] = dir
        # Set the output directory to be base of input dir appended with /rec
        head, tail = os.path.split(dir)
        while head != '/':
            head, tail = os.path.split(head)
            if tail == 'raw':
                self.output_dir_entry.setText(os.path.join(head, "rec"))
                parameters.params['e_outdir'] = os.path.join(head, "rec")
                break
        if head == '/':
            self.output_dir_entry.setText(os.path.join(dir, "rec"))
            parameters.params['e_outdir'] = os.path.join(dir, "rec")


    def set_input_dir(self):
        logging.debug(str(self.input_dir_entry.text()))
        parameters.params['e_indir'] = str(self.input_dir_entry.text())

    def select_output_dir(self):
        outdir = "/"
        if os.path.isdir(parameters.params['e_outdir']):
            outdir = parameters.params['e_outdir']
        elif os.path.isdir("/beamlinedata/BMIT/projects"):
            outdir = "/beamlinedata/BMIT/projects"
        dir_explore = QFileDialog(self)
        dir = dir_explore.getExistingDirectory(directory=outdir)
        self.output_dir_entry.setText(dir)
        parameters.params['e_outdir'] = dir

    def set_output_dir(self):
        logging.debug(str(self.output_dir_entry.text()))
        parameters.params['e_outdir'] = str(self.output_dir_entry.text())

    def set_big_tiff(self):
        logging.debug("Bigtiff: " + str(self.bigtiff_checkbox.isChecked()))
        parameters.params['e_bigtif'] = bool(self.bigtiff_checkbox.isChecked())

    def set_preproc(self):
        logging.debug("Preproc: " + str(self.preproc_checkbox.isChecked()))
        parameters.params['e_pre'] = bool(self.preproc_checkbox.isChecked())

    def set_preproc_entry(self):
        logging.debug(self.preproc_entry.text())
        parameters.params['e_pre_cmd'] = str(self.preproc_entry.text())

    def set_open_image_after_reco(self):
        logging.debug("Switch to Image Viewer After Reco: " + str(self.open_image_after_reco_checkbox.isChecked()))
        parameters.params['e_openIV'] = bool(self.open_image_after_reco_checkbox.isChecked())

    def set_darks(self):
        logging.debug(self.darks_entry.text())
        self.e_DIRTYP[0] = str(self.darks_entry.text())
        parameters.params['e_darks'] = str(self.darks_entry.text())

    def set_flats(self):
        logging.debug(self.flats_entry.text())
        self.e_DIRTYP[1] = str(self.flats_entry.text())
        parameters.params['e_flats'] = str(self.flats_entry.text())

    def set_tomo(self):
        logging.debug(self.tomo_entry.text())
        self.e_DIRTYP[2] = str(self.tomo_entry.text())
        parameters.params['e_tomo'] = str(self.tomo_entry.text())

    def set_flats2(self):
        logging.debug(self.flats2_entry.text())
        self.e_DIRTYP[3] = str(self.flats2_entry.text())
        parameters.params['e_flats2'] = str(self.flats2_entry.text())

    def set_flats_darks_checkbox(self):
        logging.debug("Use same flats/darks across multiple experiments: "
                      + str(self.use_common_flats_darks_checkbox.isChecked()))
        parameters.params['e_common_darks_flats'] = bool(self.use_common_flats_darks_checkbox.isChecked())

    def select_darks_button_pressed(self):
        logging.debug("Select path to darks pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory(directory=parameters.params['e_indir'])
        self.darks_absolute_entry.setText(directory)
        parameters.params['e_common_darks'] = directory

    def select_flats_button_pressed(self):
        logging.debug("Select path to flats pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory(directory=parameters.params['e_indir'])
        self.flats_absolute_entry.setText(directory)
        parameters.params['e_common_flats'] = directory

    def select_flats2_button_pressed(self):
        logging.debug("Select path to flats2 pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory(directory=parameters.params['e_indir'])
        self.flats2_absolute_entry.setText(directory)
        parameters.params['e_common_flats2'] = directory

    def set_common_darks(self):
        logging.debug("Common darks path: " + str(self.darks_absolute_entry.text()))
        parameters.params['e_common_darks'] = str(self.darks_absolute_entry.text())

    def set_common_flats(self):
        logging.debug("Common flats path: " + str(self.flats_absolute_entry.text()))
        parameters.params['e_common_flats'] = str(self.flats_absolute_entry.text())

    def set_use_flats2(self):
        logging.debug("Use common flats2 checkbox: " + str(self.use_flats2_checkbox.isChecked()))
        parameters.params['e_use_common_flats2'] = bool(self.use_flats2_checkbox.isChecked())

    def set_common_flats2(self):
        logging.debug("Common flats2 path: " + str(self.flats2_absolute_entry.text()))
        parameters.params['e_common_flats2'] = str(self.flats2_absolute_entry.text())

    def select_temp_dir(self):
        dir_explore = QFileDialog(self)
        tmp_dir = dir_explore.getExistingDirectory()
        self.temp_dir_entry.setText(tmp_dir)

    def set_temp_dir(self):
        logging.debug(str(self.temp_dir_entry.text()))
        parameters.params['e_tmpdir'] = str(self.temp_dir_entry.text())

    def set_keep_tmp_data(self):
        logging.debug("Keep tmp: " + str(self.keep_tmp_data_checkbox.isChecked()))
        parameters.params['e_keep_tmp'] = bool(self.keep_tmp_data_checkbox.isChecked())

    def quit_button_pressed(self):
        """
        Displays confirmation dialog and cleans temporary directories
        """
        logging.debug("QUIT")
        reply = QMessageBox.question(self, 'Quit', 'Are you sure you want to quit?',
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            # remove all directories with projections
            clean_tmp_dirs(parameters.params['e_tmpdir'], self.get_fdt_names())
            # remove axis-search dir too
            tmp = os.path.join(parameters.params['e_tmpdir'], 'axis-search')
            QCoreApplication.instance().quit()
        else:
            pass

    def help_button_pressed(self):
        """
        Displays pop-up help information
        """
        logging.debug("HELP")
        h = "This utility provides an interface to the ufo-kit software package.\n"
        h += "Use it for batch processing and optimization of reconstruction parameters.\n"
        h += "It creates a list of paths to all CT directories in the _input_ directory.\n"
        h += "A CT directory is defined as directory with at least \n"
        h += "_flats_, _darks_, _tomo_, and, optionally, _flats2_ subdirectories, \n"
        h += "which are not empty and contain only *.tif files. Names of CT\n"
        h += "directories are compared with the directory tree in the _output_ directory.\n"
        h += "(Note: relative directory tree in _input_ is preserved when writing results to the _output_.)\n"
        h += "Those CT sets will be reconstructed, whose names are not yet in the _output_ directory."
        h += "Program will create an array of ufo/tofu commands according to defined parameters \n"
        h += "and then execute them sequentially. These commands can be also printed on the screen.\n"
        h += "Note2: if you bin in preprocess the center of rotation will change a lot; \n"
        h += "Note4: set to \"flats\" if \"flats2\" exist but you need to ignore them; \n"
        h += "Created by Sergei Gasilov, BMIT CLS, Dec. 2018.\n Extended by Iain Emslie, Summer 2021."
        QMessageBox.information(self, "Help", h)

    def delete_button_pressed(self):
        """
        Deletes the directory that contains reconstructed data
        """
        logging.debug("DELETE")
        msg = "Delete directory with reconstructed data?"
        dialog = QMessageBox.warning(self, "Warning: data can be lost", msg, QMessageBox.Yes | QMessageBox.No)

        if dialog == QMessageBox.Yes:
            if os.path.exists(str(parameters.params['e_outdir'])):
                logging.debug("YES")
                if parameters.params['e_outdir'] == parameters.params['e_indir']:
                    logging.debug("Cannot delete: output directory is the same as input")
                else:
                    os.system( 'rm -rf {}'.format(parameters.params['e_outdir']))
                    logging.debug("Directory with reconstructed data was removed")
            else:
                logging.debug("Directory does not exist")
        else:
            logging.debug("NO")

    def dryrun_button_pressed(self):
        """
        Sets the dry-run parameter for Tofu to True
        and calls reconstruction
        """
        logging.debug("DRY")
        parameters.params['e_dryrun'] = str(True)
        self.reco_button_pressed()
        parameters.params['e_dryrun'] = bool(False)

    def set_save_args(self):
        logging.debug("Save args: " + str(self.save_params_checkbox.isChecked()))
        parameters.params['e_parfile'] = bool(self.save_params_checkbox.isChecked())

    def export_settings_button_pressed(self):
        """
        Saves currently displayed GUI settings
        to an external .yaml file specified by user
        """
        logging.debug("Save settings pressed")
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "QFileDialog.getSaveFileName()", "", "YAML Files (*.yaml);; All Files (*)", options=options)
        if fileName:
            logging.debug("Export YAML Path: " + fileName)
        file_extension = os.path.splitext(fileName)
        if file_extension[-1] == "":
            fileName = fileName + '.yaml'
        #Create and write to YAML file based on given fileName
        self.yaml_io.write_yaml(fileName, parameters.params)

    def import_settings_button_pressed(self):
        """
        Loads external settings from .yaml file specified by user
        Signal is sent to enable updating of displayed GUI values
        """
        logging.debug("Import settings pressed")
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', "", "YAML Files (*.yaml);; All Files (*)", options=options)
        if filePath:
            logging.debug("Import YAML Path: " + filePath)
            yaml_data = self.yaml_io.read_yaml(filePath)
            parameters.params = dict(yaml_data)
            self.signal_update_vals_from_params.emit(parameters.params)

    def reco_button_pressed(self):
        """
        Gets the settings set by the user in the GUI
        These are then passed to main_tk
        """
        logging.debug("RECO")
        logging.debug(parameters.params)
        self.run_reconstruction(parameters.params, batch_run=False)

    def run_reconstruction(self, params, batch_run):
        try:
            self.validate_input()

            args = tk_args(params['e_indir'], params['e_tmpdir'],
                           params['e_outdir'], params['e_bigtif'],
                           params['e_ax'], params['e_ax_range'],
                           params['e_ax_row'], params['e_ax_p_size'],
                           params['e_ax_fix'], params['e_dax'], params['e_inp'],
                           params['e_inp_thr'], params['e_inp_sig'],
                           params['e_RR'], params['e_RR_ufo'],
                           params['e_RR_ufo_1d'], params['e_RR_sig_hor'], params['e_RR_sig_ver'],
                           params['e_rr_srp_wind_sort'], params['e_rr_srp_wide'],
                           params['e_rr_srp_wind_wide'], params['e_rr_srp_snr'],
                           params['e_PR'], params['e_energy'], params['e_pixel'],
                           params['e_z'], params['e_log10db'], params['e_vcrop'],
                           params['e_y'], params['e_yheight'], params['e_ystep'],
                           params['e_gray256'], params['e_bit'], params['e_hmin'],
                           params['e_hmax'], params['e_pre'], params['e_pre_cmd'],
                           params['e_a0'], params['e_crop'], params['e_x0'],
                           params['e_dx'], params['e_y0'], params['e_dy'],
                           params['e_dryrun'], params['e_parfile'],
                           params['e_keep_tmp'], params['e_sinFFC'],
                           params['e_sinFFC_method'], params['e_sinFFCEigenReps'],
                           params['e_sinFFCEigenDowns'], params['e_sinFFCDowns'],
                           params['e_common_darks_flats'], params['e_common_darks'],
                           params['e_common_flats'], params['e_use_common_flats2'],
                           params['e_common_flats2'],
                           # NLMDN Parameters
                           params['e_nlmdn_apply_after_reco'],
                           params['e_nlmdn_indir'], params['e_nlmdn_input_is_file'],
                           params['e_nlmdn_outdir'], params['e_nlmdn_bigtif'],
                           params['e_nlmdn_r'], params['e_nlmdn_dx'],
                           params['e_nlmdn_h'], params['e_nlmdn_sig'],
                           params['e_nlmdn_w'], params['e_nlmdn_fast'],
                           params['e_nlmdn_autosig'], params['e_nlmdn_dryrun'],
                           # Advanced Parameters
                           params['e_adv_lamino_group'],
                           params['e_adv_lamino_angle'], params['e_adv_overall_rotation'],
                           params['e_adv_center_pos_z'], params['e_adv_axis_rotation_y'],
                           params['e_adv_dark_scale'], params['e_adv_flat_scale'],
                           params['e_adv_verbose'], params['e_adv_slice_mem_coeff'],
                           params['e_adv_num_gpu'], params['e_adv_slices_per_device']
                           )
            main_tk(args, self.get_fdt_names())
            if batch_run is False:
                msg = "Done. See output in terminal for details."
                QMessageBox.information(self, "Finished", msg)
                if not params['e_dryrun']:
                    self.signal_reco_done.emit(params)
        except InvalidInputError as err:
            msg = ""
            err_arg = err.args
            msg += err.args[0]
            QMessageBox.information(self, "Invalid Input Error", msg)

    # NEED TO DETERMINE VALID RANGES
    # ALSO CHECK TYPES SOMEHOW
    def validate_input(self):
        """
        Determines whether user-input values are valid
        """

        # Search rotation: e_ax_range

        # Search in slice: e_ax_row
        if int(parameters.params['e_ax_row']) < 0:
            raise InvalidInputError("Value out of range for: Search in slice from row number")

        # Size of reconstructed: e_ax_p_size
        if int(parameters.params['e_ax_p_size']) < 0:
            raise InvalidInputError("Value out of range for: Size of reconstructed patch [pixel]")

        # Axis is in column No: e_ax_fix
        if float(parameters.params['e_ax_fix']) < 0:
            raise InvalidInputError("Value out of range for: Axis is in column No [pixel]")

        # Increment axis: e_dax
        if float(parameters.params['e_dax']) < 0:
            raise InvalidInputError("Value out of range for: Increment axis every reconstruction")

        # Threshold: e_inp_thr
        if int(parameters.params['e_inp_thr']) < 0:
            raise InvalidInputError("Value out of range for: Threshold (prominence of the spot) [counts]")

        # Spot blur: e_inp_sig
        if int(parameters.params['e_inp_sig']) < 0:
            raise InvalidInputError("Value out of range for: Spot blur. sigma [pixels]")

        # Sigma: e_sig_hor
        if int(parameters.params['e_RR_sig_hor']) < 0:
            raise InvalidInputError("Value out of range for: ufo ring-removal sigma horizontal")

        # Sigma: e_sig_ver
        if int(parameters.params['e_RR_sig_ver']) < 0:
            raise InvalidInputError("Value out of range for: ufo ring-removal sigma vertical")

        # Window size: e_rr_srp_wind_sort
        if int(parameters.params['e_rr_srp_wind_sort']) < 0:
            raise InvalidInputError("Value out of range for: window size")

        # Wind: e_rr_srp_wind_wide
        if int(parameters.params['e_rr_srp_wind_wide']) < 0:
            raise InvalidInputError("Value out of range for: wind")

        # SNR: e_rr_srp_snr
        if int(parameters.params['e_rr_srp_snr']) < 0:
            raise InvalidInputError("Value out of range for: SNR")

        # Photon energy: e_energy
        if float(parameters.params['e_energy']) < 0:
            raise InvalidInputError("Value out of range for: Photon energy [keV]")

        # Pixel size: e_pixel
        if float(parameters.params['e_pixel']) < 0:
            raise InvalidInputError("Value out of range for: Pixel size [micron]")

        # Sample detector distance: e_z
        if float(parameters.params['e_z']) < 0:
            raise InvalidInputError("Value out of range for: Sample-detector distance [m]")

        # Delta/beta ratio: e_log10db
        if int(parameters.params['e_log10db']) < 0:
            raise InvalidInputError("Value out of range for: Delta/beta ratio: (try default if unsure)")

        # First row in projections: e_y
        if int(parameters.params['e_y']) < 0:
            raise InvalidInputError("Value out of range for: First row in projections")

        # Number of rows: e_yheight
        if int(parameters.params['e_yheight']) < 0:
            raise InvalidInputError("Value out of range for: Number of rows (ROI height)")

        # Reconstruct every Nth row: e_ystep
        if int(parameters.params['e_ystep']) < 0:
            raise InvalidInputError("Value out of range for: Reconstruct every Nth row")

        # Can be negative when 16-bit selected
        # Min value: e_hmin
        #if float(parameters.params['e_hmin']) < 0:
        #    raise InvalidInputError("Value out of range for: Min value in 32-bit histogram")

        # Max value: e_hmax
        if float(parameters.params['e_hmax']) < 0:
            raise InvalidInputError("Value out of range for: Max value in 32-bit histogram")

        # x: e_x0
        if int(parameters.params['e_x0']) < 0:
            raise InvalidInputError("Value out of range for: Crop slices: x")

        # width: e_dx
        if int(parameters.params['e_dx']) < 0:
            raise InvalidInputError("Value out of range for: Crop slices: width")

        # y: e_y0
        if int(parameters.params['e_y0']) < 0:
            raise InvalidInputError("Value out of range for: Crop slices: y")

        # height: e_dy
        if int(parameters.params['e_dy']) < 0:
            raise InvalidInputError("Value out of range for: Crop slices: height")

        if int(parameters.params['e_sinFFCEigenReps']) < 0:
            raise InvalidInputError("Value out of range for: Flat Field Correction: Eigen PCO Repetitions")

        if int(parameters.params['e_sinFFCEigenDowns']) < 0:
            raise InvalidInputError("Value out of range for: Flat Field Correction: Eigen PCO Downsample")

        if int(parameters.params['e_sinFFCDowns']) < 0:
            raise InvalidInputError("Value out of range for: Flat Field Correction: Downsample")

        # Can be negative value
        # Optional: rotate volume: e_a0
        #if float(parameters.params['e_a0']) < 0:
        #    raise InvalidInputError("Value out of range for: Optional: rotate volume clock by [deg]")
        #TODO ADD CHECKING NLMDN SETTINGS
        #TODO ADD CHECKING FOR ADVANCED SETTINGS
        '''
        if int(parameters.params['e_adv_rotation_range']) < 0:
            raise InvalidInputError("Advanced: Rotation range must be greater than or equal to zero")

        if float(parameters.params['e_adv_lamino_angle']) < 0 or float(parameters.params['e_adv_lamino_angle']) > 90:
            raise InvalidInputError("Advanced: Lamino angle must be a float between 0 and 90")

        if float(parameters.params['e_adv_slice_mem_coeff']) < 0 or float(parameters.params['e_adv_slice_mem_coeff']) > 1:
            raise InvalidInputError("Advanced: Slice memory coefficient must be between 0 and 1")
        '''

    def get_fdt_names(self):
        DIRTYP = []
        for i in self.e_DIRTYP:
            DIRTYP.append(i)
        logging.debug("Result of get_fdt_names")
        logging.debug(DIRTYP)
        return DIRTYP

class tk_args():
    def __init__(self, e_indir, e_tmpdir, e_outdir, e_bigtif,
                e_ax, e_ax_range, e_ax_row,e_ax_p_size, e_ax_fix, e_dax,
                e_inp, e_inp_thr, e_inp_sig,
                e_RR, e_RR_ufo, e_RR_ufo_1d, e_RR_sig_hor, e_RR_sig_ver,
                e_rr_srp_wind_sort, e_rr_srp_wide, e_rr_srp_wide_wind, e_rr_srp_wide_snr,
                e_PR, e_energy, e_pixel, e_z, e_log10db,
                e_vcrop, e_y, e_yheight, e_ystep, e_gray256, e_bit, e_hmin, e_hmax,
                e_pre, e_pre_cmd, e_a0, e_crop, e_x0, e_dx, e_y0, e_dy,
                e_dryrun, e_parfile, e_keep_tmp, e_sinFFC, e_sinFFC_method, e_sinFFCEigenReps,
                e_sinFFCEigenDowns, e_sinFFCDowns, e_common_darks_flats,
                e_common_darks, e_common_flats, e_use_common_flats2, e_common_flats2,
                e_nlmdn_apply_after_reco, e_nlmdn_indir, e_nlmdn_input_is_file, e_nlmdn_outdir, e_nlmdn_bigtif,
                e_nlmdn_r, e_nlmdn_dx, e_nlmdn_h, e_nlmdn_sig,
                e_nlmdn_w, e_nlmdn_fast, e_nlmdn_autosig, e_nlmdn_dryrun,
                e_adv_lamino_group,
                e_adv_lamino_angle, e_adv_overall_rotation, e_adv_center_pos_z, e_adv_axis_rotation_y,
                e_adv_dark_scale, e_adv_flat_scale,
                e_adv_verbose, e_adv_slice_mem_coeff, e_adv_num_gpu, e_adv_slices_per_device):

        self.args={}
        # PATHS
        self.args['indir']=str(e_indir)
        setattr(self,'indir',self.args['indir'])
        self.args['outdir']=str(e_outdir)
        setattr(self,'outdir',self.args['outdir'])
        self.args['tmpdir']=str(e_tmpdir)
        setattr(self,'tmpdir',self.args['tmpdir'])
        self.args['bigtif_sli']=bool(e_bigtif)
        setattr(self,'bigtif_sli',self.args['bigtif_sli'])
        # center of rotation parameters
        self.args['ax']=int(e_ax)
        setattr(self,'ax',self.args['ax'])
        self.args['ax_range']=str(e_ax_range)
        setattr(self,'ax_range',self.args['ax_range'])
        self.args['ax_p_size']=int(e_ax_p_size)
        setattr(self,'ax_p_size',self.args['ax_p_size'])
        self.args['ax_row']=int(e_ax_row)
        setattr(self,'ax_row',self.args['ax_row'])
        self.args['ax_fix']=float(e_ax_fix)
        setattr(self,'ax_fix',self.args['ax_fix'])
        self.args['dax']=float(e_dax)
        setattr(self,'dax',self.args['dax'])
        #ring removal
        self.args['inp']=bool(e_inp)
        setattr(self,'inp',self.args['inp'])
        self.args['inp_thr']=int(e_inp_thr)
        setattr(self,'inp_thr',self.args['inp_thr'])
        self.args['inp_sig']=int(e_inp_sig)
        setattr(self,'inp_sig',self.args['inp_sig'])
        self.args['RR']=bool(e_RR)
        setattr(self,'RR',self.args['RR'])
        self.args['RR_ufo'] = bool(e_RR_ufo)
        setattr(self, 'RR_ufo', self.args['RR_ufo'])
        self.args['RR_ufo_1d'] = bool(e_RR_ufo_1d)
        setattr(self, 'RR_ufo_1d', self.args['RR_ufo_1d'])
        self.args['RR_sig_hor']=int(e_RR_sig_hor)
        setattr(self,'RR_sig_hor',self.args['RR_sig_hor'])
        self.args['RR_sig_ver'] = int(e_RR_sig_ver)
        setattr(self, 'RR_sig_ver', self.args['RR_sig_ver'])
        self.args['RR_srp_wind_sort'] = int(e_rr_srp_wind_sort)
        setattr(self, 'RR_srp_wind_sort', self.args['RR_srp_wind_sort'])
        self.args['RR_srp_wide'] = bool(e_rr_srp_wide)
        setattr(self, 'RR_srp_wide', self.args['RR_srp_wide'])
        self.args['RR_srp_wide_wind'] = int(e_rr_srp_wide_wind)
        setattr(self, 'RR_srp_wide_wind', self.args['RR_srp_wide_wind'])
        self.args['RR_srp_wide_snr'] = int(e_rr_srp_wide_snr)
        setattr(self, 'RR_srp_wide_snr', self.args['RR_srp_wide_snr'])
        # phase retrieval
        self.args['PR']=bool(e_PR)
        setattr(self,'PR',self.args['PR'])
        self.args['energy']=float(e_energy)
        setattr(self,'energy',self.args['energy'])
        self.args['pixel']=float(e_pixel)*1e-6
        setattr(self,'pixel',self.args['pixel'])
        self.args['z']=float(e_z)
        setattr(self,'z',self.args['z'])
        self.args['log10db']=np.log10(float(e_log10db))
        setattr(self,'log10db',self.args['log10db'])
        # Crop vertically
        self.args['vcrop']=bool(e_vcrop)
        setattr(self,'vcrop',self.args['vcrop'])
        self.args['y']=int(e_y)
        setattr(self,'y',self.args['y'])
        self.args['yheight']=int(e_yheight)
        setattr(self,'yheight',self.args['yheight'])
        self.args['ystep']=int(e_ystep)
        setattr(self,'ystep',self.args['ystep'])
        # conv to 8 bit
        self.args['gray256']=bool(e_gray256)
        setattr(self,'gray256',self.args['gray256'])
        self.args['bit']=int(e_bit)
        setattr(self,'bit',self.args['bit'])
        self.args['hmin']=float(e_hmin)
        setattr(self,'hmin',self.args['hmin'])
        self.args['hmax']=float(e_hmax)
        setattr(self,'hmax',self.args['hmax'])
        # preprocessing attributes
        self.args['pre']=bool(e_pre)
        setattr(self,'pre',self.args['pre'])
        self.args['pre_cmd']=e_pre_cmd
        setattr(self,'pre_cmd',self.args['pre_cmd'])
        # ROI in slice
        self.args['crop']=bool(e_crop)
        setattr(self,'crop',self.args['crop'])
        self.args['x0']=int(e_x0)
        setattr(self,'x0',self.args['x0'])
        self.args['dx']=int(e_dx)
        setattr(self,'dx',self.args['dx'])
        self.args['y0']=int(e_y0)
        setattr(self,'y0',self.args['y0'])
        self.args['dy']=int(e_dy)
        setattr(self,'dy',self.args['dy'])
        # Optional FBP params
        self.args['a0']= float(e_a0)
        setattr(self,'a0',self.args['a0'])
        # misc settings
        self.args['dryrun']=bool(e_dryrun)
        setattr(self,'dryrun',self.args['dryrun'])
        self.args['parfile']=bool(e_parfile)
        setattr(self,'parfile',self.args['parfile'])
        self.args['keep_tmp']=bool(e_keep_tmp)
        setattr(self,'keep_tmp',self.args['keep_tmp'])
        #sinFFC settings
        self.args['sinFFC']=bool(e_sinFFC)
        setattr(self,'sinFFC', self.args['sinFFC'])
        self.args['sinFFC_method'] = str(e_sinFFC_method)
        setattr(self, 'sinFFC_method', self.args['sinFFC_method'])
        self.args['sinFFCEigenReps']=int(e_sinFFCEigenReps)
        setattr(self, 'sinFFCEigenReps', self.args['sinFFCEigenReps'])
        self.args['sinFFCEigenDowns'] = int(e_sinFFCEigenDowns)
        setattr(self, 'sinFFCEigenDowns', self.args['sinFFCEigenDowns'])
        self.args['sinFFCDowns'] = int(e_sinFFCDowns)
        setattr(self, 'sinFFCDowns', self.args['sinFFCDowns'])
        #Settings for using flats/darks across multiple experiments
        self.args['common_darks_flats'] = bool(e_common_darks_flats)
        setattr(self, 'common_darks_flats', self.args['common_darks_flats'])
        self.args['common_darks'] = str(e_common_darks)
        setattr(self, 'common_darks', self.args['common_darks'])
        self.args['common_flats'] = str(e_common_flats)
        setattr(self, 'common_flats', self.args['common_flats'])
        self.args['use_common_flats2'] = bool(e_use_common_flats2)
        setattr(self, 'use_common_flats2', self.args['use_common_flats2'])
        self.args['common_flats2'] = str(e_common_flats2)
        setattr(self, 'common_flats2', self.args['common_flats2'])
        #NLMDN Settings
        self.args['nlmdn_apply_after_reco'] = bool(e_nlmdn_apply_after_reco)
        setattr(self, 'nlmdn_apply_after_reco', self.args['nlmdn_apply_after_reco'])
        self.args['nlmdn_indir'] = str(e_nlmdn_indir)
        setattr(self, 'nlmdn_indir', self.args['nlmdn_indir'])
        self.args['nlmdn_input_is_file'] = bool(e_nlmdn_input_is_file)
        setattr(self, 'nlmdn_input_is_file', self.args['nlmdn_input_is_file'])
        self.args['nlmdn_outdir'] = str(e_nlmdn_outdir)
        setattr(self, 'nlmdn_outdir', self.args['nlmdn_outdir'])
        self.args['nlmdn_bigtif'] = bool(e_nlmdn_bigtif)
        setattr(self, 'nlmdn_bigtif', self.args['nlmdn_bigtif'])
        self.args['nlmdn_r'] = str(e_nlmdn_r)
        setattr(self, 'nlmdn_r', self.args['nlmdn_r'])
        self.args['nlmdn_dx'] = str(e_nlmdn_dx)
        setattr(self, 'nlmdn_dx', self.args['nlmdn_dx'])
        self.args['nlmdn_h'] = str(e_nlmdn_h)
        setattr(self, 'nlmdn_h', self.args['nlmdn_h'])
        self.args['nlmdn_sig'] = str(e_nlmdn_sig)
        setattr(self, 'nlmdn_sig', self.args['nlmdn_sig'])
        self.args['nlmdn_w'] = str(e_nlmdn_w)
        setattr(self, 'nlmdn_w', self.args['nlmdn_w'])
        self.args['nlmdn_fast'] = bool(e_nlmdn_fast)
        setattr(self, 'nlmdn_fast', self.args['nlmdn_fast'])
        self.args['nlmdn_autosig'] = bool(e_nlmdn_autosig)
        setattr(self, 'nlmdn_autosig', self.args['nlmdn_fast'])
        self.args['nlmdn_dryrun'] = bool(e_nlmdn_dryrun)
        setattr(self, 'nlmdn_dryrun', self.args['nlmdn_dryrun'])
        #Advanced Settings
        self.args['adv_lamino_group'] = bool(e_adv_lamino_group)
        setattr(self, 'adv_lamino_group', self.args['adv_lamino_group'])
        self.args['adv_lamino_angle'] = str(e_adv_lamino_angle)
        setattr(self, 'adv_lamino_angle', self.args['adv_lamino_angle'])
        self.args['adv_overall_rotation'] = str(e_adv_overall_rotation)
        setattr(self, 'adv_overall_rotation', self.args['adv_overall_rotation'])
        self.args['adv_center_pos_z'] = str(e_adv_center_pos_z)
        setattr(self, 'adv_center_pos_z', self.args['adv_center_pos_z'])
        self.args['adv_axis_rotation_y'] = str(e_adv_axis_rotation_y)
        setattr(self, 'adv_axis_rotation_y', self.args['adv_axis_rotation_y'])
        self.args['adv_dark_scale'] = str(e_adv_dark_scale)
        setattr(self, 'adv_dark_scale', self.args['adv_dark_scale'])
        self.args['adv_flat_scale'] = str(e_adv_flat_scale)
        setattr(self, 'adv_flat_scale', self.args['adv_flat_scale'])
        #Optimization
        self.args['adv_verbose'] = bool(e_adv_verbose)
        setattr(self, 'adv_verbose', self.args['adv_verbose'])
        self.args['adv_slice_mem_coeff'] = str(e_adv_slice_mem_coeff)
        setattr(self, 'adv_slice_mem_coeff', self.args['adv_slice_mem_coeff'])
        self.args['adv_num_gpu'] = str(e_adv_num_gpu)
        setattr(self, 'adv_num_gpu', self.args['adv_num_gpu'])
        self.args['adv_slices_per_device'] = str(e_adv_slices_per_device)
        setattr(self, 'adv_slices_per_device', self.args['adv_slices_per_device'])

        logging.debug("Contents of arg dict: ")
        logging.debug(self.args.items())

class InvalidInputError(Exception):
    """
    Error to be raised when input values from GUI are out of range or invalid
    """
    pass