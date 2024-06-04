import logging
from PyQt5.QtWidgets import (QGridLayout, QLabel, QGroupBox, QLineEdit, QRadioButton, QPushButton,
    QFileDialog)
from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.ez.util import add_value_to_dict_entry, get_double_validator, reverse_tupleize

LOG = logging.getLogger(__name__)


class Batch360Group(QGroupBox):
    """
    Advanced Tofu Reco settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Batch processing of unstitched half acq. mode data")
        self.setStyleSheet("QGroupBox {color: black;}")
        self.setEnabled(False)

        self.olap_search_only_rButton = QRadioButton()
        self.olap_search_only_rButton.setText("Find the overlap only")
        self.olap_search_only_rButton.setToolTip("Will only estimate the overlap between pairs \n"
                                                 "of 0, 180 projections in each half acq mode CT scan\n"
                                                 "and save it in a structured file in the working directory")
        self.olap_search_only_rButton.clicked.connect(self.set_rButton)

        self.stitch_and_reco_rButton = QRadioButton()
        self.stitch_and_reco_rButton.setText("Stitch and reconstruct. \n"
                                            "You must provide structured file with overlap for each data set."
                                            )
        self.stitch_and_reco_rButton.clicked.connect(self.set_rButton_stitch_reco)

        self.find_olap_stitch_and_reco_rButton = QRadioButton()
        self.find_olap_stitch_and_reco_rButton.setText("Estimates overlap, stitches, and reconstructs")
        self.find_olap_stitch_and_reco_rButton.clicked.connect(self.set_rButton)

        # Import file with overlaps
        self.open_olap_file_button = QPushButton()
        self.open_olap_file_button.setText("Import file with overlaps")
        self.open_olap_file_button.pressed.connect(self.import_olap_file_button_pressed)
        self.open_olap_file_button.setEnabled(False)

        # Select directory for intermediate 360 data
        self.halfacq_dir_select = QPushButton()
        self.halfacq_dir_select.setText("Select working directory")
        self.halfacq_dir_select.setToolTip(
            "Slices to search overlap and horizontally stitched 360 projections will be saved there.\n"
        )
        self.halfacq_dir_select.pressed.connect(self.select_halfacq_dir)
        self.halfacq_dir_entry = QLineEdit()
        self.halfacq_dir_entry.setToolTip(
            "Slices to search overlap and horizontally stitched 360 projections will be saved there.\n"
        )
        self.halfacq_dir_entry.editingFinished.connect(self.set_halfacq_dir)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.olap_search_only_rButton, 0, 0)
        layout.addWidget(self.stitch_and_reco_rButton, 1, 0)
        layout.addWidget(self.open_olap_file_button, 1, 1)
        layout.addWidget(self.find_olap_stitch_and_reco_rButton, 3, 0)

        layout.addWidget(self.halfacq_dir_select, 4, 0)
        layout.addWidget(self.halfacq_dir_entry, 4, 1)

        self.setLayout(layout)

    def enable_by_trigger_from_main_tab(self):
        if not self.isEnabled():
            self.setEnabled(True)
        else:
            self.setEnabled(False)

    def set_rButton(self):
        if self.olap_search_only_rButton.isChecked():
            add_value_to_dict_entry(EZVARS['half-acq']['task_type'], 0)
        elif self.find_olap_stitch_and_reco_rButton.isChecked():
            add_value_to_dict_entry(EZVARS['half-acq']['task_type'], 2)
        self.open_olap_file_button.setEnabled(False)

    def set_rButton_stitch_reco(self):
        if self.stitch_and_reco_rButton.isChecked():
            add_value_to_dict_entry(EZVARS['half-acq']['task_type'], 1)
            self.open_olap_file_button.setEnabled(True)

    def select_halfacq_dir(self):
        dir_explore = QFileDialog(self)
        tmp_dir = dir_explore.getExistingDirectory(directory=self.halfacq_dir_entry.text())
        if tmp_dir:
            self.halfacq_dir_entry.setText(tmp_dir)
            self.set_halfacq_dir()

    def set_halfacq_dir(self):
        LOG.debug(str(self.halfacq_dir_entry.text()))
        dict_entry = EZVARS['half-acq']['dir']
        text = self.halfacq_dir_entry.text().strip()
        add_value_to_dict_entry(dict_entry, text)
        self.halfacq_dir_entry.setText(text)

    def import_olap_file_button_pressed(self):
        """
        Loads external settings from .yaml file specified by user
        Signal is sent to enable updating of displayed GUI values
        """
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "QFileDialog.getOpenFileName()",
            "",
            "YAML Files (*.yaml);; All Files (*)",
            options=options,
        )
        if filePath:
            LOG.debug("Import YAML Path: " + filePath)
            # structure holding path to CT set and respective overlap
            # must be imported
            #import_values(filePath)
            #self.signal_update_vals_from_params.emit()



