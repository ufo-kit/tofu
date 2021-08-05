
from PyQt5.QtWidgets import QMessageBox


def message_dialog(window_title, message_text):
    alert = QMessageBox()
    alert.setWindowTitle(window_title)
    alert.setText(message_text)
    alert.exec_()


def error_message(message_text):
    message_dialog("Error", message_text)


def warning_message(message_text):
    message_dialog("Warning", message_text)


def info_message(message_text):
    message_dialog("Info", message_text)