def populate_link_model(link_model, nodes):
    read = nodes['read']
    read_2 = nodes['read_2']
    composite = nodes['cpm']
    records = [[read, read.model, 'number'],
               [read_2, read_2.model, 'height'],
               [composite, composite.model['Read'], 'y']]

    for (i, (node, model, prop)) in enumerate(records):
        link_model.add_item(node, model, prop, 0, i)

    return records


def get_index_from_treemodel(node_model, row, prop_name):
    item = node_model.item(row, 0)
    i = 0
    prop_item = item.child(i)
    while prop_item.text() != prop_name:
        i += 1
        prop_item = item.child(i)

    return node_model.indexFromItem(prop_item)


def add_nodes_to_scene(scene, model_names=None):
    if not model_names:
        model_names = ['read']
    nodes = []

    for name in model_names:
        model_cls = scene.registry.create(name)
        nodes.append(scene.create_node(model_cls))

    return nodes
