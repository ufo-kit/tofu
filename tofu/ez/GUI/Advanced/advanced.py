import logging
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit

import tofu.ez.params as parameters


LOG = logging.getLogger(__name__)


class AdvancedGroup(QGroupBox):
    """
    Advanced Tofu Reco settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Advanced TOFU Reconstruction Settings")
        self.setStyleSheet("QGroupBox {color: green;}")

        # LAMINO
        self.lamino_group = QGroupBox("Extended Settings of Reconstruction Algorithms")
        self.lamino_group.clicked.connect(self.set_lamino_group)

        self.lamino_angle_label = QLabel("Laminographic angle                              ")
        self.lamino_angle_entry = QLineEdit()
        self.lamino_angle_entry.editingFinished.connect(self.set_lamino_angle)

        self.overall_rotation_label = QLabel("Overall rotation range about CT Z-axis")
        self.overall_rotation_entry = QLineEdit()
        self.overall_rotation_entry.editingFinished.connect(self.set_overall_rotation)

        self.center_position_z_label = QLabel("Center Position Z                              ")
        self.center_position_z_entry = QLineEdit()
        self.center_position_z_entry.editingFinished.connect(self.set_center_position_z)

        self.axis_rotation_y_label = QLabel(
            "Sample rotation about the beam Y-axis                             "
        )
        self.axis_rotation_y_entry = QLineEdit()
        self.axis_rotation_y_entry.editingFinished.connect(self.set_rotation_about_beam)

        # AUXILIARY FFC
        self.dark_scale_label = QLabel("Dark scale                              ")
        self.dark_scale_entry = QLineEdit()
        self.dark_scale_entry.editingFinished.connect(self.set_dark_scale)

        self.flat_scale_label = QLabel("Flat scale                              ")
        self.flat_scale_entry = QLineEdit()
        self.flat_scale_entry.editingFinished.connect(self.set_flat_scale)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        self.lamino_group.setCheckable(True)
        self.lamino_group.setChecked(False)
        lamino_layout = QGridLayout()
        lamino_layout.addWidget(self.lamino_angle_label, 0, 0)
        lamino_layout.addWidget(self.lamino_angle_entry, 0, 1)
        lamino_layout.addWidget(self.overall_rotation_label, 1, 0)
        lamino_layout.addWidget(self.overall_rotation_entry, 1, 1)
        lamino_layout.addWidget(self.center_position_z_label, 2, 0)
        lamino_layout.addWidget(self.center_position_z_entry, 2, 1)
        lamino_layout.addWidget(self.axis_rotation_y_label, 3, 0)
        lamino_layout.addWidget(self.axis_rotation_y_entry, 3, 1)
        self.lamino_group.setLayout(lamino_layout)

        aux_group = QGroupBox("Auxiliary FFC Settings")
        aux_group.setCheckable(True)
        aux_group.setChecked(False)
        aux_layout = QGridLayout()
        aux_layout.addWidget(self.dark_scale_label, 0, 0)
        aux_layout.addWidget(self.dark_scale_entry, 0, 1)
        aux_layout.addWidget(self.flat_scale_label, 1, 0)
        aux_layout.addWidget(self.flat_scale_entry, 1, 1)
        aux_group.setLayout(aux_layout)

        layout.addWidget(self.lamino_group)
        layout.addWidget(aux_group)

        self.setLayout(layout)

    def init_values(self):
        self.lamino_group.setChecked(False)
        parameters.params['advanced_advtofu_extended_settings'] = False
        self.lamino_angle_entry.setText("30")
        parameters.params['advanced_advtofu_lamino_angle'] = 30
        self.overall_rotation_entry.setText("360")
        parameters.params['advanced_adv_tofu_z_axis_rotation'] = 360
        self.center_position_z_entry.setText("")
        parameters.params['advanced_advtofu_center_position_z'] = ""
        self.axis_rotation_y_entry.setText("")
        parameters.params['advanced_advtofu_y_axis_rotation'] = ""
        self.dark_scale_entry.setText("")
        parameters.params['advanced_advtofu_aux_ffc_dark_scale'] = ""
        self.flat_scale_entry.setText("")
        parameters.params['advanced_advtofu_aux_ffc_flat_scale'] = ""

    def set_values_from_params(self):
        self.lamino_group.setChecked(parameters.params['advanced_advtofu_extended_settings'])
        self.lamino_angle_entry.setText(str(parameters.params['advanced_advtofu_lamino_angle']))
        self.overall_rotation_entry.setText(str(parameters.params['advanced_adv_tofu_z_axis_rotation']))
        self.center_position_z_entry.setText(str(parameters.params['advanced_advtofu_center_position_z']))
        self.axis_rotation_y_entry.setText(str(parameters.params['advanced_advtofu_y_axis_rotation']))
        self.dark_scale_entry.setText(str(parameters.params['advanced_advtofu_aux_ffc_dark_scale']))
        self.flat_scale_entry.setText(str(parameters.params['advanced_advtofu_aux_ffc_flat_scale']))

    def set_lamino_group(self):
        LOG.debug("Lamino: " + str(self.lamino_group.isChecked()))
        parameters.params['advanced_advtofu_extended_settings'] = bool(self.lamino_group.isChecked())

    def set_lamino_angle(self):
        LOG.debug(self.lamino_angle_entry.text())
        parameters.params['advanced_advtofu_lamino_angle'] = str(self.lamino_angle_entry.text())

    def set_overall_rotation(self):
        LOG.debug(self.overall_rotation_entry.text())
        parameters.params['advanced_adv_tofu_z_axis_rotation'] = str(self.overall_rotation_entry.text())

    def set_center_position_z(self):
        LOG.debug(self.center_position_z_entry.text())
        parameters.params['advanced_advtofu_center_position_z'] = str(self.center_position_z_entry.text())

    def set_rotation_about_beam(self):
        LOG.debug(self.axis_rotation_y_entry.text())
        parameters.params['advanced_advtofu_y_axis_rotation'] = str(self.axis_rotation_y_entry.text())

    def set_dark_scale(self):
        LOG.debug(self.dark_scale_entry.text())
        parameters.params['advanced_advtofu_aux_ffc_dark_scale'] = str(self.dark_scale_entry.text())

    def set_flat_scale(self):
        LOG.debug(self.flat_scale_entry.text())
        parameters.params['advanced_advtofu_aux_ffc_flat_scale'] = str(self.flat_scale_entry.text())
