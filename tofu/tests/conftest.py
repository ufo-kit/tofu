import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from pyqtgraph.Qt.QtWidgets import QInputDialog


def pytest_collection_modifyitems(config, items):
    skip_gpu = pytest.mark.skip(reason="UFO GPU/OpenCL runtime is not available in this job")
    for item in items:
        if "gpu" in item.keywords and not config.getoption("--run-gpu"):
            item.add_marker(skip_gpu)


def pytest_addoption(parser):
    parser.addoption(
        "--run-gpu",
        action="store_true",
        default=False,
        help="run tests that execute UFO GPU/OpenCL pipelines",
    )


@pytest.fixture(scope='function')
def nodes(monkeypatch):
    from tofu.flow.main import get_filled_registry
    from tofu.flow.scene import UfoScene

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
    from tofu.flow.main import get_filled_registry
    from tofu.flow.scene import UfoScene

    reg = get_filled_registry()
    return UfoScene(reg)


@pytest.fixture(scope='function')
def scene_with_composite(nodes):
    from tofu.flow.scene import UfoScene

    return UfoScene(nodes['cpm'].model._registry)


@pytest.fixture(scope='function')
def node_model():
    from tofu.flow.propertylinksmodels import NodeTreeModel

    model = NodeTreeModel()
    model.setColumnCount(1)

    return model


@pytest.fixture(scope='function')
def link_model(node_model):
    from tofu.flow.propertylinksmodels import PropertyLinksModel

    model = PropertyLinksModel(node_model)

    return model
