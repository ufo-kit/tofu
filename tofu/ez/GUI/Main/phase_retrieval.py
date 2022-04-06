import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QCheckBox

import tofu.ez.params as parameters


LOG = logging.getLogger(__name__)


class PhaseRetrievalGroup(QGroupBox):
    """
    Phase Retrieval settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Phase Retrieval")
        self.setStyleSheet("QGroupBox {color: blue;}")

        self.enable_PR_checkBox = QCheckBox()
        self.enable_PR_checkBox.setText("Enable Paganin/TIE phase retrieval")
        self.enable_PR_checkBox.stateChanged.connect(self.set_PR)

        self.photon_energy_label = QLabel()
        self.photon_energy_label.setText("Photon energy [keV]")
        self.photon_energy_entry = QLineEdit()
        self.photon_energy_entry.editingFinished.connect(self.set_photon_energy)
        self.photon_energy_entry.setStyleSheet("background-color:white")

        self.pixel_size_label = QLabel()
        self.pixel_size_label.setText("Pixel size [micron]")
        self.pixel_size_entry = QLineEdit()
        self.pixel_size_entry.editingFinished.connect(self.set_pixel_size)
        self.pixel_size_entry.setStyleSheet("background-color:white")

        self.detector_distance_label = QLabel()
        self.detector_distance_label.setText("Sample-detector distance [m]")
        self.detector_distance_entry = QLineEdit()
        self.detector_distance_entry.editingFinished.connect(self.set_detector_distance)
        self.detector_distance_entry.setStyleSheet("background-color:white")

        self.delta_beta_ratio_label = QLabel()
        self.delta_beta_ratio_label.setText("Delta/beta ratio: (try default if unsure)")
        self.delta_beta_ratio_entry = QLineEdit()
        self.delta_beta_ratio_entry.editingFinished.connect(self.set_delta_beta)
        self.delta_beta_ratio_entry.setStyleSheet("background-color:white")

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.enable_PR_checkBox, 0, 0)
        layout.addWidget(self.photon_energy_label, 1, 0)
        layout.addWidget(self.photon_energy_entry, 1, 1)
        layout.addWidget(self.pixel_size_label, 2, 0)
        layout.addWidget(self.pixel_size_entry, 2, 1)
        layout.addWidget(self.detector_distance_label, 3, 0)
        layout.addWidget(self.detector_distance_entry, 3, 1)
        layout.addWidget(self.delta_beta_ratio_label, 4, 0)
        layout.addWidget(self.delta_beta_ratio_entry, 4, 1)

        self.setLayout(layout)

    def init_values(self):
        self.enable_PR_checkBox.setChecked(False)
        parameters.params['main_pr_phase_retrieval'] = False
        self.photon_energy_entry.setText("20")
        self.pixel_size_entry.setText("3.6")
        self.detector_distance_entry.setText("0.1")
        self.delta_beta_ratio_entry.setText("200")

    def set_values_from_params(self):
        self.enable_PR_checkBox.setChecked(parameters.params['main_pr_phase_retrieval'])
        self.photon_energy_entry.setText(str(parameters.params['main_pr_photon_energy']))
        self.pixel_size_entry.setText(str(parameters.params['main_pr_pixel_size']))
        self.detector_distance_entry.setText(str(parameters.params['main_pr_detector_distance']))
        self.delta_beta_ratio_entry.setText(str(parameters.params['main_pr_delta_beta_ratio']))

    def set_PR(self):
        LOG.debug("PR: " + str(self.enable_PR_checkBox.isChecked()))
        parameters.params['main_pr_phase_retrieval'] = bool(self.enable_PR_checkBox.isChecked())

    def set_photon_energy(self):
        LOG.debug(self.photon_energy_entry.text())
        parameters.params['main_pr_photon_energy'] = str(self.photon_energy_entry.text())

    def set_pixel_size(self):
        LOG.debug(self.pixel_size_entry.text())
        parameters.params['main_pr_pixel_size'] = str(self.pixel_size_entry.text())

    def set_detector_distance(self):
        LOG.debug(self.detector_distance_entry.text())
        parameters.params['main_pr_detector_distance'] = str(self.detector_distance_entry.text())

    def set_delta_beta(self):
        LOG.debug(self.delta_beta_ratio_entry.text())
        parameters.params['main_pr_delta_beta_ratio'] = str(self.delta_beta_ratio_entry.text())