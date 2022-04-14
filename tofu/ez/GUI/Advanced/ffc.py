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

import tofu.ez.params as parameters


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
        self.eigen_pco_repetitions_entry.editingFinished.connect(self.set_pcoReps)

        self.eigen_pco_downsample_label = QLabel("Eigen PCO Downsample")
        self.eigen_pco_downsample_entry = QLineEdit()
        self.eigen_pco_downsample_entry.editingFinished.connect(self.set_pcoDowns)

        self.downsample_label = QLabel("Downsample")
        self.downsample_entry = QLineEdit()
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

    def init_values(self):
        self.eigen_rButton.setChecked(True)
        self.average_rButton.setChecked(False)
        self.ssim_rButton.setChecked(False)
        parameters.params['advanced_ffc_method'] = "eigen"
        self.enable_sinFFC_checkbox.setChecked(False)
        self.eigen_pco_repetitions_entry.setText("4")
        self.eigen_pco_downsample_entry.setText("2")
        self.downsample_entry.setText("4")

    def set_values_from_params(self):
        self.enable_sinFFC_checkbox.setChecked(parameters.params['advanced_ffc_sinFFC'])
        self.set_method_from_params()
        self.eigen_pco_repetitions_entry.setText(str(parameters.params['advanced_ffc_eigen_pco_reps']))
        self.eigen_pco_downsample_entry.setText(str(parameters.params['advanced_ffc_eigen_pco_downsample']))
        self.downsample_entry.setText(str(parameters.params['advanced_ffc_downsample']))

    def set_sinFFC(self):
        logging.debug("sinFFC: " + str(self.enable_sinFFC_checkbox.isChecked()))
        parameters.params['advanced_ffc_sinFFC'] = bool(self.enable_sinFFC_checkbox.isChecked())

    def set_pcoReps(self):
        logging.debug("PCO Reps: " + str(self.eigen_pco_repetitions_entry.text()))
        parameters.params['advanced_ffc_eigen_pco_reps'] = str(self.eigen_pco_repetitions_entry.text())

    def set_pcoDowns(self):
        logging.debug("PCO Downsample: " + str(self.eigen_pco_downsample_entry.text()))
        parameters.params['advanced_ffc_eigen_pco_downsample'] = str(self.eigen_pco_downsample_entry.text())

    def set_downsample(self):
        logging.debug("Downsample: " + str(self.downsample_entry.text()))
        parameters.params['advanced_ffc_downsample'] = str(self.downsample_entry.text())

    def set_method(self):
        if self.eigen_rButton.isChecked():
            logging.debug("Method: Eigen")
            parameters.params['advanced_ffc_method'] = "eigen"
        elif self.average_rButton.isChecked():
            logging.debug("Method: Average")
            parameters.params['advanced_ffc_method'] = "average"
        elif self.ssim_rButton.isChecked():
            logging.debug("Method: SSIM")
            parameters.params['advanced_ffc_method'] = "ssim"

    def set_method_from_params(self):
        if parameters.params['advanced_ffc_method'] == 1:
            self.eigen_rButton.setChecked(True)
            self.average_rButton.setChecked(False)
            self.ssim_rButton.setChecked(False)
        elif parameters.params['advanced_ffc_method'] == 2:
            self.eigen_rButton.setChecked(False)
            self.average_rButton.setChecked(True)
            self.ssim_rButton.setChecked(False)
        elif parameters.params['advanced_ffc_method'] == 3:
            self.eigen_rButton.setChecked(False)
            self.average_rButton.setChecked(False)
            self.ssim_rButton.setChecked(True)
