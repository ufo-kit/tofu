import pytest
from PyQt5.QtWidgets import QInputDialog
from tofu.flow.main import get_filled_registry
from tofu.flow.scene import UfoScene
from tofu.flow.propertylinksmodels import PropertyLinksModel, NodeTreeModel


@pytest.fixture(scope='function')
def nodes(monkeypatch):
    reg = get_filled_registry()
    scene = UfoScene(reg)

    nodes = {}

    # Composite node
    for name in ['read', 'pad']:
        model_cls = reg.create(name)
        node = scene.create_node(model_cls)
        node.graphics_object.setSelected(True)

    monkeypatch.setattr(QInputDialog, "getText", lambda *args: ('cpm', True))
    nodes['cpm'] = scene.create_composite()
    nodes['cpm'].graphics_object.setSelected(False)

    # Simple nodes
    for i in range(5):
        name = f'read_{i}' if i else 'read'
        model_cls = reg.create('read')
        nodes[name] = scene.create_node(model_cls)

    model_cls = reg.create('image_viewer')
    nodes['image_viewer'] = scene.create_node(model_cls)

    model_cls = reg.create('average')
    nodes['average'] = scene.create_node(model_cls)

    return nodes


@pytest.fixture(scope='function')
def scene():
    reg = get_filled_registry()
    return UfoScene(reg)


@pytest.fixture(scope='function')
def scene_with_composite(nodes):
    return UfoScene(nodes['cpm'].model._registry)


@pytest.fixture(scope='function')
def node_model():
    model = NodeTreeModel()
    model.setColumnCount(1)

    return model


@pytest.fixture(scope='function')
def link_model(node_model):
    model = PropertyLinksModel(node_model)

    return model
