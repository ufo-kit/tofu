import logging
from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QGroupBox,
    QLineEdit,
    QComboBox,
    QHBoxLayout,
)
from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.ez.util import add_value_to_dict_entry, get_int_validator, get_double_validator

LOG = logging.getLogger(__name__)


class FindSpotsGroup(QGroupBox):
    """
    Flat Field Correction Settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Extended settings to find large bad spots in images")
        self.setStyleSheet("QGroupBox {color: brown;}")
        self.setEnabled(False)

        self.median_width_label = QLabel("Median width")
        self.median_width_entry = QLineEdit()
        self.median_width_entry.setValidator(get_int_validator())
        self.median_width_entry.editingFinished.connect(self.set_median_width)
        self.median_width_entry.setToolTip(SECTIONS['find-large-spots']['median-width']['help'])
        self.median_width_label.setToolTip(SECTIONS['find-large-spots']['median-width']['help'])

        self.dil_disk_rad_label = QLabel("Dilation disk radius")
        self.dil_disk_rad_entry = QLineEdit()
        self.dil_disk_rad_entry.setValidator(get_int_validator())
        self.dil_disk_rad_entry.editingFinished.connect(self.set_dil_disk_rad)
        self.dil_disk_rad_entry.setToolTip(SECTIONS['find-large-spots']['dilation-disk-radius']['help'])
        self.dil_disk_rad_label.setToolTip(SECTIONS['find-large-spots']['dilation-disk-radius']['help'])

        self.grow_thr_label = QLabel("Grow threshold")
        self.grow_thr_entry = QLineEdit()
        self.grow_thr_entry.setValidator(get_double_validator())
        self.grow_thr_entry.editingFinished.connect(self.set_grow_thr)
        self.grow_thr_entry.setToolTip(SECTIONS['find-large-spots']['grow-threshold']['help'])
        self.grow_thr_label.setToolTip(SECTIONS['find-large-spots']['grow-threshold']['help'])

        self.spot_thr_sign_label = QLabel("Spot threshold mode")
        self.spot_thr_sign_entry = QComboBox()
        self.spot_thr_sign_entry.addItems(["absolute", "above", "below"])
        self.spot_thr_sign_entry.setCurrentText("absolute")
        self.spot_thr_sign_entry.currentIndexChanged.connect(self.set_spot_thr_sign)
        self.spot_thr_sign_entry.setToolTip(SECTIONS['find-large-spots']['spot-threshold-mode']['help'])
        self.spot_thr_sign_label.setToolTip(SECTIONS['find-large-spots']['spot-threshold-mode']['help'])

        self.median_direction_label = QLabel("Median direction")
        self.median_direction_entry = QComboBox()
        self.median_direction_entry.addItems(['both', 'horizontal', 'vertical'])
        self.median_direction_entry.setCurrentText("horizontal")
        self.median_direction_entry.currentIndexChanged.connect(self.set_median_direction)
        self.median_direction_entry.setToolTip(SECTIONS['find-large-spots']['median-direction']['help'])
        self.median_direction_label.setToolTip(SECTIONS['find-large-spots']['median-direction']['help'])




        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        # layout.addWidget(self.median_width_label, 1, 0)
        # layout.addWidget(self.median_width_entry, 1, 1, 1, 3)
        #
        # layout.addWidget(self.grow_thr_label, 2, 0)
        # layout.addWidget(self.grow_thr_entry, 2, 1, 1, 3)
        #
        # layout.addWidget(self.dil_disk_rad_label, 3, 0)
        # layout.addWidget(self.dil_disk_rad_entry, 3, 1, 1, 3)
        #
        # layout.addWidget(self.spot_thr_sign_label, 4, 0)
        # layout.addWidget(self.spot_thr_sign_entry, 4, 1)
        #
        # layout.addWidget(self.median_direction_label, 4, 2)
        # layout.addWidget(self.median_direction_entry, 4, 3)

        layout.addWidget(self.median_width_label, 1, 0)
        layout.addWidget(self.median_width_entry, 1, 1)

        layout.addWidget(self.grow_thr_label, 2, 0)
        layout.addWidget(self.grow_thr_entry, 2, 1)

        layout.addWidget(self.dil_disk_rad_label, 3, 0)
        layout.addWidget(self.dil_disk_rad_entry, 3, 1)

        layout.addWidget(self.spot_thr_sign_label, 4, 0)
        layout.addWidget(self.spot_thr_sign_entry, 4, 1)

        layout.addWidget(self.median_direction_label, 5, 0)
        layout.addWidget(self.median_direction_entry, 5, 1)

        self.setLayout(layout)

    def load_values(self):
        if EZVARS['filters']['rm_spots_use_median']['value']:
            self.setEnabled(True)
        self.median_width_entry.setText(str(SECTIONS['find-large-spots']['median-width']['value']))
        self.dil_disk_rad_entry.setText(str(SECTIONS['find-large-spots']['dilation-disk-radius']['value']))
        self.grow_thr_entry.setText(str(SECTIONS['find-large-spots']['grow-threshold']['value']))
        self.spot_thr_sign_entry.setCurrentText(str(SECTIONS['find-large-spots']['spot-threshold-mode']['value']))
        self.median_direction_entry.setCurrentText(str(SECTIONS['find-large-spots']['median-direction']['value']))

    def enable_by_trigger_from_main_tab(self):
        dict_entry = SECTIONS['find-large-spots']['method']
        if not self.isEnabled():
            self.setEnabled(True)
            add_value_to_dict_entry(EZVARS['filters']['rm_spots_use_median'], True)
            add_value_to_dict_entry(dict_entry, 'median')
        else:
            self.setEnabled(False)
            add_value_to_dict_entry(EZVARS['filters']['rm_spots_use_median'], False)
            add_value_to_dict_entry(dict_entry, 'grow')

    def set_median_width(self):
        dict_entry = SECTIONS['find-large-spots']['median-width']
        add_value_to_dict_entry(dict_entry, self.median_width_entry.text())

    def set_dil_disk_rad(self):
        dict_entry = SECTIONS['find-large-spots']['dilation-disk-radius']
        add_value_to_dict_entry(dict_entry, self.dil_disk_rad_entry.text())

    def set_grow_thr(self):
        dict_entry = SECTIONS['find-large-spots']['grow-threshold']
        add_value_to_dict_entry(dict_entry, self.grow_thr_entry.text())

    def set_spot_thr_sign(self):
        dict_entry = SECTIONS['find-large-spots']['spot-threshold-mode']
        self.spot_thr_sign_entry.currentText()
        add_value_to_dict_entry(dict_entry, self.spot_thr_sign_entry.currentText())

    def set_median_direction(self):
        dict_entry = SECTIONS['find-large-spots']['median-direction']
        add_value_to_dict_entry(dict_entry, self.median_direction_entry.currentText())
