import pytest
import numpy as np
from PyQt5.QtGui import QValidator
from tofu.flow.viewer import ImageLabel, ImageViewingError, ScreenImage, ImageViewer


@pytest.fixture(scope='function')
def screen_image():
    image = np.arange(256, dtype=np.float32).reshape(16, 16)

    return ScreenImage(image=image)


@pytest.fixture(scope='function')
def viewer(qtbot):
    viewer = ImageViewer()
    viewer.images = np.ones((10, 16, 16))
    viewer.popup()
    qtbot.addWidget(viewer._pg_window)

    return viewer


class TestScreenImage:
    def test_image_setter(self):
        screen_image = ScreenImage()
        assert screen_image.image is None
        screen_image.image = np.random.normal(size=(8, 8))
        assert screen_image.minimum is not None
        assert screen_image.maximum is not None
        assert screen_image.black_point is not None
        assert screen_image.white_point is not None

    def test_black_point_setter(self, screen_image):
        screen_image.black_point = 100
        assert screen_image.black_point == 100
        screen_image.white_point = 150
        # Black point cannot be greater than white point
        with pytest.raises(ImageViewingError):
            screen_image.black_point = 200

    def test_white_point_setter(self, screen_image):
        screen_image.white_point = 100
        assert screen_image.white_point == 100
        screen_image.black_point = 50
        # White point cannot be smaller than black point
        with pytest.raises(ImageViewingError):
            screen_image.white_point = 0

    def test_reset(self, screen_image):
        screen_image.reset()
        # We can test with ==, the data types  are the same so the extrema must be exactly the same
        assert screen_image.minimum == 0
        assert screen_image.maximum == 255
        assert screen_image.black_point == 0
        assert screen_image.white_point == 255
        # Going out of the original gray value range must not cause exception on reset
        screen_image.black_point = -100
        screen_image.white_point = -50
        screen_image.reset()

    def test_auto_levels(self, screen_image):
        screen_image.auto_levels()
        # nonsense values must pass as well
        screen_image.auto_levels(percentile=200.0)
        screen_image.auto_levels(percentile=-200.0)

    def test_set_black_point_normalized(self, screen_image):
        screen_image.set_black_point_normalized(100)
        assert screen_image.black_point == 100
        screen_image.set_white_point_normalized(150)
        # Black point cannot be greater than white point
        with pytest.raises(ImageViewingError):
            screen_image.set_black_point_normalized(200)

    def test_set_white_point_normalized(self, screen_image):
        screen_image.set_white_point_normalized(100)
        assert screen_image.white_point == 100
        screen_image.set_black_point_normalized(50)
        # White point cannot be smaller than black point
        with pytest.raises(ImageViewingError):
            screen_image.set_white_point_normalized(0)

    def test_convert_normalized_value_to_native(self, screen_image):
        assert screen_image.convert_normalized_value_to_native(128) == 128.
        with pytest.raises(ImageViewingError):
            screen_image.convert_normalized_value_to_native(-500)

        with pytest.raises(ImageViewingError):
            screen_image.convert_normalized_value_to_native(500)

    def test_convert_native_value_to_normalized(self, screen_image):
        assert screen_image.convert_native_value_to_normalized(128) == 128.
        with pytest.raises(ImageViewingError):
            screen_image.convert_native_value_to_normalized(-500)

        with pytest.raises(ImageViewingError):
            screen_image.convert_native_value_to_normalized(500)

        # One gray value must not cause division by zero erro
        screen_image.image = np.ones((4, 4))
        screen_image.reset()
        screen_image.convert_native_value_to_normalized(1)

    def test_get_pixmap(self, qtbot, screen_image):
        # Empty image must raise an exception
        with pytest.raises(ImageViewingError):
            ScreenImage().get_pixmap()

        # Downsampling
        pixmap = screen_image.get_pixmap()
        assert (pixmap.height(), pixmap.width()) == screen_image.image.shape

        pixmap = screen_image.get_pixmap(downsampling=2)
        assert (pixmap.height(), pixmap.width()) == tuple(dim // 2 for dim in
                                                          screen_image.image.shape)

        # One gray value must not cause division by zero erro
        screen_image.image = np.ones((4, 4))
        screen_image.reset()
        screen_image.get_pixmap()


class TestImageLabel:
    def test_updateImage(self, qtbot, screen_image):
        label = ImageLabel()
        # Empty image must pass
        label.updateImage()

        label.screen_image = screen_image
        label.updateImage()
        assert label.pixmap() is not None

    def test_resizeEvent(self, qtbot, screen_image):
        label = ImageLabel(screen_image)
        label.updateImage()
        old_size = label.pixmap().size()
        # ensure the label will get the resize event
        label.show()
        label.resize(8, 8)
        new_size = label.pixmap().size()
        assert new_size != old_size


class TestImageViewer:
    def test_images_setter(self, qtbot):
        viewer = ImageViewer()
        viewer.images = np.zeros((16, 16))
        assert viewer.images.ndim == 3
        assert viewer.slider.isHidden()
        assert float(viewer.min_slider_edit.text()) == 0
        assert float(viewer.max_slider_edit.text()) == 0

        viewer.images = np.ones((5, 16, 16))
        assert viewer.images.ndim == 3
        assert not viewer.slider.isHidden()
        assert viewer.slider.minimum() == 0
        assert viewer.slider.maximum() == viewer.images.shape[0] - 1
        assert float(viewer.min_slider_edit.text()) == 1
        assert float(viewer.max_slider_edit.text()) == 1

        # Test viewer and popup window equality
        viewer.popup()
        qtbot.addWidget(viewer._pg_window)
        np.testing.assert_almost_equal(viewer.images, 1)
        np.testing.assert_almost_equal(viewer._pg_window.image, 1)

        # 3D
        viewer.images = np.ones((5, 16, 16)) * 5
        np.testing.assert_almost_equal(viewer.images, 5)
        np.testing.assert_almost_equal(viewer._pg_window.image, 5)

        # 2D
        viewer.images = np.ones((16, 16)) * 3
        np.testing.assert_almost_equal(viewer.images, 3)
        np.testing.assert_almost_equal(viewer._pg_window.image, 3)

        # validators
        viewer.images = 10 + np.arange(200 * 8 ** 2).reshape(200, 8, 8)
        validator = viewer.slider_edit.validator()
        assert validator.validate('199', 0)[0] == QValidator.Acceptable
        assert validator.validate('2000', 0)[0] == QValidator.Invalid
        assert viewer.min_slider_edit.validator().bottom() == viewer.images[0].min()
        assert viewer.min_slider_edit.validator().top() == viewer.images[0].max()
        viewer._pg_window.close()

    def test_append(self, qtbot):
        viewer = ImageViewer()

        # Append to empty
        viewer.append(np.zeros((4, 4)))
        assert viewer.images.ndim == 3
        assert viewer.images.shape == (1, 4, 4)

        # Append 2D
        viewer.append(np.zeros((4, 4)))
        assert viewer.images.shape == (2, 4, 4)

        # Append 3D
        viewer.append(np.zeros((3, 4, 4)))
        assert viewer.images.shape == (5, 4, 4)

        # Append wrong shape
        with pytest.raises(ImageViewingError):
            viewer.append(np.zeros((3, 2, 2)))

    def test_set_enabled_adjustments(self, qtbot):
        viewer = ImageViewer()

        def assert_all(value):
            viewer.set_enabled_adjustments(value)
            assert viewer.slider.isEnabled() == value
            assert viewer.slider_edit.isEnabled() == value
            assert viewer.min_slider.isEnabled() == value
            assert viewer.min_slider_edit.isEnabled() == value
            assert viewer.max_slider.isEnabled() == value
            assert viewer.max_slider_edit.isEnabled() == value

        assert_all(True)
        assert_all(False)

    def test_reset_clim(self, viewer):
        image = np.arange(16 ** 2).reshape(16, 16)
        viewer.images = image
        viewer.append(image * 2)
        viewer.slider.setValue(1)
        viewer.reset_clim(auto=False)
        si = viewer.screen_image
        min_converted = si.convert_native_value_to_normalized(si.black_point)
        max_converted = si.convert_native_value_to_normalized(si.white_point)

        assert viewer.screen_image.maximum == pytest.approx(510)
        assert viewer.min_slider.value() == pytest.approx(min_converted)
        assert viewer.max_slider.value() == pytest.approx(max_converted)
        assert float(viewer.min_slider_edit.text()) == pytest.approx(si.black_point)
        assert float(viewer.max_slider_edit.text()) == pytest.approx(si.white_point)

        # Pop up window must be updated
        assert viewer._pg_window.getLevels() == pytest.approx((si.black_point, si.white_point))
        viewer._pg_window.close()

    def test_on_slider_value_changed(self, viewer):
        viewer.slider.setValue(5)

        assert viewer._pg_window.currentIndex == 5
        assert viewer.slider_edit.text() == '5'
        viewer._pg_window.close()

    def test_on_slider_edit_return_pressed(self, viewer):
        viewer.slider_edit.setText('5')
        viewer.slider_edit.returnPressed.emit()

        assert viewer.slider.value() == 5
        assert viewer._pg_window.currentIndex == 5
        viewer._pg_window.close()

    def test_on_min_slider_edit_return_pressed(self, viewer):
        viewer.images = np.arange(256).reshape(16, 16)
        viewer.min_slider_edit.setText('100')
        viewer.min_slider_edit.returnPressed.emit()
        assert viewer.screen_image.black_point == pytest.approx(100)
        assert viewer.min_slider.value() == pytest.approx(100)
        assert viewer._pg_window.getLevels()[0] == pytest.approx(100)
        viewer._pg_window.close()

    def test_on_max_slider_edit_return_pressed(self, viewer):
        viewer.images = np.arange(256).reshape(16, 16)
        viewer.max_slider_edit.setText('100')
        viewer.max_slider_edit.returnPressed.emit()
        assert viewer.screen_image.white_point == pytest.approx(100)
        assert viewer.max_slider.value() == pytest.approx(100)
        assert viewer._pg_window.getLevels()[1] == pytest.approx(100)
        viewer._pg_window.close()

    def test_on_min_slider_value_changed(self, viewer):
        viewer.images = np.arange(256).reshape(16, 16)
        viewer.min_slider.valueChanged.emit(100)
        assert viewer.screen_image.black_point == pytest.approx(100)
        assert float(viewer.min_slider_edit.text()) == pytest.approx(100)
        assert viewer._pg_window.getLevels()[0] == pytest.approx(100)
        viewer._pg_window.close()

    def test_on_max_slider_value_changed(self, viewer):
        viewer.images = np.arange(256).reshape(16, 16)
        viewer.max_slider.valueChanged.emit(100)
        assert viewer.screen_image.white_point == pytest.approx(100)
        assert float(viewer.max_slider_edit.text()) == pytest.approx(100)
        assert viewer._pg_window.getLevels()[1] == pytest.approx(100)
        viewer._pg_window.close()

    def test_popup(self, qtbot, viewer):
        # Close and another popup call must show the widget
        viewer._pg_window.close()
        viewer.popup()
        assert viewer._pg_window.isVisible()
        # 2D must work
        other = ImageViewer()
        other.images = np.ones((4, 4))
        other.popup()
        qtbot.addWidget(other._pg_window)
        assert other._pg_window is not None
        viewer._pg_window.close()
        other._pg_window.close()
