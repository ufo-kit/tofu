import pytest
from PyQt5.QtCore import Qt, QItemSelectionModel
from tofu.flow.propertylinkswidget import NodesView, PropertyLinks, PropertyLinksView
from tofu.tests.flow_util import get_index_from_treemodel, populate_link_model


@pytest.fixture(scope='function')
def node_view(node_model):
    view = NodesView()
    view.setHeaderHidden(True)
    view.setAlternatingRowColors(True)
    view.setDragEnabled(True)
    view.setAcceptDrops(False)
    view.setModel(node_model)

    return view


@pytest.fixture(scope='function')
def link_view():
    return PropertyLinksView()


@pytest.fixture(scope='function')
def link_widget(node_model):
    return PropertyLinks()


def test_property_links_view_delete_key(qtbot, link_model, link_view, nodes):
    qtbot.addWidget(link_view)
    link_view.setModel(link_model)
    populate_link_model(link_model, nodes)
    link_view.selectColumn(0)
    qtbot.keyPress(link_view, Qt.Key_Delete)
    assert link_model.columnCount() == 2


def test_node_view_get_drag_index(qtbot, node_view, nodes):
    node_model = node_view.model()
    read = nodes['read']
    node_model.add_node(read)
    sm = node_view.selectionModel()

    # Nothing selected
    assert node_view.get_drag_index() is None

    # Node selection must yield nothing
    index = node_model.indexFromItem(node_model.item(0, 0))
    sm.select(index, QItemSelectionModel.Select)
    assert node_view.get_drag_index() is None
    sm.clear()

    # Property selection must yield an index which can be dragged
    index = get_index_from_treemodel(node_model, 0, 'number')
    sm.select(index, QItemSelectionModel.Select)
    assert node_view.get_drag_index() is not None
    sm.clear()
