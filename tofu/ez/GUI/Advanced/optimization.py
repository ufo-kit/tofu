import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QCheckBox

import tofu.ez.params as parameters


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
        tmpstr="Fraction of VRAM which will be used to store images \n" \
               "Reserve ~2 GB of VRAM for computation \n" \
               "Decrease the coefficient if you have very large data and start getting errors"
        self.slice_memory_entry.setToolTip(tmpstr)
        self.slice_memory_label.setToolTip(tmpstr)
        self.slice_memory_entry.editingFinished.connect(self.set_slice)

        self.num_GPU_label = QLabel("Number of GPUs")
        self.num_GPU_entry = QLineEdit()
        self.num_GPU_entry.editingFinished.connect(self.set_num_gpu)

        self.slices_per_device_label = QLabel("Slices per device")
        self.slices_per_device_entry = QLineEdit()
        self.slices_per_device_entry.editingFinished.connect(self.set_slices_per_device)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.verbose_switch, 0, 0)

        gpu_group = QGroupBox("GPU optimization")
        gpu_group.setCheckable(True)
        gpu_group.setChecked(False)
        gpu_layout = QGridLayout()
        gpu_layout.addWidget(self.slice_memory_label, 0, 0)
        gpu_layout.addWidget(self.slice_memory_entry, 0, 1)
        gpu_layout.addWidget(self.num_GPU_label, 1, 0)
        gpu_layout.addWidget(self.num_GPU_entry, 1, 1)
        gpu_layout.addWidget(self.slices_per_device_label, 2, 0)
        gpu_layout.addWidget(self.slices_per_device_entry, 2, 1)
        gpu_group.setLayout(gpu_layout)

        layout.addWidget(gpu_group, 1, 0)

        self.setLayout(layout)

    def init_values(self):
        self.verbose_switch.setChecked(False)
        parameters.params['advanced_optimize_verbose_console'] = False
        parameters.params['advanced_optimize_slice_mem_coeff'] = 0.7
        self.slice_memory_entry.setText(
            str(parameters.params['advanced_optimize_slice_mem_coeff']))
        self.num_GPU_entry.setText("")
        parameters.params['advanced_optimize_num_gpus'] = ""
        self.slices_per_device_entry.setText("")
        parameters.params['advanced_optimize_slices_per_device'] = ""

    def set_values_from_params(self):
        self.verbose_switch.setChecked(bool(parameters.params['advanced_optimize_verbose_console']))
        self.slice_memory_entry.setText(str(parameters.params['advanced_optimize_slice_mem_coeff']))
        self.num_GPU_entry.setText(str(parameters.params['advanced_optimize_num_gpus']))
        self.slices_per_device_entry.setText(str(parameters.params['advanced_optimize_slices_per_device']))

    def set_verbose_switch(self):
        LOG.debug("Verbose: " + str(self.verbose_switch.isChecked()))
        parameters.params['advanced_optimize_verbose_console'] = bool(self.verbose_switch.isChecked())

    def set_slice(self):
        LOG.debug(self.slice_memory_entry.text())
        parameters.params['advanced_optimize_slice_mem_coeff'] = str(self.slice_memory_entry.text())

    def set_num_gpu(self):
        LOG.debug(self.num_GPU_entry.text())
        parameters.params['advanced_optimize_num_gpus'] = str(self.num_GPU_entry.text())

    def set_slices_per_device(self):
        LOG.debug(self.slices_per_device_entry.text())
        parameters.params['advanced_optimize_slices_per_device'] = str(self.slices_per_device_entry.text())