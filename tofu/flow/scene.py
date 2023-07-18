import logging
import numpy as np
import networkx as nx
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QInputDialog
from qtpynodeeditor import FlowScene, NodeDataModel, PortType, opposite_port

from tofu.flow.models import (BaseCompositeModel, ImageViewerModel, PropertyModel,
                              UFO_DATA_TYPE, get_composite_model_class,
                              get_composite_model_classes_from_json)
from tofu.flow.util import CompositeConnection, FlowError, saved_kwargs
from tofu.flow.propertylinksmodels import PropertyLinksModel, NodeTreeModel


LOG = logging.getLogger(__name__)


class UfoScene(FlowScene):
    nodes_duplicated = pyqtSignal(list, dict)
    # view item, its name and model name
    item_focus_in = pyqtSignal(QObject, str, str, NodeDataModel)

    def __init__(self, registry=None, style=None, parent=None,
                 allow_node_creation=True, allow_node_deletion=True):
        super().__init__(registry=registry,
                         style=style,
                         parent=parent,
                         allow_node_creation=allow_node_creation,
                         allow_node_deletion=allow_node_deletion)
        self._composite_nodes = {}
        self._selected_nodes_on_disabled = []
        self.node_model = NodeTreeModel()
        self.node_model.setColumnCount(1)
        self.property_links_model = PropertyLinksModel(self.node_model)
        self.style_collection.node.opacity = 1
        self.style_collection.connection.use_data_defined_colors = True
        self.node_double_clicked.connect(self.on_node_double_clicked)

    def __getstate__(self):
        state = super().__getstate__()
        state['property-links'] = self.property_links_model.save()

        return state

    def __setstate__(self, doc):
        for node in doc['nodes']:
            model = node['model']
            if 'models' in model and 'connections' in model:
                # First register the composite model
                models = get_composite_model_classes_from_json(model)
                for model in models:
                    self.registry.register_model(model, category='Composite',
                                                 registry=self.registry)

        # Restore the scene
        super().__setstate__(doc)

        # and the property link models and widgets
        if 'property-links' in doc:
            self.node_model.set_nodes(self.nodes.values())
            self.property_links_model.restore(doc['property-links'], self.nodes)

    def create_node(self, data_model, restore_links=True):
        """Overrides :class:`FlowScene` in order to create a node with *data_model* with a unique
        caption.
        """
        LOG.debug(f'Create node with model {data_model}')
        node = super().create_node(data_model)
        self._setup_new_node(node)
        if restore_links and isinstance(node.model, BaseCompositeModel):
            node.model.restore_links(node)

        return node

    def restore_node(self, node_json):
        LOG.debug(f"Restore node with model {node_json['model']['name']}")
        with saved_kwargs(self.registry, node_json['model']):
            node = super().restore_node(node_json)
        self._setup_new_node(node)

        return node

    def on_item_focus_in(self, view_item, prop_name, caption, model):
        self.item_focus_in.emit(view_item, prop_name, caption, model)

    def _setup_new_node(self, node):
        self._set_unique_caption(node)
        self.node_model.add_node(node)
        if isinstance(node.model, BaseCompositeModel):
            node.model.property_links_model = self.property_links_model
        node.model.item_focus_in.connect(self.on_item_focus_in)

    def _set_unique_caption(self, new_node):
        caption = new_node.model.caption
        captions = [node.model.caption for node in self.nodes.values() if node != new_node]
        if caption in captions:
            fmt = new_node.model.base_caption + ' {}'
            i = 2
            while fmt.format(i) in captions:
                i += 1
            caption = fmt.format(i)
        new_node.model.caption = caption

    def remove_node(self, node):
        if hasattr(node.model, 'cleanup'):
            node.model.cleanup()

        if (isinstance(node.model, BaseCompositeModel) and node.model.name
                in self._composite_nodes):
            del self._composite_nodes[node.model.name]
        self.node_model.remove_node(node)
        super().remove_node(node)

    def is_selected_one_composite(self):
        result = False
        nodes = self.selected_nodes()
        if len(nodes) == 1:
            result = isinstance(nodes[0].model, BaseCompositeModel)

        return result

    def skip_nodes(self):
        selected_nodes = self.selected_nodes()
        # First check if the selected nodes may be skipped
        for node in selected_nodes:
            if (node.model.num_ports[PortType.input] != 1
                    or node.model.num_ports[PortType.output] != 1):
                raise FlowError('Only nodes with one input and one output can be skipped')
            ports = list(node.state.ports)
            if ports[0].data_type != UFO_DATA_TYPE or ports[1].data_type != UFO_DATA_TYPE:
                raise FlowError('Only tasks with UFO input and output can be skipped')

        # And only if all is fine, then skip them
        for node in selected_nodes:
            node.model.skip = not node.model.skip
            opacity = 0.5 if node.model.skip else 1
            node.state.input_connections[0].graphics_object.setOpacity(opacity)
            node.state.output_connections[0].graphics_object.setOpacity(opacity)
            node.graphics_object.setOpacity(opacity)

    def auto_fill(self):
        for node in self.nodes.values():
            if isinstance(node.model, BaseCompositeModel):
                paths = node.model.get_leaf_paths()
            else:
                paths = [[node.model]]
            for path in paths:
                model = path[-1]
                if isinstance(model, PropertyModel):
                    model.auto_fill()

    def copy_nodes(self):
        new_nodes = {}
        selected_nodes = self.selected_nodes()

        # Create nodes
        for node in selected_nodes:
            new_node = self.create_node(node.model)
            new_nodes[node] = new_node
            values = node.model.save()
            new_node.model.restore(values, restore_caption=False)

        # Create connections
        for node, new_node in new_nodes.items():
            for connection in self.connections:
                port = connection.ports[0]
                in_index = port.index
                out_index = connection.ports[1].index
                if port.node == node:
                    other_node = connection.ports[1].node
                    if other_node in new_nodes:
                        # Other node has been also selected
                        self.create_connection_by_index(new_node,
                                                        in_index,
                                                        new_nodes[other_node],
                                                        out_index,
                                                        None)

        self.nodes_duplicated.emit(selected_nodes, new_nodes)

    def create_composite(self):
        composite_name, ok = QInputDialog.getText(None, 'Create Composite Node', 'Name:')
        if not ok:
            return
        if composite_name in self.registry.registered_model_creators():
            raise FlowError(f'Composite node with name "{composite_name}" has already '
                            'been registered')
        self._composite_nodes[composite_name] = {}
        connection_replacements = []
        models = []
        connections = []
        selected_nodes = self.selected_nodes()

        for node in selected_nodes:
            unique_name = node.model.caption
            models.append((node.model.name,
                           node.model.save(),
                           True,
                           node.__getstate__()['position']))
            self._composite_nodes[composite_name][unique_name] = node.__getstate__()

        # Connections
        assigned_ports = []
        x = []
        y = []
        for node in selected_nodes:
            x.append(node.position.x())
            y.append(node.position.y())
            for port_type in ['input', 'output']:
                for index, port in node[port_type].items():
                    if port.connections:
                        # We allow only one connection
                        conn = port.connections[0]
                        other_port = conn.ports[0] if conn.ports[1] == port else conn.ports[1]
                        other = conn.get_node(opposite_port(port_type))
                        if (other in selected_nodes and port not in assigned_ports
                                and other_port not in assigned_ports):
                            # Connection reaches to a node outside selection
                            if port_type == PortType.input:
                                to_node_name = node.model.caption
                                to_node_index = index
                                from_node_name = other.model.caption
                                from_node_index = other_port.index
                            else:
                                to_node_name = other.model.caption
                                to_node_index = other_port.index
                                from_node_name = node.model.caption
                                from_node_index = index
                            conn = CompositeConnection(from_node_name, from_node_index,
                                                       to_node_name, to_node_index)
                            connections.append(conn)
                            assigned_ports.append(port)
                        if other not in selected_nodes:
                            inside = (node.model.caption, port_type, index)
                            connection_replacements.append((other_port, inside))

        # Get links which will be internal to the newly created model
        node_models = []
        for selected_node in self.selected_nodes():
            if isinstance(selected_node.model, BaseCompositeModel):
                paths = selected_node.model.get_leaf_paths()
            else:
                paths = [[selected_node.model]]
            node_models += [path[-1] for path in paths]
        internal_links = list(self.property_links_model.get_model_links(node_models).values())

        composite = get_composite_model_class(composite_name,
                                              models,
                                              connections,
                                              links=internal_links)

        self.registry.register_model(composite,
                                     category='Composite',
                                     registry=self.registry)
        node = self.create_node(composite, restore_links=False)

        for selected_node in selected_nodes:
            if isinstance(selected_node.model, BaseCompositeModel):
                # Get all leaf PropertyModel instances
                paths = selected_node.model.get_leaf_paths()
            else:
                paths = [[selected_node.model]]
            # In case selected node is composite, replace all leaf node links
            for path in paths:
                new_model = node.model.get_model_from_path([model.caption for model in path])
                self.property_links_model.replace_item(node, new_model, path[-1])
            self.remove_node(selected_node)

        for outside_port, inside in connection_replacements:
            port_type, index = node.model.get_outside_port(*inside)
            self.create_connection(outside_port, node[port_type][index], check_cycles=False)

        # Put the new composite node to the average of x and y position of the selected nodes
        node.position = (np.mean(x), np.mean(y))
        node.graphics_object.setSelected(True)

        return node

    def on_node_double_clicked(self, node):
        views = self.views()
        if views:
            node.model.double_clicked(views[0])

    def expand_composite(self, node):
        name = node.model.name
        original_nodes = self._composite_nodes.get(name, None)

        return node.model.expand_into_scene(self, node, original_nodes=original_nodes)

    def is_fully_connected(self):
        """Are all the ports in all nodes connected?"""
        def are_ports_connected(node, port_type):
            for port in node[port_type].values():
                if not port.connections:
                    return False
            return True

        for node in self.nodes.values():
            if not are_ports_connected(node, 'input'):
                return False
            if not are_ports_connected(node, 'output'):
                return False

        return True

    def are_all_ufo_tasks(self, graphs=None):
        """If all inputs and outputs of all models in all *graphs* have `UfoBuffer` data type, return
        True. If *graphs* are not specified, they are created from the scene.
        """
        if graphs is None:
            graphs = self.get_simple_node_graphs()

        for graph in graphs:
            for model in graph.nodes:
                for port_type in ['input', 'output']:
                    for data_type in model.data_type[port_type].values():
                        if data_type.id != 'UfoBuffer':
                            return False

        return True

    def get_simple_node_graphs(self):
        """
        Get a graph from the scene without composite nodes which can be directly used byt the
        execution.
        """
        def get_composite(graph):
            """Get first found composite model."""
            for model in graph.nodes:
                if isinstance(model, BaseCompositeModel):
                    return model

        def replace_edge(graph, composite, edges, port_type):
            """Replace interface edges (going in or out from the composite model)."""
            for edge in edges:
                ports = graph.edges[edge]
                other = edge[0] if port_type == PortType.input else edge[1]
                model, index = composite.get_model_and_port_index(port_type, ports[port_type])
                if model not in graph:
                    graph.add_node(model)
                if port_type == PortType.input:
                    source = other
                    dest = model
                    input_port = index
                    output_port = ports[PortType.output]
                else:
                    source = model
                    dest = other
                    input_port = ports[PortType.input]
                    output_port = index
                LOG.debug(f'Adding edge {source.name}@{output_port} -> {dest.name}@{input_port}')
                graph.add_edge(source, dest, input=input_port, output=output_port)

        def replace_composite(graph, composite):
            composite.expand_into_graph(graph)
            edges = graph.in_edges(composite, keys=True)
            replace_edge(graph, composite, edges, PortType.input)
            edges = graph.out_edges(composite, keys=True)
            replace_edge(graph, composite, edges, PortType.output)
            graph.remove_node(composite)

        # Initial graph with composite nodes. We need a multigraph because composite nodes may have
        # many outputs which can lead to a same destination node.
        graph = nx.MultiDiGraph()
        for node in self.nodes.values():
            if not node.model.skip:
                graph.add_node(node.model)

        for conn in self.connections:
            p_dest, p_source = conn.ports
            if p_dest.node.model.skip:
                LOG.debug(f'Skiping connection {p_source.node.model.name} -> '
                          f'{p_dest.node.model.name}')
                continue
            while p_source.node.model.skip:
                LOG.debug(f'Skiping connection {p_source.node.model.name} -> '
                          f'{p_dest.node.model.name}')
                previous_conn = p_source.node.state.input_connections[0]
                previous_node = previous_conn.output_node
                p_source = list(previous_node.state.output_ports)[0]
            graph.add_edge(p_source.node.model, p_dest.node.model, input=p_dest.index,
                           output=p_source.index)

        # Expand composite nodes until there are only simple ones left
        model = get_composite(graph)
        while model:
            LOG.debug(f'Replacing composite {model.name}')
            replace_composite(graph, model)
            model = get_composite(graph)

        components = nx.weakly_connected_components(graph)

        return [nx.subgraph(graph, component) for component in components]

    def set_enabled(self, enabled):
        selected_nodes = self.selected_nodes()
        self.allow_node_creation = enabled
        self.allow_node_deletion = enabled
        for node in self.nodes.values():
            if not isinstance(node.model, ImageViewerModel):
                node.graphics_object.setEnabled(enabled)
                if enabled:
                    if node in self._selected_nodes_on_disabled:
                        node.graphics_object.setSelected(True)
                else:
                    if node in selected_nodes:
                        self._selected_nodes_on_disabled.append(node)

        for conn in self.connections:
            conn._graphics_object.setEnabled(enabled)

        if enabled:
            self._selected_nodes_on_disabled = []
