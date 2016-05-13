import pyqtgraph as pg
import pyqtgraph.opengl as gl
import logging
import numpy as np
import tifffile
import h5py
from tofu.util import (get_h5_shape, get_h5_data)

from PyQt4 import QtGui, QtCore


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


def create_volume(data):
    gradient = (data - np.roll(data, 1))**2
    cmin = gradient.min()
    div = gradient.max() - cmin
    gradient = (gradient - cmin) / div * 255

    volume = np.empty(data.shape + (4, ), dtype=np.ubyte)
    volume[..., 0] = data
    volume[..., 1] = data
    volume[..., 2] = data
    volume[..., 3] = gradient
    return volume


class ImageViewer(QtGui.QWidget):
    """
    Present a sequence of files that can be browsed with a slider.

    To get the currently selected position connect to the *slider* attribute's
    valueChanged signal.
    """

    def __init__(self, filenames, parent=None):
        super(ImageViewer, self).__init__(parent)
        image_view = pg.ImageView()
        image_view.getView().setAspectLocked(True)
        self.image_item = image_view.getImageItem()

        self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider.valueChanged.connect(self.update_image)

        self.main_layout = QtGui.QVBoxLayout(self)
        self.main_layout.addWidget(image_view)
        self.main_layout.addWidget(self.slider)
        self.setLayout(self.main_layout)
        self.load_files(filenames)

    def load_files(self, filenames):
        """Load *filenames* for display."""
        self.filenames = filenames
        if '.h5:/' in self.filenames:
            maximum = get_h5_shape(self.filenames)[0] - 1
        else:
            maximum = len(self.filenames) - 1
        self.slider.setRange(0, maximum)
        self.slider.setSliderPosition(0)
        self.update_image()

    def update_image(self):
        """Update the currently display image."""
        if self.filenames:
            pos = self.slider.value()
            if '.h5:/' in self.filenames:
                image = get_h5_data(self.filenames, pos)
                image = image.T
            else:
                image = read_tiff(self.filenames[pos])
            self.image_item.setImage(image)


class ImageWindow(object):
    """
    Stand-alone window to display image sequences.
    """

    global_app = None

    def __init__(self, filenames):
        self.global_app = QtGui.QApplication.instance() or QtGui.QApplication([])

        self.viewer = ImageViewer(filenames)
        self.viewer.show()


class OverlapViewer(QtGui.QWidget):
    """
    Presents two images by subtracting the flipped second from the first.

    To get the current deviation connect to the *slider* attribute's
    valueChanged signal.
    """
    def __init__(self, parent=None, remove_extrema=False):
        super(OverlapViewer, self).__init__()
        image_view = pg.ImageView()
        image_view.getView().setAspectLocked(True)
        self.image_item = image_view.getImageItem()

        self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.valueChanged.connect(self.update_image)

        self.main_layout = QtGui.QVBoxLayout()
        self.main_layout.addWidget(image_view)
        self.main_layout.addWidget(self.slider)
        self.setLayout(self.main_layout)
        self.first, self.second = (None, None)
        self.remove_extrema = remove_extrema
        self.subtract = True

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
            
            if self.subtract:
                self.image_item.setImage(moved - self.first)
            else:
                self.image_item.setImage(moved + self.first)


class VolumeViewer(QtGui.QWidget):

    def __init__(self, step=1, density=1, parent=None):
        super(VolumeViewer, self).__init__(parent)
        self.volume_view = gl.GLViewWidget()
        self.main_layout = QtGui.QVBoxLayout()
        self.main_layout.addWidget(self.volume_view)
        self.setLayout(self.main_layout)
        self.step = step
        self.density = density

    def load_files(self, filenames):
        """Load *filenames* for display."""
        if '.h5:/' in filenames:
            num_full = get_h5_shape(filenames)[0]
            num = get_h5_shape(filenames)[0] / self.step
            first = get_h5_data(filenames, 0)[::self.step, ::self.step]
        else:
            filenames = filenames[::self.step]
            num = len(filenames)
            first = read_tiff(filenames[0])[::self.step, ::self.step]
        width, height = first.shape
        data = np.empty((width, height, num), dtype=np.float32)
        data[:,:,0] = first

        if '.h5:/' in filenames:
            for i, j in zip(range(0, num - 1), range(0, num_full - 1, self.step)):
                data[:, :, i + 1] = get_h5_data(filenames, j)[::self.step, ::self.step]
        else:
            for i, filename in enumerate(filenames[1:]):
                data[:, :, i + 1] = read_tiff(filename)[::self.step, ::self.step]

        volume = create_volume(data)
        dx, dy, dz, _ = volume.shape

        try:
            self.volume_view.removeItem(self.volume_item)
        except AttributeError:
            pass

        self.volume_item = gl.GLVolumeItem(volume, sliceDensity=self.density)
        self.volume_item.translate(-dx / 2, -dy / 2, -dz / 2)
        self.volume_item.scale(0.05, 0.05, 0.05, local=False)
        self.volume_view.addItem(self.volume_item)
