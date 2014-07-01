"""Sinogram generation module."""
import glob
from gi.repository import Ufo
from unfoog.util import range_from, set_reader, check_input


NEG_LOG_SOURCE = """
__kernel void neg_log (global float *input,
                       global float *output)
{
    int idx = get_global_id (1) * get_global_size (0) + get_global_id (0);
    output[idx] = - log (input[idx]);
}"""


def _set_pass(region, proj_reader, flat_reader=None, dark_reader=None):
    """Set pass in a multipass execution. We need to set the *region* (y_0, height, step) which tell
    us which row do we start and end with in this pass. *proj_reader* is the projection reader,
    *flat_reader* and *dark_reader* are optional dark and flat field readers.
    """

    def set_reader_roi(reader):
        if reader:
            reader.props.y = region[0]
            reader.props.height = region[1] - region[0]

    set_reader_roi(proj_reader)
    set_reader_roi(flat_reader)
    set_reader_roi(dark_reader)


def _execute(args, sino_region=None):
    """Execute one pass with *sino_region* (from, to, step) which specifies which sinograms
    will be generated.
    """
    sched = Ufo.Scheduler()
    sched.set_properties(expand=False)
    g, reader = make_sino_graph(args, sino_region=sino_region)
    sched.run(g)

    return reader.props.total_height


def make_sino_graph(args, sino_region=None):
    """Create a graph for sinograms generation. *args* are static arguments and *region* is used to
    determine the number of sinograms in terms of (from, to, step) in this pass.
    """
    if args.region:
        check_input(args.input, args.region)
        region = range_from(args.region)
        proj_count = len(range(*region))
    else:
        proj_count = len(glob.glob(args.input))

    pm = Ufo.PluginManager()
    g = Ufo.TaskGraph()

    proj_reader = pm.get_task('reader')
    set_reader(proj_reader, args.input, region=args.region)
    # Setup projection downsampling
    if sino_region and sino_region[-1] > 1:
        proj_down = pm.get_task('downsample')
        # Do not assume anything about the downsampler
        proj_down.props.x_factor = 1
        proj_down.props.y_factor = sino_region[-1]

    writer = pm.get_task('writer')
    writer.set_properties(filename='{0}'.format(args.output), append=bool(args.chunk))

    sinogen = pm.get_task('sino-generator')
    sinogen.set_properties(num_projections=proj_count)

    flat_reader = None
    dark_reader = None
    if args.flats and args.darks:
        # Read flat fields
        flat_reader = pm.get_task('reader')
        flat_reader.set_properties(path=args.flats)

        flat_avg = pm.get_task('averager')
        flat_avg.set_properties(num_generate=proj_count)

        # Read dark fields
        dark_reader = pm.get_task('reader')
        dark_reader.set_properties(path=args.darks)

        dark_avg = pm.get_task('averager')
        dark_avg.set_properties(num_generate=proj_count)

        # Setup flat-field correction
        ffc = pm.get_task('flat-field-correction')

        # Setup projection downsampling
        if sino_region and sino_region[-1] > 1:
            flat_down = pm.get_task('downsample')
            dark_down = pm.get_task('downsample')
            flat_down.props.x_factor = 1
            flat_down.props.y_factor = sino_region[-1]
            dark_down.props.x_factor = 1
            dark_down.props.y_factor = sino_region[-1]

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
        if sino_region and sino_region[-1] > 1:
            g.connect_nodes(proj_reader, proj_down)
            g.connect_nodes(proj_down, sinogen)
        else:
            g.connect_nodes(proj_reader, sinogen)

    g.connect_nodes(sinogen, writer)

    if sino_region:
        _set_pass(sino_region, proj_reader, flat_reader=flat_reader, dark_reader=dark_reader)

    return g, proj_reader


def make_sinos(args):
    """Make the sinograms with arguments provided by *args*."""
    if args.sino_region:
        sino_region = range_from(args.sino_region)
        if not args.chunk:
            _execute(args, sino_region=sino_region)
    elif args.chunk:
        # No range specified, we have to ask the graph itself for image height
        height = _execute(args, sino_region=(0, args.chunk, 1))
        sino_region = (args.chunk, height, 1)
    else:
        _execute(args)

    if args.chunk:
        # Chunk is stretched in order to point to correct absolute positions
        # when step in the range is specified
        chunk = args.chunk * sino_region[2]
        # Starts are indices specifying the row at which to start
        starts = range(*(sino_region[0], sino_region[1], chunk)) + [sino_region[1]]
        for i in range(len(starts) - 1):
            subregion = (starts[i], starts[i + 1], sino_region[2])
            _execute(args, sino_region=subregion)
