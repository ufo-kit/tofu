import contextlib
import json
import pkg_resources
from PyQt5.QtCore import Qt
from qtpynodeeditor import PortType


MODEL_ROLE = Qt.UserRole + 1
PROPERTY_ROLE = MODEL_ROLE + 1
NODE_ROLE = PROPERTY_ROLE + 1


with open(pkg_resources.resource_filename(__name__, 'config.json')) as f:
    ENTRIES = json.load(f)


def get_config_key(*keys, default=None):
    current = ENTRIES.get(keys[0], default)
    if current != default and len(keys) > 1:
        for key in keys[1:]:
            current = current.get(key, default)
            if current == default:
                break

    return current


@contextlib.contextmanager
def saved_kwargs(registry, state):
    """
    Tell the registry to use the number of saved inputs for model creation but only for one model
    creation, i.e. reset the context afterward.
    """
    if 'num-inputs' in state:
        kwargs = registry.registered_model_creators()[state['name']][1]
        kwargs['num_inputs'] = state['num-inputs']

    try:
        yield
    finally:
        if 'num-inputs' in state:
            del kwargs['num_inputs']


class CompositeConnection:
    def __init__(self, from_unique_name, from_port_index, to_unique_name, to_port_index):
        if from_unique_name == to_unique_name:
            raise ValueError('from_unique_name and to_unique_name must be different')
        self.from_unique_name = from_unique_name
        self.from_port_index = from_port_index
        self.to_unique_name = to_unique_name
        self.to_port_index = to_port_index

    def contains(self, unique_name, port_type, port_index):
        is_from = is_to = False

        if port_type == PortType.output:
            is_from = (unique_name == self.from_unique_name and port_index == self.from_port_index)
        else:
            is_to = (unique_name == self.to_unique_name and port_index == self.to_port_index)

        return is_from or is_to

    def save(self):
        return [self.from_unique_name, self.from_port_index,
                self.to_unique_name, self.to_port_index]

    def __str__(self):
        return repr(self)

    def __repr__(self):
        fmt = 'Connection({}@{} -> {}@{})'

        return fmt.format(self.from_unique_name, self.from_port_index,
                          self.to_unique_name, self.to_port_index)


class FlowError(Exception):
    pass
