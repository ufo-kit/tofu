import yaml
import logging
import glob
import os

from PyQt5.QtWidgets import QGroupBox, QLabel, QGridLayout, QPushButton, QFileDialog, QLineEdit

from tofu.ez.GUI.Main.config import ConfigGroup
from tofu.ez.GUI.Stitch_tools_tab.auto_horizontal_stitch_funcs import AutoHorizontalStitchFunctions


class BatchProcessGroup(QGroupBox):
    def __init__(self):
        super().__init__()

        self.parameters = {}
        self.config_group = None
        self.auto_stitch_funcs = None

        self.info_label = QLabel()
        self.set_info_label()

        self.input_dir_button = QPushButton("Select input directory")
        self.input_dir_button.setFixedWidth(500)
        self.input_dir_button.clicked.connect(self.input_dir_button_pressed)

        self.input_dir_entry = QLineEdit("...Enter the path to the input directory")
        self.input_dir_entry.setFixedWidth(450)
        self.input_dir_entry.textChanged.connect(self.set_input_entry)

        self.batch_proc_button = QPushButton("Begin Batch Process")
        self.batch_proc_button.clicked.connect(self.batch_proc_button_pressed)
        self.batch_proc_button.setStyleSheet("background-color:orangered; font-size:26px")
        self.batch_proc_button.setFixedHeight(100)

        self.set_layout()

    def set_layout(self):
        self.setMaximumSize(1000, 400)

        layout = QGridLayout()

        layout.addWidget(self.input_dir_button, 0, 0)
        layout.addWidget(self.input_dir_entry, 0, 1)

        layout.addWidget(self.info_label, 1, 0)

        layout.addWidget(self.batch_proc_button, 2, 0, 1, 2)
        self.setLayout(layout)

        self.show()

    def set_info_label(self):
        info_str = "EZ Batch Process allows for batch reconstruction and processing of images.\n\n"
        info_str += "The program reads a list of .yaml parameter files from the input directory and executes\n" \
                    "them sequentially in alpha-numeric order.\n"
        info_str += "It is the user's responsibility to name files so that they are executed in the desired order.\n"
        info_str += "It is suggested to prepend descriptive filenames with numbers to indicate the order.\n" \
                    "For example: \n\n"
        info_str += "00_horizontal_stitch_params.yaml\n"
        info_str += "01_ezufo_params.yaml\n"
        info_str += "02_vertical_stitch_params.yaml\n"
        self.info_label.setText(info_str)

    def input_dir_button_pressed(self):
        logging.debug("Input Button Pressed")
        dir_explore = QFileDialog(self)
        input_dir = dir_explore.getExistingDirectory()
        self.input_dir_entry.setText(input_dir)
        self.parameters['input_dir'] = input_dir

    def set_input_entry(self):
        logging.debug("Input Entry: " + str(self.input_dir_entry.text()))
        self.parameters['input_dir'] = str(self.input_dir_entry.text())

    def batch_proc_button_pressed(self):
        logging.debug("Batch Process Button Pressed")
        try:
            param_files_list = sorted(glob.glob(os.path.join(self.parameters['input_dir'], "*.yaml")))
            if len(param_files_list) == 0:
                print("=> Error: Did not find any .yaml files in the input directory. Please try again.")
            else:
                print("*************************************************************************")
                print("************************** Begin Batch Process **************************")
                print("*************************************************************************\n")
                print("=> Found the following .yaml files:")
                for file in param_files_list:
                    print("-->  " + file)
                    # Open .yaml file and store the parameters
                    try:
                        file_in = open(file, 'r')
                        params = yaml.load(file_in, Loader=yaml.FullLoader)
                    except FileNotFoundError:
                        print("Something went wrong")
                    params_type = params['parameters_type']
                    print("       type: " + params_type)
                    if params_type == "auto_horizontal_stitch":
                        # Call functions to begin auto horizontal stitch and pass params
                        self.auto_stitch_funcs = AutoHorizontalStitchFunctions(params)
                        self.auto_stitch_funcs.run_horizontal_auto_stitch()
                    elif params_type == "ez_ufo_reco":
                        # Call functions to begin ezufo reco and pass params
                        self.config_group = ConfigGroup()
                        self.config_group.run_reconstruction(params, batch_run=True)
                    elif params_type == "auto_vertical_stitch":
                        pass
                        # Call functions to begin auto horizontal stitch and pass params
        except KeyError:
            print("Please select an input directory")
