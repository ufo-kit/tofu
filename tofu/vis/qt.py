import pyqtgraph as pg

from PyQt4 import QtGui, QtCore
from .. import tifffile


def read_tiff(filename):
    tiff = tifffile.TiffFile(filename)
    array = tiff.asarray()
    return array.T


class ImageViewer(QtGui.QWidget):
    """
    Present a sequence of files that can be browsed with a slider.

    To get the currently selected position connect to the *slider* attribute's
    valueChanged signal.
    """

    def __init__(self, filenames, parent=None):
        super(ImageViewer, self).__init__(parent)
        self.image_view = pg.ImageView()
        self.image_view.getView().setAspectLocked(True)

        self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider.valueChanged.connect(self.update_image)

        self.main_layout = QtGui.QVBoxLayout(self)
        self.main_layout.addWidget(self.image_view)
        self.main_layout.addWidget(self.slider)
        self.setLayout(self.main_layout)
        self.load_files(filenames)

    def load_files(self, filenames):
        """Load *filenames* for display."""
        self.filenames = filenames
        self.slider.setRange(0, len(self.filenames))
        self.slider.setSliderPosition(0)
        self.update_image()

    def update_image(self):
        """Update the currently display image."""
        pos = self.slider.value()
        image = read_tiff(self.filenames[pos])
        self.image_view.setImage(image)
