from PyQt5.QtCore import QMimeData, Qt, QDataStream, QByteArray, QIODevice, QModelIndex
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QAbstractItemView, QLabel, QTableView, QTreeView, QVBoxLayout, QWidget


def _encode_mime_data(index: QModelIndex):
    """Encode item in *index* into :class:`QMimeData`."""
    mime_data = QMimeData()
    data = QByteArray()
    stream = QDataStream(data, QIODevice.WriteOnly)
    try:
        stream.writeInt32(index.row())
        stream.writeInt32(index.column())
        stream.writeUInt64(index.internalId())
    finally:
        stream.device().close()
    mime_data.setData("application/x-sourcetreemodelindex", data)

    return mime_data


class PropertyLinksView(QTableView):

    """Table view for displaying node property links."""

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            model = self.model()
            for index in self.selectedIndexes():
                model.remove_item(index)
            model.compact()


class NodesView(QTreeView):

    """Tree view displaying nodes in the scene."""

    def get_drag_index(self):
        selected = self.selectedIndexes()

        if not selected:
            return

        index = selected[0]
        if index.child(0, 0).row() != -1:
            return

        return index

    def mouseMoveEvent(self, event):
        """All that a mouse *event* can do is start a drag and drop operation."""
        index = self.get_drag_index()
        if not index:
            return

        drag = QDrag(self)
        mime_data = _encode_mime_data(index)
        drag.setMimeData(mime_data)
        drag.exec_(Qt.CopyAction)

        return True


class PropertyLinks(QWidget):

    """Widget displaying nodes in the scene and their property links in one window."""

    def __init__(self, node_model, table_model, parent=None):
        super().__init__(parent=parent, flags=Qt.Window)
        self.setWindowTitle('Property Links')
        self.resize(600, 800)

        self._treeview = NodesView()
        self._treeview.setHeaderHidden(True)
        self._treeview.setAlternatingRowColors(True)
        self._treeview.setDragEnabled(True)
        self._treeview.setAcceptDrops(False)
        self._treeview.setModel(node_model)
        node_model.itemChanged.connect(self.on_node_model_changed)

        self._table_view = PropertyLinksView()
        self._table_view.setDragDropOverwriteMode(False)
        self._table_view.setDragDropMode(QAbstractItemView.DropOnly)
        table_model.itemChanged.connect(self.on_table_model_changed)
        table_model.rowsInserted.connect(self.on_table_model_rows_inserted)
        table_model.restored.connect(self.on_table_model_restored)
        self._table_view.setModel(table_model)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self._treeview)
        main_layout.addWidget(QLabel('Drag properties from above to the area below'))
        main_layout.addWidget(self._table_view)
        self.setLayout(main_layout)

    def show(self):
        self._table_view.resizeColumnsToContents()
        self._treeview.sortByColumn(0, Qt.AscendingOrder)
        super().show()

    def on_table_model_changed(self, item):
        self._table_view.resizeColumnToContents(item.column())

    def on_table_model_rows_inserted(self, index, start, stop):
        self._table_view.resizeColumnToContents(0)

    def on_table_model_restored(self):
        self._table_view.resizeColumnsToContents()

    def on_node_model_changed(self, item):
        self._treeview.sortByColumn(0, Qt.AscendingOrder)
