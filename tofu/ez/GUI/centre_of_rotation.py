import logging
from qtpy.QtWidgets import QGridLayout, QLabel, QRadioButton, QGroupBox, QLineEdit

import tofu.ez.GUI.params as parameters


LOG = logging.getLogger(__name__)


class CentreOfRotationGroup(QGroupBox):
    """
    Centre of Rotation settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Centre of Rotation")
        self.setStyleSheet('QGroupBox {color: green;}')

        self.auto_correlate_rButton = QRadioButton()
        self.auto_correlate_rButton.setText("Auto: Correlate first/last projections")
        self.auto_correlate_rButton.clicked.connect(self.set_rButton)

        self.auto_minimize_rButton = QRadioButton()
        self.auto_minimize_rButton.setText("Auto: Minimize STD of a slice")
        self.auto_minimize_rButton.clicked.connect(self.set_rButton)

        self.define_axis_rButton = QRadioButton()
        self.define_axis_rButton.setText("Define rotation axis manually")
        self.define_axis_rButton.clicked.connect(self.set_rButton)

        self.search_rotation_label = QLabel()
        self.search_rotation_label.setText("Search rotation axis in start, stop, step interval:")
        self.search_rotation_entry = QLineEdit()
        self.search_rotation_entry.textChanged.connect(self.set_search_rotation)
        self.search_rotation_entry.setStyleSheet("background-color:white")

        self.search_in_slice_label = QLabel()
        self.search_in_slice_label.setText("Search in slice from row number")
        self.search_in_slice_entry = QLineEdit()
        self.search_in_slice_entry.textChanged.connect(self.set_search_slice)
        self.search_in_slice_entry.setStyleSheet("background-color:white")

        self.side_of_recon_label = QLabel()
        self.side_of_recon_label.setText("Side of reconstructed path [pixel]")
        self.side_of_recon_entry = QLineEdit()
        self.side_of_recon_entry.textChanged.connect(self.set_side_of_reco)
        self.side_of_recon_entry.setStyleSheet("background-color:white")

        self.axis_col_label = QLabel()
        self.axis_col_label.setText("Axis is in column No [pixel]")
        self.axis_col_entry = QLineEdit()
        self.axis_col_entry.textChanged.connect(self.set_axis_col)
        self.axis_col_entry.setStyleSheet("background-color:white")

        self.inc_axis_label = QLabel()
        self.inc_axis_label.setText("Increment axis every reconstruction")
        self.inc_axis_entry = QLineEdit()
        self.inc_axis_entry.textChanged.connect(self.set_axis_inc)
        self.inc_axis_entry.setStyleSheet("background-color:white")

        #self.setStyleSheet('background-color:lightcoral')

        self.set_layout()
        #self.init_values()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.auto_correlate_rButton, 0, 0)
        layout.addWidget(self.auto_minimize_rButton, 0, 1)
        layout.addWidget(self.search_rotation_label, 1, 0)
        layout.addWidget(self.search_rotation_entry, 1, 1)
        layout.addWidget(self.search_in_slice_label, 2, 0)
        layout.addWidget(self.search_in_slice_entry, 2, 1)
        layout.addWidget(self.side_of_recon_label, 3, 0)
        layout.addWidget(self.side_of_recon_entry, 3, 1)
        layout.addWidget(self.define_axis_rButton, 4, 0)
        layout.addWidget(self.axis_col_label, 5, 0)
        layout.addWidget(self.axis_col_entry, 5, 1)
        layout.addWidget(self.inc_axis_label, 6, 0)
        layout.addWidget(self.inc_axis_entry, 6, 1)

        self.setLayout(layout)

    def init_values(self):
        self.auto_correlate_rButton.setChecked(True)
        self.auto_minimize_rButton.setChecked(False)
        self.define_axis_rButton.setChecked(False)
        self.set_rButton()
        self.search_rotation_entry.setText("1010,1030,0.5")
        self.search_in_slice_entry.setText("100")
        self.side_of_recon_entry.setText("256")
        self.axis_col_entry.setText("0.0")
        self.inc_axis_entry.setText("0.0")

    def set_values_from_params(self):
        self.set_rButton_from_params()
        self.search_rotation_entry.setText(str(parameters.params['e_ax_range']))
        self.search_in_slice_entry.setText(str(parameters.params['e_ax_row']))
        self.side_of_recon_entry.setText(str(parameters.params['e_ax_p_size']))
        self.axis_col_entry.setText(str(parameters.params['e_ax_fix']))
        self.inc_axis_entry.setText(str(parameters.params['e_dax']))

    def set_rButton(self):
        if self.auto_correlate_rButton.isChecked():
            LOG.debug("Auto Correlate")
            parameters.params['e_ax'] = 1
        elif self.auto_minimize_rButton.isChecked():
            LOG.debug("Auto Minimize")
            parameters.params['e_ax'] = 2
        elif self.define_axis_rButton.isChecked():
            LOG.debug("Define axis")
            parameters.params['e_ax'] = 3

    def set_rButton_from_params(self):
        if parameters.params['e_ax'] == 1:
            self.auto_correlate_rButton.setChecked(True)
            self.auto_minimize_rButton.setChecked(False)
            self.define_axis_rButton.setChecked(False)
        elif parameters.params['e_ax'] == 2:
            self.auto_correlate_rButton.setChecked(False)
            self.auto_minimize_rButton.setChecked(True)
            self.define_axis_rButton.setChecked(False)
        elif parameters.params['e_ax'] == 3:
            self.auto_correlate_rButton.setChecked(False)
            self.auto_minimize_rButton.setChecked(False)
            self.define_axis_rButton.setChecked(True)

    def set_search_rotation(self):
        LOG.debug(self.search_rotation_entry.text())
        parameters.params['e_ax_range'] = self.search_rotation_entry.text()

    def set_search_slice(self):
        LOG.debug(self.search_in_slice_entry.text())
        parameters.params['e_ax_row'] = self.search_in_slice_entry.text()

    def set_side_of_reco(self):
        LOG.debug(self.side_of_recon_entry.text())
        parameters.params['e_ax_p_size'] = self.side_of_recon_entry.text()

    def set_axis_col(self):
        LOG.debug(self.axis_col_entry.text())
        parameters.params['e_ax_fix'] = self.axis_col_entry.text()

    def set_axis_inc(self):
        LOG.debug(self.inc_axis_entry.text())
        parameters.params['e_dax'] = self.inc_axis_entry.text()
