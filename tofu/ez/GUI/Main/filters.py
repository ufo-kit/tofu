import logging
from PyQt5.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QLabel,
    QRadioButton,
    QCheckBox,
    QGroupBox,
    QLineEdit,
)
from PyQt5.QtCore import Qt

import tofu.ez.params as parameters


LOG = logging.getLogger(__name__)


class FiltersGroup(QGroupBox):
    """
    Filter settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Filters")
        self.setStyleSheet("QGroupBox {color: orange;}")

        self.remove_spots_checkBox = QCheckBox()
        self.remove_spots_checkBox.setText("Remove large spots from projections")
        self.remove_spots_checkBox.setToolTip(
            "Efficiently suppresses very intense rings \n stemming from defects in scintillator"
        )
        self.remove_spots_checkBox.stateChanged.connect(self.set_remove_spots)

        self.threshold_label = QLabel()
        self.threshold_label.setText("Threshold (prominence of the spot) [counts]")
        self.threshold_label.setToolTip(
            "Outliers which will be considered as the part of the large spot"
        )
        self.threshold_entry = QLineEdit()
        self.threshold_entry.editingFinished.connect(self.set_threshold)

        self.spot_blur_label = QLabel()
        self.spot_blur_label.setText("Spot blur. sigma [pixels]")
        self.spot_blur_label.setToolTip(
            "Regulates extent of the masked region around the detected outlier"
        )
        self.spot_blur_entry = QLineEdit()
        self.spot_blur_entry.editingFinished.connect(self.set_spot_blur)

        self.enable_RR_checkbox = QCheckBox()
        self.enable_RR_checkbox.setText("Enable ring removal")
        self.remove_spots_checkBox.setToolTip(
            "To suppress ring artifacts"
            " stemming from intensity fluctuations and detector nonlinearities"
        )
        self.enable_RR_checkbox.stateChanged.connect(self.set_ring_removal)

        self.use_LPF_rButton = QRadioButton()
        self.use_LPF_rButton.setText("Use ufo Fourier-transform based filter")
        self.use_LPF_rButton.clicked.connect(self.select_rButton)

        self.sarepy_rButton = QRadioButton()
        self.sarepy_rButton.setText("Use sarepy sorting: ")
        self.sarepy_rButton.clicked.connect(self.select_rButton)
        self.sarepy_rButton.setToolTip(
            "Non-FFT based algorithms from \n /Nghia T. Vo et al, Opt. Express 26, 28396 (2018)"
        )

        self.filter_rButton_group = QButtonGroup(self)
        self.filter_rButton_group.addButton(self.use_LPF_rButton)
        self.filter_rButton_group.addButton(self.sarepy_rButton)

        self.one_dimens_rButton = QRadioButton()
        self.one_dimens_rButton.setText("1D")
        self.one_dimens_rButton.clicked.connect(self.select_dimens_rButton)
        self.one_dimens_rButton.setToolTip("Only low-pass filter along the lines of sinogram")

        self.two_dimens_rButton = QRadioButton()
        self.two_dimens_rButton.setText("2D")
        self.two_dimens_rButton.clicked.connect(self.select_dimens_rButton)
        self.two_dimens_rButton.setToolTip(
            "Low-pass filter along the lines and high-pass filter along the columns"
        )

        self.dimens_rButton_group = QButtonGroup(self)
        self.dimens_rButton_group.addButton(self.one_dimens_rButton)
        self.dimens_rButton_group.addButton(self.two_dimens_rButton)

        self.sigma_horizontal_label = QLabel()
        self.sigma_horizontal_label.setText("sigma horizontal")
        self.sigma_horizontal_label.setToolTip(
            "Width [pixels] of Gaussian-shaped low-pass filter in frequency domain"
        )
        self.sigma_horizontal_entry = QLineEdit()
        self.sigma_horizontal_entry.editingFinished.connect(self.set_sigma_horizontal)

        self.sigma_vertical_label = QLabel()
        self.sigma_vertical_label.setText("sigma vertical")
        self.sigma_vertical_label.setToolTip(
            "Width [pixels] of Gaussian-shaped high-pass filter in frequency domain"
        )
        self.sigma_vertical_entry = QLineEdit()
        self.sigma_vertical_entry.editingFinished.connect(self.set_sigma_vertical)

        self.wind_size_label = QLabel()
        self.wind_size_label.setText("window size")
        self.wind_size_label.setToolTip("Window size in remove_stripe_based_sorting algorithm")
        self.wind_size_entry = QLineEdit()
        self.wind_size_entry.editingFinished.connect(self.set_window_size)
        self.wind_size_entry.setToolTip("Typically in the range 31..51 ")

        self.remove_wide_checkbox = QCheckBox()
        self.remove_wide_checkbox.setText("Remove wide")
        self.remove_wide_checkbox.setToolTip("Window size in remove_large_stripe algorithm")
        self.remove_wide_checkbox.stateChanged.connect(self.set_remove_wide)

        self.remove_wide_label = QLabel()
        self.remove_wide_label.setText("window")
        self.remove_wide_label.setToolTip("Typically in the range 51..131 ")
        self.remove_wide_entry = QLineEdit()
        self.remove_wide_entry.editingFinished.connect(self.set_wind)

        self.SNR_label = QLabel()
        self.SNR_label.setText("SNR")
        self.SNR_label.setToolTip("SNR param in remove_large_stripe algorithm")
        self.SNR_entry = QLineEdit()
        self.SNR_entry.editingFinished.connect(self.set_SNR)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        remove_spots_groupbox = QGroupBox()
        remove_spots_layout = QGridLayout()
        remove_spots_layout.addWidget(self.remove_spots_checkBox, 0, 0)
        remove_spots_layout.addWidget(self.threshold_label, 1, 0)
        remove_spots_layout.addWidget(self.threshold_entry, 1, 1, 1, 7)
        remove_spots_layout.addWidget(self.spot_blur_label, 2, 0)
        remove_spots_layout.addWidget(self.spot_blur_entry, 2, 1, 1, 7)
        remove_spots_groupbox.setLayout(remove_spots_layout)
        layout.addWidget(remove_spots_groupbox)

        rr_groupbox = QGroupBox()
        rr_layout = QGridLayout()
        rr_layout.addWidget(self.enable_RR_checkbox, 3, 0)
        rr_layout.addWidget(self.use_LPF_rButton, 4, 0)
        rr_layout.addWidget(self.one_dimens_rButton, 4, 1)
        rr_layout.addWidget(self.two_dimens_rButton, 4, 2)
        rr_layout.addWidget(self.sigma_horizontal_label, 4, 3, Qt.AlignRight)
        rr_layout.addWidget(self.sigma_horizontal_entry, 4, 4)
        rr_layout.addWidget(self.sigma_vertical_label, 4, 5, Qt.AlignRight)
        rr_layout.addWidget(self.sigma_vertical_entry, 4, 6)
        rr_layout.addWidget(self.sarepy_rButton, 5, 0)
        rr_layout.addWidget(self.wind_size_label, 5, 1)
        rr_layout.addWidget(self.wind_size_entry, 5, 2)
        rr_layout.addWidget(self.remove_wide_checkbox, 5, 3)
        rr_layout.addWidget(self.remove_wide_label, 5, 4, Qt.AlignRight)
        rr_layout.addWidget(self.remove_wide_entry, 5, 5)
        rr_layout.addWidget(self.SNR_label, 5, 6)
        rr_layout.addWidget(self.SNR_entry, 5, 7)
        rr_groupbox.setLayout(rr_layout)

        layout.addWidget(rr_groupbox, 3, 0)

        self.setLayout(layout)

    def init_values(self):
        self.remove_wide_checkbox.setChecked(False)
        self.set_remove_spots()
        parameters.params['main_filters_remove_spots'] = False
        self.threshold_entry.setText(
            str(parameters.params['main_filters_remove_spots_threshold'])
        )
        self.spot_blur_entry.setText(
            str(parameters.params['main_filters_remove_spots_blur_sigma'])
        )
        self.enable_RR_checkbox.setChecked(False)
        self.set_ring_removal()
        parameters.params['main_filters_ring_removal'] = False
        self.use_LPF_rButton.setChecked(True)
        self.select_rButton()
        self.sarepy_rButton.setChecked(False)
        self.two_dimens_rButton.setChecked(True)
        parameters.params['main_filters_ring_removal_ufo_lpf_1d_or_2d'] = False
        self.sigma_horizontal_entry.setText(
            str(parameters.params['main_filters_ring_removal_ufo_lpf_sigma_horizontal'])
        )
        self.sigma_vertical_entry.setText(
            str(parameters.params['main_filters_ring_removal_ufo_lpf_sigma_vertical'])
        )

        self.wind_size_entry.setText("21")
        self.remove_wide_checkbox.setChecked(False)
        parameters.params['main_filters_ring_removal_sarepy_wide'] = False
        self.remove_wide_entry.setText("91")
        self.SNR_entry.setText("3")

    def set_values_from_params(self):
        self.remove_spots_checkBox.setChecked(parameters.params['main_filters_remove_spots'])
        self.threshold_entry.setText(str(parameters.params['main_filters_remove_spots_threshold']))
        self.spot_blur_entry.setText(str(parameters.params['main_filters_remove_spots_blur_sigma']))
        self.enable_RR_checkbox.setChecked(parameters.params['main_filters_ring_removal'])
        if parameters.params['main_filters_ring_removal_ufo_lpf'] == True:
            self.use_LPF_rButton.setChecked(True)
        elif parameters.params['main_filters_ring_removal_ufo_lpf'] == False:
            self.use_LPF_rButton.setChecked(False)
        if parameters.params['main_filters_ring_removal_ufo_lpf_1d_or_2d'] == True:
            self.one_dimens_rButton.setChecked(True)
            self.two_dimens_rButton.setChecked(False)
        elif parameters.params['main_filters_ring_removal_ufo_lpf_1d_or_2d'] == False:
            self.two_dimens_rButton.setChecked(True)
            self.one_dimens_rButton.setChecked(False)
        self.sigma_horizontal_entry.setText(str(parameters.params['main_filters_ring_removal_ufo_lpf_sigma_horizontal']))
        self.sigma_vertical_entry.setText(str(parameters.params['main_filters_ring_removal_ufo_lpf_sigma_vertical']))
        self.wind_size_entry.setText(str(parameters.params['main_filters_ring_removal_sarepy_window_size']))
        self.remove_wide_checkbox.setChecked(parameters.params['main_filters_ring_removal_sarepy_wide'])
        self.remove_wide_entry.setText(str(parameters.params['main_filters_ring_removal_sarepy_window']))
        self.SNR_entry.setText(str(parameters.params['main_filters_ring_removal_sarepy_SNR']))

    def set_remove_spots(self):
        LOG.debug("Remove large spots:" + str(self.remove_spots_checkBox.isChecked()))
        parameters.params['main_filters_remove_spots'] = bool(self.remove_spots_checkBox.isChecked())

    def set_threshold(self):
        LOG.debug(self.threshold_entry.text())
        parameters.params['main_filters_remove_spots_threshold'] = str(self.threshold_entry.text())

    def set_spot_blur(self):
        LOG.debug(self.spot_blur_entry.text())
        parameters.params['main_filters_remove_spots_blur_sigma'] = str(self.spot_blur_entry.text())

    def set_ring_removal(self):
        LOG.debug("RR: " + str(self.enable_RR_checkbox.isChecked()))
        parameters.params['main_filters_ring_removal'] = bool(self.enable_RR_checkbox.isChecked())

    def select_rButton(self):
        if self.use_LPF_rButton.isChecked():
            LOG.debug("Use LPF")
            parameters.params['main_filters_ring_removal_ufo_lpf'] = bool(True)
        elif self.sarepy_rButton.isChecked():
            LOG.debug("Use Sarepy")
            parameters.params['main_filters_ring_removal_ufo_lpf'] = bool(False)

    def select_dimens_rButton(self):
        if self.one_dimens_rButton.isChecked():
            LOG.debug("One dimension")
            parameters.params['main_filters_ring_removal_ufo_lpf_1d_or_2d'] = bool(True)
        elif self.two_dimens_rButton.isChecked():
            LOG.debug("Two dimensions")
            parameters.params['main_filters_ring_removal_ufo_lpf_1d_or_2d'] = bool(False)

    def set_sigma_horizontal(self):
        LOG.debug(self.sigma_horizontal_entry.text())
        parameters.params['main_filters_ring_removal_ufo_lpf_sigma_horizontal'] = \
            str(self.sigma_horizontal_entry.text())

    def set_sigma_vertical(self):
        LOG.debug(self.sigma_vertical_entry.text())
        parameters.params['main_filters_ring_removal_ufo_lpf_sigma_vertical'] = \
            str(self.sigma_vertical_entry.text())

    def set_window_size(self):
        LOG.debug(self.wind_size_entry.text())
        parameters.params['main_filters_ring_removal_sarepy_window_size'] = str(self.wind_size_entry.text())

    def set_remove_wide(self):
        LOG.debug("Wide: " + str(self.remove_wide_checkbox.isChecked()))
        parameters.params['main_filters_ring_removal_sarepy_wide'] = bool(self.remove_wide_checkbox.isChecked())

    def set_wind(self):
        LOG.debug(self.remove_wide_entry.text())
        parameters.params['main_filters_ring_removal_sarepy_window'] = str(self.remove_wide_entry.text())

    def set_SNR(self):
        LOG.debug(self.SNR_entry.text())
        parameters.params['main_filters_ring_removal_sarepy_SNR'] = str(self.SNR_entry.text())