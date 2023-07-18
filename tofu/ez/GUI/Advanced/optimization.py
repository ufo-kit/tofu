import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QCheckBox, QComboBox

from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.util import add_value_to_dict_entry, get_double_validator


LOG = logging.getLogger(__name__)


class OptimizationGroup(QGroupBox):
    """
    Optimization settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Optimization Settings")
        self.setStyleSheet("QGroupBox {color: orange;}")

        self.verbose_switch = QCheckBox("Enable verbose console output")
        self.verbose_switch.stateChanged.connect(self.set_verbose_switch)

        self.slice_memory_label = QLabel("Slice memory coefficient")
        self.slice_memory_entry = QLineEdit()
        self.slice_memory_entry.setValidator(get_double_validator())
        tmpstr="Fraction of VRAM which will be used to store images \n" \
               "Reserve ~2 GB of VRAM for computation \n" \
               "Decrease the coefficient if you have very large data and start getting errors"
        self.slice_memory_entry.setToolTip(tmpstr)
        self.slice_memory_label.setToolTip(tmpstr)
        self.slice_memory_entry.editingFinished.connect(self.set_slice)

        self.data_spllitting_policy_label = QLabel("Data Splitting Policy")
        self.data_spllitting_policy_combobox = QComboBox()
        self.data_spllitting_policy_label.setToolTip(SECTIONS['general-reconstruction']['data-splitting-policy']['help'])
        self.data_spllitting_policy_combobox.setToolTip(SECTIONS['general-reconstruction']['data-splitting-policy']['help'])
        self.data_spllitting_policy_combobox.addItems(["one","many"])
        self.data_spllitting_policy_combobox.currentIndexChanged.connect(self.set_data_splitting_policy)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.verbose_switch, 0, 0)

        gpu_group = QGroupBox("GPU optimization")
        gpu_group.setCheckable(True)
        gpu_group.setChecked(bool(EZVARS['advanced']['enable-optimization']['value']))
        gpu_group.clicked.connect(self.set_enable_optimization)
        
        gpu_layout = QGridLayout()
        gpu_layout.addWidget(self.slice_memory_label, 0, 0)
        gpu_layout.addWidget(self.slice_memory_entry, 0, 1)
        gpu_layout.addWidget(self.data_spllitting_policy_label, 1, 0)
        gpu_layout.addWidget(self.data_spllitting_policy_combobox, 1, 1)
        gpu_group.setLayout(gpu_layout)

        layout.addWidget(gpu_group, 1, 0)

        self.setLayout(layout)

    def load_values(self):
        self.verbose_switch.setChecked(bool(SECTIONS['general']['verbose']['value']))
        self.slice_memory_entry.setText(str(SECTIONS['general-reconstruction']['slice-memory-coeff']['value']))
        idx = self.data_spllitting_policy_combobox.findText(SECTIONS['general-reconstruction']['data-splitting-policy']['value'])
        if idx >= 0:
            self.data_spllitting_policy_combobox.setCurrentIndex(idx)

    def set_verbose_switch(self):
        LOG.debug("Verbose: " + str(self.verbose_switch.isChecked()))
        dict_entry = SECTIONS['general']['verbose']
        add_value_to_dict_entry(dict_entry, self.verbose_switch.isChecked())

    def set_enable_optimization(self):
        checkbox = self.sender()
        LOG.debug("GPU Optimization: " + str(checkbox.isChecked()))
        dict_entry = EZVARS['advanced']['enable-optimization']
        add_value_to_dict_entry(dict_entry, checkbox.isChecked())
        
    def set_slice(self):
        LOG.debug(self.slice_memory_entry.text())
        dict_entry = SECTIONS['general-reconstruction']['slice-memory-coeff']
        add_value_to_dict_entry(dict_entry, str(self.slice_memory_entry.text()))
        self.slice_memory_entry.setText(str(dict_entry['value']))
        
    def set_data_splitting_policy(self):
        LOG.debug(self.data_spllitting_policy_combobox.currentText())
        dict_entry = SECTIONS['general-reconstruction']['data-splitting-policy']
        add_value_to_dict_entry(dict_entry, str(self.data_spllitting_policy_combobox.currentText()))
        