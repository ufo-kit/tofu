"""Sinogram generation module."""
import os
from gi.repository import Ufo
from unfoog.util import range_from


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


def _set_pass(region, proj_reader, flat_reader=None, dark_reader=None):
    """Set pass in a multipass execution. We need to set the *region* (y_0, height) which tell us
    which row do we start and end with in this pass. *proj_reader* is the projection reader,
    *flat_reader* and *dark_reader* are optional dark and flat field readers.
    """
    def set_reader(reader):
        if reader:
            reader.props.y = region[0]
            reader.props.height = region[1] - region[0]

    set_reader(proj_reader)
    set_reader(flat_reader)
    set_reader(dark_reader)


def _execute(args, region=None):
    """Execute one pass with *region* (from, to, step) which specifies which sinograms will be
    generated.
    """
    sched = Ufo.Scheduler()
    sched.set_properties(expand=False)
    g, reader = make_sino_graph(args, region=region)
    sched.run(g)

    return reader.props.total_height


def make_sino_graph(args, region=None):
    """Create a graph for sinograms generation. *args* are static arguments and *region* is used to
    determine the number of sinograms in terms of (from, to, step) in this pass.
    """
    pm = Ufo.PluginManager()
    g = Ufo.TaskGraph()

    proj_path, proj_nth, proj_count = split_extended_path(args.input)
    proj_reader = pm.get_task('reader')
    proj_reader.set_properties(path=proj_path, nth=proj_nth, count=proj_count)
    if region and region[-1] > 1:
        proj_down = pm.get_task('downsample')
        # Do not assume anything about the downsampler
        proj_down.props.x_factor = 1
        proj_down.props.y_factor = region[-1]

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

        # Setup nth row
        if region and region[-1] > 1:
            flat_down = pm.get_task('downsample')
            dark_down = pm.get_task('downsample')
            flat_down.props.x_factor = 1
            flat_down.props.y_factor = region[-1]
            dark_down.props.x_factor = 1
            dark_down.props.y_factor = region[-1]

            g.connect_nodes(proj_reader, proj_down)
            g.connect_nodes(flat_reader, flat_down)
            g.connect_nodes(flat_down, flat_avg)
            g.connect_nodes(dark_reader, dark_down)
            g.connect_nodes(dark_down, dark_avg)
            g.connect_nodes_full(proj_down, ffc, 0)
        else:
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
        if region and region[-1] > 1:
            g.connect_nodes(proj_reader, proj_down)
            g.connect_nodes(proj_down, sinogen)
        else:
            g.connect_nodes(proj_reader, sinogen)

    g.connect_nodes(sinogen, writer)

    if region:
        _set_pass(region, proj_reader, flat_reader=flat_reader, dark_reader=dark_reader)

    return g, proj_reader


def make_sinos(args):
    """Make the sinograms with arguments provided by *args*."""
    if args.region:
        region = range_from(args.region)
        if not args.chunk:
            _execute(args, region=region)
    elif args.chunk:
        # No range specified, we have to ask the graph itself for image height
        height = _execute(args, region=(0, args.chunk, 1))
        region = (args.chunk, height, 1)
    else:
        _execute(args)

    if args.chunk:
        # Chunk is stretched in order to point to correct absolute positions
        # when step in the range is specified
        chunk = args.chunk * region[2]
        # Starts are indices specifying the row at which to start
        starts = range(*(region[0], region[1], chunk)) + [region[1]]
        for i in range(len(starts) - 1):
            subregion = (starts[i], starts[i + 1], region[2])
            _execute(args, region=subregion)
