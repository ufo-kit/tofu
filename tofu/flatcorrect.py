"""Flat field correction."""
from gi.repository import Ufo
from tofu.util import get_filenames, set_node_props, make_subargs


def create_pipeline(args, graph):
    """Create flat field correction pipeline. All the settings are provided in *args*. *graph* is
    used for making the connections. Returns the flat field correction task which can be used
    for further pipelining.
    """
    pm = Ufo.PluginManager()

    def get_task(name, **kwargs):
        """Get task *name* with properties *kwargs*."""
        task = pm.get_task(name)
        task.set_properties(**kwargs)
        return task

    reader = get_task('reader', path=args.input)
    dark_reader = get_task('reader', path=args.darks)
    flat_before_reader = get_task('reader', path=args.flats)
    ffc = get_task('flat-field-correction', dark_scale=args.dark_scale,
                   absorption_correction=args.absorptivity,
                   fix_nan_and_inf=args.fix_nan_and_inf)
    mode = args.reduction_mode.lower()
    roi_args = make_subargs(args, ['y', 'height', 'y_step'])
    set_node_props(reader, args)
    set_node_props(dark_reader, roi_args)
    set_node_props(flat_before_reader, roi_args)

    if args.flats2:
        flat_after_reader = get_task('reader', path=args.flats2)
        set_node_props(flat_after_reader, roi_args)
        flat_interpolate = get_task('interpolate', number=len(get_filenames(args.input)))

    if mode == 'median':
        dark_stack = get_task('stack', num_items=len(get_filenames(args.darks)))
        dark_reduced = get_task('flatten', mode='median')
        flat_before_stack = get_task('stack', num_items=len(get_filenames(args.flats)))
        flat_before_reduced = get_task('flatten', mode='median')

        graph.connect_nodes(dark_reader, dark_stack)
        graph.connect_nodes(dark_stack, dark_reduced)
        graph.connect_nodes(flat_before_reader, flat_before_stack)
        graph.connect_nodes(flat_before_stack, flat_before_reduced)

        if args.flats2:
            flat_after_stack = get_task('stack', num_items=len(get_filenames(args.flats2)))
            flat_after_reduced = get_task('flatten', mode='median')
            graph.connect_nodes(flat_after_reader, flat_after_stack)
            graph.connect_nodes(flat_after_stack, flat_after_reduced)
    elif mode == 'average':
        dark_reduced = get_task('averager')
        flat_before_reduced = get_task('averager')
        graph.connect_nodes(dark_reader, dark_reduced)
        graph.connect_nodes(flat_before_reader, flat_before_reduced)

        if args.flats2:
            flat_after_reduced = get_task('averager')
            graph.connect_nodes(flat_after_reader, flat_after_reduced)
    else:
        raise ValueError('Invalid reduction mode')

    graph.connect_nodes_full(reader, ffc, 0)
    graph.connect_nodes_full(dark_reduced, ffc, 1)
    if args.flats2:
        graph.connect_nodes_full(flat_before_reduced, flat_interpolate, 0)
        graph.connect_nodes_full(flat_after_reduced, flat_interpolate, 1)
        graph.connect_nodes_full(flat_interpolate, ffc, 2)
    else:
        graph.connect_nodes_full(flat_before_reduced, ffc, 2)

    return ffc
