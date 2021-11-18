import os
import logging
import numpy as np

from qtpy.QtWidgets import QMessageBox, QFileDialog, QCheckBox, QPushButton, QGridLayout, QLabel, QGroupBox, QLineEdit
from qtpy.QtCore import QCoreApplication
from qtpy.QtCore import Signal
from tofu.ez.main import main_tk, clean_tmp_dirs
from tofu.ez.GUI.yaml_in_out import Yaml_IO

import tofu.ez.GUI.params as parameters


LOG = logging.getLogger(__name__)


class ConfigGroup(QGroupBox):
    """
    Setup and configuration settings
    """
    # Used to send signal to ezufo_launcher when settings are imported https://stackoverflow.com/questions/2970312/pyqt4-qtcore-pyqtsignal-object-has-no-attribute-connect
    signal_update_vals_from_params = Signal(dict)

    def __init__(self):
        super().__init__()

        self.setTitle("Configuration")
        self.setStyleSheet('QGroupBox {color: purple;}')

        self.yaml_io = Yaml_IO()

        #Select input directory
        self.input_dir_select = QPushButton()
        self.input_dir_select.setStyleSheet("background-color:gainsboro")
        self.input_dir_select.setText("Select input directory (or paste abs. path)")
        self.input_dir_select.setStyleSheet("background-color:lightgrey; font: 12pt;")

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.textChanged.connect(self.set_input_dir)
        self.input_dir_select.pressed.connect(self.select_input_dir)

        #Select output directory
        self.output_dir_select = QPushButton()
        self.output_dir_select.setStyleSheet("background-color:gainsboro")
        self.output_dir_select.setText("Select output directory (or paste abs. path)")
        self.output_dir_select.setStyleSheet("background-color:lightgrey; font: 12pt;")

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.textChanged.connect(self.set_output_dir)
        self.output_dir_select.pressed.connect(self.select_output_dir)

        #Save in separate files or in one huge tiff file
        self.bigtiff_checkbox = QCheckBox()
        self.bigtiff_checkbox.setText("Save slices in multipage tiffs")
        self.bigtiff_checkbox.stateChanged.connect(self.set_big_tiff)

        #Crop in the reconstruction plane
        self.preproc_checkbox = QCheckBox()
        self.preproc_checkbox.setText("Preprocess with a generic ufo-launch pipeline, f.i.")
        self.preproc_checkbox.stateChanged.connect(self.set_preproc)

        self.preproc_entry = QLineEdit()
        self.preproc_entry.textChanged.connect(self.set_preproc_entry)

        #Names of directories with flats/darks/projections frames
        self.e_DIRTYP = []
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

        #Select temporary directory
        self.temp_dir_select = QPushButton()
        self.temp_dir_select.setText("Select temporary directory (or paste abs. path)")
        self.temp_dir_select.pressed.connect(self.select_temp_dir)
        self.temp_dir_select.setStyleSheet("background-color:lightgrey; font: 12pt;")
        self.temp_dir_entry = QLineEdit()
        self.temp_dir_entry.textChanged.connect(self.set_temp_dir)

        #Keep temp data selection
        self.keep_tmp_data_checkbox = QCheckBox()
        self.keep_tmp_data_checkbox.setText("Keep all temp data till the end of reconstruction")
        self.keep_tmp_data_checkbox.stateChanged.connect(self.set_keep_tmp_data)

        #IMPORT SETTINGS FROM FILE
        self.open_settings_file = QPushButton()
        self.open_settings_file.setText("Import settings from file")
        self.open_settings_file.setStyleSheet("background-color:lightgrey; font: 12pt;")
        self.open_settings_file.pressed.connect(self.import_settings_button_pressed)

        #EXPORT SETTINGS TO FILE
        self.save_settings_file = QPushButton()
        self.save_settings_file.setText("Export settings to file")
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

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.input_dir_select, 0, 0)
        layout.addWidget(self.input_dir_entry, 0, 1, 1, 4)
        layout.addWidget(self.output_dir_select, 1, 0)
        layout.addWidget(self.output_dir_entry, 1, 1, 1, 3)
        layout.addWidget(self.bigtiff_checkbox, 1, 4)
        layout.addWidget(self.preproc_checkbox, 2, 0)
        layout.addWidget(self.preproc_entry, 2, 1, 1, 4)
        layout.addWidget(self.dir_name_label, 3, 0)
        layout.addWidget(self.darks_entry, 3, 1)
        layout.addWidget(self.flats_entry, 3, 2)
        layout.addWidget(self.tomo_entry, 3, 3)
        layout.addWidget(self.flats2_entry, 3, 4)
        layout.addWidget(self.temp_dir_select, 4, 0)
        layout.addWidget(self.temp_dir_entry, 4, 1, 1, 3)
        layout.addWidget(self.keep_tmp_data_checkbox, 4, 4)
        layout.addWidget(self.open_settings_file, 5, 0, 1, 3)
        layout.addWidget(self.save_settings_file, 5, 3, 1, 3)
        layout.addWidget(self.quit_button, 6, 0)
        layout.addWidget(self.help_button, 6, 1)
        layout.addWidget(self.delete_reco_dir_button, 6, 2)
        layout.addWidget(self.dry_run_button, 6, 3)
        layout.addWidget(self.reco_button, 6, 4)

        self.setLayout(layout)

    def init_values(self):
        self.indir = os.getcwd()
        self.input_dir_entry.setText(self.indir)
        self.outdir = os.path.abspath(os.getcwd() + '-rec')
        self.output_dir_entry.setText(self.outdir)
        parameters.params['e_bigtif'] = False
        self.preproc_checkbox.setChecked(False)
        self.set_preproc()
        parameters.params['e_pre'] = False
        self.preproc_entry.setText("remove-outliers size=3 threshold=500 sign=1")
        self.darks_entry.setText("darks")
        self.flats_entry.setText("flats")
        self.tomo_entry.setText("tomo")
        self.flats2_entry.setText("flats2")
        self.temp_dir_entry.setText("/data/tmp-ezufo")
        self.keep_tmp_data_checkbox.setChecked(False)
        parameters.params['e_keep_tmp'] = False
        self.set_temp_dir()
        self.dry_run_button.setChecked(False)
        parameters.params['e_dryrun'] = False
        parameters.params['e_parfile'] = False

    def set_values_from_params(self):
        self.input_dir_entry.setText(parameters.params['e_indir'])
        self.output_dir_entry.setText(parameters.params['e_outdir'])
        self.bigtiff_checkbox.setChecked(parameters.params['e_bigtif'])
        self.preproc_checkbox.setChecked(parameters.params['e_pre'])
        self.preproc_entry.setText(parameters.params['e_pre_cmd'])
        self.darks_entry.setText(parameters.params['e_darks']) #***** SAVE THESE TO YAML AS WELL
        self.flats_entry.setText(parameters.params['e_flats']) #****
        self.tomo_entry.setText(parameters.params['e_tomo']) #*****
        self.flats2_entry.setText(parameters.params['e_flats2']) #*****
        self.temp_dir_entry.setText(parameters.params['e_tmpdir'])
        self.keep_tmp_data_checkbox.setChecked(parameters.params['e_keep_tmp'])
        self.dry_run_button.setChecked(parameters.params['e_dryrun'])

    def select_input_dir(self):
        dir_explore = QFileDialog(self)
        dir = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(dir)
        self.output_dir_entry.setText(dir + "-rec")
        parameters.params['e_indir'] = dir
        parameters.params['e_outdir'] = dir + "-rec"

    def set_input_dir(self):
        LOG.debug(str(self.input_dir_entry.text()))
        parameters.params['e_indir'] = str(self.input_dir_entry.text())

    def select_output_dir(self):
        dir_explore = QFileDialog(self)
        dir = dir_explore.getExistingDirectory()
        self.output_dir_entry.setText(dir)
        parameters.params['e_outdir'] = dir

    def set_output_dir(self):
        LOG.debug(str(self.output_dir_entry.text()))
        parameters.params['e_outdir'] = str(self.output_dir_entry.text())

    def set_big_tiff(self):
        LOG.debug("Bigtiff: " + str(self.bigtiff_checkbox.isChecked()))
        parameters.params['e_bigtif'] = bool(self.bigtiff_checkbox.isChecked())

    def set_preproc(self):
        LOG.debug("Preproc: " + str(self.preproc_checkbox.isChecked()))
        parameters.params['e_pre'] = bool(self.preproc_checkbox.isChecked())

    def set_preproc_entry(self):
        LOG.debug(self.preproc_entry.text())
        parameters.params['e_pre_cmd'] = str(self.preproc_entry.text())

    def set_darks(self):
        LOG.debug(self.darks_entry.text())
        self.e_DIRTYP[0] = str(self.darks_entry.text())
        parameters.params['e_darks'] = str(self.darks_entry.text())

    def set_flats(self):
        LOG.debug(self.flats_entry.text())
        self.e_DIRTYP[1] = str(self.flats_entry.text())
        parameters.params['e_flats'] = str(self.flats_entry.text())

    def set_tomo(self):
        LOG.debug(self.tomo_entry.text())
        self.e_DIRTYP[2] = str(self.tomo_entry.text())
        parameters.params['e_tomo'] = str(self.tomo_entry.text())

    def set_flats2(self):
        LOG.debug(self.flats2_entry.text())
        self.e_DIRTYP[3] = str(self.flats2_entry.text())
        parameters.params['e_flats2'] = str(self.flats2_entry.text())

    def select_temp_dir(self):
        dir_explore = QFileDialog(self)
        dir = dir_explore.getExistingDirectory()
        self.temp_dir_entry.setText(dir)

    def set_temp_dir(self):
        LOG.debug(str(self.temp_dir_entry.text()))
        parameters.params['e_tmpdir'] = str(self.temp_dir_entry.text())

    def set_keep_tmp_data(self):
        LOG.debug("Keep tmp: " + str(self.keep_tmp_data_checkbox.isChecked()))
        parameters.params['e_keep_tmp'] = bool(self.keep_tmp_data_checkbox.isChecked())

    def quit_button_pressed(self):
        LOG.debug("QUIT")
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
        LOG.debug("HELP")
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
        h += "SerG, BMIT CLS, Dec. 2018."
        QMessageBox.information(self, "Help", h)

    def delete_button_pressed(self):
        LOG.debug("DELETE")
        msg = "Delete directory with reconstructed data?"
        dialog = QMessageBox.warning(self, "Warning: data can be lost", msg, QMessageBox.Yes | QMessageBox.No)

        if dialog == QMessageBox.Yes:
            if os.path.exists(str(parameters.params['e_outdir'])):
                LOG.debug("YES")
                if parameters.params['e_outdir'] == parameters.params['e_indir']:
                    QMessageBox.warning("Cannot delete: output directory is the same as input")
                else:
                    os.system( 'rm -rf {}'.format(parameters.params['e_outdir']))
                    LOG.debug("Directory with reconstructed data was removed")
            else:
                LOG.debug("Directory does not exist")
        else:
            LOG.debug("NO")

    def dryrun_button_pressed(self):
        LOG.debug("DRY")
        parameters.params['e_dryrun'] = str(True)
        self.reco_button_pressed()
        parameters.params['e_dryrun'] = str(False)

    def set_save_args(self):
        LOG.debug("Save args: " + str(self.save_args_checkbox.isChecked()))
        parameters.params['e_parfile'] = bool(self.save_args_checkbox.isChecked())

    def export_settings_button_pressed(self):
        LOG.debug("Save settings pressed")
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "QFileDialog.getSaveFileName()", "", "YAML Files (*.yaml);; All Files (*)", options=options)
        if fileName:
            LOG.debug("Export YAML Path: " + fileName)
        #Create and write to YAML file based on given fileName
        self.yaml_io.write_yaml(fileName, parameters.params)

    def import_settings_button_pressed(self):
        LOG.debug("Import settings pressed")
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(self, 'QFileDialog.getOpenFileName()', "", "YAML Files (*.yaml);; All Files (*)", options=options)
        if filePath:
            LOG.debug("Import YAML Path: " + filePath)
            yaml_data = self.yaml_io.read_yaml(filePath)
            parameters.params = dict(yaml_data)
            self.signal_update_vals_from_params.emit(parameters.params)

    def reco_button_pressed(self):
        LOG.debug("RECO")
        LOG.debug(parameters.params)

        try:
            self.validate_input()

            args = tk_args( parameters.params['e_indir'],  parameters.params['e_tmpdir'],  parameters.params['e_outdir'],  parameters.params['e_bigtif'],
                            parameters.params['e_ax'],  parameters.params['e_ax_range'],  parameters.params['e_ax_row'],  parameters.params['e_ax_p_size'],  parameters.params['e_ax_fix'],  parameters.params['e_dax'],
                            parameters.params['e_inp'],  parameters.params['e_inp_thr'],  parameters.params['e_inp_sig'],
                            parameters.params['e_RR'],  parameters.params['e_RR_ufo'],  parameters.params['e_RR_ufo_1d'],  parameters.params['e_RR_par'],
                            parameters.params['e_rr_srp_wind_sort'],  parameters.params['e_rr_srp_wide'],  parameters.params['e_rr_srp_wind_wide'],  parameters.params['e_rr_srp_snr'],
                            parameters.params['e_PR'],  parameters.params['e_energy'],  parameters.params['e_pixel'],  parameters.params['e_z'],  parameters.params['e_log10db'],
                            parameters.params['e_vcrop'],  parameters.params['e_y'],  parameters.params['e_yheight'],  parameters.params['e_ystep'],
                            parameters.params['e_gray256'],  parameters.params['e_bit'],  parameters.params['e_hmin'],  parameters.params['e_hmax'],
                            parameters.params['e_pre'],  parameters.params['e_pre_cmd'],
                            parameters.params['e_a0'],
                            parameters.params['e_crop'],  parameters.params['e_x0'],  parameters.params['e_dx'],  parameters.params['e_y0'],  parameters.params['e_dy'],
                            parameters.params['e_dryrun'],  parameters.params['e_parfile'],  parameters.params['e_keep_tmp'])
            main_tk(args, self.get_fdt_names())
            msg = "Done. See output in terminal for details."
            QMessageBox.information(self, "Finished", msg)
        except InvalidInputError as err:
            msg = ""
            err_arg = err.args
            msg += err.args[0]
            QMessageBox.information(self, "Invalid Input Error", msg)

    # NEED TO DETERMINE VALID RANGES
    # ALSO CHECK TYPES SOMEHOW
    def validate_input(self):

        # Search rotation: e_ax_range

        # Search in slice: e_ax_row
        if int(parameters.params['e_ax_row']) < 0:
            raise InvalidInputError("Value out of range for: Search in slice from row number")

        # Side of reconstructed: e_ax_p_size
        if int(parameters.params['e_ax_p_size']) < 0:
            raise InvalidInputError("Value out of range for: Side of reconstructed path [pixel]")

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

        # Sigma: e_RR_par
        if int(parameters.params['e_RR_par']) < 0:
            raise InvalidInputError("Value out of range for: sigma")

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
        if int(parameters.params['e_energy']) < 0:
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

        # Min value: e_hmin
        if float(parameters.params['e_hmin']) < 0:
            raise InvalidInputError("Value out of range for: Min value in 32-bit histogram")

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

        # Optional: rotate volume: e_a0
        if float(parameters.params['e_a0']) < 0:
            raise InvalidInputError("Value out of range for: Optional: rotate volume clock by [deg]")

    def get_fdt_names(self):
        DIRTYP = []
        for i in self.e_DIRTYP:
            DIRTYP.append(i)
        LOG.debug("Result of get_fdt_names")
        LOG.debug(DIRTYP)
        return DIRTYP

class tk_args():
    def __init__(self, e_indir, e_tmpdir, e_outdir, e_bigtif, \
                e_ax, e_ax_range, e_ax_row,e_ax_p_size, e_ax_fix, e_dax, \
                e_inp, e_inp_thr, e_inp_sig, \
                e_RR, e_RR_ufo, e_RR_ufo_1d, e_RR_par, \
                e_rr_srp_wind_sort, e_rr_srp_wide, e_rr_srp_wide_wind, e_rr_srp_wide_snr,
                e_PR, e_energy, e_pixel, e_z, e_log10db,\
                e_vcrop, e_y, e_yheight, e_ystep,\
                e_gray256, e_bit, e_hmin, e_hmax, \
                e_pre, e_pre_cmd, \
                e_a0, \
                e_crop, e_x0, e_dx, e_y0, e_dy, \
                e_dryrun, e_parfile, e_keep_tmp):
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
        self.args['RR_par']=int(e_RR_par)
        setattr(self,'RR_par',self.args['RR_par'])
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

        LOG.debug("Contents of arg dict: ")
        LOG.debug(self.args.items())


class InvalidInputError(Exception):
    """
    Error to be raised when input values from GUI are out of range or invalid
    """
    pass
