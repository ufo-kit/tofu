import logging
from PyQt5.QtWidgets import (QGridLayout, QLabel, QGroupBox, QLineEdit, QRadioButton, QPushButton,
    QFileDialog, QMessageBox,QCheckBox)
from PyQt5.QtCore import pyqtSignal
from tofu.ez.params import EZVARS_aux
from tofu.ez.util import add_value_to_dict_entry, import_values
import os
from shutil import rmtree

class Batch360Group(QGroupBox):
    """
    Advanced Tofu Reco settings
    """
    imported_good_list_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()

        self.setTitle("AUTO STITCHING AND BATCH PROCESSING OF HALF ACQ. MODE DATA")
        self.setStyleSheet("QGroupBox {color: black;}")
        self.setEnabled(False)


        self.info_label = QLabel(f"Input directory structure MUST have four depth layers:\n"
                                 f"Input -> Scans --> CT subdirectories --> flats/darks/tomo. \n"
                                 f"You have to configure 360_overlap_search utility in top left  "
                                 f"to enable the automatic stitching. \n"
                                 "Then switch to Main tab set reco parameters and press Reconstruct as usual.\n")

        self.dummy_text = QLabel()
        self.list_is_good = False
        self.outloopscans = None

        self.stitch_and_reco_rButton = QRadioButton()
        self.stitch_and_reco_rButton.setText("Stitch and reconstruct. \n"
                                            "You must provide structured file with overlap for each data set."
                                            )
        self.stitch_and_reco_rButton.clicked.connect(self.set_rButton)

        self.find_olap_stitch_and_reco_rButton = QRadioButton()
        self.find_olap_stitch_and_reco_rButton.setText("Estimate overlap, stitch, and reconstruct")
        self.find_olap_stitch_and_reco_rButton.clicked.connect(self.set_rButton)

        # Import file with overlaps
        self.open_olap_file_button = QPushButton()
        self.open_olap_file_button.setText("Import file with overlaps with the structure\n"
                                           "as produced by 360-find-overlaps tool")
        self.open_olap_file_button.pressed.connect(self.import_olap_file_button_pressed)
        self.open_olap_file_button.setEnabled(True)
        h = 'Example of the file structure (as created by 360-find-overlap tool):'
        # h += '/data/TestBatch/foo2': # outer loop scan
        # h += '    {'z02': 40, 'z03': 41},'  # several inner loop scans
        self.open_olap_file_button.setToolTip(h)


        # Select directory for intermediate 360 data
        self.halfacq_dir_select = QPushButton()
        self.halfacq_dir_select.setText("Select working directory")
        self.halfacq_dir_select.setToolTip(
            "Slices to search overlap and horizontally stitched 360 projections will be saved there.\n"
        )
        self.halfacq_dir_select.pressed.connect(self.select_halfacq_dir)
        self.halfacq_dir_entry = QLineEdit()
        self.halfacq_dir_entry.setToolTip(
            "Slices to search overlap and horizontally stitched 360 projections will be saved there.\n"
        )
        self.halfacq_dir_entry.editingFinished.connect(self.set_halfacq_dir)

        self.doVertStitching_checkbox = QCheckBox("Invoke vertical stitching when "
                                         "reconstruction is over. \n You must set"
                                         "params correctly in the Stitch Tab.")
        self.doVertStitching_checkbox.clicked.connect(self.set_doVertStitching)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()

        layout.addWidget(self.info_label, 0, 0, 1, 2)
        layout.addWidget(self.stitch_and_reco_rButton, 2, 0)
        layout.addWidget(self.open_olap_file_button, 2, 1)
        layout.addWidget(self.find_olap_stitch_and_reco_rButton, 1, 0)

        layout.addWidget(self.halfacq_dir_select, 3, 0)
        layout.addWidget(self.halfacq_dir_entry, 3, 1)
        #layout.addWidget(self.doVertStitching_checkbox, 4, 0, 1, 2)

        self.setLayout(layout)

    def load_values(self):
        self.set_rButton_from_params()
        self.halfacq_dir_entry.setText(str(EZVARS_aux['half-acq']['workdir']['value']))
        #I have to mention everything in load_values so that they will be initialized properly
        self.dummy_text.setText(str(EZVARS_aux['half-acq']['list_dirs']['value']))
        self.dummy_text.setText(str(EZVARS_aux['half-acq']['list_olaps']['value']))


    def enable_by_trigger_from_main_tab(self, enabled):
        if enabled:
            self.setEnabled(True)
            self.find_olap_stitch_and_reco_rButton.setChecked(True)
            self.set_rButton()
        else:
            self.setEnabled(False)

    def set_rButton_from_params(self):
        # TODO: it seems it is not being set correctly. Plus: check that dir empty here?
        if EZVARS_aux['half-acq']['task_type']['value']:
            self.stitch_and_reco_rButton.setChecked(False)
            self.find_olap_stitch_and_reco_rButton.setChecked(True)
            self.open_olap_file_button.setEnabled(False)
        else:
            self.stitch_and_reco_rButton.setChecked(True)
            self.find_olap_stitch_and_reco_rButton.setChecked(False)
            self.open_olap_file_button.setEnabled(True)
        return

    def set_rButton(self):
        if self.stitch_and_reco_rButton.isChecked():
            add_value_to_dict_entry(EZVARS_aux['half-acq']['task_type'], 0)
            self.open_olap_file_button.setEnabled(True)
        elif self.find_olap_stitch_and_reco_rButton.isChecked():
            add_value_to_dict_entry(EZVARS_aux['half-acq']['task_type'], 1)
            self.open_olap_file_button.setEnabled(False)

    def select_halfacq_dir(self):
        dir_explore = QFileDialog(self)
        tmp_dir = dir_explore.getExistingDirectory(directory=self.halfacq_dir_entry.text())
        if tmp_dir:
            self.halfacq_dir_entry.setText(tmp_dir)
            self.set_halfacq_dir()
        else:
            QMessageBox.information(self, "Select valid directory")
            return
        #if os.path.exists(self.EZVARS_aux['find360olap']['tmp-dir']) and \
        if len(os.listdir(tmp_dir)) > 0:
            qm = QMessageBox()
            rep = qm.question(self, 'WARNING', "Directory exists and not empty. \n "
                                               "Clean it or select a new directory. \n"
                                               "Is it SAFE to delete directory now?", qm.Yes | qm.No)
            if rep == qm.Yes:
                try:
                    rmtree(tmp_dir)
                except:
                    QMessageBox.information(self, "Problem", "Cannot delete existing directory")
                    return
            else:
                return

    def set_halfacq_dir(self):
        dict_entry = EZVARS_aux['half-acq']['workdir']
        text = self.halfacq_dir_entry.text().strip()
        add_value_to_dict_entry(dict_entry, text)
        # stitched_data_dir_name = os.path.join(EZVARS_aux['half-acq']['workdir']['value'],
        #                                       'stitched-data')
        # if os.path.exists(stitched_data_dir_name) and \
        #         len(os.listdir(stitched_data_dir_name)) > 0:
        #     QMessageBox.information(self, "Problem", "Directory for stitched data already exists \n"
        #                                              "and not empty. Clean it and try again.")

    def set_doVertStitching(self):
        add_value_to_dict_entry(EZVARS_aux['half-acq']['dovertsti'],
                                self.doVertStitching_checkbox.isChecked())

    def import_olap_file_button_pressed(self):
        """
        Loads external settings from .yaml file specified by user
        Signal is sent to enable updating of displayed GUI values
        """
        options = QFileDialog.Options()
        filePath, _ = QFileDialog.getOpenFileName(
            self,
            "QFileDialog.getOpenFileName()",
            "",
            "YAML Files (*.yaml);; All Files (*)",
            options=options,
        )
        if filePath:
            # structure holding path to CT sets and respective overlaps
            # must be imported
            try:
                self.olap_lists = import_values(filePath, ['ezvars_aux'])
            except:
                QMessageBox.information(self, "Cannot import list of overlaps")
#             self.list_is_good = self.check_olap_lists()
#             if self.list_is_good:
#                 self.imported_good_list_signal.emit(self.olap_lists)
#                 self.set_olap_list_in_EZVARS_aux()
#                 print(EZVARS_aux)
#
#     def check_olap_lists(self):
#         try:
#             self.outloopscans = set([os.path.dirname(w) for w in self.olap_lists.keys()])
#         except:
#             QMessageBox.information(self, "Cannot extract directory names from the supplied file")
#             return False
#         try:
#             for o in self.olap_lists.values(): int(o)
#         except:
#             QMessageBox.information(self, "One of overlaps is not a number in the supplied file")
#             return False
# #        EZVARS_aux['half-acq']['list_dirs']['value'] = ''
#         return True
#
#     def set_olap_list_in_EZVARS_aux(self):
#         for outscan in self.outloopscans:
#             EZVARS_aux['axes-list'].update({str(outscan) : {} })
#             for j in self.olap_lists.keys():
#                 tmp = os.path.dirname(j)
#                 if outscan == tmp:
#                     EZVARS_aux['axes-list'][outscan][j[len(tmp)+1:]] = self.olap_lists[j]
#         return








