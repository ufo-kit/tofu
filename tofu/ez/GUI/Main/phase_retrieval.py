import logging
import math
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QCheckBox
from tofu.config import SECTIONS
from tofu.ez.params import EZVARS
from tofu.ez.util import add_value_to_dict_entry, reverse_tupleize, get_double_validator, get_tuple_validator

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
        self.photon_energy_entry.setValidator(get_double_validator())
        self.photon_energy_entry.editingFinished.connect(self.set_photon_energy)

        self.pixel_size_label = QLabel()
        self.pixel_size_label.setText("Pixel size [micron]")
        self.pixel_size_entry = QLineEdit()
        self.pixel_size_entry.setValidator(get_double_validator())
        self.pixel_size_entry.editingFinished.connect(self.set_pixel_size)

        self.detector_distance_label = QLabel()
        self.detector_distance_label.setText("Sample-detector distance [m]")
        self.detector_distance_entry = QLineEdit()
        self.detector_distance_entry.setValidator(get_tuple_validator())
        self.detector_distance_entry.editingFinished.connect(self.set_detector_distance)

        self.delta_beta_ratio_label = QLabel()
        self.delta_beta_ratio_label.setText("Delta/beta ratio: (try default if unsure)")
        self.delta_beta_ratio_entry = QLineEdit()
        self.delta_beta_ratio_entry.setValidator(get_double_validator())
        self.delta_beta_ratio_entry.editingFinished.connect(self.set_delta_beta)

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
    
    def load_values(self):
        self.enable_PR_checkBox.setChecked(EZVARS['retrieve-phase']['apply-pr']['value'])
        self.photon_energy_entry.setText(str(SECTIONS['retrieve-phase']['energy']['value']))
        self.pixel_size_entry.setText(str(
            round(self.meters_to_microns(SECTIONS['retrieve-phase']['pixel-size']['value']),6)))
        self.detector_distance_entry.setText(str(reverse_tupleize()(SECTIONS['retrieve-phase']['propagation-distance']['value'])))
        self.delta_beta_ratio_entry.setText(str(
            round(self.regularization_rate_to_delta_beta_ratio(SECTIONS['retrieve-phase']['regularization-rate']['value']),6)))

    def set_PR(self):
        LOG.debug("PR: " + str(self.enable_PR_checkBox.isChecked()))
        dict_entry = EZVARS['retrieve-phase']['apply-pr']
        add_value_to_dict_entry(dict_entry, self.enable_PR_checkBox.isChecked())

    def set_photon_energy(self):
        LOG.debug(self.photon_energy_entry.text())
        dict_entry = SECTIONS['retrieve-phase']['energy']
        add_value_to_dict_entry(dict_entry, str(self.photon_energy_entry.text()))
        self.photon_energy_entry.setText(str(dict_entry['value']))

    def set_pixel_size(self):
        LOG.debug(self.pixel_size_entry.text())
        dict_entry = SECTIONS['retrieve-phase']['pixel-size']
        add_value_to_dict_entry(dict_entry, 
                                self.microns_to_meters(float(self.pixel_size_entry.text())))

    def set_detector_distance(self):
        LOG.debug(self.detector_distance_entry.text())
        dict_entry = SECTIONS['retrieve-phase']['propagation-distance']
        add_value_to_dict_entry(dict_entry, str(self.detector_distance_entry.text()))
        self.detector_distance_entry.setText(str(reverse_tupleize()(dict_entry['value'])))

    def set_delta_beta(self):
        LOG.debug(self.delta_beta_ratio_entry.text())
        dict_entry = SECTIONS['retrieve-phase']['regularization-rate']
        add_value_to_dict_entry(dict_entry, 
                                self.delta_beta_ratio_to_regularization_rate(float(self.delta_beta_ratio_entry.text())))

    def meters_to_microns(self,value)->float:
        return value * 1e6
    
    def microns_to_meters(self,value)->float:
        return value * 1e-6
    
    def delta_beta_ratio_to_regularization_rate(self,value:float)->float:
        return math.log10(value)
    
    def regularization_rate_to_delta_beta_ratio(self,value)->float:
        return 10**value