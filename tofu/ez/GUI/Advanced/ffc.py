import logging
from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QGroupBox,
    QLineEdit,
    QCheckBox,
    QRadioButton,
    QHBoxLayout,
)

from tofu.ez.params import EZVARS
from tofu.util import add_value_to_dict_entry, get_int_validator

LOG = logging.getLogger(__name__)


class FFCGroup(QGroupBox):
    """
    Flat Field Correction Settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Flat Field Correction")
        self.setStyleSheet("QGroupBox {color: indigo;}")

        self.method_label = QLabel("Method:")

        self.average_rButton = QRadioButton("Average")
        self.average_rButton.clicked.connect(self.set_method)

        self.ssim_rButton = QRadioButton("SSIM")
        self.ssim_rButton.clicked.connect(self.set_method)

        self.eigen_rButton = QRadioButton("Eigen")
        self.eigen_rButton.clicked.connect(self.set_method)

        self.enable_sinFFC_checkbox = QCheckBox(
            "Use Smart Intensity Normalization Flat Field Correction"
        )
        self.enable_sinFFC_checkbox.stateChanged.connect(self.set_sinFFC)

        self.eigen_pco_repetitions_label = QLabel("Eigen PCO Repetitions")
        self.eigen_pco_repetitions_entry = QLineEdit()
        self.eigen_pco_repetitions_entry.setValidator(get_int_validator())
        self.eigen_pco_repetitions_entry.editingFinished.connect(self.set_pcoReps)

        self.eigen_pco_downsample_label = QLabel("Eigen PCO Downsample")
        self.eigen_pco_downsample_entry = QLineEdit()
        self.eigen_pco_downsample_entry.setValidator(get_int_validator())
        self.eigen_pco_downsample_entry.editingFinished.connect(self.set_pcoDowns)

        self.downsample_label = QLabel("Downsample")
        self.downsample_entry = QLineEdit()
        self.downsample_entry.setValidator(get_int_validator())
        self.downsample_entry.editingFinished.connect(self.set_downsample)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        rbutton_layout = QHBoxLayout()
        rbutton_layout.addWidget(self.method_label)
        rbutton_layout.addWidget(self.eigen_rButton)
        rbutton_layout.addWidget(self.average_rButton)
        rbutton_layout.addWidget(self.ssim_rButton)

        layout.addWidget(self.enable_sinFFC_checkbox, 0, 0)
        layout.addItem(rbutton_layout, 1, 0, 1, 2)
        layout.addWidget(self.eigen_pco_repetitions_label, 2, 0)
        layout.addWidget(self.eigen_pco_repetitions_entry, 2, 1)
        layout.addWidget(self.eigen_pco_downsample_label, 3, 0)
        layout.addWidget(self.eigen_pco_downsample_entry, 3, 1)
        layout.addWidget(self.downsample_label, 4, 0)
        layout.addWidget(self.downsample_entry, 4, 1)

        self.setLayout(layout)

    def load_values(self):
        self.enable_sinFFC_checkbox.setChecked(EZVARS['flat-correction']['smart-ffc']['value'])
        self.set_method_from_params()
        self.eigen_pco_repetitions_entry.setText(str(EZVARS['flat-correction']['eigen-pco-reps']['value']))
        self.eigen_pco_downsample_entry.setText(str(EZVARS['flat-correction']['eigen-pco-downsample']['value']))
        self.downsample_entry.setText(str(EZVARS['flat-correction']['downsample']['value']))

    def set_sinFFC(self):
        LOG.debug("sinFFC: " + str(self.enable_sinFFC_checkbox.isChecked()))
        dict_entry = EZVARS['flat-correction']['smart-ffc']
        add_value_to_dict_entry(dict_entry, self.enable_sinFFC_checkbox.isChecked())

    def set_pcoReps(self):
        LOG.debug("PCO Reps: " + str(self.eigen_pco_repetitions_entry.text()))
        dict_entry = EZVARS['flat-correction']['eigen-pco-reps']
        add_value_to_dict_entry(dict_entry, str(self.eigen_pco_repetitions_entry.text()))
        self.eigen_pco_repetitions_entry.setText(str(dict_entry['value']))

    def set_pcoDowns(self):
        LOG.debug("PCO Downsample: " + str(self.eigen_pco_downsample_entry.text()))
        dict_entry = EZVARS['flat-correction']['eigen-pco-downsample']
        add_value_to_dict_entry(dict_entry, str(self.eigen_pco_downsample_entry.text()))
        self.eigen_pco_downsample_entry.setText(str(dict_entry['value']))

    def set_downsample(self):
        LOG.debug("Downsample: " + str(self.downsample_entry.text()))
        dict_entry = EZVARS['flat-correction']['downsample']
        add_value_to_dict_entry(dict_entry, str(self.downsample_entry.text()))
        self.downsample_entry.setText(str(dict_entry['value']))

    def set_method(self):
        if self.eigen_rButton.isChecked():
            LOG.debug("Method: Eigen")
            EZVARS['flat-correction']['smart-ffc-method']['value'] = "eigen"
        elif self.average_rButton.isChecked():
            LOG.debug("Method: Average")
            EZVARS['flat-correction']['smart-ffc-method']['value'] = "average"
        elif self.ssim_rButton.isChecked():
            LOG.debug("Method: SSIM")
            EZVARS['flat-correction']['smart-ffc-method']['value'] = "ssim"

    def set_method_from_params(self):
        if EZVARS['flat-correction']['smart-ffc-method']['value'] == "eigen":
            self.eigen_rButton.setChecked(True)
            self.average_rButton.setChecked(False)
            self.ssim_rButton.setChecked(False)
        elif EZVARS['flat-correction']['smart-ffc-method']['value'] == "average":
            self.eigen_rButton.setChecked(False)
            self.average_rButton.setChecked(True)
            self.ssim_rButton.setChecked(False)
        elif EZVARS['flat-correction']['smart-ffc-method']['value'] == "ssim":
            self.eigen_rButton.setChecked(False)
            self.average_rButton.setChecked(False)
            self.ssim_rButton.setChecked(True)
