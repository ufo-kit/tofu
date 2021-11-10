import logging
from PyQt5.QtCore import QDataStream, pyqtSignal
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from tofu.flow.models import PropertyModel, BaseCompositeModel
from tofu.flow.util import MODEL_ROLE, NODE_ROLE, PROPERTY_ROLE


LOG = logging.getLogger(__name__)


def _decode_mime_data(data):
    byte_array = data.data('application/x-sourcetreemodelindex')
    ds = QDataStream(byte_array)
    row = ds.readInt32()
    column = ds.readInt32()
    internal_id = ds.readUInt64()

    return (row, column, internal_id)


def _data_from_tree_index(index):
    """
    Traverse parents up to the root and get the root node, model and it's property from *index*,
    which must be a property record (leaf in the tree).
    """
    prop_name = index.data()
    index = index.parent()
    model = index.data(role=MODEL_ROLE)

    while index.data(role=NODE_ROLE) is None and index.isValid():
        index = index.parent()

    node = index.data(role=NODE_ROLE)

    return (node, model, prop_name)


def _get_string_path(node, model, prop_name):
    if isinstance(node.model, BaseCompositeModel):
        path = node.model.get_path_from_model(model)
    else:
        path = [model]
    str_path = [model.caption for model in path]
    str_path.append(prop_name)

    return str_path


class NodeTreeModel(QStandardItemModel):

    """Tree model representing nodes in the scene."""

    def add_node(self, node):
        item = self._add_model(node.model)
        if item:
            item.setData(node, role=NODE_ROLE)

    def remove_node(self, node):
        for j in range(self.rowCount()):
            item = self.item(j, 0)
            if item and item.data(role=NODE_ROLE) == node:
                self.removeRow(j)
                break

    def clear(self):
        """In PyQt5, clear doesn't emit the rowsAboutToBeRemoved signal and this does effectively
        the same.
        """
        self.removeRows(0, self.rowCount())
        self.removeColumns(0, self.columnCount())
        self.rowCount(), self.columnCount()

    def set_nodes(self, nodes):
        self.clear()
        for node in nodes:
            self.add_node(node)

    def _add_model(self, flow_model, parent=None):
        if not parent:
            parent = self.invisibleRootItem()
        item = None
        if (isinstance(flow_model, PropertyModel) or isinstance(flow_model, BaseCompositeModel)):
            item = QStandardItem(flow_model.caption)
            item.setData(flow_model, role=MODEL_ROLE)
            item.setEditable(False)
            if isinstance(flow_model, PropertyModel):
                for prop in sorted(flow_model):
                    prop_item = QStandardItem(prop)
                    prop_item.setEditable(False)
                    item.appendRow(prop_item)
            else:
                for submodel_name in sorted(flow_model):
                    self._add_model(flow_model[submodel_name], parent=item)

        if item:
            parent.appendRow(item)

        return item


class PropertyLinksModel(QStandardItemModel):

    """Links model representing property links between nodes in the scene."""

    restored = pyqtSignal()

    def __init__(self, node_model):
        super().__init__()
        self._silent = {}
        self._slaves = {}
        self._node_model = node_model
        self._node_model.rowsAboutToBeRemoved.connect(self.on_node_rows_about_to_be_removed)

    def __contains__(self, key):
        for column in range(self.columnCount()):
            if self.findItems(key, column=column):
                return True

        return False

    def clear(self):
        for j in range(self.rowCount()):
            for i in range(self.columnCount()):
                self.remove_item(self.indexFromItem(self.item(j, i)))
        super().clear()

    def find_items(self, data_list, roles):
        result = []
        for j in range(self.rowCount()):
            for i in range(self.columnCount()):
                item = self.item(j, i)
                if item:
                    success = True
                    for (data, role) in zip(data_list, roles):
                        if item.data(role=role) != data:
                            success = False
                            break
                    if success:
                        result.append(item)

        return result

    def get_model_links(self, models):
        """
        Get links between *models*. Return dict {row index: [str_path, ...]}, where *str_path* is
        the path from the topmost model (in case of composites along the way) to the property name.
        """
        items = {}
        for model in models:
            for item in self.find_items([model], [MODEL_ROLE]):
                str_path = item.text().split('->')
                if item.row() not in items:
                    items[item.row()] = [str_path]
                else:
                    items[item.row()].append(str_path)

        return items

    def get_root_model(self, model):
        root_model = None
        items = self.find_items([model], [MODEL_ROLE])

        if items:
            root_model = items[0].data(role=MODEL_ROLE)
        else:
            for (silent_model, prop_name) in self._silent:
                if silent_model == model:
                    root_model = self._silent[(silent_model, prop_name)][0]

        return root_model

    def get_model_properties(self, model):
        items = self.find_items([model], [MODEL_ROLE])
        return [item.data(role=PROPERTY_ROLE) for item in items]

    def add_item(self, node, model, prop_name, row, column, insert=False):
        """
        Add item where *node* is the root node (can be composite), *model* is the leaf model
        (there can be composites above if the leaf is nested) and *prop_name* is the property name.
        *row* and *column* determine the table cell to which to add the item or replace an old item
        with the new one. If *insert* is True, insert a new row at *row*.
        """
        str_path = '->'.join(_get_string_path(node, model, prop_name))
        if str_path in self:
            raise ValueError(f'{str_path} already inside')
        item = QStandardItem(str_path)
        item.setData(model, role=MODEL_ROLE)
        item.setData(prop_name, role=PROPERTY_ROLE)
        item.setData(node, role=NODE_ROLE)
        item.setEditable(False)

        if row == -1:
            row = self.rowCount()
        if column == -1:
            # +1 to find an empty cell even if the row is full
            for i in range(self.columnCount() + 1):
                if self.item(row, i) is None:
                    column = i
                    break

        LOG.debug(f'Add item {node.model.caption}({item.data(role=MODEL_ROLE)}):'
                  f'{item.data(role=PROPERTY_ROLE)} at ({row}, {column})')
        if insert:
            self.insertRow(row, item)
        else:
            self.setItem(row, column, item)

        # In case the composite is being edit in a subwindow, connect the slave nodes from the
        # subsecene
        if isinstance(node.model, BaseCompositeModel):
            node.model.add_slave_links()

        model.property_changed.connect(self.on_property_changed)

    def remove_item(self, index):
        flow_model = index.data(role=MODEL_ROLE)
        if not flow_model:
            # Empty cell
            return
        property_name = index.data(role=PROPERTY_ROLE)
        flow_model.property_changed.disconnect(self.on_property_changed)
        self.setItem(index.row(), index.column(), None)

        # Remove all associated slaves
        root_key = (flow_model, property_name)
        if root_key in self._slaves:
            for slave_key in tuple(self._slaves[root_key]):
                self.remove_silent(*slave_key)

    def add_silent(self, model, property_name, root, root_property_name):
        key = (model, property_name)
        if key in self._silent:
            return
        model.property_changed.connect(self.on_property_changed)
        root_key = (root, root_property_name)
        if not self.find_items(root_key, (MODEL_ROLE, PROPERTY_ROLE)):
            raise ValueError(f'{model} not in property links')
        self._silent[key] = root_key
        if root_key not in self._slaves:
            self._slaves[root_key] = [key]
        else:
            self._slaves[root_key].append(key)
        LOG.debug(f'Slave {root}->{root_property_name} -> {model}->{property_name} added')

    def remove_silent(self, model, property_name):
        key = (model, property_name)
        if key not in self._silent:
            # Already removed, e.g. by deleting an item by del key while some composite windows were
            # still opened
            return
        model.property_changed.disconnect(self.on_property_changed)
        root_key = self._silent[key]
        index = self._slaves[root_key].index(key)
        del self._slaves[root_key][index]
        if not self._slaves[root_key]:
            del self._slaves[root_key]
        del self._silent[key]
        LOG.debug(f'Slave {model}->{property_name} removed')

    def replace_item(self, node, new_model, old_model):
        for j in range(self.rowCount()):
            for i in range(self.columnCount()):
                item = self.item(j, i)
                if item and item.data(role=MODEL_ROLE) == old_model:
                    # Don't break, replace all properties of *old_model*
                    prop_name = item.data(role=PROPERTY_ROLE)
                    slaves = tuple(self._slaves.get((old_model, prop_name), []))
                    self.remove_item(self.indexFromItem(item))
                    self.add_item(node, new_model, prop_name, j, i)
                    for (slave_model, slave_property_name) in slaves:
                        self.add_silent(slave_model, slave_property_name, new_model, prop_name)

    def on_node_rows_about_to_be_removed(self, parent, first, last):
        for k in range(first, last + 1):
            node = self._node_model.item(k, 0).data(role=NODE_ROLE)
            for j in range(self.rowCount()):
                for i in range(self.columnCount()):
                    item = self.item(j, i)
                    if item and item.data(role=NODE_ROLE) == node:
                        self.remove_item(self.indexFromItem(item))

        self.compact()

    def canDropMimeData(self, data, action, row, column, parent):
        can_drop = False
        if data.hasFormat('application/x-sourcetreemodelindex'):
            src_row, src_column, src_internal_id = _decode_mime_data(data)
            src_model_index = self._node_model.createIndex(src_row, src_column, src_internal_id)
            # src_model_index is the property, it's parent is the model
            node, flow_model, property_name = _data_from_tree_index(src_model_index)
            str_path = '->'.join(_get_string_path(node, flow_model, property_name))
            can_drop = str_path not in self
            if parent.isValid():
                # Parent itself can be an empty cell, so use the first column which is for sure
                # occupied since the parent is valid (row exists and we are not between rows)
                first_item = self.item(parent.row(), 0)
                parent_model = first_item.data(role=MODEL_ROLE)
                parent_property_name = first_item.data(role=PROPERTY_ROLE)
                if not type(flow_model[property_name]) is type(parent_model[parent_property_name]):
                    # Data can be dropped only if the types of properties match
                    can_drop = False

        return can_drop

    def dropMimeData(self, data, action, row, column, parent):
        src_row, src_column, src_internal_id = _decode_mime_data(data)

        src_model_index = self._node_model.createIndex(src_row, src_column, src_internal_id)
        node, flow_model, property_name = _data_from_tree_index(src_model_index)
        if parent.isValid():
            row = parent.row()
            insert = False
        else:
            insert = True
        # drops never replace items and column=-1 means "find an empty cell"
        self.add_item(node, flow_model, property_name, row, -1, insert=insert)

        return True

    def save(self):
        state = []
        for j in range(self.rowCount()):
            row_state = []
            for i in range(self.columnCount()):
                item = self.item(j, i)
                if not item:
                    continue
                node = item.data(role=NODE_ROLE)
                model = item.data(role=MODEL_ROLE)
                prop_name = item.data(role=PROPERTY_ROLE)
                str_path = _get_string_path(node, model, prop_name)
                row_state.append([node.id, str_path])
            state.append(row_state)

        return state

    def restore(self, state, nodes):
        self.clear()
        for (j, row) in enumerate(state):
            for (i, (node_id, path)) in enumerate(row):
                node = nodes[node_id]
                # Last path entry is the property name
                if isinstance(node.model, BaseCompositeModel):
                    flow_model = node.model.get_model_from_path(path[1:-1])
                else:
                    flow_model = node.model
                self.add_item(node, flow_model, path[-1], j, i)
        self.restored.emit()

    def compact(self):
        # Shift rows to the left
        for j in range(self.rowCount()):
            filled = []
            for i in range(self.columnCount()):
                if self.item(j, i):
                    filled.append(self.takeItem(j, i))
            for (i, item) in enumerate(filled):
                self.setItem(j, i, item)

        # Check empty rows
        for j in range(self.rowCount())[::-1]:
            is_empty = True
            for i in range(self.columnCount()):
                if self.item(j, i):
                    is_empty = False
            if is_empty:
                self.removeRow(j)

        # Check empty columns
        for i in range(self.columnCount())[::-1]:
            is_empty = True
            for j in range(self.rowCount()):
                if self.item(j, i):
                    is_empty = False
            if is_empty:
                self.removeColumn(i)

    def on_property_changed(self, sig_model, sig_property_name, value):
        LOG.debug(f'on_property_changed: {sig_model}, {sig_model.caption}, '
                  f'{sig_property_name}, {value}')
        sig_key = (sig_model, sig_property_name)
        if sig_key in self._silent:
            # pyqtSignal came from a composite subwindow, get root model from the silent slave
            root_key = self._silent[sig_key]
            root_key[0][root_key[1]] = value
        else:
            root_key = (sig_model, sig_property_name)

        row = -1
        for j in range(self.rowCount()):
            for i in range(self.columnCount()):
                item = self.item(j, i)
                if (item and item.data(role=MODEL_ROLE) == root_key[0]
                        and item.data(role=PROPERTY_ROLE) == root_key[1]):
                    row = j
                    break
            if row != -1:
                break

        for i in range(self.columnCount()):
            item = self.item(row, i)
            if item:
                model = item.data(role=MODEL_ROLE)
                property_name = item.data(role=PROPERTY_ROLE)
                if root_key != (model, property_name):
                    model[property_name] = value
                # Notify all slaves
                key = (model, property_name)
                if key in self._slaves:
                    for (slave_model, slave_property_name) in self._slaves[key]:
                        if (slave_model, slave_property_name) != (sig_model, sig_property_name):
                            slave_model[slave_property_name] = value
