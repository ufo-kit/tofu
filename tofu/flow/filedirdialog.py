import os
from PyQt5.QtWidgets import QFileDialog


class FileDirDialog(QFileDialog):

    """
    A workaround for being able to select both files and directories.

    Source:
    https://stackoverflow.com/questions/27520304/qfiledialog-that-accepts-a-single-file-or-a-single-directory
    """

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setOption(QFileDialog.DontUseNativeDialog)
        self.setFileMode(QFileDialog.Directory)
        self.currentChanged.connect(self._selected)

    def _selected(self, name):
        if os.path.isdir(name):
            self.setFileMode(QFileDialog.Directory)
        else:
            self.setFileMode(QFileDialog.ExistingFile)
