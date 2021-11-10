import logging
import numpy as np
import os
from PyQt5 import QtGui
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QFileDialog, QGridLayout, QLabel, QLineEdit, QMenu, QWidget, QSlider
from tofu.flow.util import FlowError


LOG = logging.getLogger(__name__)


class ScreenImage:

    """On-screen image representation."""

    def __init__(self, image=None):
        self._black_point = None
        self._white_point = None
        self.minimum = None
        self.maximum = None
        self.image = image

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, image):
        """
        Keep the minimum, maximum, black and white points as they are so that images don't
        flicker when going through a sequence.
        """
        self._image = image
        if self._image is not None:
            self._image = image.astype(np.float32)
            if self.minimum is None:
                self.minimum = np.nanmin(self._image)
            if self.maximum is None:
                self.maximum = np.nanmax(self._image)
            if self.black_point is None:
                self.black_point = self.minimum
            if self.white_point is None:
                self.white_point = self.maximum

    @property
    def white_point(self):
        return self._white_point

    @white_point.setter
    def white_point(self, value):
        if self.black_point is not None and value < self.black_point:
            raise ImageViewingError('White point cannot be smaller than black point')
        self._white_point = value

    @property
    def black_point(self):
        return self._black_point

    @black_point.setter
    def black_point(self, value):
        if self.white_point is not None and value > self.white_point:
            raise ImageViewingError('Black point cannot be greater than white point')
        self._black_point = value

    def reset(self):
        """Reset black and white points."""
        if self._image is not None:
            self.minimum = np.nanmin(self._image)
            self.maximum = np.nanmax(self._image)
            self._black_point = self.minimum
            self._white_point = self.maximum

    def auto_levels(self, percentile=0.1):
        """
        Compute cumulative histogram normalized to [0, 100] and truncate gray values which fall
        below *percentile* or above 100 - *percentile*.
        """
        hist, bins = np.histogram(self._image, bins=256)
        cumsum = np.cumsum(hist) / float(np.sum(hist)) * 100
        valid = bins[np.where((cumsum > percentile) & (cumsum < 100 - percentile))]
        if len(valid):
            self.black_point = valid[0]
            self.white_point = valid[-1]
        else:
            self.black_point = self.white_point = self._image[0, 0]

    def set_black_point_normalized(self, value):
        """Set black point according to *value*, where value is from interval [0, 255]."""
        native = self.convert_normalized_value_to_native(value)
        if native > self.white_point:
            raise ImageViewingError('Black point cannot be greater than white point')
        self.black_point = native

    def set_white_point_normalized(self, value):
        """Set white point according to *value*, where value is from interval [0, 255]."""
        native = self.convert_normalized_value_to_native(value)
        if native < self.black_point:
            raise ImageViewingError('White point cannot be smaller than white point')
        self.white_point = native

    def convert_normalized_value_to_native(self, value):
        """Convert *value* from interval [0, 255] to the gray value in the image."""
        if value < 0 or value > 255:
            raise ImageViewingError('Normalized value must be in interval [0, 255]')
        span = self.maximum - self.minimum

        return value / 255 * span + self.minimum

    def convert_native_value_to_normalized(self, value):
        """Convert gray value in the image to a normalized value in interval [0, 255]."""
        if value < self.minimum or value > self.maximum:
            raise ImageViewingError(f'Value must be in interval [{self.minimum}, {self.maximum}]')
        span = self.maximum - self.minimum

        return (value - self.minimum) / span * 255 if span > 0 else 0

    def get_pixmap(self, downsampling=1):
        """Get :class:`QPixmap` for display."""
        if self.black_point is None or self.white_point is None:
            raise ImageViewingError('Image has not been set')
        image = self.image[::downsampling, ::downsampling] - self.black_point
        if self.white_point - self.black_point > 0:
            image = np.clip(image * 255 / (self.white_point - self.black_point), 0, 255)
        image = image.astype(np.uint8)

        qim = QtGui.QImage(image, image.shape[1], image.shape[0],
                           image[0].nbytes, QtGui.QImage.Format.Format_Grayscale8)

        return QtGui.QPixmap.fromImage(qim)


class ImageLabel(QLabel):

    """QLabel holding the image data."""

    def __init__(self, screen_image=None, parent=None):
        super().__init__(parent=parent)
        self.screen_image = screen_image

    def updateImage(self):
        if self.screen_image and self.screen_image.image is not None:
            hd = self.screen_image.image.shape[1] // self.width()
            vd = self.screen_image.image.shape[0] // self.height()
            downsampling = max(min(hd, vd), 1)
            pixmap = self.screen_image.get_pixmap(downsampling=downsampling)
            self.setPixmap(pixmap.scaled(self.width(), self.height(), Qt.KeepAspectRatio))

    def resizeEvent(self, event):
        self.updateImage()


class ImageViewer(QWidget):
    edit_height = 16
    edit_width = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._images = None
        self._last_save_dir = '.'
        # Pyqtgraph popped up window
        self._pg_window = None
        self.screen_image = ScreenImage()
        self.new_image_auto_levels = True

        self.label = ImageLabel(self.screen_image)
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignCenter)
        self.slider_edit = QLineEdit()
        self.slider_edit.setFixedSize(self.edit_width, self.edit_height)
        self.slider_edit.returnPressed.connect(self.on_slider_edit_return_pressed)
        self.slider = QSlider(Qt.Horizontal)
        validator = QtGui.QIntValidator(0, self.slider.maximum())
        self.slider_edit.setValidator(validator)
        self.slider.valueChanged.connect(self.on_slider_value_changed)

        self.min_slider = QSlider(Qt.Horizontal)
        self.max_slider = QSlider(Qt.Horizontal)
        self.min_slider_edit = QLineEdit()
        self.min_slider_edit.setFixedSize(self.edit_width, self.edit_height)
        self.max_slider_edit = QLineEdit()
        self.max_slider_edit.setFixedSize(self.edit_width, self.edit_height)
        self.min_slider.setMinimum(0)
        self.max_slider.setMinimum(0)
        self.min_slider.setMaximum(255)
        self.max_slider.setMaximum(255)
        self.max_slider.setValue(255)
        self.min_slider.valueChanged.connect(self.on_min_slider_value_changed)
        self.max_slider.valueChanged.connect(self.on_max_slider_value_changed)
        self.min_slider_edit.returnPressed.connect(self.on_min_slider_edit_return_pressed)
        self.max_slider_edit.returnPressed.connect(self.on_max_slider_edit_return_pressed)

        # Tooltips
        self.slider.setToolTip('Image index in sequence')
        self.slider_edit.setToolTip(self.slider.toolTip())
        self.min_slider.setToolTip('Black point')
        self.min_slider_edit.setToolTip(self.min_slider.toolTip())
        self.max_slider.setToolTip('White point')
        self.max_slider_edit.setToolTip(self.min_slider.toolTip())

        mainLayout = QGridLayout()
        mainLayout.addWidget(self.label, 0, 0, 1, 2)
        mainLayout.addWidget(self.slider_edit, 1, 0)
        mainLayout.addWidget(self.slider, 1, 1)
        mainLayout.addWidget(self.min_slider_edit, 2, 0)
        mainLayout.addWidget(self.min_slider, 2, 1)
        mainLayout.addWidget(self.max_slider_edit, 3, 0)
        mainLayout.addWidget(self.max_slider, 3, 1)
        self.setLayout(mainLayout)

    def contextMenuEvent(self, event):
        contextMenu = QMenu(self)
        reset_action = contextMenu.addAction('Reset')
        auto_levels_action = contextMenu.addAction('Auto Levels')
        new_image_auto_levels = contextMenu.addAction('Auto Levels on New Image')
        new_image_auto_levels.setCheckable(True)
        new_image_auto_levels.setChecked(self.new_image_auto_levels)
        pop_action = None
        save_action = None
        try:
            import pyqtgraph
            if self._images is not None and not self.popup_visible:
                pop_action = contextMenu.addAction('Pop Up')
        except:
            LOG.debug('pyqtgraph not installed, pop up option disabled')
        try:
            import imageio
            if self._images is not None:
                save_action = contextMenu.addAction('Save')
        except:
            LOG.debug('imageio not installed, save option disabled')

        action = contextMenu.exec_(self.mapToGlobal(event.pos()))
        if not action:
            return

        if action == save_action:
            file_name, _ = QFileDialog.getSaveFileName(None,
                                                       "Select File Name",
                                                       self._last_save_dir,
                                                       "Images (*.tif *.png *.jpg)")
            if file_name:
                if not os.path.splitext(file_name)[1]:
                    file_name += '.tif'
                self._last_save_dir = os.path.dirname(file_name)
                if self._images.shape[0] == 1:
                    imageio.imsave(file_name, self._images[0])
                else:
                    if os.path.splitext(file_name)[1] != '.tif':
                        raise ImageViewingError('3D data can be stored only in tif format')
                    # bigtiff size from tifffile
                    imageio.volsave(file_name, self._images,
                                    bigtiff=self._images.nbytes > 2 ** 32 - 2 ** 25)
        elif action == reset_action:
            self.reset_clim()
        elif action == auto_levels_action:
            self.reset_clim(auto=True)
        elif action == new_image_auto_levels:
            self.new_image_auto_levels = action.isChecked()
        elif action == pop_action:
            self.popup()

    @property
    def images(self):
        return self._images

    @images.setter
    def images(self, images):
        was_none = self._images is None
        self._images = images
        if self._images is None:
            self.screen_image.image = None
            self.set_enabled_adjustments(False)
            return
        self.set_enabled_adjustments(True)

        if self._images.ndim == 2:
            self._images = self._images[np.newaxis, :, :]
        if self._images.shape[0] == 1:
            self.slider.hide()
            self.slider_edit.hide()
        else:
            self.slider.setMaximum(len(self._images) - 1)
            self.slider.show()
            self.slider_edit.show()
            self.slider_edit.setText('0')
            self.slider.blockSignals(True)
            self.slider.setValue(0)
            self.slider.blockSignals(False)

        if self._pg_window is not None:
            self._update_pg_window_images()
            self._update_pg_window_index()

        self.screen_image.image = self._images[0]
        if was_none or self.new_image_auto_levels:
            self.reset_clim(auto=True)
        else:
            self.label.updateImage()

        validator = self.min_slider_edit.validator()
        if validator is None:
            validator = QtGui.QDoubleValidator(self.screen_image.minimum,
                                               self.screen_image.maximum, 100)
            self.min_slider_edit.setValidator(validator)
            self.max_slider_edit.setValidator(validator)
        else:
            validator.setRange(self.screen_image.minimum, self.screen_image.maximum, 100)
        self.slider_edit.validator().setTop(self.slider.maximum())

        if self.label.width() < 256 or self.label.height() < 256:
            self.label.resize(256, 256)

    def append(self, images):
        if self.images is None:
            self.images = images
        else:
            if images.ndim == 2:
                images = images[np.newaxis, :, :]
            if images.shape[1:] != self.images.shape[1:]:
                raise ImageViewingError('Appended images have different shape '
                                        f'{images.shape[1:]} than the displayed ones '
                                        f'{self.images.shape[1:]}')
            self.images = np.concatenate((self.images, images))

    def set_enabled_adjustments(self, enabled):
        self.slider.setEnabled(enabled)
        self.slider_edit.setEnabled(enabled)
        self.min_slider.setEnabled(enabled)
        self.min_slider_edit.setEnabled(enabled)
        self.max_slider.setEnabled(enabled)
        self.max_slider_edit.setEnabled(enabled)

    def reset_clim(self, auto=False):
        self.screen_image.reset()
        if auto:
            self.screen_image.auto_levels()
        self.min_slider_edit.setText('{:g}'.format(self.screen_image.black_point))
        self.max_slider_edit.setText('{:g}'.format(self.screen_image.white_point))
        self.set_slider_value(self.min_slider, self.screen_image.black_point)
        self.set_slider_value(self.max_slider, self.screen_image.white_point)
        self.label.updateImage()
        self._update_pg_window_lut()

    @property
    def popup_visible(self):
        return self._pg_window and self._pg_window.isVisible()

    def popup(self):
        import pyqtgraph
        pyqtgraph.setConfigOptions(antialias=True, imageAxisOrder='row-major')
        if self._pg_window is not None:
            if not self._pg_window.isVisible():
                self._pg_window.show()
            return

        def on_pg_window_time_changed(index, time):
            self._set_index(index)
            self.slider.blockSignals(True)
            self.slider_edit.setText(str(index))
            self.slider.setValue(index)
            self.slider.blockSignals(False)

        def on_pg_window_levels_changed(hist_item):
            minimum, maximum = hist_item.getLevels()
            if (self.screen_image.minimum <= minimum <= self.screen_image.maximum
                    and self.screen_image.minimum <= maximum <= self.screen_image.maximum):
                self.min_slider_edit.setText('{:g}'.format(minimum))
                self.set_slider_value(self.min_slider, minimum)
                self.max_slider_edit.setText('{:g}'.format(maximum))
                self.set_slider_value(self.max_slider, maximum)
                self.screen_image.black_point = minimum
                self.screen_image.white_point = maximum
                self.label.updateImage()

        def pg_mouse_moved(ev):
            if self._pg_window.imageItem.sceneBoundingRect().contains(ev):
                pos = self._pg_window.imageItem.mapFromScene(ev)
                x = int(pos.x() + 0.5)
                y = int(pos.y() + 0.5)
                self._pg_window.view.setTitle('x={}, y={}, I={:g}'.format(x, y,
                                              self._pg_window.imageItem.image[y, x]))
            else:
                self._pg_window.view.setTitle('')

        self._pg_window = pyqtgraph.ImageView(view=pyqtgraph.PlotItem())
        self._pg_window.imageItem.scene().sigMouseMoved.connect(pg_mouse_moved)
        self._pg_window.setWindowFlag(Qt.SubWindow, True)
        self._update_pg_window_images()
        self._update_pg_window_index()
        self._update_pg_window_lut()
        self._pg_window.show()
        self._pg_window.sigTimeChanged.connect(on_pg_window_time_changed)
        self._pg_window.ui.histogram.item.sigLevelsChanged.connect(on_pg_window_levels_changed)

    def cleanup(self):
        if self._pg_window:
            self._pg_window.close()
        self._pg_window = None

    def _set_index(self, index):
        self.screen_image.image = self.images[index]
        self.label.updateImage()

    def _update_pg_window_images(self):
        if self.images.shape[0] == 1:
            im_to_set = self.images[0]
        else:
            im_to_set = self.images

        self._pg_window.setImage(im_to_set, autoLevels=False)

    def _update_pg_window_index(self):
        if self._images.shape[0] > 1 and self._pg_window is not None:
            self._pg_window.blockSignals(True)
            self._pg_window.setCurrentIndex(self.slider.value())
            self._pg_window.blockSignals(False)

    def _update_pg_window_lut(self):
        if self._pg_window is not None:
            self._pg_window.ui.histogram.item.blockSignals(True)
            self._pg_window.setLevels(self.screen_image.black_point, self.screen_image.white_point)
            self._pg_window.ui.histogram.item.blockSignals(False)

    def on_slider_value_changed(self, value):
        self._set_index(value)
        self.slider_edit.setText(str(value))
        self._update_pg_window_index()

    def on_slider_edit_return_pressed(self):
        self.slider.setValue(int(self.slider_edit.text()))

    def on_min_slider_edit_return_pressed(self):
        value = float(self.min_slider_edit.text())
        if value < self.screen_image.white_point:
            self.screen_image.black_point = value
            self.set_slider_value(self.min_slider, value)
            self.label.updateImage()
            self._update_pg_window_lut()

    def on_max_slider_edit_return_pressed(self):
        value = float(self.max_slider_edit.text())
        if value > self.screen_image.black_point:
            self.screen_image.white_point = value
            self.set_slider_value(self.max_slider, value)
            self.label.updateImage()
            self._update_pg_window_lut()

    def on_min_slider_value_changed(self, value):
        self.screen_image.set_black_point_normalized(value)
        self.min_slider_edit.setText('{:g}'.format(self.screen_image.black_point))
        self.label.updateImage()
        self._update_pg_window_lut()

    def on_max_slider_value_changed(self, value):
        self.screen_image.set_white_point_normalized(value)
        self.max_slider_edit.setText('{:g}'.format(self.screen_image.white_point))
        self.label.updateImage()
        self._update_pg_window_lut()

    def set_slider_value(self, slider, value):
        slider.blockSignals(True)
        slider.setValue(int(self.screen_image.convert_native_value_to_normalized(value)))
        slider.blockSignals(False)


class ImageViewingError(FlowError):
    pass
