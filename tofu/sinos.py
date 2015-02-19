"""Sinogram generation module."""
from gi.repository import Ufo
from tofu.flatcorrect import create_pipeline as create_flat_corr_pipeline
from tofu.util import set_node_props, get_filenames


def make_sinos(args):
    """Make the sinograms with arguments provided by *args*."""
    if args.pass_size and not args.height:
        raise ValueError('`height` must be specified if `pass_size` is specified')

    if args.height:
        step = args.y_step * args.pass_size if args.pass_size else args.height
        starts = range(args.y, args.y + args.height, step)
        args.height = step
        for start in starts:
            args.y = start
            _execute(args, append=start != starts[0])
    else:
        _execute(args, append=False)


def _execute(args, append=False):
    pm = Ufo.PluginManager()
    graph = Ufo.TaskGraph()
    sched = Ufo.Scheduler()

    writer = pm.get_task('write')
    writer.props.filename = args.output
    writer.props.append = append

    sinos = create_pipeline(args, graph)
    graph.connect_nodes(sinos, writer)
    sched.run(graph)


def create_pipeline(args, graph):
    """Create sinogram generating pipeline based on arguments from *args*."""
    pm = Ufo.PluginManager()
    sinos = pm.get_task('transpose-projections')

    if args.end:
        region = (args.start, args.end, args.step)
        num_projections = len(range(*region))
    else:
        num_projections = len(get_filenames(args.input))
    sinos.props.number = num_projections

    if args.darks and args.flats:
        start = create_flat_corr_pipeline(args, graph)
    else:
        start = pm.get_task('read')
        start.props.path = args.input
        set_node_props(start, args)

    graph.connect_nodes(start, sinos)

    return sinos
