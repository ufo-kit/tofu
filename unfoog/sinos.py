"""Sinogram generation module."""
import os
from gi.repository import Ufo


def split_extended_path(extended_path):
    """Return (path, first, last-1) from *extended_path* (e.g.
    /home/foo/bla:0:10)."""
    split = extended_path.split(':')
    path = split[0]
    filenames = sorted([f for f in os.listdir(path)
                        if os.path.isfile(os.path.join(path, f))])

    first = int(split[1]) if len(split) > 1 else 0
    last = int(split[2]) - first if len(split) > 2 else len(filenames) - first
    return (path, first, last)


NEG_LOG_SOURCE = """
__kernel void neg_log (global float *input,
                       global float *output)
{
    int idx = get_global_id (1) * get_global_size (0) + get_global_id (0);
    output[idx] = - log (input[idx]);
}"""


def _set_pass(y_0, height, proj_reader, flat_reader=None, dark_reader=None):
    """Set pass in a multipass execution. We need to set the *y_0* and *height* which tell us which
    row do we start and end with in this pass. *proj_reader* is the projection reader, *writer* is
    image writer which also needs to be told what is the offset of the file name index which depends
    again on the *y_0*. *flat_reader* and *dark_reader* are optional dark and flat field readers.
    """
    def set_reader(reader):
        if reader:
            reader.props.y = y_0
            reader.props.height = height

    set_reader(proj_reader)
    set_reader(flat_reader)
    set_reader(dark_reader)


def _execute(args, limits):
    """Execute one pass with *limits* (height of the projections as [start, region])."""
    sched = Ufo.Scheduler()
    sched.set_properties(expand=False)
    g = make_sino_graph(args, limits=limits)
    sched.run(g)


def make_sino_graph(args, limits=None):
    """Create a graph for sinograms generation. *args* are static arguments and *limits* are used to
    determine the number of sinograms to be processed in this pass if given.
    """
    pm = Ufo.PluginManager()
    g = Ufo.TaskGraph()

    proj_path, proj_nth, proj_count = split_extended_path(args.input)
    proj_reader = pm.get_task('reader')
    proj_reader.set_properties(path=proj_path, nth=proj_nth, count=proj_count)

    writer = pm.get_task('writer')
    writer.set_properties(filename='{0}'.format(args.output), append=bool(args.chunk))

    sinogen = pm.get_task('sino-generator')
    sinogen.set_properties(num_projections=proj_count)

    flat_reader = None
    dark_reader = None
    if args.flats and args.darks:
        # Read flat fields
        flat_path, flat_nth, flat_count = split_extended_path(args.flats)
        flat_reader = pm.get_task('reader')
        flat_reader.set_properties(path=flat_path, nth=flat_nth, count=flat_count)

        flat_avg = pm.get_task('averager')
        flat_avg.set_properties(num_generate=proj_count)

        # Read dark fields
        dark_path, dark_nth, dark_count = split_extended_path(args.darks)
        dark_reader = pm.get_task('reader')
        dark_reader.set_properties(path=dark_path, nth=dark_nth, count=dark_count)

        dark_avg = pm.get_task('averager')
        dark_avg.set_properties(num_generate=proj_count)

        # Setup flat-field correction
        ffc = pm.get_task('flat-field-correction')

        g.connect_nodes(dark_reader, dark_avg)
        g.connect_nodes(flat_reader, flat_avg)

        g.connect_nodes_full(proj_reader, ffc, 0)
        g.connect_nodes_full(dark_avg, ffc, 1)
        g.connect_nodes_full(flat_avg, ffc, 2)

        if not args.disable_absorption_correction:
            neglog = pm.get_task('opencl')
            neglog.props.source = NEG_LOG_SOURCE
            neglog.props.kernel = 'neg_log'
            g.connect_nodes(ffc, neglog)
            g.connect_nodes(neglog, sinogen)
        else:
            g.connect_nodes(ffc, sinogen)
    else:
        g.connect_nodes(proj_reader, sinogen)

    g.connect_nodes(sinogen, writer)

    if args.chunk:
        _set_pass(limits[0], limits[1], proj_reader, flat_reader=flat_reader,
                  dark_reader=dark_reader)

    return g


def make_sinos(args):
    """Make the sinograms with arguments provided by *args*."""
    if args.chunk and not args.num_sinos:
        raise ValueError('Number of sinograms must be specified for multipass execution')
    if args.chunk > args.num_sinos:
        raise ValueError('Number of sinograms must be greater than pass size')

    limits = (0, args.chunk) if args.chunk else None
    _execute(args, limits=limits)

    if args.chunk:
        # Starts are indices specifying the row at which to start
        starts = range(args.chunk, args.num_sinos, args.chunk) + [args.num_sinos]
        for i in range(len(starts) - 1):
            _execute(args, limits=(starts[i], starts[i + 1] - starts[i]))
