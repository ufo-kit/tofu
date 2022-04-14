import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QRadioButton, QGroupBox, QLineEdit

import tofu.ez.params as parameters


LOG = logging.getLogger(__name__)


class CentreOfRotationGroup(QGroupBox):
    """
    Centre of Rotation settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Centre of Rotation")
        self.setStyleSheet("QGroupBox {color: green;}")

        self.auto_correlate_rButton = QRadioButton()
        self.auto_correlate_rButton.setText("Auto: Correlate first/last projections")
        self.auto_correlate_rButton.clicked.connect(self.set_rButton)

        self.auto_minimize_rButton = QRadioButton()
        self.auto_minimize_rButton.setText("Auto: Minimize STD of a slice")
        self.auto_minimize_rButton.setToolTip(
            "Reconstructed patches are saved \nin your-temporary-data-folder\\axis-search"
        )
        self.auto_minimize_rButton.clicked.connect(self.set_rButton)

        self.define_axis_rButton = QRadioButton()
        self.define_axis_rButton.setText("Define rotation axis manually")
        self.define_axis_rButton.clicked.connect(self.set_rButton)

        self.search_rotation_label = QLabel()
        self.search_rotation_label.setText("Search rotation axis in [start, stop, step] interval")
        self.search_rotation_entry = QLineEdit()
        self.search_rotation_entry.editingFinished.connect(self.set_search_rotation)
        self.search_rotation_entry.setStyleSheet("background-color:white")

        self.search_in_slice_label = QLabel()
        self.search_in_slice_label.setText("Search in slice from row number")
        self.search_in_slice_entry = QLineEdit()
        self.search_in_slice_entry.editingFinished.connect(self.set_search_slice)
        self.search_in_slice_entry.setStyleSheet("background-color:white")

        self.size_of_recon_label = QLabel()
        self.size_of_recon_label.setText("Size of reconstructed patch [pixel]")
        self.size_of_recon_entry = QLineEdit()
        self.size_of_recon_entry.editingFinished.connect(self.set_size_of_reco)
        self.size_of_recon_entry.setStyleSheet("background-color:white")

        self.axis_col_label = QLabel()
        self.axis_col_label.setText("Axis is in column No [pixel]")
        self.axis_col_entry = QLineEdit()
        self.axis_col_entry.editingFinished.connect(self.set_axis_col)
        self.axis_col_entry.setStyleSheet("background-color:white")

        self.inc_axis_label = QLabel()
        self.inc_axis_label.setText("Increment axis every reconstruction")
        self.inc_axis_entry = QLineEdit()
        self.inc_axis_entry.editingFinished.connect(self.set_axis_inc)
        self.inc_axis_entry.setStyleSheet("background-color:white")

        self.image_midpoint_rButton = QRadioButton()
        self.image_midpoint_rButton.setText("Use image midpoint (for half-acquisition)")
        self.image_midpoint_rButton.clicked.connect(self.set_rButton)

        # TODO Used for proper spacing - should be a better way
        self.blank_label = QLabel("                                ")
        self.blank_label2 = QLabel("                                ")

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.auto_correlate_rButton, 0, 0)
        layout.addWidget(self.blank_label, 0, 1)
        layout.addWidget(self.blank_label2, 0, 2)
        layout.addWidget(self.auto_minimize_rButton, 1, 0)
        layout.addWidget(self.search_rotation_label, 2, 0)
        layout.addWidget(self.search_rotation_entry, 2, 1, 1, 2)
        layout.addWidget(self.search_in_slice_label, 3, 0)
        layout.addWidget(self.search_in_slice_entry, 3, 1, 1, 2)
        layout.addWidget(self.size_of_recon_label, 4, 0)
        layout.addWidget(self.size_of_recon_entry, 4, 1, 1, 2)
        layout.addWidget(self.define_axis_rButton, 5, 0)
        layout.addWidget(self.axis_col_label, 6, 0)
        layout.addWidget(self.axis_col_entry, 6, 1, 1, 2)
        layout.addWidget(self.inc_axis_label, 7, 0)
        layout.addWidget(self.inc_axis_entry, 7, 1, 1, 2)
        layout.addWidget(self.image_midpoint_rButton, 8, 0)

        self.setLayout(layout)

    def init_values(self):
        self.auto_correlate_rButton.setChecked(True)
        self.auto_minimize_rButton.setChecked(False)
        self.define_axis_rButton.setChecked(False)
        self.image_midpoint_rButton.setChecked(False)
        self.set_rButton()
        self.search_rotation_entry.setText("1010,1030,0.5")
        self.search_in_slice_entry.setText("100")
        self.size_of_recon_entry.setText("256")
        self.axis_col_entry.setText("0.0")
        self.inc_axis_entry.setText("0.0")

    # self.bypass_checkbox.setChecked(False)

    def set_values_from_params(self):
        self.set_rButton_from_params()
        self.search_rotation_entry.setText(str(parameters.params['main_cor_axis_search_interval']))
        self.search_in_slice_entry.setText(str(parameters.params['main_cor_search_row_start']))
        self.size_of_recon_entry.setText(str(parameters.params['main_cor_recon_patch_size']))
        self.axis_col_entry.setText(str(parameters.params['main_cor_axis_column']))
        self.inc_axis_entry.setText(str(parameters.params['main_cor_axis_increment_step']))

    def set_rButton(self):
        if self.auto_correlate_rButton.isChecked():
            LOG.debug("Auto Correlate")
            parameters.params['main_cor_axis_search_method'] = 1
        elif self.auto_minimize_rButton.isChecked():
            LOG.debug("Auto Minimize")
            parameters.params['main_cor_axis_search_method'] = 2
        elif self.define_axis_rButton.isChecked():
            LOG.debug("Define axis")
            parameters.params['main_cor_axis_search_method'] = 3
        elif self.image_midpoint_rButton.isChecked():
            LOG.debug("Use image midpoint")
            parameters.params['main_cor_axis_search_method'] = 4

    def set_rButton_from_params(self):
        if parameters.params['main_cor_axis_search_method'] == 1:
            self.auto_correlate_rButton.setChecked(True)
            self.auto_minimize_rButton.setChecked(False)
            self.define_axis_rButton.setChecked(False)
            self.image_midpoint_rButton.setChecked(False)
        elif parameters.params['main_cor_axis_search_method'] == 2:
            self.auto_correlate_rButton.setChecked(False)
            self.auto_minimize_rButton.setChecked(True)
            self.define_axis_rButton.setChecked(False)
            self.image_midpoint_rButton.setChecked(False)
        elif parameters.params['main_cor_axis_search_method'] == 3:
            self.auto_correlate_rButton.setChecked(False)
            self.auto_minimize_rButton.setChecked(False)
            self.define_axis_rButton.setChecked(True)
            self.image_midpoint_rButton.setChecked(False)
        elif parameters.params['main_cor_axis_search_method'] == 4:
            self.auto_correlate_rButton.setChecked(False)
            self.auto_minimize_rButton.setChecked(False)
            self.define_axis_rButton.setChecked(False)
            self.image_midpoint_rButton.setChecked(True)

    def set_search_rotation(self):
        LOG.debug(self.search_rotation_entry.text())
        parameters.params['main_cor_axis_search_interval'] = str(self.search_rotation_entry.text())

    def set_search_slice(self):
        LOG.debug(self.search_in_slice_entry.text())
        parameters.params['main_cor_search_row_start'] = str(self.search_in_slice_entry.text())

    def set_size_of_reco(self):
        LOG.debug(self.size_of_recon_entry.text())
        parameters.params['main_cor_recon_patch_size'] = str(self.size_of_recon_entry.text())

    def set_axis_col(self):
        LOG.debug(self.axis_col_entry.text())
        parameters.params['main_cor_axis_column'] = str(self.axis_col_entry.text())

    def set_axis_inc(self):
        LOG.debug(self.inc_axis_entry.text())
        parameters.params['main_cor_axis_increment_step'] = str(self.inc_axis_entry.text())