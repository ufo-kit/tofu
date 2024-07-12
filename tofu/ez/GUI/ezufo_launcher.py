import logging
import os
import sys
from PyQt5 import QtWidgets as qtw

from tofu.ez.GUI.Main.centre_of_rotation import CentreOfRotationGroup
from tofu.ez.GUI.Main.filters import FiltersGroup
from tofu.ez.GUI.Advanced.ffc import FFCGroup
from tofu.ez.GUI.Advanced.find_large_spots import FindSpotsGroup
from tofu.ez.GUI.Main.phase_retrieval import PhaseRetrievalGroup
from tofu.ez.GUI.Main.region_and_histogram import ROIandHistGroup
from tofu.ez.GUI.Main.config import ConfigGroup
from tofu.ez.main import clean_tmp_dirs
from tofu.ez.GUI.image_viewer import ImageViewerGroup
from tofu.ez.params import EZVARS, EZVARS_aux
from tofu.config import SECTIONS
from tofu.ez.util import load_values_from_ezdefault, get_fdt_names
from tofu.ez.GUI.Advanced.advanced import AdvancedGroup
from tofu.ez.GUI.Advanced.optimization import OptimizationGroup
from tofu.ez.GUI.Advanced.nlmdn import NLMDNGroup
from tofu.ez.GUI.Stitch_tools_tab.ez_360_multi_stitch_qt import MultiStitch360Group
from tofu.ez.GUI.Stitch_tools_tab.ezstitch_qt import EZStitchGroup
from tofu.ez.GUI.Stitch_tools_tab.ezmview_qt import EZMViewGroup
from tofu.ez.GUI.Stitch_tools_tab.ez_360_overlap_qt import Overlap360Group
from tofu.ez.GUI.Advanced.Batch360 import Batch360Group
# from tofu.ez.Helpers.batch_search_stitch_360 import Batcher
from tofu.ez.GUI.login_dialog import Login


LOG = logging.getLogger(__name__)


class GUI(qtw.QWidget):
    """
    Creates main GUI and sets defaults and creates some signals.
    First, load_vales_from_ezdefault has to be called in order to create ['value'] key for
    every parameter in EZVAR and SECTIONS dictionaries. Each element of those dictionaries
    is supposed to have 'ezdefault' key which is used to set the default value.
    These ['value']s will be used to set default values of all entries in GUI
    by calling load_value function in respective QGroupBoxes.
    These values can be changed by user and editing of each Qt feature must
    trigger set_ method in respective QGroupBoxe to update the ['value'].
    These dictionaries can be exported to yaml file and when imported later
    will be assigned to Qt GUI entries and to ['values'] of EZVAR and CONFIG dictionaries.
    When parameters are imported a signal is emitted which calls update_values
    function defined below which has to call load_values which must exist in every groupbox in the GUI
    """

    def __init__(self, *args, **kwargs):
        super(GUI, self).__init__(*args, **kwargs)
        self.setWindowTitle("EZ-UFO")

        self.setStyleSheet("font: 10pt; font-family: Arial")
        
        # initialize dictionary entries
        load_values_from_ezdefault(EZVARS)
        load_values_from_ezdefault(SECTIONS)
        load_values_from_ezdefault(EZVARS_aux)

        # Call login dialog
        # self.login_parameters = {}
        # QTimer.singleShot(0, self.login)

        # Initialize tab screen
        self.tabs = qtw.QTabWidget()
        self.tab1 = qtw.QWidget()
        self.tab2 = qtw.QWidget()
        self.tab3 = qtw.QWidget()
        self.tab4 = qtw.QWidget()
        self.tab5 = qtw.QWidget()
        self.tab6 = qtw.QWidget()

        # Create and setup classes for each section of GUI
        # Main Tab
        self.config_group = ConfigGroup()
        self.config_group.load_values()
        
        self.centre_of_rotation_group = CentreOfRotationGroup()
        self.centre_of_rotation_group.load_values()

        self.filters_group = FiltersGroup()
        self.filters_group.load_values()
        
        self.ffc_group = FFCGroup()
        self.ffc_group.load_values()

        self.phase_retrieval_group = PhaseRetrievalGroup()
        self.phase_retrieval_group.load_values()
        
        self.binning_group = ROIandHistGroup()
        self.binning_group.load_values()

        # Image Viewer
        self.image_group = ImageViewerGroup()

        # Advanced Tab
        self.advanced_group = AdvancedGroup()
        self.advanced_group.load_values()

        self.optimization_group = OptimizationGroup()
        self.optimization_group.load_values()

        self.nlmdn_group = NLMDNGroup()
        self.nlmdn_group.load_values()

        self.find_spots_group = FindSpotsGroup()
        self.find_spots_group.load_values()

        self.batch360_group = Batch360Group()
        self.batch360_group.load_values()

        # Stitch_tools_tab Tab 
        # ----((P)Completed up to here) ----#
        self.multi_stitch_group = MultiStitch360Group()
        self.multi_stitch_group.load_values()

        self.ezmview_group = EZMViewGroup()
        self.ezmview_group.init_values()

        self.ezstitch_group = EZStitchGroup()
        self.ezstitch_group.load_values()

        self.overlap_group = Overlap360Group()
        self.overlap_group.load_values()
        
        #######################################################

        self.set_layout()
        self.resize(0, 0)  # window to minimum size

        # When new settings are imported signal is sent and this catches it to update params for each GUI object
        self.config_group.signal_update_vals_from_params.connect(self.update_values)

        # When RECO is done send signal from config
        self.config_group.signal_reco_done.connect(self.switch_to_image_tab)

        # To pass directory names from config tab to stitch tab when button pressed
        self.multi_stitch_group.get_fdt_names_on_stitch_pressed.connect(self.config_group.set_fdt_names)
        self.overlap_group.get_fdt_names_on_stitch_pressed.connect(self.config_group.set_fdt_names)

        # To pass RR params from filters section to 360-search tab when button pressed
        self.overlap_group.get_RR_params_on_start_pressed.connect(
            self.filters_group.set_ufoRR_params_for_360_axis_search)

        # Enable GroupBoxes in Advanced setting when certain options are
        # selected in the Main tab
        self.filters_group.mask_method_median_checked.connect(
            self.find_spots_group.enable_by_trigger_from_main_tab
        )
        self.centre_of_rotation_group.enable_360Batch_Group_in_Advanced.connect(
            self.batch360_group.enable_by_trigger_from_main_tab
        )
        # self.batch360_group.imported_good_list_signal.connect(
        #     self.update_overlap_list
        # )


        finish = qtw.QAction("Quit", self)
        finish.triggered.connect(self.closeEvent)

        self.show()

    def set_layout(self):
        """
        Set the layout of groups/tabs for the overall application layout
        """
        layout = qtw.QVBoxLayout(self)

        main_layout = qtw.QGridLayout()
        main_layout.addWidget(self.centre_of_rotation_group, 0, 0)
        main_layout.addWidget(self.filters_group, 0, 1)
        main_layout.addWidget(self.phase_retrieval_group, 1, 0)
        main_layout.addWidget(self.binning_group, 1, 1)
        main_layout.addWidget(self.config_group, 2, 0, 2, 0)

        image_layout = qtw.QGridLayout()
        image_layout.addWidget(self.image_group, 0, 0)

        advanced_layout = qtw.QGridLayout()

        #advanced_layout.addWidget(self.batch360_group, 0, 0)
        advanced_layout.addWidget(self.find_spots_group, 0, 0)
        advanced_layout.addWidget(self.advanced_group, 1, 0)
        advanced_layout.addWidget(self.optimization_group, 1, 1)
        advanced_layout.addWidget(self.nlmdn_group, 0, 1)
        advanced_layout.addWidget(self.ffc_group, 2, 0)
        advanced_layout.addWidget(self.ezmview_group, 2, 1)

        helpers_layout = qtw.QGridLayout()
        helpers_layout.addWidget(self.overlap_group, 0, 0, 2, 1)
        helpers_layout.addWidget(self.batch360_group, 3, 1, 1, 1)
        helpers_layout.addWidget(self.multi_stitch_group, 2, 0, 2, 1)
        helpers_layout.addWidget(self.ezstitch_group, 0, 1, 3, 1)

        # Add tabs
        self.tabs.addTab(self.tab1, "Main")
        self.tabs.addTab(self.tab2, "Reco+")
        self.tabs.addTab(self.tab3, "Stitching tools")
        self.tabs.addTab(self.tab5, "Image Viewer")

        # Create main tab
        self.tab1.layout = main_layout
        self.tab1.setLayout(self.tab1.layout)

        # Create advanced tab
        self.tab2.layout = advanced_layout
        self.tab2.setLayout(self.tab2.layout)

        # Create helpers tab
        self.tab3.layout = helpers_layout
        self.tab3.setLayout(self.tab3.layout)

        # Create image tab
        self.tab5.layout = image_layout
        self.tab5.setLayout(self.tab5.layout)

        # Add tabs to widget
        layout.addWidget(self.tabs)
        self.setLayout(layout)

    def update_values(self):
        """
        Updates displayed values when loaded in from external .yaml file of parameters
        """
        LOG.debug("Update Values from dictionary entries")
        self.centre_of_rotation_group.load_values()
        self.filters_group.load_values()
        self.find_spots_group.load_values()
        self.ffc_group.load_values()
        self.phase_retrieval_group.load_values()
        self.binning_group.load_values()
        self.config_group.load_values()
        self.nlmdn_group.load_values()
        self.advanced_group.load_values()
        self.optimization_group.load_values()
        self.overlap_group.load_values()
        self.batch360_group.load_values()
        self.ezstitch_group.load_values()

    def switch_to_image_tab(self):
        """
        Function is called after reconstruction
        when checkbox "Load images and open viewer after reconstruction" is enabled
        Automatically loads images from the output reconstruction directory for viewing
        """
        if EZVARS['inout']['open-viewer']['value'] is True:
            LOG.debug("Switch to Image Tab")
            self.tabs.setCurrentWidget(self.tab2)
            if os.path.isdir(str(EZVARS['inout']['output-dir']['value'] + '/sli')):
                files = os.listdir(str(EZVARS['inout']['output-dir']['value'] + '/sli'))
                #Start thread here to load images

                ##CHECK IF ONLY SINGLE IMAGE THEN USE OPEN IMAGE -- OTHERWISE OPEN STACK
                if len(files) == 1:
                    print("Only one file in {}: Opening single image {}".
                          format(EZVARS['inout']['output-dir']['value'] + '/sli', files[0]))
                    filePath = str(EZVARS['inout']['output-dir']['value'] + '/sli/' + str(files[0]))
                    self.image_group.open_image_from_filepath(filePath)
                else:
                    print("Multiple files in {}: Opening stack of images".
                          format(str(EZVARS['inout']['output-dir']['value'] + '/sli')))
                    self.image_group.open_stack_from_path(
                        str(EZVARS['inout']['output-dir']['value'] + '/sli'))
            else:
                print("No output directory found")
                
    def closeEvent(self, event):
        """
        Creates verification message box
        Cleans up temporary directories when user quits application
        """
        logging.debug("QUIT")
        reply = qtw.QMessageBox.question(self, 'Quit', 'Are you sure you want to quit?',
                        qtw.QMessageBox.Yes | qtw.QMessageBox.No, qtw.QMessageBox.No)
        if reply == qtw.QMessageBox.Yes:
            # remove all directories with projections
            clean_tmp_dirs(EZVARS['inout']['tmp-dir']['value'], get_fdt_names())
            # remove axis-search dir too
            tmp = os.path.join(EZVARS['inout']['tmp-dir']['value'], 'axis-search')
            event.accept()
        else:
            event.ignore()

    def login(self):
        login_dialog = Login(self.login_parameters)
        if login_dialog.exec_() != qtw.QDialog.Accepted:
            self.exit()
        else:
            #self.file_writer_group.root_dir_entry.setText(self.login_parameters['expdir'])
            self.config_group.input_dir_entry.setText(self.login_parameters['expdir'] + "/raw")
            self.config_group.set_input_dir()
            self.config_group.output_dir_entry.setText(self.login_parameters['expdir'] + "/rec")
            self.config_group.set_output_dir()
            '''
            td = date.today()
            tdstr = "{}.{}.{}".format(td.year, td.month, td.day)
            logfname = os.path.join(self.login_parameters['expdir'], 'exp-log-' + tdstr + '.log')
            if self.login_parameters.has_key('project'):
                logfname = os.path.join(self.login_parameters['expdir'], '{}-log-{}-{}.log'.
                                        format(self.login_parameters['project'], self.login_parameters['bl'], tdstr))
            try:
                open(logfname, 'a').close()
            except:
                warning_message('Cannot create log file in the selected directory. \n'
                                'Check permissions and restart.')
                self.exit()
            '''

    def exit(self):
        self.close()


def main_qt(args=None):
    app = qtw.QApplication(sys.argv)
    window = GUI()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main_qt()
