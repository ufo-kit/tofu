from PyQt5.QtWidgets import (
    QGroupBox,
    QRadioButton,
    QPushButton,
    QCheckBox,
    QLabel,
    QLineEdit,
    QGridLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSignal
import logging
import os
from tofu.ez.params import EZVARS_prep, EZVARS
from tofu.ez.util import add_value_to_dict_entry, get_int_validator
from tofu.ez.ufo_cmd_gen import fmt_crop_bin
from tofu.ez.GUI.message_dialog import warning_message
from shutil import rmtree


LOG = logging.getLogger(__name__)

class PreprocessingGroupMainTab(QGroupBox):
    signal_prepro_more = pyqtSignal()
    def __init__(self):
        super().__init__()

        self.preproc_title_checkbox = QCheckBox("Preprocess raw images:    ")
        self.preproc_title_checkbox.stateChanged.connect(self.set_enable_preproc)

        self.preproc_title_checkbox.setToolTip(
            "Use to suppress \"Zingers\" by removing the hot-spots (outliers)"
            "or  to apply more operations to raw images \n"
            'before the reconstruction begins'
        )

        self.preproc_switch_rmout_only = QRadioButton()
        self.preproc_switch_rmout_only.setText("Remove positive outliers:  ")
        self.preproc_switch_rmout_only.setChecked(True)
        self.preproc_switch_rmout_only.clicked.connect(self.set_choose_preproc)

        self.preproc_rmout_size_label = QLabel()
        self.preproc_rmout_size_label.setText("Size of window [pxls]")
        self.preproc_rmout_size_entry = QLineEdit()
        self.preproc_rmout_size_entry.setValidator(get_int_validator())
        self.preproc_rmout_size_entry.editingFinished.connect(self.set_choose_preproc)
        #self.preproc_rmout_size_entry.setFixedWidth(40)

        self.preproc_rmout_thr_label = QLabel()
        self.preproc_rmout_thr_label.setText("Threshold")
        self.preproc_rmout_thr_entry = QLineEdit()
        self.preproc_rmout_thr_entry.setValidator(get_int_validator())
        self.preproc_rmout_size_entry.editingFinished.connect(self.set_rmout_thr)
        #self.preproc_rmout_thr_entry.setFixedWidth(40)

        self.preproc_switch_more = QRadioButton()
        self.preproc_switch_more.setText("More operations")
        self.preproc_switch_more.setToolTip(
            "More operations from Preprocessing tab including generic ufo-launch pipeline."
        )
        self.preproc_switch_more.clicked.connect(self.set_choose_preproc)

        self.preproc_spacer = QLabel()
        self.preproc_spacer.setText("     ")
        self.preproc_spacer.setFixedWidth(50)

        self.preproc_entry = QLineEdit()
        #self.preproc_entry.editingFinished.connect(self.set_preproc_entry)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.preproc_title_checkbox, 0, 0)
        layout.addWidget(self.preproc_switch_rmout_only, 0, 1)
        layout.addWidget(self.preproc_rmout_size_label, 0, 2)
        layout.addWidget(self.preproc_rmout_size_entry, 0 ,3)
        layout.addWidget(self.preproc_spacer, 0, 4)
        layout.addWidget(self.preproc_rmout_thr_label, 0, 5)
        layout.addWidget(self.preproc_rmout_thr_entry, 0 ,6)

        c=7
        layout.addWidget(self.preproc_spacer, 0, c)
        c+=1
        layout.addWidget(self.preproc_spacer, 0, c)

        c+=1
        layout.addWidget(self.preproc_switch_more, 0, c)

        self.setLayout(layout)

    def load_values(self):
        self.preproc_title_checkbox.setChecked(bool(EZVARS['inout']['preprocess']['value']))
        if EZVARS_prep['prepro']['extended_prepro']['value']:
            self.preproc_switch_more.setChecked(True)
            self.preproc_switch_rmout_only.setChecked(False)
        else:
            self.preproc_switch_more.setChecked(False)
            self.preproc_switch_rmout_only.setChecked(True)
        self.preproc_rmout_thr_entry.setText(str(EZVARS_prep['prepro']['rmout_thr']['value']))
        self.preproc_rmout_size_entry.setText(str(EZVARS_prep['prepro']['rmout_size']['value']))
        return

    def set_enable_preproc(self):
        dict_entry = EZVARS['inout']['preprocess']
        add_value_to_dict_entry(dict_entry, bool(self.preproc_title_checkbox.isChecked()))
        # if self.preproc_title_checkbox.isChecked():
        #     add_value_to_dict_entry(dict_entry, bool(self.preproc_title_checkbox.isChecked()))
        # else:
        #     add_value_to_dict_entry(dict_entry, self.preproc_title_checkbox.isChecked())

    def set_choose_preproc(self):
        if self.preproc_switch_rmout_only.isChecked():
            self.preproc_switch_more.setChecked(False)
            add_value_to_dict_entry(EZVARS_prep['prepro']['extended_prepro'], False)
        if self.preproc_switch_more.isChecked():
            add_value_to_dict_entry(EZVARS_prep['prepro']['extended_prepro'], True)
            self.preproc_switch_rmout_only.setChecked(False)
            self.signal_prepro_more.emit()


    def set_rmout_size(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['rmout_size'], int(self.preproc_rmout_size_entry.text()))

    def set_rmout_thr(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['rmout_thr'], int(self.preproc_rmout_thr_entry.text()))





class PreprocessingGroup(QGroupBox):
    def __init__(self):
        super().__init__()

        self.setTitle("Apply basic image filters change the data cube bit-depth")
        self.setStyleSheet('QGroupBox {color: Green;}')

        self.input_dir_button = QPushButton("Select input directory")
        self.input_dir_button.clicked.connect(self.input_button_pressed)
        self.input_dir_entry = QLineEdit()
        #self.input_dir_entry.setText("/staff/gasilos/_aaa_images/flats")
        self.input_dir_entry.editingFinished.connect(self.set_input_entry)

        self.output_dir_button = QPushButton("Select output directory")
        self.output_dir_button.clicked.connect(self.output_button_pressed)
        self.output_dir_entry = QLineEdit()
        #self.output_dir_entry.setText("/staff/gasilos/_aaa_images/flats-processed")
        self.output_dir_entry.editingFinished.connect(self.set_output_entry)

        self.bigtiff_checkbox = QCheckBox("Save result in bigtiff")
        self.bigtiff_checkbox.stateChanged.connect(self.set_bigtiff)

        self.subdir_checkbox = QCheckBox("Apply only to subdirs with name")
        self.subdir_entry = QLineEdit()
        #self.input_dir_entry.editingFinished.connect(self.set_input_entry)

        self.dummy_label = QLabel("\t")

        self.do_crop_checkbox = QCheckBox("Crop images. (0,0) is top left corner")
        self.do_crop_checkbox.stateChanged.connect(self.set_do_crop)

        self.x_label = QLabel()
        self.x_label.setText("x (first column)")
        self.x_entry = QLineEdit()
        self.x_entry.setValidator(get_int_validator())
        self.x_entry.editingFinished.connect(self.set_x)

        self.width_label = QLabel()
        self.width_label.setText("width")
        self.width_entry = QLineEdit()
        self.width_entry.setValidator(get_int_validator())
        self.width_entry.editingFinished.connect(self.set_width)

        self.y_label = QLabel()
        self.y_label.setText("y (first row)")
        self.y_entry = QLineEdit()
        self.y_entry.setValidator(get_int_validator())
        self.y_entry.editingFinished.connect(self.set_y)

        self.height_label = QLabel()
        self.height_label.setText("height")
        self.height_entry = QLineEdit()
        self.height_entry.setValidator(get_int_validator())
        self.height_entry.editingFinished.connect(self.set_height)

        self.im_range_checkbox = QCheckBox("Apply only to a range of images")
        self.im_range_checkbox.stateChanged.connect(self.set_im_lim_range)

        self.im_start_label = QLabel("First image")
        self.im_start_entry = QLineEdit()
        self.im_start_entry.editingFinished.connect(self.set_im_start)

        self.im_range_label = QLabel("Range")
        self.im_range_entry = QLineEdit()
        self.im_range_entry.editingFinished.connect(self.set_im_range)

        self.im_step_label = QLabel("Step")
        self.im_step_entry = QLineEdit()
        self.im_step_entry.editingFinished.connect(self.set_im_step)

        self.do_bin_checkbox = QCheckBox("Bin images")
        self.do_bin_checkbox.stateChanged.connect(self.set_do_bin)

        self.bin2D_rButton = QRadioButton()
        self.bin2D_rButton.setText("2D")
        self.bin2D_rButton.setChecked(True)
        self.bin2D_rButton.clicked.connect(self.set_bin_kernel)

        self.bin3D_rButton = QRadioButton()
        self.bin3D_rButton.setText("3D")
        self.bin3D_rButton.setChecked(False)
        self.bin3D_rButton.clicked.connect(self.set_bin_kernel)

        self.bin_size_label = QLabel("Bin size [pixels]")
        self.bin_size_entry = QLineEdit()
        self.bin_size_entry.editingFinished.connect(self.set_bin_size)



        self.clip_histo_checkbox = QCheckBox()
        self.clip_histo_checkbox.setText("Clip the histogram and change the data cube bit-depth to")
        self.clip_histo_checkbox.stateChanged.connect(self.set_clip_histo)

        self.bit8_rButton = QRadioButton()
        self.bit8_rButton.setText("8-bit")
        self.bit8_rButton.setChecked(True)
        self.bit8_rButton.clicked.connect(self.set_bitdepth)

        self.bit16_rButton = QRadioButton()
        self.bit16_rButton.setText("16-bit")
        self.bit16_rButton.setChecked(False)
        self.bit16_rButton.clicked.connect(self.set_bitdepth)

        self.min_val_label = QLabel()
        self.min_val_label.setText("Min value in input histogram")
        self.min_val_entry = QLineEdit()
        self.min_val_entry.editingFinished.connect(self.set_min_val)

        self.max_val_label = QLabel()
        self.max_val_label.setText("Max value")
        self.max_val_entry = QLineEdit()
        self.max_val_entry.editingFinished.connect(self.set_max_val)


        self.preproc_checkbox = QCheckBox()
        self.preproc_checkbox.setText("Append a generic ufo-launch pipeline, f.i.")
        self.preproc_checkbox.setToolTip(
            "Selected ufo filters will be applied to each "
            "image before reconstruction begins. \n"
            'To print the list of filters use "ufo-query -l" command. \n'
            'Parameters of each filter can be seen with "ufo-query -p filtername".'
        )
        self.preproc_checkbox.stateChanged.connect(self.set_preproc)
        self.preproc_entry = QLineEdit()
        self.preproc_entry.editingFinished.connect(self.set_preproc_entry)

        self.apply_button = QPushButton()
        self.apply_button.setText("Apply filters")
        self.apply_button.clicked.connect(self.apply_button_pressed)
        self.apply_button.setStyleSheet("color:royalblue;font-weight:bold")

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        l=0
        box2 = QGridLayout()
        box2.addWidget(self.do_crop_checkbox, 0, 0, 1, 5)
        box2.addWidget(self.x_label, 1, 0)
        box2.addWidget(self.x_entry, 1, 1)
        box2.addWidget(self.dummy_label, 1, 2)
        box2.addWidget(self.width_label, 1, 3)
        box2.addWidget(self.width_entry, 1, 4)
        box2.addWidget(self.y_label, 2, 0)
        box2.addWidget(self.y_entry, 2, 1)
        box2.addWidget(self.dummy_label, 2, 2)
        box2.addWidget(self.height_label, 2, 3)
        box2.addWidget(self.height_entry, 2, 4)
        layout.addItem(box2, l, 0); l+=1
        
        
        box4 = QGridLayout()
        box4.addWidget(self.do_bin_checkbox, 0, 0)
        box4.addWidget(self.bin2D_rButton, 0, 1)
        box4.addWidget(self.bin3D_rButton, 0, 2)
        box4.addWidget(self.bin3D_rButton, 0, 3)
        box4.addWidget(self.bin_size_label, 0, 4)
        box4.addWidget(self.bin_size_entry, 0, 5)
        layout.addItem(box4, l, 0); l+=1
        
        box5 = QGridLayout()
        box5.addWidget(self.preproc_checkbox, 0, 0)
        box5.addWidget(self.preproc_entry, 1, 0)
        layout.addItem(box5, l, 0); l+=1

        # READ and write here in the widget

        box1 = QGridLayout()
        box1.addWidget(self.input_dir_button, 0, 0)
        box1.addWidget(self.input_dir_entry, 1, 0)
        box1.addWidget(self.subdir_checkbox, 2, 0)
        box1.addWidget(self.subdir_entry, 3, 0)
        layout.addItem(box1, l,0); l+=1

        box3 = QGridLayout()
        box3.addWidget(self.im_range_checkbox, 0, 0, 1, 9)
        box3.addWidget(self.im_start_label, 1, 0, 1, 1)
        box3.addWidget(self.im_start_entry, 1, 1, 1, 1)
        box3.addWidget(self.dummy_label, 1, 3, 1, 1)
        box3.addWidget(self.im_range_label, 1, 4, 1, 1)
        box3.addWidget(self.im_range_entry, 1, 5, 1, 1)
        box3.addWidget(self.dummy_label, 1, 6, 1, 1)
        box3.addWidget(self.im_step_label, 1, 7, 1, 1)
        box3.addWidget(self.im_step_entry, 1, 8, 1, 1)
        layout.addItem(box3, l, 0); l+=1

        #WRITE
        layout.addWidget(self.output_dir_button, l, 0); l+=1
        layout.addWidget(self.output_dir_entry, l, 0); l+=1
        layout.addWidget(self.bigtiff_checkbox, l, 0); l += 1
        box5 = QGridLayout()
        box5.addWidget(self.clip_histo_checkbox, 0, 0, 1, 2)
        box5.addWidget(self.dummy_label, 0, 1)
        box5.addWidget(self.bit8_rButton, 0, 2)
        box5.addWidget(self.dummy_label, 0, 3)
        box5.addWidget(self.bit16_rButton, 0, 4)
        box5.addWidget(self.min_val_label, 1, 0)
        box5.addWidget(self.min_val_entry, 1, 1)
        box5.addWidget(self.dummy_label, 1, 2)
        box5.addWidget(self.max_val_label, 1, 3)
        box5.addWidget(self.max_val_entry, 1, 4)
        layout.addItem(box5, l, 0); l+=1

        
        layout.addWidget(self.apply_button, l, 0)



        self.setLayout(layout)

    def load_values(self):
        self.input_dir_entry.setText(str(EZVARS_prep['prepro']['input-dir']['value']))
        self.output_dir_entry.setText(str(EZVARS_prep['prepro']['output-dir']['value']))
        self.bigtiff_checkbox.setChecked(EZVARS_prep['prepro']['bigtiff']['value'])
        self.subdir_checkbox.setChecked(EZVARS_prep['prepro']['sdir_only']['value'])
        self.subdir_entry.setText(str(EZVARS_prep['prepro']['subdir']['value']))
        self.do_crop_checkbox.setChecked(EZVARS_prep['prepro']['crop']['value'])
        self.x_entry.setText(str(EZVARS_prep['prepro']['x']['value']))
        self.width_entry.setText(str(EZVARS_prep['prepro']['width']['value']))
        self.y_entry.setText(str(EZVARS_prep['prepro']['y']['value']))
        self.height_entry.setText(str(EZVARS_prep['prepro']['height']['value']))
        self.im_range_checkbox.setChecked(EZVARS_prep['prepro']['im_lim_range']['value'])
        self.im_start_entry.setText(str(EZVARS_prep['prepro']['im_start']['value']))
        self.im_range_entry.setText(str(EZVARS_prep['prepro']['im_range']['value']))
        self.im_step_entry.setText(str(EZVARS_prep['prepro']['im_step']['value']))
        self.do_bin_checkbox.setChecked(EZVARS_prep['prepro']['bin']['value'])
        if EZVARS_prep['prepro']['bin3d']['value']:
            self.bin3D_rButton.setChecked(True)
            self.bin2D_rButton.setChecked(False)
        else:
            self.bin3D_rButton.setChecked(False)
            self.bin2D_rButton.setChecked(True)
        self.bin_size_entry.setText(str(EZVARS_prep['prepro']['bin_size']['value']))
        self.clip_histo_checkbox.setChecked(EZVARS_prep['prepro']['clip_hist']['value'])
        if EZVARS_prep['prepro']['out8bit']['value']:
            self.bit8_rButton.setChecked(True)
            self.bit16_rButton.setChecked(False)
        else:
            self.bit8_rButton.setChecked(False)
            self.bit16_rButton.setChecked(True)
        self.min_val_entry.setText(str(EZVARS_prep['prepro']['min_int_val']['value']))
        self.max_val_entry.setText(str(EZVARS_prep['prepro']['max_int_val']['value']))
        # self.preproc_checkbox.setChecked(EZVARS_prep['prepro']['use_generic_ufo_cmd']['value'])
        # self.preproc_entry.setText(EZVARS_prep['prepro']['generic_ufo_cmd']['value'])





    def input_button_pressed(self):
        dir_explore = QFileDialog(self)
        add_value_to_dict_entry(EZVARS_prep['prepro']['input-dir'], dir_explore.getExistingDirectory())
        self.input_dir_entry.setText(EZVARS_prep['prepro']['input-dir']['value'])

    def set_input_entry(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['input-dir'], str(self.input_dir_entry.text()))

    def output_button_pressed(self):
        dir_explore = QFileDialog(self)
        add_value_to_dict_entry(EZVARS_prep['prepro']['output-dir'], dir_explore.getExistingDirectory())
        self.output_dir_entry.setText(EZVARS_prep['prepro']['output-dir']['value'])

    def set_output_entry(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['output-dir'], str(self.output_dir_entry.text()))

    def set_bigtiff(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['bigtiff'], bool(self.bigtiff_checkbox.isChecked()))

    def set_do_crop(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['crop'], bool(self.do_crop_checkbox.isChecked()))

    def set_x(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['x'], int(self.x_entry.text()))

    def set_width(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['width'], int(self.width_entry.text()))

    def set_y(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['y'], int(self.y_entry.text()))

    def set_height(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['height'], int(self.height_entry.text()))

    def set_im_lim_range(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['im_lim_range'], bool(self.im_range_checkbox.isChecked()))

    def set_im_start(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['im_start'], int(self.im_start_entry.text()))

    def set_im_range(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['im_range'], int(self.im_range_entry.text()))

    def set_im_step(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['im_step'], int(self.im_step_entry.text()))

    def set_do_bin(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['bin'], bool(self.do_bin_checkbox.isChecked()))

    def set_bin_kernel(self):
        if self.bin2D_rButton.isChecked():
            add_value_to_dict_entry(EZVARS_prep['prepro']['bin3d'], False)
            self.bin3D_rButton.setChecked(False)
            return
        if self.bin3D_rButton.isChecked():
            add_value_to_dict_entry(EZVARS_prep['prepro']['bin3d'], True)
            self.bin2D_rButton.setChecked(False)

    def set_bin_size(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['bin_size'], int(self.bin_size_entry.text()))

    def set_clip_histo(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['clip_hist'], bool(self.clip_histo_checkbox.isChecked()))

    def set_bitdepth(self):
        if self.bit8_rButton.isChecked():
            add_value_to_dict_entry(EZVARS_prep['prepro']['out8bit'], True)
            #add_value_to_dict_entry(EZVARS_prep['prepro']['out16bit'], False)
            self.bit16_rButton.setChecked(False)
            return
        if self.bit16_rButton.isChecked():
            #add_value_to_dict_entry(EZVARS_prep['prepro']['out16bit'], True)
            add_value_to_dict_entry(EZVARS_prep['prepro']['out8bit'], False)
            self.bit8_rButton.setChecked(False)

    def set_min_val(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['min_int_val'], float(self.min_val_entry.text()))

    def set_max_val(self):
        add_value_to_dict_entry(EZVARS_prep['prepro']['max_int_val'], float(self.max_val_entry.text()))

    def set_preproc(self):
        LOG.debug("Preproc: " + str(self.preproc_checkbox.isChecked()))
        dict_entry = EZVARS_prep['prepro']['use_generic_ufo_cmd']
        add_value_to_dict_entry(dict_entry, self.preproc_checkbox.isChecked())

    def set_preproc_entry(self):
        LOG.debug(self.preproc_entry.text())
        dict_entry = EZVARS_prep['prepro']['generic_ufo_cmd']
        text  = self.preproc_entry.text().strip()
        add_value_to_dict_entry(dict_entry, text)
        self.preproc_entry.setText(text)

    def apply_button_pressed(self):
        self.verify_safe2delete(EZVARS_prep['prepro']['output-dir']['value'])
        indirs = []
        for root, dirs, files in os.walk(EZVARS_prep['prepro']['input-dir']['value']):
            for fname in files:
                if fname.endswith('.tif'):
                    indirs.append(root[len(EZVARS_prep['prepro']['input-dir']['value'])+1:])
                    break
        if len(indirs) == 0:
            warning_message(f"Didn't find any tiff files in the input directory")
            return
        cmds = []
        for indir in indirs:
            cmds.append(fmt_crop_bin(os.path.join(EZVARS_prep['prepro']['input-dir']['value'], indir),
                               os.path.join(EZVARS_prep['prepro']['output-dir']['value'],indir)))
        for cmd in cmds:
            print(cmd)
            os.system(cmd)

    def verify_safe2delete(self, dir_path):
        if os.path.exists(dir_path) and len(os.listdir(dir_path)) > 0:
            qm = QMessageBox()
            rep = qm.question(self, '', f"Output dir is not empty. Is it safe to delete it?",
                              qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(dir_path)
                except:
                    warning_message(f"Error while deleting Output directory")
                    return
            else:
                return

class DummyBox(QGroupBox):
    def __init__(self):
        super().__init__()

        self.setTitle("Reserved")
        self.setStyleSheet('QGroupBox {color: Gray;}')

        self.row1_dummy_label1 = QLabel("\t\t\t\t\t\t")
        self.row1_dummy_label2 = QLabel()

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.row1_dummy_label1)
        self.setLayout(layout)