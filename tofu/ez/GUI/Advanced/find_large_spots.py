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
from tofu.config import SECTIONS
from tofu.ez.util import add_value_to_dict_entry, get_int_validator

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

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.median_width_label, 1, 0)
        layout.addWidget(self.median_width_entry, 1, 1)

        self.setLayout(layout)

    # def load_values(self):
    #     self.enable_sinFFC_checkbox.setChecked(EZVARS['flat-correction']['smart-ffc']['value'])
    #     self.set_method_from_params()
    #     self.eigen_pco_repetitions_entry.setText(str(EZVARS['flat-correction']['eigen-pco-reps']['value']))
    #     self.eigen_pco_downsample_entry.setText(str(EZVARS['flat-correction']['eigen-pco-downsample']['value']))
    #     self.downsample_entry.setText(str(EZVARS['flat-correction']['downsample']['value']))

    def enable_by_trigger_from_main_tab(self):
        dict_entry = SECTIONS['find-large-spots']['method']
        if not self.isEnabled():
            self.setEnabled(True)
            add_value_to_dict_entry(dict_entry, 'median')
        else:
            self.setEnabled(False)
            add_value_to_dict_entry(dict_entry, 'grow')
        print(SECTIONS['find-large-spots']['method']['value'])

    def enable_median(self):
        return 0

    def set_median_width(self):
        dict_entry = SECTIONS['find-large-spots']['median-width']
        add_value_to_dict_entry(dict_entry, self.threshold_entry.text())
        self.threshold_entry.setText(str(dict_entry['value']))