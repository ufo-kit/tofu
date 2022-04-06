import os
import logging
import pyqtgraph as pg
import numpy as np
import tifffile
from PyQt5.QtWidgets import (
    QPushButton,
    QGroupBox,
    QLabel,
    QDoubleSpinBox,
    QRadioButton,
    QScrollBar,
    QVBoxLayout,
    QGridLayout,
    QFileDialog,
    QMessageBox,
)
from PyQt5.QtCore import Qt
import tofu.ez.image_read_write as image_read_write

#TODO Integrate axis search tab ob tofu gui into this interface

LOG = logging.getLogger(__name__)


class ImageViewerGroup(QGroupBox):
    def __init__(self):
        super().__init__()

        #TODO: initialize on every opening with explicit data type
        #mmatching the data format being opened.
        #must check that there is enough RAM before loading!!
        self.tiff_arr = np.empty([0, 0, 0]) # float32
        self.img_arr = np.empty([0, 0])
        self.bit_depth = 32

        self.open_file_button = QPushButton("Open Image File")
        self.open_file_button.clicked.connect(self.open_image_from_file)
        self.open_file_button.setStyleSheet("background-color: lightgrey; font: 11pt")

        self.open_stack_button = QPushButton("Open Image Stack")
        self.open_stack_button.clicked.connect(self.open_stack_from_directory)
        self.open_stack_button.setStyleSheet("background-color: lightgrey; font: 11pt")

        self.save_file_button = QPushButton("Save Image File")
        self.save_file_button.clicked.connect(self.save_image_to_file)
        self.save_file_button.setStyleSheet("background-color: lightgrey; font: 11pt")

        self.save_stack_button = QPushButton("Save Image Stack")
        self.save_stack_button.clicked.connect(self.save_stack_to_directory)
        self.save_stack_button.setStyleSheet("background-color: lightgrey; font: 11pt")

        self.open_big_tiff_button = QPushButton("Open BigTiff")
        self.open_big_tiff_button.clicked.connect(self.open_big_tiff)
        self.open_big_tiff_button.setStyleSheet("background-color: lightgrey; font: 11pt")

        self.save_big_tiff_button = QPushButton("Save BigTiff")
        self.save_big_tiff_button.clicked.connect(self.save_stack_to_big_tiff)
        self.save_big_tiff_button.setStyleSheet("background-color: lightgrey; font: 11pt")

        self.save_8bit_rButton = QRadioButton()
        self.save_8bit_rButton.setText("Save as 8-bit")
        self.save_8bit_rButton.clicked.connect(self.set_8bit)
        self.save_8bit_rButton.setChecked(False)

        self.save_16bit_rButton = QRadioButton()
        self.save_16bit_rButton.setText("Save as 16-bit")
        self.save_16bit_rButton.clicked.connect(self.set_16bit)
        self.save_16bit_rButton.setChecked(False)

        self.save_32bit_rButton = QRadioButton()
        self.save_32bit_rButton.setText("Save as 32-bit")
        self.save_32bit_rButton.clicked.connect(self.set_32bit)
        self.save_32bit_rButton.setChecked(True)

        self.hist_min_label = QLabel("Histogram Min:")
        self.hist_min_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.hist_max_label = QLabel("Histogram Max:")
        self.hist_max_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.hist_min_input = QDoubleSpinBox()
        self.hist_min_input.setDecimals(12)
        self.hist_min_input.setRange(-10, 10)
        self.hist_min_input.valueChanged.connect(self.min_spin_changed)
        self.hist_max_input = QDoubleSpinBox()
        self.hist_max_input.setDecimals(12)
        self.hist_max_input.setRange(-10, 10)
        self.hist_max_input.valueChanged.connect(self.max_spin_changed)

        self.apply_histogram_button = QPushButton("Apply Histogram to Image Stack")
        self.apply_histogram_button.clicked.connect(self.apply_histogram_button_clicked)

        self.image_window = pg.ImageView()

        self.image_window.ui.histogram.gradient.hide()
        self.histo = self.image_window.getHistogramWidget()

        self.scroller = QScrollBar(Qt.Horizontal)
        self.scroller.orientation()
        self.scroller.setEnabled(False)
        self.scroller.valueChanged.connect(self.scroll_changed)

        self.set_layout()

    def set_layout(self):
        vbox = QVBoxLayout()
        vbox.addWidget(self.save_8bit_rButton)
        vbox.addWidget(self.save_16bit_rButton)
        vbox.addWidget(self.save_32bit_rButton)

        gridbox = QGridLayout()
        gridbox.addWidget(self.hist_max_label, 0, 0)
        gridbox.addWidget(self.hist_max_input, 0, 1)
        gridbox.addWidget(self.hist_min_label, 1, 0)
        gridbox.addWidget(self.hist_min_input, 1, 1)

        layout = QGridLayout()
        layout.addWidget(self.open_file_button, 0, 0)
        layout.addWidget(self.save_file_button, 1, 0)
        layout.addWidget(self.open_stack_button, 0, 1)
        layout.addWidget(self.save_stack_button, 1, 1)
        layout.addWidget(self.open_big_tiff_button, 0, 2)
        layout.addWidget(self.save_big_tiff_button, 1, 2)
        layout.addItem(vbox, 0, 3, 2, 1)
        layout.addItem(gridbox, 0, 4, 2, 1)
        layout.addWidget(self.apply_histogram_button, 0, 5)
        layout.addWidget(self.image_window, 2, 0, 1, 6)
        layout.addWidget(self.scroller, 4, 0, 1, 5)

        self.setLayout(layout)

        self.resize(640, 480)

        self.show()

    def scroll_changed(self):
        """
        Updated the currently displayed image based on position of scroll bar
        :return: None
        """
        self.image_window.setImage(self.tiff_arr[self.scroller.value()].T)

    def open_image_from_file(self):
        """
        Opens and displays a single image (.tif) specified by the user in the file dialog
        :return: None
        """
        LOG.debug("Open image button pressed")
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(
            self, "Open .tif Image File", "", "Tiff Files (*.tif *.tiff)", options=options
        )
        if filePath:
            LOG.debug("Import image path: " + filePath)
            self.img_arr = image_read_write.read_image(filePath)
            self.image_window.setImage(self.img_arr.T)
            self.scroller.setEnabled(False)

    def open_image_from_filepath(self, filePath):
        """
        Opens and displays a single image (.tif) contained in a directory - (used when one slice is reconstructed)
        :param filePath: Full path and filename
        :return: None
        """
        LOG.debug("Open image from filepath: " + str(filePath))
        if filePath:
            LOG.debug("Import image path: " + filePath)
            self.img_arr = image_read_write.read_image(filePath)
            self.image_window.setImage(self.img_arr.T)
            self.scroller.setEnabled(False)

    def save_image_to_file(self):
        """
        Saves the currently displayed image to a file (.tif) specified by the user in the file dialog
        :return: None
        """
        LOG.debug("Save image to file")
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getSaveFileName(
            self, "QFileDialog.getSaveFileName()", "", "Tiff Files (*.tif *.tiff)", options=options
        )
        if filepath:
            LOG.debug(filepath)
            bit_depth_string = self.check_bit_depth(self.bit_depth)
            img = self.image_window.imageItem.qimage
            # https://www.programmersought.com/article/73475006380/
            size = img.size()
            s = img.bits().asstring(
                size.width() * size.height() * img.depth() // 8
            )  # format 0xffRRGGBB
            arr = np.fromstring(s, dtype=np.uint8).reshape(
                (size.height(), size.width(), img.depth() // 8)
            )
            image_read_write.write_image(
                arr.T[0].T, os.path.dirname(filepath), os.path.basename(filepath), bit_depth_string
            )

    def open_stack_from_directory(self):
        """
        Opens all images (.tif) in a directory and displays them. Allows for scrolling through images with slider
        :return: None
        """
        LOG.debug("Open image stack button pressed")
        dir_explore = QFileDialog()
        directory = dir_explore.getExistingDirectory()
        if directory:
            try:
                tiff_list = (".tif", ".tiff")
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Information)
                msg.setWindowTitle("Loading Images...")
                msg.setText("Loading Images from Directory")
                msg.show()
                self.tiff_arr = image_read_write.read_all_images(directory, tiff_list)
                self.scroller.setRange(0, self.tiff_arr.shape[0] - 1)
                self.scroller.setEnabled(True)
                self.image_window.setImage(self.tiff_arr[0].T)
                msg.close()
                mid_index = self.tiff_arr.shape[0] // 2
                self.scroller.setValue(mid_index)
            except image_read_write.InvalidDataSetError:
                print("Invalid Data Set")

    def open_stack_from_path(self, dir_path: str):
        """
        Read images (.tif) from directory path into RAM as 3D numpy array
        :param dir_path: Path to directory containing multiple .tiff image files
        """
        LOG.debug("Open stack from path")
        try:
            tiff_list = (".tif", ".tiff")
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Loading Images...")
            msg.setText("Loading Images from Directory")
            msg.show()
            self.tiff_arr = image_read_write.read_all_images(dir_path, tiff_list)
            self.scroller.setRange(0, self.tiff_arr.shape[0] - 1)
            self.scroller.setEnabled(True)
            self.image_window.setImage(self.tiff_arr[0].T)
            msg.close()
            mid_index = self.tiff_arr.shape[0] // 2
            self.scroller.setValue(mid_index)
        except image_read_write.InvalidDataSetError:
            print("Invalid Data Set")

    def save_stack_to_directory(self):
        """
        Saves images stored in numpy array to individual files (.tif) in directory specified by user dialog
        Saves these images as BigTiff if checkbox is set to True
        """
        LOG.debug("Save stack to directory button pressed")
        LOG.debug("Saving with bitdepth: " + str(self.bit_depth))
        dir_explore = QFileDialog()
        directory = dir_explore.getExistingDirectory()
        LOG.debug("Writing to directory: " + directory)
        if directory:
            bit_depth_string = self.check_bit_depth(self.bit_depth)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Saving Images...")
            msg.setText("Saving Images to Directory")
            msg.show()
            self.apply_histogram_to_images()
            image_read_write.write_all_images(self.tiff_arr, directory, bit_depth_string)
            msg.close()

    def open_big_tiff(self):
        """
        Opens images stored in a big tiff file (.tif) and displays them. Allows user to view them using scrollbar.
        :return: None
        """
        LOG.debug("Open big tiff button pressed")
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(
            self, "QFileDialog.getOpenFileName()", "", "All Files (*)", options=options
        )
        if filePath:
            LOG.debug("Import image path: " + filePath)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Loading Images...")
            msg.setText("Loading Images from BigTiff")
            msg.show()
            self.tiff_arr = tifffile.imread(filePath).astype(dtype=np.float32)
            self.scroller.setRange(0, self.tiff_arr.shape[0] - 1)
            self.scroller.setEnabled(True)
            self.image_window.setImage(self.tiff_arr[0].T)
            msg.close()
            mid_index = self.tiff_arr.shape[0] // 2
            self.scroller.setValue(mid_index)

    def save_stack_to_big_tiff(self):
        """
        Saves the stack of images currently loaded into RAM to a single bigtif file
        :return: None
        """
        LOG.debug("Save stack to bigtiff button pressed")
        LOG.debug("Saving with bitdepth: " + str(self.bit_depth))
        dir_explore = QFileDialog()
        options = QFileDialog.Options()
        filepath, _ = QFileDialog.getSaveFileName(
            self, "QFileDialog.getSaveFileName()", "", "Tiff Files (*.tif *.tiff)", options=options
        )
        if filepath:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Saving Images...")
            msg.setText("Saving Images to BigTiff")
            msg.show()
            # self.apply_histogram_to_images()
            bit_depth_string = self.check_bit_depth(self.bit_depth)
            tifffile.imwrite(filepath, self.tiff_arr, bigtiff=True, dtype=bit_depth_string)
            msg.close()

    def min_spin_changed(self):
        """
        Changes the levels of the histogram widget if the min spinbox has been changed
        :return: None
        """
        histo = self.image_window.getHistogramWidget()
        levels = histo.getLevels()
        min_level = self.hist_min_input.value()
        self.image_window.setLevels(min_level, levels[1])

    def max_spin_changed(self):
        """
        Changes the levels of the histogram widget if the max spinbox has been changed
        :return: None
        """
        histo = self.image_window.getHistogramWidget()
        levels = histo.getLevels()
        max_level = self.hist_max_input.value()
        self.image_window.setLevels(levels[0], max_level)

    def apply_histogram_button_clicked(self):
        LOG.debug("Apply Histogram Button Clicked")
        print("Applying histogram to images. This may take a moment.")
        self.apply_histogram_to_images()

    def apply_histogram_to_images(self):
        """
        Gets the histogram levels of the currently displayed image and applies them to all images in RAM
        :return: None
        """
        levels = self.histo.getLevels()
        self.tiff_arr = np.clip(self.tiff_arr, levels[0], levels[1])

    def check_bit_depth(self, bit_depth: int) -> str:
        """
        Returns a string indicating the bitdepth to store the images based on value of bit-depth radio buttons
        :param bit_depth:
        :return: String specifying datatype for numpy array
        """
        if bit_depth == 8:
            return "uint8"
        elif bit_depth == 16:
            return "uint16"
        elif bit_depth == 32:
            return "uint32"

    def set_8bit(self):
        """
        Sets value of bit_depth variable based on radio button selection
        :return: None
        """
        LOG.debug("Set 8-bit")
        self.bit_depth = 8

    def set_16bit(self):
        """
        Sets value of bit_depth variable based on radio button selection
        :return: None
        """
        LOG.debug("Set 16-bit")
        self.bit_depth = 16

    def set_32bit(self):
        """
        Sets value of bit_depth variable based on radio button selection
        :return: None
        """
        LOG.debug("Set 32-bit")
        self.bit_depth = 32
