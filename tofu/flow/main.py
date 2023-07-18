import json
import logging
import os
import pathlib
import sys
from PyQt5.QtCore import Qt, QObject, QPoint, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QFileDialog, QWidget, QVBoxLayout, QMenuBar,
                             QMessageBox, QProgressBar, QMainWindow, QStyle)
from qtpynodeeditor import DataModelRegistry, FlowView
import xdg.BaseDirectory

from tofu.flow.execution import UfoExecutor
from tofu.flow.models import (BaseCompositeModel, get_composite_model_classes_from_json,
                              get_composite_model_classes, get_ufo_model_classes, ImageViewerModel,
                              UfoGeneralBackprojectModel, UfoMemoryOutModel, UfoOpenCLModel,
                              UfoReadModel, UfoRetrievePhaseModel, UfoWriteModel)
from tofu.flow.scene import UfoScene
from tofu.flow.propertylinkswidget import PropertyLinks
from tofu.flow.runslider import RunSlider
from tofu.flow.util import FlowError


LOG = logging.getLogger(__name__)


class ApplicationWindow(QMainWindow):
    def __init__(self, ufo_scene):
        super().__init__()
        self.ufo_scene = ufo_scene
        self.property_links_widget = PropertyLinks(ufo_scene.node_model,
                                                   ufo_scene.property_links_model,
                                                   parent=self)
        self.run_slider = RunSlider(parent=self)
        self.executor = UfoExecutor()
        self.console = None
        self.run_slider_key = (None, None)
        self.last_dirs = {'scene': None, 'composite': None}
        self._creating_composite = False
        self._expanding_composite = False

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        self.flow_view = FlowView(self.ufo_scene)
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)

        menu_bar = QMenuBar()
        flow_menu = menu_bar.addMenu('Flow')
        new_action = flow_menu.addAction("New")
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.on_new)
        save_action = flow_menu.addAction("Save")
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.on_save)
        save_json_action = flow_menu.addAction("Save json")
        save_json_action.setShortcut('Ctrl+J')
        save_json_action.triggered.connect(self.on_save_json)
        load_action = flow_menu.addAction("Open")
        load_action.setShortcut('Ctrl+O')
        load_action.triggered.connect(self.on_open)
        self.run_action = flow_menu.addAction(self.style().standardIcon(QStyle.SP_MediaPlay),
                                              'Run')
        self.run_action.setShortcut('Ctrl+R')
        self.run_action.triggered.connect(self.on_run)
        abort_action = flow_menu.addAction(self.style().standardIcon(QStyle.SP_MediaStop), 'Abort')
        abort_action.setShortcut('Ctrl+Shift+X')
        abort_action.triggered.connect(self.executor.abort)
        exit_action = flow_menu.addAction('Exit')
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)

        # Nodes submenu
        selection_menu = menu_bar.addMenu('Nodes')
        selection_menu.setToolTipsVisible(True)
        selection_menu.aboutToShow.connect(self.on_selection_menu_about_to_show)
        self.skip_action = selection_menu.addAction('Skip Toggle')
        self.skip_action.setShortcut('S')
        self.skip_action.triggered.connect(self.ufo_scene.skip_nodes)
        auto_fill_action = selection_menu.addAction('Auto fill')
        auto_fill_action.triggered.connect(self.ufo_scene.auto_fill)
        copy_action = selection_menu.addAction("Duplicate")
        copy_action.setShortcut('Ctrl+Shift+D')
        copy_action.triggered.connect(self.ufo_scene.copy_nodes)
        # Composite
        create_composite_action = selection_menu.addAction("Create Composite")
        create_composite_action.setShortcut('Ctrl+Shift+C')
        create_composite_action.triggered.connect(self.on_create_composite)
        import_composites_action = selection_menu.addAction("Import Composites")
        import_composites_action.setToolTip('Import one or more composite nodes '
                                            'from a file or files')
        import_composites_action.setShortcut('Ctrl+I')
        import_composites_action.triggered.connect(self.on_import_composites)
        self.export_composite_action = selection_menu.addAction("Export Composite")
        self.export_composite_action.triggered.connect(self.on_export_composite)
        self.edit_composite_action = selection_menu.addAction("Edit Composite")
        self.edit_composite_action.triggered.connect(self.on_edit_composite)
        self.expand_composite_action = selection_menu.addAction("Expand Composite")
        self.expand_composite_action.setShortcut('Ctrl+Shift+E')
        self.expand_composite_action.triggered.connect(self.on_expand_composite)

        view_menu = menu_bar.addMenu('View')
        reset_view_action = view_menu.addAction("Reset Zoom")
        reset_view_action.setShortcut('Ctrl+0')
        reset_view_action.triggered.connect(self.on_reset_view)
        property_links_action = view_menu.addAction("Link Properties")
        property_links_action.setShortcut('Ctrl+L')
        property_links_action.triggered.connect(self.on_property_links_action)
        console_action = view_menu.addAction("Open Python Console")
        console_action.setShortcut('Ctrl+Shift+P')
        console_action.triggered.connect(self.on_console_action)
        run_slider_action = view_menu.addAction("Run Slider")
        run_slider_action.setShortcut('Ctrl+Shift+S')
        run_slider_action.triggered.connect(self.on_run_slider_action)
        self.fix_run_slider = view_menu.addAction("Fix Run Slider")
        self.fix_run_slider.setCheckable(True)
        self.fix_run_slider.setShortcut('Ctrl+Alt+Shift+S')

        main_layout.addWidget(menu_bar)
        main_layout.addWidget(self.flow_view)
        main_layout.addWidget(self.progress_bar)

        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.resize(1280, 1000)

        # Signals
        self.executor.exception_occured.connect(self.on_exception_occured)
        self.executor.execution_finished.connect(self.on_execution_finished)
        self.executor.number_of_inputs_changed.connect(self.on_number_of_inputs_changed)
        self.executor.processed_signal.connect(self.on_processed)
        self.ufo_scene.node_deleted.connect(self.on_node_deleted)
        self.ufo_scene.nodes_duplicated.connect(self.on_nodes_duplicated)
        self.ufo_scene.item_focus_in.connect(self.on_item_focus_in)
        self.run_slider.value_changed.connect(self.on_run_slider_value_changed)

        self.setWindowTitle('tofu flow')

    def on_save(self):
        if self.last_dirs['scene']:
            path = self.last_dirs['scene']
        else:
            path = xdg.BaseDirectory.save_data_path('tofu', 'flows')
            if not os.path.exists(path):
                os.makedirs(path)

        file_name, _ = QFileDialog.getSaveFileName(self,
                                                   "Select File Name",
                                                   str(path),
                                                   "Flow Scene Files (*.flow)")
        if file_name:
            self.last_dirs['scene'] = os.path.dirname(file_name)
            self.ufo_scene.save(file_name)

    def on_new(self):
        self.run_slider.reset()
        self.ufo_scene.clear_scene()
        self.setWindowTitle('tofu flow')

    def on_open(self):
        if self.last_dirs['scene']:
            path = self.last_dirs['scene']
        else:
            path = xdg.BaseDirectory.save_data_path('tofu', 'flows')
            if not os.path.exists(path):
                path = pathlib.Path.home()

        file_name, _ = QFileDialog.getOpenFileName(self,
                                                   "Open Flow Scene",
                                                   str(path),
                                                   "Flow Scene Files (*.flow)")

        if file_name:
            self.last_dirs['scene'] = os.path.dirname(file_name)
            self.ufo_scene.load(file_name)
            self.run_slider.reset()
            self.setWindowTitle(file_name)

    def on_exception_occured(self, text):
        msg = QMessageBox(parent=self)
        msg.setIcon(QMessageBox.Critical)
        msg.setText(text)
        msg.setWindowTitle("Error")
        msg.exec_()

    def on_number_of_inputs_changed(self, value):
        self.progress_bar.setMaximum(value)

    def on_processed(self, value):
        self.progress_bar.setValue(value + 1)

    def on_node_deleted(self, node):
        slider_model, prop_name = self.run_slider_key
        if slider_model:
            if (isinstance(node.model, BaseCompositeModel)
                and node.model.is_model_inside(slider_model)
                    and not (self._expanding_composite or self._creating_composite)):
                self.run_slider.reset()
                self.run_slider_key = (None, None)
            elif node.model == slider_model and not self._creating_composite:
                self.run_slider.reset()
                self.run_slider_key = (None, None)

    def on_nodes_duplicated(self, selected_nodes, new_nodes):
        min_y = float('inf')
        y_1 = float('-inf')
        for node in selected_nodes:
            height = node.model.embedded_widget().height()
            y = node.graphics_object.y()
            if y < min_y:
                min_y = y
            if y + height > y_1:
                y_1 = y + height

        for node in selected_nodes:
            dy = node.graphics_object.y() - min_y
            new_pos = QPoint(int(node.graphics_object.x()), int(dy + y_1 + 100))
            new_nodes[node].graphics_object.setPos(new_pos)

    def on_item_focus_in(self, item, prop_name, caption, model):
        if not self.fix_run_slider.isChecked() or not self.run_slider.view_item:
            if self.run_slider.setup(item):
                self.run_slider_key = (model, prop_name)
                self.run_slider.setWindowTitle(f'{caption}->{prop_name}')

    def on_selection_menu_about_to_show(self):
        composites = False
        num_selected = len(self.ufo_scene.selected_nodes())
        for node in self.ufo_scene.selected_nodes():
            if isinstance(node.model, BaseCompositeModel):
                composites = True
                break

        self.edit_composite_action.setEnabled(num_selected == 1 and composites)
        self.export_composite_action.setEnabled(num_selected == 1 and composites)
        self.expand_composite_action.setEnabled(composites)
        self.skip_action.setEnabled(self.ufo_scene.selected_nodes() != [])

    def on_edit_composite(self):
        if self.ufo_scene.is_selected_one_composite():
            # Check again in case this was invoked by the keyboard shortcut
            node = self.ufo_scene.selected_nodes()[0]
            node.model.edit_in_window(self)

    def on_create_composite(self):
        self._creating_composite = True
        try:
            path = None
            prop_name = self.run_slider_key[1]
            if self.run_slider_key[0]:
                for node in self.ufo_scene.selected_nodes():
                    if isinstance(node.model, BaseCompositeModel):
                        if node.model.is_model_inside(self.run_slider_key[0]):
                            path = node.model.get_path_from_model(self.run_slider_key[0])
                    elif node.model == self.run_slider_key[0]:
                        path = [self.run_slider_key[0]]

            composite_model = self.ufo_scene.create_composite().model

            if path:
                str_path = [model.caption for model in path]
                new_model = composite_model.get_model_from_path(str_path)
                new_view_item = new_model.get_view_item(prop_name)
                # Do not make complete setup, that would reset limits, just update the view item
                self.run_slider.view_item = new_view_item
                self.run_slider_key = (new_model, prop_name)
                title = '->'.join([composite_model.caption] + str_path + [prop_name])
                self.run_slider.setWindowTitle(title)
        finally:
            self._creating_composite = False

    def on_expand_composite(self):
        self._expanding_composite = True
        try:
            slider_model, prop_name = self.run_slider_key
            for node in self.ufo_scene.selected_nodes():
                if isinstance(node.model, BaseCompositeModel):
                    if slider_model:
                        str_path = None
                        if node.model.is_model_inside(slider_model):
                            str_path = [model.caption for model in
                                        node.model.get_path_from_model(slider_model)]

                    new_nodes = self.ufo_scene.expand_composite(node)[0]

                    # Pass the new node to the run slider if it was contained in this composite
                    if slider_model and str_path:
                        if slider_model.caption in new_nodes:
                            # runslider linked to a simple node after expanstion
                            slider_model = new_nodes[slider_model.caption].model
                            self.run_slider_key = (slider_model, prop_name)
                            new_view_item = slider_model.get_view_item(prop_name)
                            # Do not make complete setup, that would reset limits, just update the
                            # view item
                            self.run_slider.view_item = new_view_item
                            self.run_slider.setWindowTitle(f'{slider_model.caption}->{prop_name}')
                        else:
                            # runslider linked to another composite node (nesting) after expanstion
                            for node in new_nodes.values():
                                if isinstance(node.model, BaseCompositeModel):
                                    if node.model.contains_path(str_path[2:]):
                                        new_model = node.model.get_model_from_path(str_path[2:])
                                        self.run_slider_key = (new_model, prop_name)
                                        new_view_item = new_model.get_view_item(prop_name)
                                        # Do not make complete setup, that would reset limits, just
                                        # update the view item
                                        self.run_slider.view_item = new_view_item
                                        title = '->'.join(str_path[1:] + [prop_name])
                                        self.run_slider.setWindowTitle(title)
                                        self.run_slider_key = (new_model, prop_name)
                                        break

        finally:
            self._expanding_composite = False

    def on_import_composites(self):
        if self.last_dirs['composite']:
            path = self.last_dirs['composite']
        else:
            path = xdg.BaseDirectory.save_data_path('tofu', 'flows', 'composites')
            if not os.path.exists(path):
                path = pathlib.Path.home()

        file_names, _ = QFileDialog.getOpenFileNames(self,
                                                     "Select File Names",
                                                     str(path),
                                                     "Composite Model Files (*.cm)")

        if not file_names:
            return

        self.last_dirs['composite'] = os.path.dirname(file_names[0])

        overwriting = {}
        for file_name in file_names:
            LOG.debug(f'Loading composite from {file_name}')
            with open(file_name, 'r') as f:
                state = json.load(f)
            for model in get_composite_model_classes_from_json(state):
                if model.name in self.ufo_scene.registry.registered_model_creators():
                    overwriting[model.name] = os.path.basename(file_name)
                self.ufo_scene.registry.register_model(model,
                                                       category='Composite',
                                                       registry=self.ufo_scene.registry)

        if overwriting:
            msg = QMessageBox(parent=self)
            msg.setIcon(QMessageBox.Warning)
            msg.setText('Composite nodes with same names detected. Files from which '
                        'the nodes have been loaded are listed in details.')
            msg.setDetailedText('\n'.join([f'Node name "{name}" from file "{file_name}"'
                                           for (name, file_name) in overwriting.items()]))
            msg.setWindowTitle('Warning')
            msg.exec_()

    def export_composite(self, node, file_name):
        state = node.model.save()
        with open(file_name, 'w') as f:
            json.dump(state, f, indent=4)

    def on_export_composite(self):
        if not self.ufo_scene.is_selected_one_composite():
            # Check again in case this was invoked by the keyboard shortcut
            return

        if self.last_dirs['composite']:
            path = self.last_dirs['composite']
        else:
            path = xdg.BaseDirectory.save_data_path('tofu', 'flows', 'composites')
            if not os.path.exists(path):
                os.makedirs(path)

        file_name, _ = QFileDialog.getSaveFileName(self,
                                                   "Select File Name",
                                                   str(path),
                                                   "Composite Model Files (*.cm)")
        if file_name:
            self.last_dirs['composite'] = os.path.dirname(file_name)
            if not file_name.endswith('.cm'):
                file_name += '.cm'
            self.export_composite(self.ufo_scene.selected_nodes()[0], file_name)

    def on_reset_view(self):
        for view in self.ufo_scene.views():
            transform = view.transform()
            transform.reset()
            view.setTransform(transform)

    def on_property_links_action(self):
        self.property_links_widget.show()
        # Make sure it goes to the front if it is currently burried under other windows
        self.property_links_widget.raise_()

    def on_console_action(self):
        if self.console:
            self.console.show()
            return

        try:
            from pyqtconsole.console import PythonConsole
            from pyqtconsole.highlighter import format
            self.console = PythonConsole(formats={
                'keyword': format('darkBlue', 'bold')
            })
            self.console.setWindowFlag(Qt.SubWindow, True)
            self.console.ctrl_d_exits_console(True)
            self.console.push_local_ns('scene', self.ufo_scene)
            self.console.resize(640, 480)
            self.console.show()
            self.console.eval_queued()
        except ImportError as e:
            LOG.error(e, exc_info=True)
            self.on_exception_occured(str(e))

    def on_run_slider_action(self):
        if not self.run_slider.view_item:
            msg = QMessageBox(parent=self)
            msg.setIcon(QMessageBox.Information)
            msg.setText('Click on an input field in the flow to connect the slider')
            msg.exec_()
        else:
            self.run_slider.show()
            # Make sure it goes to the front if it is currently burried under other windows
            self.run_slider.raise_()

    def on_run_slider_value_changed(self, value):
        if self.run_action.isEnabled():
            self.on_run()

    def on_run(self):
        graphs = self.ufo_scene.get_simple_node_graphs()
        if len(graphs) != 1:
            raise FlowError('Scene must contain one fully connected graph')
        if not self.ufo_scene.is_fully_connected():
            raise FlowError('Not all node ports are connected')
        self.executor.run(graphs[0])
        self.run_action.setEnabled(False)
        self.ufo_scene.set_enabled(False)

    def on_save_json(self):
        graphs = self.ufo_scene.get_simple_node_graphs()
        if len(graphs) != 1:
            raise FlowError('Scene must contain one fully connected graph')
        if not self.ufo_scene.is_fully_connected():
            raise FlowError('Not all node ports are connected')
        if not self.ufo_scene.are_all_ufo_tasks(graphs=graphs):
            raise FlowError('Flow contains other than pure UFO nodes (nodes with different '
                            'data types, e.g. Memory Out or Image Viewer)')

        ufo_graph = self.executor.setup_ufo_graph(graphs[0])

        if self.last_dirs['scene']:
            path = self.last_dirs['scene']
        else:
            path = xdg.BaseDirectory.save_data_path('tofu', 'flows')
            if not os.path.exists(path):
                os.makedirs(path)

        file_name, _ = QFileDialog.getSaveFileName(self,
                                                   "Select File Name",
                                                   str(path),
                                                   "json-File (*.json)")
        if file_name:
            self.last_dirs['scene'] = os.path.dirname(file_name)
            if not file_name.endswith('.json'):
                file_name += '.json'
            ufo_graph.save_to_json(file_name)

    def on_execution_finished(self):
        self.progress_bar.reset()
        self.run_action.setEnabled(True)
        self.ufo_scene.set_enabled(True)


class GlobalExceptionHandler(QObject):
    """
    Intercept exceptions, log them and inform user if they are UI-related. Emit a signal when the
    error message should be shown to the user so that e.g. a message can be shown in the main
    thread.
    """
    exception_occured = pyqtSignal(str)

    def excepthook(self, exc_type, exc_value, exc_traceback):
        LOG.error(exc_value, exc_info=(exc_type, exc_value, exc_traceback))
        if issubclass(exc_type, FlowError):
            self.exception_occured.emit(str(exc_value))


def get_filled_registry():
    registry = DataModelRegistry()

    for model in get_ufo_model_classes():
        category = 'Processing'
        if model.num_ports['input'] == 0:
            category = 'Input'
        if model.num_ports['output'] == 0:
            category = 'Output'
        registry.register_model(model, category=category, scrollable=True)
    registry.register_model(UfoGeneralBackprojectModel, category='Processing')
    registry.register_model(UfoOpenCLModel, category='Processing')
    registry.register_model(UfoRetrievePhaseModel, category='Processing')
    registry.register_model(UfoMemoryOutModel, category='Data')
    registry.register_model(ImageViewerModel, category='Output')
    registry.register_model(UfoWriteModel, category='Output')
    registry.register_model(UfoReadModel, category='Input')
    for models in get_composite_model_classes():
        for model in models:
            if model.name not in registry.registered_model_creators():
                registry.register_model(model, category='Composite', registry=registry)

    return registry


def main():
    app = QApplication(sys.argv)
    scene = UfoScene(registry=get_filled_registry())
    main_window = ApplicationWindow(scene)

    # Exception interception
    exception_handler = GlobalExceptionHandler()
    exception_handler.exception_occured.connect(main_window.on_exception_occured)
    # Do not use threading.excepthook because it needs at least python 3.8., i.e. all exceptions in
    # threads have to be handled properly (logged, signal emitted so that a message can be displayed
    # in the main thread to the user, see tofu.flow.execution for example).
    sys.excepthook = exception_handler.excepthook

    main_window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
