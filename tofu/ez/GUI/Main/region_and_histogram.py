import logging
from PyQt5.QtWidgets import QGridLayout, QRadioButton, QLabel, QGroupBox, QLineEdit, QCheckBox
from PyQt5.QtCore import Qt

from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.ez.util import add_value_to_dict_entry, get_int_validator, get_double_validator, reverse_tupleize

LOG = logging.getLogger(__name__)


class ROIandHistGroup(QGroupBox):
    """
    Binning settings
    """

    def __init__(self):
        super().__init__()

        self.setTitle("Region of Interest and Histogram Settings")
        self.setStyleSheet("QGroupBox {color: red;}")

        self.select_rows_checkbox = QCheckBox()
        self.select_rows_checkbox.setText("Select rows which will be reconstructed")
        self.select_rows_checkbox.stateChanged.connect(self.set_select_rows)

        self.first_row_label = QLabel()
        self.first_row_label.setText("First row in projections")
        self.first_row_label.setToolTip("Counting from the top")
        self.first_row_entry = QLineEdit()
        self.first_row_entry.setValidator(get_int_validator())
        self.first_row_entry.editingFinished.connect(self.set_first_row)

        self.num_rows_label = QLabel()
        self.num_rows_label.setText("Number of rows (ROI height)")
        self.num_rows_entry = QLineEdit()
        self.num_rows_entry.setValidator(get_int_validator())
        self.num_rows_entry.editingFinished.connect(self.set_num_rows)

        self.nth_row_label = QLabel()
        self.nth_row_label.setText("Step (reconstruct every Nth row)")
        self.nth_row_entry = QLineEdit()
        self.nth_row_entry.setValidator(get_int_validator())
        self.nth_row_entry.editingFinished.connect(self.set_reco_nth_rows)

        self.clip_histo_checkbox = QCheckBox()
        self.clip_histo_checkbox.setText("Clip histogram and save slices in")
        self.clip_histo_checkbox.stateChanged.connect(self.set_clip_histo)

        self.eight_bit_rButton = QRadioButton()
        self.eight_bit_rButton.setText("8-bit")
        self.eight_bit_rButton.setChecked(True)
        self.eight_bit_rButton.clicked.connect(self.set_bitdepth)

        self.sixteen_bit_rButton = QRadioButton()
        self.sixteen_bit_rButton.setText("16-bit")
        self.sixteen_bit_rButton.clicked.connect(self.set_bitdepth)

        self.min_val_label = QLabel()
        self.min_val_label.setText("Min value in 32-bit histogram")
        self.min_val_entry = QLineEdit()
        #self.min_val_entry.setValidator(get_double_validator())
        self.min_val_entry.editingFinished.connect(self.set_min_val)

        self.max_val_label = QLabel()
        self.max_val_label.setText("Max value in 32-bit histogram")
        self.max_val_entry = QLineEdit()
        #self.max_val_entry.setValidator(get_double_validator())
        self.max_val_entry.editingFinished.connect(self.set_max_val)

        self.crop_slices_checkbox = QCheckBox()
        self.crop_slices_checkbox.setText("Crop slices")
        self.crop_slices_checkbox.setToolTip("Crop slices in the reconstruction plane \n"
                                             "(x,y) - top left corner of selection \n"
                                             "(width, height) - size of selection")
        self.crop_slices_checkbox.stateChanged.connect(self.set_crop_slices)

        self.x_val_label = QLabel()
        self.x_val_label.setText("x")
        self.x_val_label.setToolTip("First column (counting from left)")
        self.x_val_entry = QLineEdit()
        self.x_val_entry.setValidator(get_int_validator())
        self.x_val_entry.editingFinished.connect(self.set_x)

        self.width_val_label = QLabel()
        self.width_val_label.setText("width")
        self.width_val_entry = QLineEdit()
        self.width_val_entry.setValidator(get_int_validator())
        self.width_val_entry.editingFinished.connect(self.set_width)

        self.y_val_label = QLabel()
        self.y_val_label.setText("y")
        self.y_val_label.setToolTip("First row (counting from top)")
        self.y_val_entry = QLineEdit()
        self.y_val_entry.setValidator(get_int_validator())
        self.y_val_entry.editingFinished.connect(self.set_y)

        self.height_val_label = QLabel()
        self.height_val_label.setText("height")
        self.height_val_entry = QLineEdit()
        self.height_val_entry.setValidator(get_int_validator())
        self.height_val_entry.editingFinished.connect(self.set_height)

        self.rotate_vol_label = QLabel()
        self.rotate_vol_label.setText("Rotate volume counterclockwise by [deg]")
        self.rotate_vol_entry = QLineEdit()
        self.rotate_vol_entry.setValidator(get_double_validator())
        self.rotate_vol_entry.editingFinished.connect(self.set_rotate_volume)

        # self.setStyleSheet('background-color:Azure')

        self.set_layout()

    def set_layout(self):
        """
        Sets the layout of buttons, labels, etc. for binning group
        """
        layout = QGridLayout()

        layout.addWidget(self.select_rows_checkbox, 0, 0)
        layout.addWidget(self.first_row_label, 1, 0)
        layout.addWidget(self.first_row_entry, 1, 1, 1, 8)
        layout.addWidget(self.num_rows_label, 2, 0)
        layout.addWidget(self.num_rows_entry, 2, 1, 1, 8)
        layout.addWidget(self.nth_row_label, 3, 0)
        layout.addWidget(self.nth_row_entry, 3, 1, 1, 8)
        layout.addWidget(self.clip_histo_checkbox, 4, 0)
        layout.addWidget(self.eight_bit_rButton, 4, 1)
        layout.addWidget(self.sixteen_bit_rButton, 4, 2)
        layout.addWidget(self.min_val_label, 5, 0)
        layout.addWidget(self.min_val_entry, 5, 1, 1, 8)
        layout.addWidget(self.max_val_label, 6, 0)
        layout.addWidget(self.max_val_entry, 6, 1, 1, 8)
        layout.addWidget(self.crop_slices_checkbox, 7, 0)
        layout.addWidget(self.x_val_label, 7, 1)#, Qt.AlignRight)
        layout.addWidget(self.x_val_entry, 7, 2)
        layout.addWidget(self.width_val_label, 7, 3)#, Qt.AlignRight)
        layout.addWidget(self.width_val_entry, 7, 4)
        layout.addWidget(self.y_val_label, 7, 5)
        layout.addWidget(self.y_val_entry, 7, 6)
        layout.addWidget(self.height_val_label, 7, 7)
        layout.addWidget(self.height_val_entry, 7, 8)
        layout.addWidget(self.rotate_vol_label, 8, 0)
        layout.addWidget(self.rotate_vol_entry, 8, 1, 1, 8)

        self.setLayout(layout)

    def load_values(self):
        self.select_rows_checkbox.setChecked(EZVARS['inout']['input_ROI']['value'])
        self.first_row_entry.setText(str(SECTIONS['reading']['y']['value']))
        self.num_rows_entry.setText(str(SECTIONS['reading']['height']['value']))
        self.nth_row_entry.setText(str(SECTIONS['reading']['y-step']['value']))
        self.clip_histo_checkbox.setChecked(EZVARS['inout']['clip_hist']['value'])
        if int(SECTIONS['general']['output-bitdepth']['value']) == 8:
            self.eight_bit_rButton.setChecked(True)
            self.sixteen_bit_rButton.setChecked(False)
        elif int(SECTIONS['general']['output-bitdepth']['value']) == 16:
            self.eight_bit_rButton.setChecked(False)
            self.sixteen_bit_rButton.setChecked(True)
        self.min_val_entry.setText(str(SECTIONS['general']['output-minimum']['value']))
        self.max_val_entry.setText(str(SECTIONS['general']['output-maximum']['value']))
        self.crop_slices_checkbox.setChecked(EZVARS['inout']['output-ROI']['value'])
        self.x_val_entry.setText(str(EZVARS['inout']['output-x']['value']))
        self.width_val_entry.setText(str(EZVARS['inout']['output-width']['value']))
        self.y_val_entry.setText(str(EZVARS['inout']['output-y']['value']))
        self.height_val_entry.setText(str(EZVARS['inout']['output-height']['value']))
        self.rotate_vol_entry.setText(str(reverse_tupleize()(SECTIONS['general-reconstruction']['volume-angle-z']['value'])))

    def set_select_rows(self):
        LOG.debug("Select rows: " + str(self.select_rows_checkbox.isChecked()))
        dict_entry = EZVARS['inout']['input_ROI']
        add_value_to_dict_entry(dict_entry, self.select_rows_checkbox.isChecked())

    def set_first_row(self):
        LOG.debug(self.first_row_entry.text())
        dict_entry = SECTIONS['reading']['y']
        add_value_to_dict_entry(dict_entry, str(self.first_row_entry.text()))
        self.first_row_entry.setText(str(dict_entry['value']))

    def set_num_rows(self):
        LOG.debug(self.num_rows_entry.text())
        dict_entry = SECTIONS['reading']['height']
        add_value_to_dict_entry(dict_entry, str(self.num_rows_entry.text()))
        self.num_rows_entry.setText(str(dict_entry['value']))

    def set_reco_nth_rows(self):
        LOG.debug(self.nth_row_entry.text())
        dict_entry = SECTIONS['reading']['y-step']
        add_value_to_dict_entry(dict_entry, str(self.nth_row_entry.text()))
        self.nth_row_entry.setText(str(dict_entry['value']))

    def set_clip_histo(self):
        LOG.debug("Clip histo: " + str(self.clip_histo_checkbox.isChecked()))
        dict_entry = EZVARS['inout']['clip_hist']
        add_value_to_dict_entry(dict_entry, self.clip_histo_checkbox.isChecked())
        if EZVARS['inout']['clip_hist']['value']:
            return self.set_bitdepth()
        else:
            return '32'

    def set_bitdepth(self):
        dict_entry = SECTIONS['general']['output-bitdepth']
        if self.eight_bit_rButton.isChecked():
            LOG.debug("8 bit")
            add_value_to_dict_entry(dict_entry, str(8))
            return '8'
        elif self.sixteen_bit_rButton.isChecked():
            LOG.debug("16 bit")
            add_value_to_dict_entry(dict_entry, str(16))
            return '16'


    def set_min_val(self):
        LOG.debug(self.min_val_entry.text())
        dict_entry = SECTIONS['general']['output-minimum']
        add_value_to_dict_entry(dict_entry, self.min_val_entry.text())

    def set_max_val(self):
        LOG.debug(self.max_val_entry.text())
        dict_entry = SECTIONS['general']['output-maximum']
        add_value_to_dict_entry(dict_entry, self.max_val_entry.text())

    def set_crop_slices(self):
        LOG.debug("Crop slices: " + str(self.crop_slices_checkbox.isChecked()))
        dict_entry = EZVARS['inout']['output-ROI']
        add_value_to_dict_entry(dict_entry, self.crop_slices_checkbox.isChecked())

    def set_x(self):
        LOG.debug(self.x_val_entry.text())
        dict_entry = EZVARS['inout']['output-x']
        add_value_to_dict_entry(dict_entry, str(self.x_val_entry.text()))
        self.x_val_entry.setText(str(dict_entry['value']))

    def set_width(self):
        LOG.debug(self.width_val_entry.text())
        dict_entry = EZVARS['inout']['output-width']
        add_value_to_dict_entry(dict_entry, str(self.width_val_entry.text()))
        self.width_val_entry.setText(str(dict_entry['value']))

    def set_y(self):
        LOG.debug(self.y_val_entry.text())
        dict_entry = EZVARS['inout']['output-y']
        add_value_to_dict_entry(dict_entry, str(self.y_val_entry.text()))
        self.y_val_entry.setText(str(dict_entry['value']))

    def set_height(self):
        LOG.debug(self.height_val_entry.text())
        dict_entry = EZVARS['inout']['output-height']
        add_value_to_dict_entry(dict_entry, str(self.height_val_entry.text()))
        self.height_val_entry.setText(str(dict_entry['value']))

    def set_rotate_volume(self):
        LOG.debug(self.rotate_vol_entry.text())
        dict_entry = SECTIONS['general-reconstruction']['volume-angle-z']
        add_value_to_dict_entry(dict_entry, str(self.rotate_vol_entry.text()))
        self.rotate_vol_entry.setText(str(reverse_tupleize()(dict_entry['value'])))
