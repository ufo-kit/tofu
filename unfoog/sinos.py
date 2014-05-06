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


def make_sinos(args):
    """Make the sinograms with arguments provided by *args*."""
    pm = Ufo.PluginManager()
    g = Ufo.TaskGraph()

    proj_path, proj_nth, proj_count = split_extended_path(args.input)
    proj_reader = pm.get_task('reader')
    proj_reader.set_properties(path=proj_path, nth=proj_nth, count=proj_count)

    writer = pm.get_task('writer')
    writer.set_properties(filename='{0}'.format(args.output))

    sinogen = pm.get_task('sino-generator')
    sinogen.set_properties(num_projections=proj_count)

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

    # Execute the graph
    sched = Ufo.Scheduler()
    sched.set_task_expansion(False)
    sched.run(g)
