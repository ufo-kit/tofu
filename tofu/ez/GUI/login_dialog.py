import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QLineEdit,
    QPushButton,
    QLabel,
    QGridLayout,
    QFileDialog,
    QComboBox,
)
from tofu.ez.GUI.message_dialog import error_message
import os


class Login(QDialog):
    def __init__(self, login_parameters_dict, **kwargs):
        super(Login, self).__init__(**kwargs)
        # Pass a method from main GUI
        self.login_parameters_dict = login_parameters_dict

        self.setWindowTitle("USER LOGIN")
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.welcome_label = QLabel()
        self.welcome_label.setText("Welcome to BMIT!")
        self.prompt_label_bl = QLabel()
        self.prompt_label_bl.setText("Please select the beamline and project:")
        self.bl_label = QLabel()
        self.bl_label.setText("Beamline:")
        self.bl_entry = QComboBox()
        self.bl_entry.addItems(["BM", "ID"])
        self.proj_label = QLabel()
        self.proj_label.setText("Project:")
        self.proj_entry = QLineEdit()
        self.prompt_label_expdir = QLabel()
        self.prompt_label_expdir.setText("OR select the path to the working directory")
        self.expdir_entry = QLineEdit()
        # self.expdir_entry.setText("/data/gui-test")
        self.expdir_entry.setReadOnly(True)
        self.expdir_select_button = QPushButton("...")
        self.expdir_select_button.clicked.connect(self.select_expdir_func)

        self.login_button = QPushButton("LOGIN")
        self.login_button.clicked.connect(self.on_login_button_clicked)
        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        self.welcome_label.setAlignment(Qt.AlignCenter)
        self.prompt_label_bl.setAlignment(Qt.AlignCenter)
        self.prompt_label_expdir.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.welcome_label, 0, 0, 1, 2)
        layout.addWidget(self.prompt_label_bl, 1, 0, 1, 2)
        layout.addWidget(self.bl_label, 2, 0, 1, 1)
        layout.addWidget(self.bl_entry, 2, 1, 1, 1)
        layout.addWidget(self.proj_label, 3, 0, 1, 1)
        layout.addWidget(self.proj_entry, 3, 1, 1, 1)
        layout.addWidget(self.prompt_label_expdir, 4, 0, 1, 2)
        layout.addWidget(self.expdir_entry, 5, 0, 1, 1)
        layout.addWidget(self.expdir_select_button, 5, 1, 1, 1)
        layout.addWidget(self.login_button, 6, 0, 1, 2)

        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        self.setLayout(layout)

    def select_expdir_func(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        root_dir = QFileDialog.getExistingDirectory(
            self, "Select working directory", "/data/gui-test", options=options
        )
        if root_dir:
            self.expdir_entry.setText(root_dir)

    def uppercase_project_entry(self):
        self.proj_entry.setText(self.proj_entry.text().upper())

    def strip_spaces_from_user_entry(self):
        self.user_entry.setText(self.user_entry.text().replace(" ", ""))

    @property
    def project_name(self):
        return self.proj_entry.text()

    @property
    def user_name(self):
        return self.user_entry.text()

    @property
    def expdir_name(self):
        return self.expdir_entry.text()

    @property
    def bl_name(self):
        return self.bl_entry.currentText()

    def validate_entries(self):
        self.uppercase_project_entry()
        # self.strip_spaces_from_user_entry()
        project_valid = bool(re.match(r"^[0-9]{2}[A-Z][0-9]{5}$", self.project_name))
        # username_valid = bool(re.match(r"^[a-zA-Z0-9]*$", self.user_name))
        # return project_valid, username_valid
        return project_valid

    def validate_dir(self, pdr):
        return os.access(pdr, os.W_OK)

    def on_login_button_clicked(self):
        # project_valid, username_valid = self.validate_entries()
        if self.project_name != "":
            prj_dir_name = os.path.join(
                "/beamlinedata/BMIT/projects/prj" + self.project_name, "raw"
            )
            project_valid = self.validate_entries()
            can_write = self.validate_dir(prj_dir_name)
            if project_valid and can_write:
                self.login_parameters_dict.update({"bl": self.bl_name})
                self.login_parameters_dict.update({"project": self.project_name})
                # add fileExistsError exception later in Py3
                self.login_parameters_dict.update({"expdir": prj_dir_name})
                self.accept()
            # elif not username_valid:
            #    error_message("Username should be alpha-numeric ")
            elif not project_valid:
                error_message(
                    "The project should be in format: CCTNNNNN, \n"
                    "where CC is cycle number, "
                    "T is one-letter type, "
                    "and NNNNN is project number"
                )
            elif not can_write:
                error_message("Cannot write in the project directory")
        elif self.expdir_name != "":
            if self.validate_dir(self.expdir_entry.text()):
                self.login_parameters_dict.update({"expdir": self.expdir_name})
                self.accept()
            else:
                error_message("Cannot write in the selected directory")
