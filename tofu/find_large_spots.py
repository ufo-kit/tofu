import logging
from gi.repository import Ufo
from tofu.util import set_node_props, determine_shape, setup_read_task, setup_padding
from tofu.tasks import get_task, get_writer


LOG = logging.getLogger(__name__)


def find_large_spots(args):
    graph = Ufo.TaskGraph()
    sched = Ufo.FixedScheduler()
    reader = get_task('read')
    writer = get_writer(args)
    if args.gauss_sigma and args.blurred_output:
        broadcast = Ufo.CopyTask()
        blurred_writer = get_task('write')
        if hasattr(blurred_writer.props, 'bytes_per_file'):
            blurred_writer.props.bytes_per_file = 0
        if hasattr(blurred_writer.props, 'tiff_bigtiff'):
            blurred_writer.props.tiff_bigtiff = False
        blurred_writer.props.filename = args.blurred_output

    find = get_task('find-large-spots')
    set_node_props(find, args)
    find.props.addressing_mode = args.find_large_spots_padding_mode

    set_node_props(reader, args)
    setup_read_task(reader, args.images, args)
    if args.gauss_sigma:
        reader_2 = get_task('read')
        set_node_props(reader_2, args)
        setup_read_task(reader_2, args.images, args)
        pad = get_task('pad')
        crop = get_task('crop')
        opencl = get_task('opencl', kernel='diff', filename='opencl.cl')

        width, height = determine_shape(args, path=args.images)
        gauss_size = int(10 * args.gauss_sigma)
        setup_padding(pad, width, height, args.find_large_spots_padding_mode,
                      crop=crop, pad_width=gauss_size, pad_height=gauss_size)
        LOG.debug("Gauss size: %d", gauss_size)
        blur = get_task('blur', sigma=args.gauss_sigma, size=gauss_size)
        graph.connect_nodes_full(reader, opencl, 0)
        graph.connect_nodes(reader_2, pad)
        graph.connect_nodes(pad, blur)
        graph.connect_nodes(blur, crop)
        graph.connect_nodes_full(crop, opencl, 1)
        if args.blurred_output:
            graph.connect_nodes(opencl, broadcast)
            graph.connect_nodes(broadcast, blurred_writer)
            source = broadcast
        else:
            source = opencl
        graph.connect_nodes(source, find)
    else:
        graph.connect_nodes(reader, find)

    graph.connect_nodes(find, writer)
    sched.run(graph)
