import glob
import os
import pathlib
import pkg_resources
import pytest
import sys
import xdg.BaseDirectory
from PyQt5.QtWidgets import QFileDialog, QInputDialog, QMessageBox
from tofu.flow.execution import UfoExecutor
from tofu.flow.main import ApplicationWindow, get_filled_registry, GlobalExceptionHandler
from tofu.flow.scene import UfoScene
from tofu.flow.util import FlowError
from tofu.tests.flow_util import add_nodes_to_scene


@pytest.fixture(scope='function')
def app_window(qtbot, scene):
    window = ApplicationWindow(scene)
    qtbot.addWidget(window)

    return window


class TestApplicationWindow:
    def test_init(self, qtbot, app_window):
        assert app_window.ufo_scene
        assert app_window.executor

    def test_on_save(self, monkeypatch, app_window):
        def getSaveFileNameDefault(inst, header, path, fltr):
            return (os.path.join(path, 'flow.flow'), True)

        def getSaveFileName(inst, header, path, fltr):
            return (os.path.join('foo', 'bar', 'flow.flow'), True)

        # Don't actually write to disk
        monkeypatch.setattr(UfoScene, "save", lambda *args: None)

        # Default directory
        monkeypatch.setattr(QFileDialog, "getSaveFileName", getSaveFileNameDefault)
        app_window.on_save()
        directory = xdg.BaseDirectory.save_data_path('tofu', 'flows')
        assert os.path.exists(directory)
        assert app_window.last_dirs['scene'] == directory

        # When user picks a different directory it must be remembered
        monkeypatch.setattr(QFileDialog, "getSaveFileName", getSaveFileName)
        app_window.on_save()
        assert app_window.last_dirs['scene'] == os.path.join('foo', 'bar')

        # And used the next time
        monkeypatch.setattr(QFileDialog, "getSaveFileName", getSaveFileNameDefault)
        app_window.on_save()
        assert app_window.last_dirs['scene'] == os.path.join('foo', 'bar')

    def test_on_open(self, monkeypatch, app_window):
        def getOpenFileNameDefault(inst, header, path, fltr):
            return (os.path.join(path, 'flow.flow'), True)

        def getOpenFileName(inst, header, path, fltr):
            return (os.path.join('foo', 'bar', 'flow.flow'), True)

        # Don't actually read from disk
        monkeypatch.setattr(UfoScene, "load", lambda *args: None)

        # Default directory
        monkeypatch.setattr(QFileDialog, "getOpenFileName", getOpenFileNameDefault)
        app_window.on_open()
        directory = xdg.BaseDirectory.save_data_path('tofu', 'flows')
        if not os.path.exists(directory):
            directory = pathlib.Path.home()
        assert app_window.last_dirs['scene'] == directory

        # When user picks a different directory it must be remembered
        monkeypatch.setattr(QFileDialog, "getOpenFileName", getOpenFileName)
        app_window.on_open()
        assert app_window.last_dirs['scene'] == os.path.join('foo', 'bar')

        # And used the next time
        monkeypatch.setattr(QFileDialog, "getOpenFileName", getOpenFileNameDefault)
        app_window.on_open()
        assert app_window.last_dirs['scene'] == os.path.join('foo', 'bar')

    def test_on_exception_occured(self, qtbot, monkeypatch, app_window):
        def exec_(inst):
            self.message_shown = True

        self.message_shown = False
        monkeypatch.setattr(QMessageBox, "exec_", exec_)
        app_window.on_exception_occured('foo')

        assert self.message_shown

    def test_on_number_of_inputs_changed(self, qtbot, app_window):
        app_window.on_number_of_inputs_changed(123)
        assert app_window.progress_bar.maximum() == 123

    def test_on_processed(self, qtbot, app_window):
        app_window.on_number_of_inputs_changed(100)
        app_window.on_processed(10)
        assert app_window.progress_bar.value() == 11

    def test_on_nodes_duplicated(self, qtbot, app_window):
        node = add_nodes_to_scene(app_window.ufo_scene)[0]
        node.graphics_object.setSelected(True)
        app_window.ufo_scene.copy_nodes()

        nodes = list(app_window.ufo_scene.nodes.values())
        assert nodes[0].graphics_object.pos().y() != nodes[1].graphics_object.pos().y()

    def test_on_selection_menu_about_to_show(self, qtbot, monkeypatch, app_window):
        # Nothing selected
        app_window.on_selection_menu_about_to_show()
        assert not app_window.edit_composite_action.isEnabled()
        assert not app_window.expand_composite_action.isEnabled()
        assert not app_window.export_composite_action.isEnabled()

        # Only non-composite nodes
        nodes = add_nodes_to_scene(app_window.ufo_scene, model_names=['read', 'average', 'null'])

        app_window.on_selection_menu_about_to_show()
        assert not app_window.edit_composite_action.isEnabled()
        assert not app_window.expand_composite_action.isEnabled()
        assert not app_window.export_composite_action.isEnabled()

        # One composite
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        for i in range(2):
            nodes[i].graphics_object.setSelected(True)
        app_window.ufo_scene.create_composite()

        app_window.on_selection_menu_about_to_show()
        assert app_window.edit_composite_action.isEnabled()
        assert app_window.expand_composite_action.isEnabled()
        assert app_window.export_composite_action.isEnabled()

        # More composites
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm_2', True))
        app_window.ufo_scene.clearSelection()
        nodes[-1].graphics_object.setSelected(True)
        app_window.ufo_scene.create_composite()
        for node in app_window.ufo_scene.nodes.values():
            node.graphics_object.setSelected(True)

        app_window.on_selection_menu_about_to_show()
        assert not app_window.edit_composite_action.isEnabled()
        assert app_window.expand_composite_action.isEnabled()
        assert not app_window.export_composite_action.isEnabled()

    def test_skip_action(self, qtbot, app_window):
        # No nodes selected, menu item must be disabled
        app_window.on_selection_menu_about_to_show()
        assert not app_window.skip_action.isEnabled()

        # Add some nodes, conect them and disable one
        nodes = add_nodes_to_scene(app_window.ufo_scene, model_names=['read', 'average', 'null'])
        app_window.ufo_scene.create_connection(nodes[0]['output'][0], nodes[1]['input'][0])
        app_window.ufo_scene.create_connection(nodes[1]['output'][0], nodes[2]['input'][0])
        average = nodes[1]
        average.graphics_object.setSelected(True)
        app_window.on_selection_menu_about_to_show()
        # Nodes selected, menu item must be enabled
        assert app_window.skip_action.isEnabled()

    def test_on_edit_composite(self, qtbot, scene_with_composite, app_window):
        app_window.ufo_scene = scene_with_composite
        node = add_nodes_to_scene(app_window.ufo_scene, model_names=['cpm'])[0]
        node.graphics_object.setSelected(True)
        app_window.on_edit_composite()
        qtbot.addWidget(node.model._other_view)

        assert node.model.is_editing

    def test_on_create_composite(self, qtbot, monkeypatch, scene_with_composite, app_window):
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        nodes = add_nodes_to_scene(app_window.ufo_scene, model_names=['read', 'pad'])

        # Link a model to the slider
        model = nodes[0].model
        view_item = model._view._properties['number'].view_item
        app_window.on_item_focus_in(view_item, 'number', 'Read', model)

        # Create a composite
        for node in app_window.ufo_scene.nodes.values():
            node.graphics_object.setSelected(True)
        app_window.on_create_composite()
        composite = list(app_window.ufo_scene.nodes.values())[0].model
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model == composite.get_model_from_path(['Read'])
        assert prop_name == 'number'

    def test_on_item_focus_in(self, qtbot, app_window, scene_with_composite):
        read, pad = add_nodes_to_scene(app_window.ufo_scene, model_names=['read', 'pad'])

        # Simple node
        model = read.model
        view_item = model._view._properties['number'].view_item
        app_window.on_item_focus_in(view_item, 'number', model.caption, model)
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model == model
        assert prop_name == 'number'

        app_window.fix_run_slider.setChecked(False)
        model = pad.model
        view_item = model._view._properties['y'].view_item
        app_window.on_item_focus_in(view_item, 'y', model.caption, model)
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model == model
        assert prop_name == 'y'

        # Focus gets another widget, but the run slider must be linked to the one focused before the
        # fix option is checked
        app_window.fix_run_slider.setChecked(True)
        model = read.model
        view_item = model._view._properties['number'].view_item
        app_window.on_item_focus_in(view_item, 'number', model.caption, model)
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model == pad.model
        assert prop_name == 'y'

    def test_on_node_deleted(self, qtbot, monkeypatch, app_window, scene_with_composite):
        app_window.ufo_scene = scene_with_composite
        cpm, cpm_2, read = add_nodes_to_scene(app_window.ufo_scene,
                                              model_names=['cpm', 'cpm', 'read'])

        # Simple node
        model = read.model
        view_item = model._view._properties['number'].view_item
        app_window.on_item_focus_in(view_item, 'number', model.caption, model)
        # remove in the scene doesn't seem to emit the signal, so use the window
        app_window.on_node_deleted(read)
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model is None
        assert prop_name is None

        # Composite node
        model = cpm.model.get_model_from_path(['Read'])
        view_item = model._view._properties['number'].view_item
        app_window.on_item_focus_in(view_item, 'number', 'cpm->Read', model)
        # remove in the scene doesn't seem to emit the signal, so use the window
        app_window.on_node_deleted(cpm)
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model is None
        assert prop_name is None

        # Nested composite node
        cpm_2.graphics_object.setSelected(True)
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('parent', True))
        app_window.on_create_composite()
        node = app_window.ufo_scene.selected_nodes()[0]
        model = node.model.get_model_from_path(['cpm 2', 'Read'])
        view_item = model._view._properties['number'].view_item
        app_window.on_item_focus_in(view_item, 'number', 'parent->cpm 2->Read', model)
        # remove in the scene doesn't seem to emit the signal, so use the window
        app_window.on_node_deleted(node)
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model is None
        assert prop_name is None

    def test_on_expand_composite(self, qtbot, scene_with_composite, app_window):
        app_window.ufo_scene = scene_with_composite
        nodes = add_nodes_to_scene(app_window.ufo_scene, model_names=['cpm', 'cpm'])

        for node in nodes:
            node.graphics_object.setSelected(True)

        app_window.on_expand_composite()
        captions = {node.model.caption for node in app_window.ufo_scene.nodes.values()}
        assert captions == {'Read 2', 'Pad 2', 'Read', 'Pad'}

        # Run slider
        # Create yet another composite and select a reader inside
        node = add_nodes_to_scene(app_window.ufo_scene, model_names=['cpm'])[0]
        model = node.model.get_model_from_path(['Read'])
        view_item = model._view._properties['number'].view_item
        app_window.on_item_focus_in(view_item, 'number', 'cpm->Read', model)

        node.graphics_object.setSelected(True)
        app_window.on_expand_composite()

        # After expansion, the reader's index will be 3
        slider_model, prop_name = app_window.run_slider_key
        assert slider_model.caption == 'Read 3'
        assert prop_name == 'number'

    def test_on_import_composites(self, qtbot, monkeypatch, app_window):
        tests_directory = pkg_resources.resource_filename(__name__, 'composites')

        def getOpenFileNamesDefault(inst, header, path, fltr):
            # Let's pretend there are files
            file_names = [os.path.join(path, 'foo.cm')]

            return (file_names, True)

        def getOpenFileNames(inst, header, path, fltr):
            file_names = sorted(glob.glob(os.path.join(tests_directory, '*.cm')))

            return (file_names, True)

        def exec_(inst):
            self.message_shown = True

        monkeypatch.setattr(QMessageBox, "exec_", exec_)

        # Nothing opened, nothing happens
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([], True))
        app_window.on_import_composites()

        # Default directory
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", getOpenFileNamesDefault)
        directory = xdg.BaseDirectory.save_data_path('tofu', 'flows', 'composites')
        if not os.path.exists(directory):
            directory = pathlib.Path.home()
        try:
            app_window.on_import_composites()
        except FileNotFoundError:
            # We don't care if there are files, just the last_dirs setting is important
            pass
        assert app_window.last_dirs['composite'] == directory

        # It's possible to open more than one at a time
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", getOpenFileNames)
        app_window.on_import_composites()
        assert 'cmp' in app_window.ufo_scene.registry.registered_model_creators()
        assert 'cmp_2' in app_window.ufo_scene.registry.registered_model_creators()
        # When user picks a different directory it must be remembered
        assert app_window.last_dirs['composite'] == tests_directory

        # And used the next time
        self.message_shown = False
        app_window.on_import_composites()
        assert app_window.last_dirs['composite'] == tests_directory
        # Message about overwriting models must be shown
        assert self.message_shown

    def test_on_export_composite(self, qtbot, monkeypatch, scene_with_composite, app_window):
        tests_directory = pkg_resources.resource_filename(__name__, 'composites')

        def getSaveFileNameDefault(inst, header, path, fltr):
            return (os.path.join(path, self.file_name), True)

        def getSaveFileName(inst, header, path, fltr):
            return (os.path.join(tests_directory, self.file_name), True)

        def export_composite(inst, node, file_name):
            self.final_file_name = file_name

        # Nothing selected, must silently pass
        app_window.on_export_composite()

        # Make a composite node
        app_window.ufo_scene = scene_with_composite
        node = add_nodes_to_scene(app_window.ufo_scene, model_names=['cpm'])[0]
        node.graphics_object.setSelected(True)
        monkeypatch.setattr(ApplicationWindow, "export_composite", export_composite)

        # Default directory
        monkeypatch.setattr(QFileDialog, "getSaveFileName", getSaveFileNameDefault)
        self.file_name = 'composite'
        directory = xdg.BaseDirectory.save_data_path('tofu', 'flows', 'composites')
        app_window.on_export_composite()
        assert self.final_file_name.endswith('.cm') and not self.final_file_name.endswith('.cm.cm')
        assert os.path.exists(directory)
        assert app_window.last_dirs['composite'] == directory

        # When user picks a different directory it must be remembered
        monkeypatch.setattr(QFileDialog, "getSaveFileName", getSaveFileName)
        app_window.on_export_composite()
        assert self.final_file_name.endswith('.cm') and not self.final_file_name.endswith('.cm.cm')
        assert app_window.last_dirs['composite'] == tests_directory

        # And used the next time
        monkeypatch.setattr(QFileDialog, "getSaveFileName", getSaveFileNameDefault)
        app_window.on_export_composite()
        assert app_window.last_dirs['composite'] == tests_directory

        # .cm must not be added if it's present in the file name
        self.file_name = 'composite.cm'
        app_window.on_export_composite()
        assert self.final_file_name.endswith('.cm') and not self.final_file_name.endswith('.cm.cm')

    def test_on_reset_view(self, qtbot, app_window):
        app_window.flow_view.scale_up()
        app_window.on_reset_view()
        assert app_window.flow_view.transform().m11() == pytest.approx(1)
        assert app_window.flow_view.transform().m22() == pytest.approx(1)

    def test_on_property_links_action(self, qtbot, app_window):
        qtbot.addWidget(app_window.property_links_widget)
        app_window.property_links_widget.show()
        assert app_window.property_links_widget.isVisible()

    def test_on_run(self, qtbot, monkeypatch, app_window):
        def executor_run(inst, graph):
            self.ran = True

        monkeypatch.setattr(UfoExecutor, "run", executor_run)
        nodes = add_nodes_to_scene(app_window.ufo_scene,
                                   model_names=['read', 'read', 'flat_field_correct', 'null'])
        i_0, i_1, ffc, null = nodes
        # No connections -> many graphs
        with pytest.raises(FlowError):
            app_window.on_run()
        assert app_window.run_action.isEnabled()

        app_window.ufo_scene.create_connection(i_0['output'][0], ffc['input'][0])
        app_window.ufo_scene.create_connection(i_1['output'][0], ffc['input'][1])
        app_window.ufo_scene.create_connection(ffc['output'][0], null['input'][0])

        # One ffc input is not connected
        with pytest.raises(FlowError):
            app_window.on_run()
        assert app_window.run_action.isEnabled()

        # All connections present -> must run
        i_2 = add_nodes_to_scene(app_window.ufo_scene, model_names=['read'])[0]
        app_window.ufo_scene.create_connection(i_2['output'][0], ffc['input'][2])
        self.ran = False
        app_window.on_run()
        assert self.ran
        assert not app_window.run_action.isEnabled()

    def test_on_save_json(self, qtbot, monkeypatch, app_window):
        import gi
        gi.require_version('Ufo', '0.0')
        from gi.repository import Ufo

        # Don't pop up file dialog
        def getSaveFileName(inst, header, path, fltr):
            return (os.path.join(path, 'flow.json'), True)
        monkeypatch.setattr(QFileDialog, "getSaveFileName", getSaveFileName)

        # Don't actually write to disk
        monkeypatch.setattr(Ufo.TaskGraph, "save_to_json", lambda *args: None)

        # Empty scene
        with pytest.raises(FlowError):
            app_window.on_save_json()

        # Wrong data types
        app_window.ufo_scene.clear_scene()
        read, mem_out, viewer = add_nodes_to_scene(app_window.ufo_scene,
                                                   model_names=['read', 'memory_out',
                                                                'image_viewer'])
        app_window.ufo_scene.create_connection(read['output'][0], mem_out['input'][0])
        app_window.ufo_scene.create_connection(mem_out['output'][0], viewer['input'][0])
        with pytest.raises(FlowError):
            app_window.on_save_json()

        # Not connected
        app_window.ufo_scene.clear_scene()
        read, null = add_nodes_to_scene(app_window.ufo_scene, model_names=['read', 'null'])
        with pytest.raises(FlowError):
            app_window.on_save_json()

        # This must pass
        app_window.ufo_scene.create_connection(read['output'][0], null['input'][0])
        app_window.on_save_json()

    def test_on_execution_finished(self, qtbot, app_window):
        app_window.run_action.setEnabled(False)
        app_window.progress_bar.setMaximum(100)
        app_window.progress_bar.setValue(50)
        app_window.on_execution_finished()

        assert app_window.progress_bar.value() == -1
        assert app_window.run_action.isEnabled()


def test_global_exception_handler(qtbot):

    handler = GlobalExceptionHandler()

    def slot(text):
        handler.called_signal = True

    handler.exception_occured.connect(slot)
    handler.called_signal = False
    try:
        raise FlowError('foo')
    except:
        # Call the hook explicitly, sys.excinfo = ... doesn't seem to have effect
        handler.excepthook(*sys.exc_info())

    assert handler.called_signal


def test_get_filled_registry():
    registry = get_filled_registry()
    assert 'read' in registry.registered_model_creators()
