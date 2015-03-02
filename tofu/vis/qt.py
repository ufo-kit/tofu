import pyqtgraph as pg
import logging
import numpy as np

from PyQt4 import QtGui, QtCore
from .. import tifffile


LOG = logging.getLogger(__name__)


def read_tiff(filename):
    tiff = tifffile.TiffFile(filename)
    array = tiff.asarray()
    return array.T


def remove_extrema(data):
    upper = np.percentile(data, 99)
    lower = np.percentile(data, 1)
    data[data > upper] = upper
    data[data < lower] = lower
    return data


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


class OverlapViewer(QtGui.QWidget):
    """
    Presents two images by subtracting the flipped second from the first.

    To get the current deviation connect to the *slider* attribute's
    valueChanged signal.
    """
    def __init__(self, parent=None, remove_extrema=False):
        super(OverlapViewer, self).__init__()
        self.image_view = pg.ImageView()
        self.image_view.getView().setAspectLocked(True)

        self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self.update_image)

        self.main_layout = QtGui.QVBoxLayout()
        self.main_layout.addWidget(self.image_view)
        self.main_layout.addWidget(self.slider)
        self.setLayout(self.main_layout)
        self.first, self.second = (None, None)
        self.remove_extrema = remove_extrema

    def set_images(self, first, second):
        """Set *first* and *second* image."""
        self.first, self.second = first.T, np.flipud(second.T)

        if self.remove_extrema:
            self.first = remove_extrema(self.first)
            self.second = remove_extrema(self.second)

        if self.first.shape != self.second.shape:
            LOG.warn("Shape {} of {} is different to {} of {}".
                     format(self.first.shape, self.first, self.second.shape, self.second))

        self.slider.setRange(0, self.first.shape[0])
        self.slider.setSliderPosition(self.first.shape[0] / 2)
        self.update_image()

    def set_position(self, position):
        self.slider.setValue(int(position))
        self.update_image()

    def update_image(self):
        """Update the current subtraction."""
        if self.first is None or self.second is None:
            LOG.warn("No images set yet")
        else:
            pos = self.slider.value()
            moved = np.roll(self.second, self.second.shape[0] / 2 - pos, axis=0)
            self.image_view.setImage(moved - self.first)
