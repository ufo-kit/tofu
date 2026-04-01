import os
from shutil import rmtree

from PyQt5.QtWidgets import QMessageBox

from tofu.ez.GUI.message_dialog import warning_message


def verify_safe2delete(parent, dir_path, dir_type):
    if os.path.exists(dir_path) and len(os.listdir(dir_path)) > 0:
        qm = QMessageBox()
        rep = qm.question(parent, '', f"{dir_type} dir is not empty. Is it safe to delete it?\n\n{dir_path}",
                          qm.Yes | qm.No)
        if rep == qm.Yes:
            try:
                rmtree(dir_path)
            except:
                warning_message(f"Error while deleting {dir_type} directory")
                raise FileExistsError
        else:
            raise FileExistsError