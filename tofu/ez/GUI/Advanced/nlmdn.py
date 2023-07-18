import logging
import os
from shutil import rmtree

from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QGroupBox,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt
from tofu.ez.ufo_cmd_gen import fmt_nlmdn_ufo_cmd
from tofu.ez.params import EZVARS
from tofu.util import add_value_to_dict_entry, get_int_validator, get_double_validator





LOG = logging.getLogger(__name__)


class NLMDNGroup(QGroupBox):
    """
    Non-local means de-noising settings
    """
    def __init__(self):
        super().__init__()

        self.setTitle("Non-local-means Denoising")
        self.setStyleSheet("QGroupBox {color: royalblue;}")

        self.apply_to_reco_checkbox = QCheckBox("Automatically apply NLMDN to reconstructed slices")
        self.apply_to_reco_checkbox.stateChanged.connect(self.set_apply_to_reco)

        self.input_dir_button = QPushButton("Select input directory")
        self.input_dir_button.clicked.connect(self.set_indir_button)

        self.select_img_button = QPushButton("Select one image")
        self.select_img_button.clicked.connect(self.select_image)

        self.input_dir_entry = QLineEdit()
        self.input_dir_entry.editingFinished.connect(self.set_indir_entry)

        self.output_dir_button = QPushButton("Select output directory or filename pattern")
        self.output_dir_button.clicked.connect(self.set_outdir_button)

        self.save_bigtif_checkbox = QCheckBox("Save in bigtif container")
        self.save_bigtif_checkbox.clicked.connect(self.set_save_bigtif)

        self.output_dir_entry = QLineEdit()
        self.output_dir_entry.editingFinished.connect(self.set_outdir_entry)

        self.similarity_radius_label = QLabel("Radius for similarity search")
        self.similarity_radius_entry = QLineEdit()
        self.similarity_radius_entry.setValidator(get_int_validator())
        self.similarity_radius_entry.editingFinished.connect(self.set_rad_sim_entry)

        self.patch_radius_label = QLabel("Radius of patches")
        self.patch_radius_entry = QLineEdit()
        self.patch_radius_entry.setValidator(get_int_validator())
        self.patch_radius_entry.editingFinished.connect(self.set_rad_patch_entry)

        self.smoothing_label = QLabel("Smoothing control parameter")
        self.smoothing_entry = QLineEdit()
        self.smoothing_entry.setValidator(get_double_validator())
        self.smoothing_entry.editingFinished.connect(self.set_smoothing_entry)

        self.noise_std_label = QLabel("Noise standard deviation")
        self.noise_std_entry = QLineEdit()
        self.noise_std_entry.setValidator(get_double_validator())
        self.noise_std_entry.editingFinished.connect(self.set_noise_entry)

        self.window_label = QLabel("Window (optional)")
        self.window_entry = QLineEdit()
        self.window_entry.setValidator(get_double_validator())
        self.window_entry.editingFinished.connect(self.set_window_entry)

        self.fast_checkbox = QCheckBox("Fast")
        self.fast_checkbox.clicked.connect(self.set_fast_checkbox)

        self.sigma_checkbox = QCheckBox("Estimate sigma")
        self.sigma_checkbox.clicked.connect(self.set_sigma_checkbox)

        self.help_button = QPushButton("Help")
        self.help_button.clicked.connect(self.help_button_pressed)

        self.delete_button = QPushButton("Delete reco dir")
        self.delete_button.clicked.connect(self.delete_button_pressed)

        self.dry_button = QPushButton("Dry run")
        self.dry_button.clicked.connect(self.dry_button_pressed)

        self.apply_button = QPushButton("Apply filter")
        self.apply_button.clicked.connect(self.apply_button_pressed)
        # self.apply_button.setStyleSheet("color:royalblue; font-weight: bold;")

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.apply_to_reco_checkbox, 0, 0, 1, 1)
        layout.addWidget(self.input_dir_button, 1, 0, 1, 2)
        layout.addWidget(self.select_img_button, 1, 2, 1, 2)
        layout.addWidget(self.input_dir_entry, 2, 0, 1, 4)
        layout.addWidget(self.output_dir_button, 3, 0, 1, 2)
        layout.addWidget(self.save_bigtif_checkbox, 3, 2, 1, 2, Qt.AlignCenter)
        layout.addWidget(self.output_dir_entry, 4, 0, 1, 4)
        layout.addWidget(self.similarity_radius_label, 5, 0, 1, 2)
        layout.addWidget(self.similarity_radius_entry, 5, 2, 1, 2)
        layout.addWidget(self.patch_radius_label, 6, 0, 1, 2)
        layout.addWidget(self.patch_radius_entry, 6, 2, 1, 2)
        layout.addWidget(self.smoothing_label, 7, 0, 1, 2)
        layout.addWidget(self.smoothing_entry, 7, 2, 1, 2)
        layout.addWidget(self.noise_std_label, 8, 0, 1, 2)
        layout.addWidget(self.noise_std_entry, 8, 2, 1, 2)
        layout.addWidget(self.window_label, 9, 0, 1, 2)
        layout.addWidget(self.window_entry, 9, 2, 1, 2)
        layout.addWidget(self.fast_checkbox, 10, 0, 1, 2, Qt.AlignCenter)
        layout.addWidget(self.sigma_checkbox, 10, 2, 1, 2, Qt.AlignCenter)

        layout.addWidget(self.help_button, 11, 0, 1, 1)
        layout.addWidget(self.delete_button, 11, 1)
        layout.addWidget(self.dry_button, 11, 2)
        layout.addWidget(self.apply_button, 11, 3)

        self.setLayout(layout)

    def load_values(self):
        self.apply_to_reco_checkbox.setChecked(bool(EZVARS['nlmdn']['do-after-reco']['value']))
        self.input_dir_entry.setText(str(EZVARS['nlmdn']['input-dir']['value']))
        self.output_dir_entry.setText(str(EZVARS['nlmdn']['output_pattern']['value']))
        self.save_bigtif_checkbox.setChecked(bool(EZVARS['nlmdn']['bigtiff_output']['value']))
        self.similarity_radius_entry.setText(str(EZVARS['nlmdn']['search-radius']['value']))
        self.patch_radius_entry.setText(str(EZVARS['nlmdn']['patch-radius']['value']))
        self.smoothing_entry.setText(str(EZVARS['nlmdn']['h']['value']))
        self.noise_std_entry.setText(str(EZVARS['nlmdn']['sigma']['value']))
        self.window_entry.setText(str(EZVARS['nlmdn']['window']['value']))
        self.fast_checkbox.setChecked(bool(EZVARS['nlmdn']['fast']['value']))
        self.sigma_checkbox.setChecked(bool(EZVARS['nlmdn']['estimate-sigma']['value']))

    def set_apply_to_reco(self):
        LOG.debug(
            "Apply NLMDN to reconstructed slices checkbox: "
            + str(self.apply_to_reco_checkbox.isChecked())
        )
        dict_entry = EZVARS['nlmdn']['do-after-reco']
        add_value_to_dict_entry(dict_entry, self.apply_to_reco_checkbox.isChecked())
        
        if self.apply_to_reco_checkbox.isChecked():
            self.input_dir_button.setDisabled(True)
            self.select_img_button.setDisabled(True)
            self.input_dir_entry.setDisabled(True)
            self.dry_button.setDisabled(True)
            self.apply_button.setDisabled(True)
            self.output_dir_button.setDisabled(True)
            self.output_dir_entry.setDisabled(True)
        elif not self.apply_to_reco_checkbox.isChecked():
            self.input_dir_button.setDisabled(False)
            self.select_img_button.setDisabled(False)
            self.input_dir_entry.setDisabled(False)
            self.dry_button.setDisabled(False)
            self.apply_button.setDisabled(False)
            self.output_dir_button.setDisabled(False)
            self.output_dir_entry.setDisabled(False)

    def set_indir_button(self):
        """
        Saves directory specified by user in file-dialog for input tomographic data
        """
        LOG.debug("Select input directory pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        if directory:
            self.input_dir_entry.setText(str(directory))
            self.set_indir_entry()
            self.output_dir_entry.setText(str(os.path.join(directory+'-nlmdn', 'im-%05i.tif')))
            self.set_outdir_entry()
            dict_entry = EZVARS['nlmdn']['input-is-1file']
            add_value_to_dict_entry(dict_entry, False)

    def set_indir_entry(self):
        LOG.debug("Indir entry: " + str(self.input_dir_entry.text()))
        dict_entry = EZVARS['nlmdn']['input-dir']
        dir = self.input_dir_entry.text().strip()
        add_value_to_dict_entry(dict_entry, str(dir))
        self.input_dir_entry.setText(str(dict_entry['value']))

    def select_image(self):
        LOG.debug("Select one image button pressed")
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open .tif Image File", "", "Tiff Files (*.tif *.tiff)", options=options
        )
        if file_path:
            img_name, img_ext = os.path.splitext(file_path)
            tmp = img_name + "-nlmfilt" + img_ext
            
            self.input_dir_entry.setText(str(file_path))
            self.set_indir_entry()
            
            self.output_dir_entry.setText(str(tmp))
            self.set_outdir_entry()
            
            dict_entry = EZVARS['nlmdn']['input-is-1file']
            add_value_to_dict_entry(dict_entry, True)

    def set_outdir_button(self):
        LOG.debug("Select output directory pressed")
        dir_explore = QFileDialog(self)
        directory = dir_explore.getExistingDirectory()
        # dict_entry = EZVARS['nlmdn']['output_pattern']
        # add_value_to_dict_entry(dict_entry, directory)
        if directory:
            self.output_dir_entry.setText(str(os.path.join(directory,'im-nlmdn-%05i.tif')))
            self.set_outdir_entry()

    def set_save_bigtif(self):
        LOG.debug("Save bigtif checkbox: " + str(self.save_bigtif_checkbox.isChecked()))
        dict_entry = EZVARS['nlmdn']['bigtiff_output']
        add_value_to_dict_entry(dict_entry, self.save_bigtif_checkbox.isChecked())

    def set_outdir_entry(self):
        LOG.debug("Outdir entry: " + str(self.output_dir_entry.text()))
        dict_entry = EZVARS['nlmdn']['output_pattern']
        dir = self.output_dir_entry.text().strip()
        add_value_to_dict_entry(dict_entry, str(dir))
        self.output_dir_entry.setText(str(dict_entry['value']))

    def set_rad_sim_entry(self):
        LOG.debug("Radius for similarity: " + str(self.similarity_radius_entry.text()))
        dict_entry = EZVARS['nlmdn']['search-radius']
        add_value_to_dict_entry(dict_entry, str(self.similarity_radius_entry.text()))
        self.similarity_radius_entry.setText(str(dict_entry['value']))

    def set_rad_patch_entry(self):
        LOG.debug("Radius of patches: " + str(self.patch_radius_entry.text()))
        dict_entry = EZVARS['nlmdn']['patch-radius']
        add_value_to_dict_entry(dict_entry, str(self.patch_radius_entry.text()))
        self.patch_radius_entry.setText(str(dict_entry['value']))

    def set_smoothing_entry(self):
        LOG.debug("Smoothing control: " + str(self.smoothing_entry.text()))
        dict_entry = EZVARS['nlmdn']['h']
        add_value_to_dict_entry(dict_entry, str(self.smoothing_entry.text()))
        self.smoothing_entry.setText(str(dict_entry['value']))

    def set_noise_entry(self):
        LOG.debug("Noise std: " + str(self.noise_std_entry.text()))
        dict_entry = EZVARS['nlmdn']['sigma']
        add_value_to_dict_entry(dict_entry, str(self.noise_std_entry.text()))
        self.noise_std_entry.setText(str(dict_entry['value']))

    def set_window_entry(self):
        LOG.debug("Window: " + str(self.window_entry.text()))
        dict_entry = EZVARS['nlmdn']['window']
        add_value_to_dict_entry(dict_entry, str(self.window_entry.text()))
        self.window_entry.setText(str(dict_entry['value']))

    def set_fast_checkbox(self):
        LOG.debug("Fast: " + str(self.fast_checkbox.isChecked()))
        dict_entry = EZVARS['nlmdn']['fast']
        add_value_to_dict_entry(dict_entry, self.fast_checkbox.isChecked())

    def set_sigma_checkbox(self):
        LOG.debug("Estimate sigma: " + str(self.sigma_checkbox.isChecked()))
        dict_entry = EZVARS['nlmdn']['estimate-sigma']
        add_value_to_dict_entry(dict_entry, self.sigma_checkbox.isChecked())

    def help_button_pressed(self):
        LOG.debug("Help Button Pressed")
        h = ""
        h += 'Note4: set to "flats" if "flats2" exist but you need to ignore them; \n'
        h += "SerG, BMIT CLS, Dec. 2020."
        QMessageBox.information(self, "Help", h)

    def delete_button_pressed(self):
        LOG.debug("Delete Reco Button Pressed")
        """
        Deletes the directory that contains reconstructed data
        """
        LOG.debug("DELETE")
        msg = "Delete directory with reconstructed data?"
        dialog = QMessageBox.warning(self, "Warning: data can be lost", msg, QMessageBox.Yes | QMessageBox.No)

        if dialog == QMessageBox.Yes:
            if os.path.exists(str(EZVARS['nlmdn']['output_pattern']['value'])):
                LOG.debug("YES")
                if EZVARS['nlmdn']['output_pattern']['value'] == EZVARS['nlmdn']['input-dir']['value']:
                    LOG.debug("Cannot delete: output directory is the same as input")
                else:
                    rmtree(EZVARS['nlmdn']['output_pattern']['value'])
                    LOG.debug("Directory with denoised images was removed")
            else:
                LOG.debug("Directory does not exist")
        else:
            LOG.debug("NO")

    def dry_button_pressed(self):
        LOG.debug("Dry Run Button Pressed")
        dict_entry = EZVARS['nlmdn']['dryrun']
        add_value_to_dict_entry(dict_entry, True)
        self.apply_button_pressed()
        add_value_to_dict_entry(dict_entry, False)

    def apply_button_pressed(self):
        LOG.debug("Apply Filter Button Pressed")

        if os.path.exists(EZVARS['nlmdn']['output_pattern']['value']) and not \
                EZVARS['nlmdn']['dryrun']['value']:
            title_text = "Warning: files can be overwritten"
            text1 = "Output directory exists. Files can be overwritten. Proceed?"
            dialog = QMessageBox.warning(self, title_text, text1, QMessageBox.Yes | QMessageBox.No)
            if dialog == QMessageBox.Yes:
                cmd = fmt_nlmdn_ufo_cmd(EZVARS['nlmdn']['input-dir']['value'],
                                        EZVARS['nlmdn']['output_pattern']['value'])
        else:
            cmd = fmt_nlmdn_ufo_cmd(EZVARS['nlmdn']['input-dir']['value'],
                                    EZVARS['nlmdn']['output_pattern']['value'])

        if EZVARS['nlmdn']['dryrun']['value']:
            print(cmd)
        else:
            os.system(cmd)
            QMessageBox.information(self, "Finished", "Finished")
