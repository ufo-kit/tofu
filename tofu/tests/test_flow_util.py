import pytest
from PyQt5.QtWidgets import QInputDialog
from tofu.flow.util import CompositeConnection, get_config_key, saved_kwargs
from tofu.flow.main import get_filled_registry


def test_get_config_key():
    # Existing key
    assert 'z' in get_config_key('models', 'general-backproject', 'hidden-properties')

    # Non-existent key
    assert get_config_key('foobarbaz') is None
    assert get_config_key('foobarbaz', default=1) == 1


def test_saved_kwargs(qtbot, monkeypatch, scene):
    registry = get_filled_registry()
    name = 'retrieve_phase'

    # No num-inputs info
    monkeypatch.setattr(QInputDialog, 'getInt', lambda *args, **kwargs: (2, True))
    state = {'name': name}
    model = registry.create(name)
    assert model.num_ports['input'] == 2

    # num-inputs specified
    state = {'name': name, 'num-inputs': 3}

    with saved_kwargs(registry, state):
        model = registry.create(name)
        assert model.num_ports['input'] == 3

    assert 'num_inputs' not in registry.registered_model_creators()[state['name']][1]


class TestCompositeConnection:
    def test_init(self):
        # Identical source and tartet -> exception
        with pytest.raises(ValueError):
            CompositeConnection('a', 0, 'a', 0)

        # OK, must pass
        CompositeConnection('a', 0, 'b', 0)

    def test_contains(self):
        conn = CompositeConnection('a', 0, 'b', 0)

        assert conn.contains('a', 'output', 0)
        assert not conn.contains('a', 'output', 1)
        assert not conn.contains('a', 'input', 0)
        assert not conn.contains('a', 'input', 1)

        assert conn.contains('b', 'input', 0)
        assert not conn.contains('b', 'input', 1)
        assert not conn.contains('b', 'output', 0)
        assert not conn.contains('b', 'output', 1)

        assert not conn.contains('foo', 'input', 14)

    def test_save(self):
        conn = CompositeConnection('a', 0, 'b', 0)

        assert conn.save() == ['a', 0, 'b', 0]
