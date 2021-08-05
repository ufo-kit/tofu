import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QRadioButton, QGroupBox, QLineEdit, QCheckBox

import tofu.ez.GUI.params as parameters

class OptimizationGroup(QGroupBox):
    """
    Optimization settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Optimization Settings")
        self.setStyleSheet('QGroupBox {color: orange;}')

        self.verbose_switch = QCheckBox("Enable verbose console output")
        self.verbose_switch.stateChanged.connect(self.set_verbose_switch)

        self.slice_memory_label = QLabel("Slice memory coefficient")
        self.slice_memory_entry = QLineEdit()
        self.slice_memory_entry.textChanged.connect(self.set_slice)

        self.num_GPU_label = QLabel("Number of GPUs")
        self.num_GPU_entry = QLineEdit()
        self.num_GPU_entry.textChanged.connect(self.set_num_gpu)

        self.slices_per_device_label = QLabel("Slices per device")
        self.slices_per_device_entry = QLineEdit()
        self.slices_per_device_entry.textChanged.connect(self.set_slices_per_device)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.verbose_switch, 0, 0)

        gpu_group = QGroupBox('GPU optimization')
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
        parameters.params['e_adv_verbose'] = False
        self.slice_memory_entry.setText("0.5")
        parameters.params['e_adv_slice_mem_coeff'] = "0.5"
        self.num_GPU_entry.setText("")
        parameters.params['e_adv_num_gpu'] = ""
        self.slices_per_device_entry.setText("")
        parameters.params['e_adv_slices_per_device'] = ""

    def set_values_from_params(self):
        self.verbose_switch.setChecked(bool(parameters.params['e_adv_verbose']))
        self.slice_memory_entry.setText(str(parameters.params['e_adv_slice_mem_coeff']))
        self.num_GPU_entry.setText(str(parameters.params['e_adv_num_gpu']))
        self.slices_per_device_entry.setText(str(parameters.params['e_adv_slices_per_device']))

    def set_verbose_switch(self):
        logging.debug("Verbose: " + str(self.verbose_switch.isChecked()))
        parameters.params['e_adv_verbose'] = bool(self.verbose_switch.isChecked())

    def set_slice(self):
        logging.debug(self.slice_memory_entry.text())
        parameters.params['e_adv_slice_mem_coeff'] = str(self.slice_memory_entry.text())

    def set_num_gpu(self):
        logging.debug(self.num_GPU_entry.text())
        parameters.params['e_adv_num_gpu'] = str(self.num_GPU_entry.text())

    def set_slices_per_device(self):
        logging.debug(self.slices_per_device_entry.text())
        parameters.params['e_adv_slices_per_device'] = str(self.slices_per_device_entry.text())