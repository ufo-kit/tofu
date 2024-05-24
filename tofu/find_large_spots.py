import logging
from gi.repository import Ufo
from tofu.util import (
    get_filtering_padding,
    set_node_props,
    determine_shape,
    read_image,
    setup_read_task,
    setup_padding
)
from tofu.tasks import get_task, get_writer


LOG = logging.getLogger(__name__)


def find_large_spots_median(args):
    import numpy as np
    import skimage.morphology as sm
    import tifffile
    from skimage.filters import median
    from skimage.measure import label
    from skimage.restoration import estimate_sigma
    from scipy.ndimage import binary_fill_holes

    images = read_image(args.images, allow_multi=True)
    if args.averaging_mode == "first":
        image = images[0]
    if args.averaging_mode == "mean":
        image = np.mean(images, axis=0)
    if args.averaging_mode == "median":
        image = np.median(images, axis=0)

    mask = np.zeros_like(image, dtype=np.uint8)

    if args.median_direction == 'both':
        kernel = sm.disk(args.median_width // 2)
    else:
        kernel = np.ones(args.median_width)
        if args.median_direction == 'vertical':
            kernel = kernel[:, np.newaxis]
        else:
            kernel = kernel[np.newaxis]

    med = median(image, kernel)
    diff = image.astype(float) - med
    if args.spot_threshold_mode == "absolute":
        diff = np.abs(diff)
    elif args.spot_threshold_mode == "below":
        diff = -diff

    if args.blurred_output:
        tifffile.imsave(args.blurred_output, diff.astype(image.dtype))

    if args.spot_threshold == 0:
        hist, bins = np.histogram(diff, bins=256)
        pdf = hist / diff.size
        args.spot_threshold = bins[np.where(np.cumsum(pdf) > 0.99)][0]
        LOG.info(f"Automatically determined spot-threshold: {args.spot_threshold}")

    if args.grow_threshold == 0:
        # 4.29 for FWTM
        args.grow_threshold = 4.29 * estimate_sigma(diff)
        LOG.info(f"Automatically determined grow-threshold: {args.grow_threshold}")

    # First, pixels which are above threshold are marked
    mask[diff > args.spot_threshold] = 1
    label_high = label(mask)

    # Then the ones which are connected to the bright ones and above a lower threshold
    mask_low = np.zeros_like(mask)
    mask_low[diff > args.grow_threshold] = 1
    label_low = label(mask_low)
    mask_low[:] = 0

    for i in range(1, label_high.max() + 1):
        indices = np.where(label_high == i)
        low_i = label_low[indices].max()
        low_indices = np.where(label_low == low_i)
        if len(low_indices[0]) <= args.max_spot_size:
            mask_low[low_indices] = 1

    mask = sm.dilation(mask_low, sm.disk(args.dilation_disk_radius))
    mask = binary_fill_holes(mask)

    tifffile.imsave(args.output, mask.astype(np.float32))


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
        width, height = determine_shape(args, path=args.images)
        pad = get_task('pad')
        crop = get_task('crop')

        if args.vertical_sigma:
            pad_width = 0
            pad_height = get_filtering_padding(height)
            fft = get_task('fft', dimensions=2)
            ifft = get_task('ifft', dimensions=2)
            filter_stripes = get_task(
                'filter-stripes',
                vertical_sigma=args.gauss_sigma,
                horizontal_sigma=0.0
            )

            graph.connect_nodes(reader, pad)
            if args.transpose_input:
                transpose = get_task('transpose')
                itranspose = get_task('transpose')
                graph.connect_nodes(pad, transpose)
                graph.connect_nodes(transpose, fft)
            else:
                graph.connect_nodes(pad, fft)
            graph.connect_nodes(fft, filter_stripes)
            graph.connect_nodes(filter_stripes, ifft)
            if args.transpose_input:
                graph.connect_nodes(ifft, itranspose)
                graph.connect_nodes(itranspose, crop)
            else:
                graph.connect_nodes(ifft, crop)
            last = crop
        else:
            reader_2 = get_task('read')
            set_node_props(reader_2, args)
            setup_read_task(reader_2, args.images, args)
            opencl = get_task('opencl', kernel='diff', filename='opencl.cl')
            gauss_size = int(10 * args.gauss_sigma)
            pad_width = pad_height = gauss_size
            LOG.debug("Gauss size: %d", gauss_size)
            blur = get_task('blur', sigma=args.gauss_sigma, size=gauss_size)
            graph.connect_nodes_full(reader, opencl, 0)
            graph.connect_nodes(reader_2, pad)
            graph.connect_nodes(pad, blur)
            graph.connect_nodes(blur, crop)
            graph.connect_nodes_full(crop, opencl, 1)
            last = opencl

        setup_padding(pad, width, height, args.find_large_spots_padding_mode,
                      crop=crop, pad_width=pad_width, pad_height=pad_height)

        if args.blurred_output:
            graph.connect_nodes(last, broadcast)
            graph.connect_nodes(broadcast, blurred_writer)
            source = broadcast
        else:
            source = last
        graph.connect_nodes(source, find)
    else:
        graph.connect_nodes(reader, find)

    graph.connect_nodes(find, writer)
    sched.run(graph)
