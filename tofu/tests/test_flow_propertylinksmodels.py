import pytest
from qtpy.QtCore import QByteArray, QMimeData, QModelIndex
from tofu.flow.propertylinksmodels import _get_string_path
from tofu.flow.propertylinkswidget import _encode_mime_data
from tofu.flow.util import MODEL_ROLE, NODE_ROLE, PROPERTY_ROLE
from tofu.tests.flow_util import get_index_from_treemodel, populate_link_model


def setup_silent(link_model, nodes):
    read = nodes['read']
    read_2 = nodes['read_2']
    composite = nodes['cpm']
    orig_key = (read.model, 'number')

    link_model.add_item(read, read.model, 'number', -1, -1)
    link_model.add_silent(composite.model['Read'], 'number', orig_key[0], orig_key[1])
    link_model.add_silent(read_2.model, 'height', orig_key[0], orig_key[1])

    # Put to 0 to make sure we are not lucky when checking if the links work
    composite.model['Read']['number'] = 0
    read_2.model['height'] = 0

    return orig_key


class TestNodeTreeModel:
    def test_add_node(self, qtbot, node_model, nodes):
        # Unsupported model type not added
        node_model.add_node(nodes['image_viewer'])
        assert node_model.rowCount() == 0
        # Supported model type (composite is handled in test_add_node)
        node_model.add_node(nodes['read'])
        assert node_model.rowCount() == 1

        # Composite
        node_model.add_node(nodes['cpm'])
        item = node_model.findItems('cpm')[0]
        # Model contains composite node
        assert item.data(role=NODE_ROLE) == nodes['cpm']
        # and it's children
        assert item.child(0).data(role=MODEL_ROLE) == nodes['cpm'].model['Pad']
        assert item.child(1).data(role=MODEL_ROLE) == nodes['cpm'].model['Read']
        # and their properties
        assert item.child(0).child(0).text() == sorted(nodes['cpm'].model['Pad'])[0]

    def test_remove_node(self, qtbot, node_model, nodes):
        node_model.add_node(nodes['cpm'])
        assert node_model.rowCount() == 1
        node_model.remove_node(nodes['cpm'])
        assert node_model.rowCount() == 0

    def test_set_nodes(self, qtbot, node_model, nodes):
        names = ['cpm', 'read']
        subset = [nodes[key] for key in names]
        node_model.set_nodes(subset)

        for (i, key) in enumerate(names):
            assert node_model.item(i).data(role=NODE_ROLE) == nodes[key]

    def test_clear(self, qtbot, node_model, nodes):
        node_model.set_nodes(nodes.values())
        assert node_model.rowCount() > 0
        assert node_model.columnCount() > 0
        node_model.clear()
        assert node_model.rowCount() == 0
        assert node_model.columnCount() == 0


class TestPropertyLinksModel:
    def test_add_item(self, qtbot, link_model, nodes):
        read = nodes['read']
        composite = nodes['cpm']
        composite.model.property_links_model = link_model
        # Put to 0 to make sure we are not lucky below when checking if the links work
        composite.model['Read']['number'] = 0

        # Items must be added
        link_model.add_item(read, read.model, 'number', -1, -1)
        item = link_model.item(0, 0)
        assert item.data(role=NODE_ROLE) == read
        assert item.data(role=MODEL_ROLE) == read.model
        assert item.data(role=PROPERTY_ROLE) == 'number'

        link_model.add_item(composite, composite.model['Read'], 'number', 0, -1)
        item = link_model.item(0, 1)
        assert item.data(role=NODE_ROLE) == composite
        assert item.data(role=MODEL_ROLE) == composite.model['Read']
        assert item.data(role=PROPERTY_ROLE) == 'number'

        # Can't add one item twice
        with pytest.raises(ValueError):
            link_model.add_item(read, read.model, 'number', -1, -1)

        # Properties must be linked
        read.model['number'] = 100
        read.model.property_changed.emit(read.model, 'number', read.model['number'])
        assert composite.model['Read']['number'] == read.model['number']

        # When composite is being added, make sure the slave links are set up
        link_model.remove_item(link_model.find_items([composite], [NODE_ROLE])[0])
        composite.model.edit_in_window()
        qtbot.addWidget(composite.model._other_view)
        link_model.add_item(composite, composite.model['Read'], 'number', 0, -1)
        key = (composite.model._window_nodes['Read'].model, 'number')
        root_key = (composite.model['Read'], 'number')
        assert link_model._slaves[root_key] == [key]
        assert link_model._silent[key] == root_key

    def test_remove_item(self, qtbot, link_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        composite = nodes['cpm']

        link_model.add_item(read, read.model, 'number', -1, -1)
        link_model.add_item(read_2, read_2.model, 'number', 0, -1)
        link_model.add_silent(composite.model['Read'], 'number', read.model, 'number')

        # Properties must be connected at first
        read.model['number'] = 100
        read.model.property_changed.emit(read.model, 'number', read.model['number'])
        assert read_2.model['number'] == read.model['number']

        link_model.remove_item(link_model.indexFromItem(link_model.item(0, 0)))
        assert link_model.item(0, 0) is None
        assert link_model._silent == {}
        assert link_model._slaves == {}

        # Properties must be disconnected after removal
        read.model['number'] = 0
        read.model.property_changed.emit(read.model, 'number', read.model['number'])
        # read_2 still at the old 100
        assert read_2.model['number'] == 100

    def test_contains(self, qtbot, link_model, nodes):
        composite = nodes['cpm']
        link_model.add_item(composite, composite.model['Read'], 'number', 0, -1)
        assert link_model.item(0, 0).text() in link_model
        assert 'foo' not in link_model

    def test_clear(self, qtbot, link_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        composite = nodes['cpm']

        link_model.add_item(read, read.model, 'number', -1, -1)
        link_model.add_item(read_2, read_2.model, 'number', 0, -1)
        link_model.add_silent(composite.model['Read'], 'number', read.model, 'number')
        link_model.clear()
        assert link_model.rowCount() == 0
        assert link_model.columnCount() == 0
        assert link_model._silent == {}
        assert link_model._slaves == {}

    def test_find_items(self, qtbot, link_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        # Empty model
        assert link_model.find_items([read.model], [MODEL_ROLE]) == []
        link_model.add_item(read, read.model, 'number', -1, -1)
        # Not inside
        assert link_model.find_items([read_2.model], [MODEL_ROLE]) == []
        # Inside
        assert (link_model.find_items([read.model], [MODEL_ROLE])[0].data(role=MODEL_ROLE)
                == read.model)

        # Model not inside, property not inside
        assert link_model.find_items((read_2.model, 'height'), (MODEL_ROLE, PROPERTY_ROLE)) == []
        # Model inside, property not inside
        assert link_model.find_items((read.model, 'height'), (MODEL_ROLE, PROPERTY_ROLE)) == []
        # Model not inside, property inside
        assert link_model.find_items((read_2.model, 'number'), (MODEL_ROLE, PROPERTY_ROLE)) == []
        # Model inside, property inside
        item = link_model.find_items((read.model, 'number'), (MODEL_ROLE, PROPERTY_ROLE))[0]
        assert item.data(role=MODEL_ROLE) == read.model
        assert item.data(role=PROPERTY_ROLE) == 'number'

    def test_get_model_links(sef, qtbot, link_model, nodes):
        populate_link_model(link_model, nodes)
        assert link_model.get_model_links(nodes['read_3'].model) == {}
        links = link_model.get_model_links([nodes['read'].model,
                                            nodes['read_2'].model,
                                            nodes['cpm'].model['Read']])
        links = list(links.values())
        # Just one row
        assert len(links) == 1
        # Three items in that row
        assert len(links[0]) == 3
        assert [nodes['read'].model.caption, 'number'] in links[0]
        assert [nodes['read_2'].model.caption, 'height'] in links[0]
        path = nodes['cpm'].model.get_path_from_model(nodes['cpm'].model['Read'])
        str_path = [model.caption for model in path] + ['y']
        assert str_path in links[0]

    def test_get_root_model(self, qtbot, link_model, nodes):
        read = nodes['read']
        composite = nodes['cpm']

        link_model.add_item(read, read.model, 'number', -1, -1)

        # Not inside
        assert link_model.get_root_model(nodes['read_2'].model) is None
        # Directly inside
        assert link_model.get_root_model(read.model) == read.model
        # Indirectly inside via silent
        link_model.add_silent(composite.model['Read'], 'number', read.model, 'number')
        assert link_model.get_root_model(composite.model['Read']) == read.model

    def test_get_model_properties(self, qtbot, link_model, nodes):
        read = nodes['read']
        link_model.add_item(read, read.model, 'number', -1, -1)
        link_model.add_item(read, read.model, 'height', -1, -1)

        # Empty
        assert link_model.get_model_properties(nodes['read_2'].model) == []
        # Multiple
        assert set(link_model.get_model_properties(read.model)) == set(['number', 'height'])

    def test_add_silent(self, qtbot, link_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        composite = nodes['cpm']
        orig_key = setup_silent(link_model, nodes)

        # orig model not inside
        with pytest.raises(ValueError):
            link_model.add_silent(composite.model['Read'], 'height',
                                  nodes['read_3'].model, 'number')
        # source property not inside
        with pytest.raises(ValueError):
            link_model.add_silent(composite.model['Read'], 'height', read.model, 'height')

        # Links inside
        assert len(link_model._slaves[orig_key]) == 2
        key = (composite.model['Read'], 'number')
        assert link_model._silent[key] == orig_key
        assert key in link_model._slaves[orig_key]

        key = (read_2.model, 'height')
        assert link_model._silent[key] == orig_key
        assert key in link_model._slaves[orig_key]

        # Properties conected
        read.model['number'] = 100
        read.model.property_changed.emit(read.model, 'number', read.model['number'])
        assert composite.model['Read']['number'] == read.model['number']
        assert read_2.model['height'] == read.model['number']

    def test_remove_silent(self, qtbot, link_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        composite = nodes['cpm']
        orig_key = setup_silent(link_model, nodes)

        key = (composite.model['Read'], 'number')
        link_model.remove_silent(*key)
        assert key not in link_model._silent

        # Silent link disconected
        read.model['number'] = 100
        read.model.property_changed.emit(read.model, 'number', read.model['number'])
        assert composite.model['Read']['number'] == 0
        assert read_2.model['height'] == read.model['number']

        # No more slaves, remove the original key as well
        key = (nodes['read_2'].model, 'height')
        link_model.remove_silent(*key)
        assert orig_key not in link_model._slaves

    def test_replace_item(self, qtbot, link_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        composite = nodes['cpm']
        orig_key = setup_silent(link_model, nodes)
        replacer = nodes['read_3']

        item = link_model.find_items(orig_key, (MODEL_ROLE, PROPERTY_ROLE))[0]
        (row, column) = item.row(), item.column()
        link_model.replace_item(replacer, replacer.model, orig_key[0])
        new_item = link_model.item(row, column)
        assert new_item.data(role=MODEL_ROLE) == replacer.model

        # Silent links re-connected
        # This must have no effect on silent models
        read.model['number'] = 100
        read.model.property_changed.emit(read.model, 'number', read.model['number'])
        assert composite.model['Read']['number'] == 0
        assert read_2.model['height'] == 0

        # This must change silent models' properties
        replacer.model['number'] = 100
        replacer.model.property_changed.emit(replacer.model, 'number', replacer.model['number'])
        assert composite.model['Read']['number'] == replacer.model['number']
        assert read_2.model['height'] == replacer.model['number']

    def test_on_node_rows_about_to_be_removed(self, qtbot, link_model, node_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        read_3 = nodes['read_3']

        node_model.add_node(read)
        node_model.add_node(read_2)
        node_model.add_node(read_3)
        link_model.add_item(read, read.model, 'number', -1, -1)
        link_model.add_item(read_2, read_2.model, 'number', 0, -1)
        link_model.add_item(read_3, read_3.model, 'number', -1, -1)

        # Remove one
        node_model.removeRow(0)
        assert link_model.find_items([read.model], [MODEL_ROLE]) == []

        # Remove all
        node_model.clear()
        assert link_model.find_items([read_2.model], [MODEL_ROLE]) == []
        assert link_model.find_items([read_3.model], [MODEL_ROLE]) == []

    def test_canDropMimeData(self, qtbot, link_model, node_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        node_model.add_node(read)
        node_model.add_node(read_2)

        # Incompatible QMimeData
        data = QMimeData()
        data.setData('application/x-foobar', QByteArray())
        assert not link_model.canDropMimeData(data, None, -1, -1, QModelIndex())

        # No parent
        index = get_index_from_treemodel(node_model, 0, 'number')
        data = _encode_mime_data(index)
        assert link_model.canDropMimeData(data, None, -1, -1, QModelIndex())
        link_model.add_item(read, read.model, 'number', -1, -1)
        assert not link_model.canDropMimeData(data, None, -1, -1, QModelIndex())

        # On parent
        # Compatible property type
        index = get_index_from_treemodel(node_model, 1, 'number')
        data = _encode_mime_data(index)
        parent = link_model.indexFromItem(link_model.item(0, 0))
        assert link_model.canDropMimeData(data, None, 0, 0, parent)
        # Incompatible property type
        index = get_index_from_treemodel(node_model, 1, 'path')
        data = _encode_mime_data(index)
        parent = link_model.indexFromItem(link_model.item(0, 0))
        assert not link_model.canDropMimeData(data, None, 0, 0, parent)

    def test_dropMimeData(self, qtbot, link_model, node_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        node_model.add_node(read)
        node_model.add_node(read_2)

        # No parent
        index = get_index_from_treemodel(node_model, 0, 'number')
        data = _encode_mime_data(index)
        link_model.dropMimeData(data, None, -1, -1, QModelIndex())
        item = link_model.item(0, 0)
        assert item.data(role=NODE_ROLE) == read
        assert item.data(role=MODEL_ROLE) == read.model
        assert item.data(role=PROPERTY_ROLE) == 'number'

        # On parent
        index = get_index_from_treemodel(node_model, 1, 'number')
        data = _encode_mime_data(index)
        parent = link_model.indexFromItem(link_model.item(0, 0))
        link_model.dropMimeData(data, None, -1, -1, parent)
        item = link_model.item(0, 1)
        assert item.data(role=NODE_ROLE) == read_2
        assert item.data(role=MODEL_ROLE) == read_2.model
        assert item.data(role=PROPERTY_ROLE) == 'number'

    def test_save(self, qtbot, link_model, nodes):
        records = populate_link_model(link_model, nodes)

        for (i, (node_id, str_path)) in enumerate(link_model.save()[0]):
            assert node_id == records[i][0].id
            path = _get_string_path(records[i][0], records[i][1], records[i][2])
            assert str_path == path

    def test_restore(self, qtbot, link_model, nodes):
        records = populate_link_model(link_model, nodes)
        state = link_model.save()
        link_model.clear()

        # Add new item
        read_3 = nodes['read_3']
        link_model.add_item(read_3, read_3.model, 'number', -1, -1)

        link_model.restore(state, {node.id: node for node in nodes.values()})
        assert link_model.columnCount() == 3
        for column in range(link_model.columnCount()):
            item = link_model.item(0, column)
            assert item.data(role=NODE_ROLE) == records[column][0]
            assert item.data(role=MODEL_ROLE) == records[column][1]
            assert item.data(role=PROPERTY_ROLE) == records[column][2]

        # Restore must clear whatever is inside
        assert link_model.find_items([read_3.model], [MODEL_ROLE]) == []

    def test_compact(self, qtbot, link_model, nodes):
        read = nodes['read']
        read_2 = nodes['read_2']
        read_3 = nodes['read_3']
        read_4 = nodes['read_4']

        def populate():
            link_model.add_item(read, read.model, 'number', 0, 0)
            link_model.add_item(read_2, read_2.model, 'number', 0, 1)
            link_model.add_item(read_3, read_3.model, 'number', 1, 0)
            link_model.add_item(read_4, read_4.model, 'number', 1, 1)

        def check(row_count, column_count):
            assert link_model.rowCount() == row_count
            assert link_model.columnCount() == column_count

        populate()
        link_model.remove_item(link_model.indexFromItem(link_model.item(0, 1)))
        link_model.compact()
        check(2, 2)
        link_model.clear()

        # Shift item to the left to an unused cell
        populate()
        link_model.remove_item(link_model.indexFromItem(link_model.item(0, 0)))
        link_model.compact()
        assert link_model.item(0, 0).data(role=NODE_ROLE) == read_2
        check(2, 2)

        # Nothing in the row, remove it
        link_model.remove_item(link_model.indexFromItem(link_model.item(0, 0)))
        link_model.compact()
        check(1, 2)

        # Remove column 0 and shift 1st column to the left
        link_model.clear()
        populate()
        link_model.remove_item(link_model.indexFromItem(link_model.item(0, 0)))
        link_model.remove_item(link_model.indexFromItem(link_model.item(1, 0)))
        link_model.compact()
        assert link_model.item(0, 0).data(role=NODE_ROLE) == read_2
        assert link_model.item(1, 0).data(role=NODE_ROLE) == read_4
        check(2, 1)

    def test_on_property_changed(self, qtbot, link_model, nodes):
        composite = nodes['cpm']
        read = nodes['read']
        read_2 = nodes['read_2']
        read_3 = nodes['read_3']
        read_4 = nodes['read_4']
        # Read 2->height and cpm->Read->number are silent dependend on Read->number
        setup_silent(link_model, nodes)

        # Put every linked property to 0 to make sure we are not lucky when checking if the links
        # work
        read_3.model['number'] = 0
        read_4.model['number'] = 0
        composite.model['Pad']['width'] = 0

        link_model.add_item(read_3, read_3.model, 'number', 0, 1)
        link_model.add_item(read_4, read_4.model, 'number', 1, 0)
        link_model.add_item(composite, composite.model['Pad'], 'width', 1, 1)

        read.model['number'] = 100
        read.model.property_changed.emit(read.model, 'number', read.model['number'])
        # Row 0
        # Direct link
        assert read_3.model['number'] == read.model['number']
        # Silent links
        assert read_2.model['height'] == read.model['number']
        assert composite.model['Read']['number'] == read.model['number']

        # Row 1
        read_4.model['number'] = 100
        read_4.model.property_changed.emit(read_4.model, 'number', read_4.model['number'])
        assert composite.model['Pad']['width'] == read_4.model['number']
