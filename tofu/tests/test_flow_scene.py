import pytest
from PyQt5.QtCore import QModelIndex
from PyQt5.QtWidgets import QInputDialog
from qtpynodeeditor import FlowView
from tofu.flow.models import BaseCompositeModel, UfoModelError, UfoReadModel
from tofu.flow.util import FlowError, MODEL_ROLE, NODE_ROLE, PROPERTY_ROLE
from tofu.tests.flow_util import add_nodes_to_scene


class TestScene:
    def test_create_node(self, qtbot, scene):
        def check_node(node, gt_caption):
            # Node must be in the scene
            assert node in scene.nodes.values()
            # Caption must be unique
            assert node.model.caption == gt_caption
            # Node must be in the nodes model
            item = scene.node_model.findItems(node.model.caption)[0]
            assert item.data(role=MODEL_ROLE) == node.model

        nodes = add_nodes_to_scene(scene, model_names=['read', 'read'])
        for (node, gt_caption) in zip(nodes, ['Read', 'Read 2']):
            check_node(node, gt_caption)

        # Property links must be set up by composites
        def check_link(model, prop_name):
            assert scene.property_links_model.find_items((model, prop_name),
                                                         (MODEL_ROLE, PROPERTY_ROLE))

        scene.clear_scene()
        node = add_nodes_to_scene(scene, model_names=['CFlatFieldCorrect'])[0]
        for link in node.model._links:
            model_name, prop_name = link[0]
            other_name, other_prop_name = link[1]
            model = node.model[model_name]
            other = node.model[other_name]
            model[prop_name] = 0
            qtbot.addWidget(model.embedded_widget())
            qtbot.addWidget(other.embedded_widget())
            qtbot.keyClick(model._view._properties[prop_name].view_item.widget, '1')

            # Other model's property has to be updated if the property links have been set up
            # correctly
            assert node.model[other_name][other_prop_name] == node.model[model_name][prop_name]

    def test_setstate(self, qtbot, scene):
        # Make sure there are some links by adding FFC
        nodes = add_nodes_to_scene(scene, model_names=['CFlatFieldCorrect', 'average'])

        # Create a connection
        scene.create_connection(nodes[0]['output'][0], nodes[1]['input'][0])
        state = scene.__getstate__()
        scene.clear_scene()
        scene.__setstate__(state)
        assert scene.__getstate__() == state

    def test_getstate(self, qtbot, scene):
        # Make sure there are some links by adding FFC
        nodes = add_nodes_to_scene(scene, model_names=['CFlatFieldCorrect', 'average'])

        # Create a connection
        scene.create_connection(nodes[0]['output'][0], nodes[1]['input'][0])
        state = scene.__getstate__()

        # Nodes
        ids = [record['id'] for record in state['nodes']]
        assert nodes[0].id in ids
        assert nodes[1].id in ids

        # Connections
        assert len(state['connections']) == 1
        conn = state['connections'][0]
        assert conn['in_id'] == nodes[1].id
        assert conn['out_id'] == nodes[0].id

        # Property links
        assert state['property-links'] == scene.property_links_model.save()

    def test_restore_node(self, qtbot, monkeypatch, scene):
        add_nodes_to_scene(scene)
        old_node = list(scene.nodes.values())[0]
        state = old_node.__getstate__()
        scene.remove_node(old_node)
        new_node = scene.restore_node(state)
        # Don't test the nodes themselves because the models won't match
        assert old_node.id == new_node.id

        # num-inputs
        monkeypatch.setattr(QInputDialog, 'getInt', lambda *args, **kwargs: (2, True))
        node = add_nodes_to_scene(scene, model_names=['retrieve_phase'])[0]
        state = node.__getstate__()
        scene.remove_node(node)
        new_node = scene.restore_node(state)
        assert new_node.model.num_ports['input'] == 2

    def test_remove_node(self, monkeypatch, qtbot, scene, nodes):
        def cleanup():
            self.cleanup_called = True

        node = add_nodes_to_scene(scene)[0]
        self.cleanup_called = False
        node.model.cleanup = cleanup
        scene.property_links_model.add_item(node, node.model, node.model.properties[0],
                                            0, 0, QModelIndex())
        scene.remove_node(list(scene.nodes.values())[0])
        # Scene, node model and property links model must be empty
        assert len(scene.nodes) == 0
        assert scene.node_model.rowCount() == 0
        assert scene.property_links_model.rowCount() == 0
        assert self.cleanup_called

        # Composite removal
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        nodes = add_nodes_to_scene(scene, model_names=['pad', 'crop'])
        for node in nodes:
            node.graphics_object.setSelected(True)
        node = scene.create_composite()
        state = node.__getstate__()
        scene.remove_node(node)
        # _composite_nodes must be updated
        assert scene._composite_nodes == {}

        # Simulate non-interactive composite creation, i.e. not combining existing nodes into a
        # composite node. When removing such node, _composite_nodes must not raise a KeyError
        node = scene.restore_node(state)
        scene.remove_node(node)

    def test_is_selected_one_composite(self, qtbot, scene, monkeypatch):
        # Circumvent the input dialog
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        nodes = add_nodes_to_scene(scene, model_names=['read', 'read'])
        for node in nodes:
            node.graphics_object.setSelected(True)

        # Simple nodes
        assert not scene.is_selected_one_composite()
        node = scene.create_composite()

        # Composite
        assert scene.is_selected_one_composite()
        node.graphics_object.setSelected(False)

        # Nothing selected
        assert not scene.is_selected_one_composite()

        # Composite and other selected
        add_nodes_to_scene(scene, ['null'])
        for node in scene.nodes.values():
            node.graphics_object.setSelected(True)
        assert not scene.is_selected_one_composite()

    def test_skip_nodes(self, qtbot, scene):
        nodes = add_nodes_to_scene(scene, model_names=['read', 'pad', 'crop', 'null'])
        read, pad, crop, null = nodes
        scene.create_connection(read['output'][0], pad['input'][0])
        scene.create_connection(pad['output'][0], crop['input'][0])
        scene.create_connection(crop['output'][0], null['input'][0])
        read.graphics_object.setSelected(True)

        # Only fully connected nodes can be disabled
        with pytest.raises(FlowError):
            scene.skip_nodes()
        read.graphics_object.setSelected(False)
        null.graphics_object.setSelected(True)
        with pytest.raises(FlowError):
            scene.skip_nodes()
        null.graphics_object.setSelected(False)

        pad.graphics_object.setSelected(True)
        scene.skip_nodes()
        assert pad.model.skip
        scene.skip_nodes()
        assert not pad.model.skip

    # Deprecation warning coming from imageio
    @pytest.mark.filterwarnings('ignore::DeprecationWarning')
    def test_auto_fill(self, qtbot, scene):
        add_nodes_to_scene(scene)
        with pytest.raises(UfoModelError):
            scene.auto_fill()

    def test_copy_node(self, qtbot, scene):
        nodes = add_nodes_to_scene(scene, model_names=['read', 'null'])
        scene.create_connection(nodes[0]['output'][0], nodes[1]['input'][0])
        for node in nodes:
            node.graphics_object.setSelected(True)

        scene.copy_nodes()
        assert len(scene.nodes) == 4

        # Choose the newly created connections
        if scene.connections[0].valid_ports['input'].node in nodes:
            ports = scene.connections[1].valid_ports
        else:
            ports = scene.connections[0].valid_ports

        # The fact that the connections are there means the nodes are there as well, so we don't
        # need to test that
        assert ports['input'].node.model.name == 'null'
        assert ports['output'].node.model.name == 'read'

    def test_create_composite(self, monkeypatch, qtbot, scene):
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        plm = scene.property_links_model
        nodes = add_nodes_to_scene(scene, model_names=['read', 'read'])
        plm.add_item(nodes[0], nodes[0].model, nodes[0].model.properties[0],
                     -1, -1, QModelIndex())
        for (i, node) in enumerate(nodes):
            node.graphics_object.setSelected(True)
        node = scene.create_composite()
        assert node.model._links == [[[nodes[0].model.caption, nodes[0].model.properties[0]]]]

        with pytest.raises(FlowError):
            # Can't create a composite with the same name
            scene.create_composite()

        assert len(scene.nodes) == 1
        assert list(scene.nodes.values())[0] == node
        assert isinstance(node.model, BaseCompositeModel)
        assert nodes[0] not in scene.nodes.values()
        assert nodes[1] not in scene.nodes.values()
        # Property links model
        assert plm.item(0, 0).data(role=NODE_ROLE) == node

        # Simulate non-interactive composite creation, i.e. not combining existing nodes into a
        # composite node. In this case it can't be possible to create a new composite node with the
        # same name as has already been registered.
        state = node.__getstate__()
        scene.remove_node(node)
        node = scene.restore_node(state)
        node.graphics_object.setSelected(True)
        with pytest.raises(FlowError):
            scene.create_composite()

        # Add outer composite with a composite and another simple model inside and set the property
        # links between the inner composite and inner simple. They must be present in the newly
        # craeted outer composite.
        average = add_nodes_to_scene(scene, model_names=['average'])[0]
        average.graphics_object.setSelected(True)
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('outer', True))
        plm.add_item(node, node.model['Read'], 'number', 0, 0)
        plm.add_item(node, node.model['Read 2'], 'number', 0, 1)
        plm.add_item(average, average.model, 'number', 0, 2)
        outer = scene.create_composite()
        assert len(outer.model._links) == 1
        row = outer.model._links[0]
        assert [node.model.caption, node.model['Read'].caption, 'number'] in row
        assert [node.model.caption, node.model['Read 2'].caption, 'number'] in row
        assert [average.model.caption, 'number'] in row
        assert [node.model.caption, node.model['Read'].caption, 'height'] not in row

    def test_on_node_double_clicked(self, qtbot, scene, monkeypatch):
        def double_clicked(*args):
            self.did_click = True

        self.did_click = False
        monkeypatch.setattr(UfoReadModel, "double_clicked", double_clicked)
        node = add_nodes_to_scene(scene)[0]
        # We need a view for double clicks
        _ = FlowView(scene)
        scene.on_node_double_clicked(node)

        assert self.did_click

    def test_expand_composite(self, qtbot, scene, monkeypatch):
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        plm = scene.property_links_model
        nodes = add_nodes_to_scene(scene, model_names=['read', 'null'])
        name_to_caption = {'read': 'Read', 'null': 'Null'}
        for node in nodes:
            node.graphics_object.setSelected(True)
        node = scene.create_composite()
        path = node.model.get_leaf_paths()[0]
        plm.add_item(node, path[-1], path[-1].properties[0], -1, -1, QModelIndex())
        scene.expand_composite(node)
        assert plm.item(0, 0).data(role=MODEL_ROLE).name == path[-1].name
        assert plm.item(0, 0).data(role=NODE_ROLE) in [node for node in scene.selected_nodes()]

        # Captions are the same
        for node in scene.nodes.values():
            assert node.model.caption == name_to_caption[node.model.name]

        # New caption if there is a node with the original one
        # Selection stays, just re-use the expanded nodes
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm_2', True))
        node = scene.create_composite()
        other_read_node = add_nodes_to_scene(scene, model_names=['read'])[0]
        scene.expand_composite(node)
        for node in scene.nodes.values():
            if node.model.name == 'read':
                if node == other_read_node:
                    assert node.model.caption == 'Read'
                else:
                    assert node.model.caption == 'Read 2'

    def test_is_fully_connected(self, qtbot, scene):
        nodes = add_nodes_to_scene(scene, model_names=['read', 'pad', 'crop', 'null'])
        read, pad, crop, null = nodes
        scene.create_connection(read['output'][0], pad['input'][0])
        scene.create_connection(pad['output'][0], crop['input'][0])
        scene.create_connection(crop['output'][0], null['input'][0])
        assert scene.is_fully_connected()
        scene.remove_node(read)
        assert not scene.is_fully_connected()

    def test_are_all_ufo_tasks(self, qtbot, scene):
        add_nodes_to_scene(scene, model_names=['read', 'pad', 'crop', 'null'])
        assert scene.are_all_ufo_tasks()
        scene.create_node(scene.registry.create('memory_out'))
        assert not scene.are_all_ufo_tasks()

    def test_get_simple_node_graphs(self, qtbot, scene, monkeypatch):
        def connect(read, pad, crop, null):
            scene.create_connection(read['output'][0], pad['input'][0])
            scene.create_connection(pad['output'][0], crop['input'][0])
            scene.create_connection(crop['output'][0], null['input'][0])

        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
        nodes = add_nodes_to_scene(scene, model_names=2 * ['read', 'pad', 'crop', 'null'])
        read, pad, crop, null = nodes[:4]
        read_2, pad_2, crop_2, null_2 = nodes[4:]
        connect(read, pad, crop, null)
        connect(read_2, pad_2, crop_2, null_2)
        connections = [('Read', 'Pad'), ('Pad', 'Crop'), ('Crop', 'Null'),
                       ('Read 2', 'Pad 2'), ('Pad 2', 'Crop 2'), ('Crop 2', 'Null 2')]

        graphs = scene.get_simple_node_graphs()
        assert len(graphs) == 2
        num_visited = 0
        for graph in graphs:
            for (src, dst, index) in graph.edges:
                assert (src.caption, dst.caption) in connections
                num_visited += 1
        assert num_visited == len(connections)

        # Create first composite
        for node in nodes:
            if node.model.name in ['pad', 'crop']:
                node.graphics_object.setSelected(True)
        scene.create_composite()

        # Create a second composite which will cause the scene to have multiple edges between two
        # nodes (the first composite's outputs and second's inputs)
        scene.clearSelection()
        monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm_2', True))
        null.graphics_object.setSelected(True)
        null_2.graphics_object.setSelected(True)
        scene.create_composite()

        # Composite must not affect simple graphs, especially the multiple edges cannot be present
        # anymore
        graphs = scene.get_simple_node_graphs()
        assert len(graphs) == 2
        num_visited = 0
        for graph in graphs:
            for (src, dst, index) in graph.edges:
                assert (src.caption, dst.caption) in connections
                num_visited += 1
        assert num_visited == len(connections)

        add_nodes_to_scene(scene)
        assert len(scene.get_simple_node_graphs()) == 3

        # Test disabling nodes
        scene.clear_scene()
        nodes = add_nodes_to_scene(scene, model_names=['read', 'pad', 'crop', 'null'])
        read, pad, crop, null = nodes
        connect(read, pad, crop, null)
        # Disable padding, the generated flow must be read -> crop -> null
        pad.graphics_object.setSelected(True)
        scene.skip_nodes()
        graph = scene.get_simple_node_graphs()[0]
        assert len(graph.edges) == 2
        edges = list(graph.edges)
        src, dst = edges[0][:-1]
        assert dst == crop.model
        src, dst = edges[1][:-1]
        assert src == crop.model
        assert dst == null.model

    def test_set_enabled(self, qtbot, scene):
        def check(enabled):
            assert scene.allow_node_creation == enabled
            assert scene.allow_node_deletion == enabled

            for node in scene.nodes.values():
                assert node._graphics_obj.isEnabled() == enabled
            for conn in scene.connections:
                assert conn._graphics_object.isEnabled() == enabled

        nodes = add_nodes_to_scene(scene, model_names=['CFlatFieldCorrect', 'average'])
        nodes[0].graphics_object.setSelected(True)

        # Create a connection
        scene.create_connection(nodes[0]['output'][0], nodes[1]['input'][0])
        scene.set_enabled(False)
        check(False)
        scene.set_enabled(True)
        check(True)
        assert nodes[0].graphics_object.isSelected()
