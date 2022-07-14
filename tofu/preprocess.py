"""Flat field correction."""
import sys
import logging
from gi.repository import Ufo
from tofu.util import (get_filenames, set_node_props, make_subargs,
                       determine_shape, setup_read_task,
                       setup_padding, next_power_of_two)
from tofu.tasks import get_task, get_writer


LOG = logging.getLogger(__name__)


def create_flat_correct_pipeline(args, graph, processing_node=None):
    """
    Create flat field correction pipeline. All the settings are provided in
    *args*. *graph* is used for making the connections. Returns the flat field
    correction task which can be used for further pipelining.
    """
    pm = Ufo.PluginManager()

    if args.projections is None or not args.flats or not args.darks:
        raise RuntimeError("You must specify --projections, --flats and --darks.")

    reader = get_task('read')
    dark_reader = get_task('read')
    flat_before_reader = get_task('read')

    ffc = get_task('flat-field-correct', processing_node=processing_node,
                   dark_scale=args.dark_scale,
                   flat_scale=args.flat_scale,
                   absorption_correct=args.absorptivity,
                   fix_nan_and_inf=args.fix_nan_and_inf)
    mode = args.reduction_mode.lower()
    roi_args = make_subargs(args, ['y', 'height', 'y_step'])
    set_node_props(reader, args)
    set_node_props(dark_reader, roi_args)
    set_node_props(flat_before_reader, roi_args)

    for r, path in ((reader, args.projections), (dark_reader, args.darks), (flat_before_reader, args.flats)):
        setup_read_task(r, path, args)

    LOG.debug("Doing flat field correction using reduction mode `{}'".format(mode))

    if args.flats2:
        flat_after_reader = get_task('read')
        setup_read_task(flat_after_reader, args.flats2, args)
        set_node_props(flat_after_reader, roi_args)
        num_files = len(get_filenames(args.projections))
        can_read = len(list(range(args.start, num_files, args.step)))
        number = args.number if args.number else num_files
        num_read = min(can_read, number)
        flat_interpolate = get_task('interpolate', processing_node=processing_node, number=num_read)

    if args.resize:
        LOG.debug("Resize input data by factor of {}".format(args.resize))
        proj_bin = get_task('bin', processing_node=processing_node, size=args.resize)
        dark_bin = get_task('bin', processing_node=processing_node, size=args.resize)
        flat_bin = get_task('bin', processing_node=processing_node, size=args.resize)
        graph.connect_nodes(reader, proj_bin)
        graph.connect_nodes(dark_reader, dark_bin)
        graph.connect_nodes(flat_before_reader, flat_bin)

        reader, dark_reader, flat_before_reader = proj_bin, dark_bin, flat_bin

        if args.flats2:
            flat_bin = get_task('bin', processing_node=processing_node, size=args.resize)
            graph.connect_nodes(flat_after_reader, flat_bin)
            flat_after_reader = flat_bin

    if mode == 'median':
        dark_stack = get_task('stack', processing_node=processing_node,
                              number=len(get_filenames(args.darks)))
        dark_reduced = get_task('flatten', processing_node=processing_node, mode='median')
        flat_before_stack = get_task('stack', processing_node=processing_node,
                                     number=len(get_filenames(args.flats)))
        flat_before_reduced = get_task('flatten', processing_node=processing_node, mode='median')

        graph.connect_nodes(dark_reader, dark_stack)
        graph.connect_nodes(dark_stack, dark_reduced)
        graph.connect_nodes(flat_before_reader, flat_before_stack)
        graph.connect_nodes(flat_before_stack, flat_before_reduced)

        if args.flats2:
            flat_after_stack = get_task('stack', processing_node=processing_node,
                                        number=len(get_filenames(args.flats2)))
            flat_after_reduced = get_task('flatten', processing_node=processing_node,
                                          mode='median')
            graph.connect_nodes(flat_after_reader, flat_after_stack)
            graph.connect_nodes(flat_after_stack, flat_after_reduced)
    elif mode == 'average':
        dark_reduced = get_task('average', processing_node=processing_node)
        flat_before_reduced = get_task('average', processing_node=processing_node)
        graph.connect_nodes(dark_reader, dark_reduced)
        graph.connect_nodes(flat_before_reader, flat_before_reduced)

        if args.flats2:
            flat_after_reduced = get_task('average', processing_node=processing_node)
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


def create_phase_retrieval_pipeline(args, graph, processing_node=None):
    LOG.debug('Creating phase retrieval pipeline')
    pm = Ufo.PluginManager()
    # Retrieve phase
    phase_retrieve = get_task('retrieve-phase', processing_node=processing_node)
    pad_phase_retrieve = get_task('pad', processing_node=processing_node)
    crop_phase_retrieve = get_task('crop', processing_node=processing_node)
    fft_phase_retrieve = get_task('fft', processing_node=processing_node)
    ifft_phase_retrieve = get_task('ifft', processing_node=processing_node)
    last = crop_phase_retrieve
    width = args.width
    height = args.height
    default_padded_width = next_power_of_two(width + 64)
    default_padded_height = next_power_of_two(height + 64)

    if not args.retrieval_padded_width:
        args.retrieval_padded_width = default_padded_width
    if not args.retrieval_padded_height:
        args.retrieval_padded_height = default_padded_height
    fmt = 'Phase retrieval padding: {}x{} -> {}x{}'
    LOG.debug(fmt.format(width, height, args.retrieval_padded_width,
                         args.retrieval_padded_height))
    x = (args.retrieval_padded_width - width) // 2
    y = (args.retrieval_padded_height - height) // 2
    pad_phase_retrieve.props.x = x
    pad_phase_retrieve.props.y = y
    pad_phase_retrieve.props.width = args.retrieval_padded_width
    pad_phase_retrieve.props.height = args.retrieval_padded_height
    pad_phase_retrieve.props.addressing_mode = args.retrieval_padding_mode
    crop_phase_retrieve.props.x = x
    crop_phase_retrieve.props.y = y
    crop_phase_retrieve.props.width = width
    crop_phase_retrieve.props.height = height
    phase_retrieve.props.method = args.retrieval_method
    phase_retrieve.props.energy = args.energy
    if len(args.propagation_distance) == 1:
        phase_retrieve.props.distance = [args.propagation_distance[0]]
    else:
        phase_retrieve.props.distance_x = args.propagation_distance[0]
        phase_retrieve.props.distance_y = args.propagation_distance[1]
    phase_retrieve.props.pixel_size = args.pixel_size
    phase_retrieve.props.regularization_rate = args.regularization_rate
    phase_retrieve.props.thresholding_rate = args.thresholding_rate
    phase_retrieve.props.frequency_cutoff = args.frequency_cutoff
    fft_phase_retrieve.props.dimensions = 2
    ifft_phase_retrieve.props.dimensions = 2

    graph.connect_nodes(pad_phase_retrieve, fft_phase_retrieve)
    graph.connect_nodes(fft_phase_retrieve, phase_retrieve)
    graph.connect_nodes(phase_retrieve, ifft_phase_retrieve)
    graph.connect_nodes(ifft_phase_retrieve, crop_phase_retrieve)
    calculate = get_task('calculate', processing_node=processing_node)

    if args.delta is not None:
        import numpy as np
        lam = 6.62606896e-34 * 299792458 / (args.energy * 1.60217733e-16)
        thickness_conversion = -lam / (2 * np.pi * args.delta)
    else:
        thickness_conversion = 1

    if args.retrieval_method == 'tie':
        expression = '(isinf (v) || isnan (v) || (v <= 0)) ? 0.0f : -log ({} * v) * {{}}'
        # 2 for 0.5 factor in ufo-filters and alpha = 10^-R, so divide by 10^R
        expression = expression.format(2 / 10 ** args.regularization_rate)
        # The following converts the TIE result to the actual phase, which when multiplied by the
        # thickness_conversion gives the projected thickness
        thickness_conversion *= -10 ** args.regularization_rate / 2
        expression = expression.format(thickness_conversion)
    else:
        expression = '(isinf (v) || isnan (v)) ? 0.0f : v * {}'.format(thickness_conversion)
    calculate.props.expression = expression
    graph.connect_nodes(crop_phase_retrieve, calculate)
    last = calculate

    return (pad_phase_retrieve, last)


def run_flat_correct(args):
    graph = Ufo.TaskGraph()
    sched = Ufo.Scheduler()
    pm = Ufo.PluginManager()

    out_task = get_writer(args)
    flat_task = create_flat_correct_pipeline(args, graph)
    graph.connect_nodes(flat_task, out_task)
    sched.run(graph)


def create_sinogram_pipeline(args, graph):
    """Create sinogram generating pipeline based on arguments from *args*."""
    pm = Ufo.PluginManager()
    sinos = pm.get_task('transpose-projections')

    if args.number:
        region = (args.start, args.start + args.number, args.step)
        num_projections = len(list(range(*region)))
    else:
        num_projections = len(get_filenames(args.projections))

    sinos.props.number = num_projections

    if args.darks and args.flats:
        start = create_flat_correct_pipeline(args, graph)
    else:
        start = get_task('read')
        start.props.path = args.projections
        set_node_props(start, args)

    graph.connect_nodes(start, sinos)

    return sinos


def run_sinogram_generation(args):
    """Make the sinograms with arguments provided by *args*."""
    if not args.height:
        args.height = determine_shape(args, args.projections)[1] - args.y

    step = args.y_step * args.pass_size if args.pass_size else args.height
    starts = list(range(args.y, args.y + args.height, step)) + [args.y + args.height]

    def generate_partial(append=False):
        graph = Ufo.TaskGraph()
        sched = Ufo.Scheduler()

        args.output_append = append
        writer = get_writer(args)

        sinos = create_sinogram_pipeline(args, graph)
        graph.connect_nodes(sinos, writer)
        sched.run(graph)

    for i in range(len(starts) - 1):
        args.y = starts[i]
        args.height = starts[i + 1] - starts[i]
        generate_partial(append=i != 0)


def create_projection_filtering_pipeline(args, graph, processing_node=None):
    pm = Ufo.PluginManager()
    pad = get_task('pad', processing_node=processing_node)
    fft = get_task('fft', processing_node=processing_node)
    ifft = get_task('ifft', processing_node=processing_node)
    fltr = get_task('filter', processing_node=processing_node)
    if args.projection_crop_after == 'filter':
        crop = get_task('crop', processing_node=processing_node)
    else:
        crop = None

    padding_width = setup_padding(pad, args.width, args.height, args.projection_padding_mode,
                                  crop=crop)[0]
    fft.props.dimensions = 1
    ifft.props.dimensions = 1
    fltr.props.filter = args.projection_filter
    fltr.props.scale = args.projection_filter_scale
    fltr.props.cutoff = args.projection_filter_cutoff

    graph.connect_nodes(pad, fft)
    graph.connect_nodes(fft, fltr)
    graph.connect_nodes(fltr, ifft)
    if crop:
        graph.connect_nodes(ifft, crop)
        last = crop
    else:
        last = ifft

    return (pad, last)


def create_preprocessing_pipeline(args, graph, source=None, processing_node=None,
                                  cone_beam_weight=True, make_reader=True):
    """If *make_reader* is True, create a read task if *source* is None and no dark and flat fields
    are given.
    """
    import numpy as np
    if not (args.width and args.height):
        width, height = determine_shape(args, args.projections)
        if not width:
            raise RuntimeError("Could not determine width from the input")
    if not args.width:
        args.width = width
    if not args.height:
        args.height = height - args.y

    LOG.debug('Image width x height: %d x %d', args.width, args.height)

    current = None
    if source:
        current = source
    elif args.darks and args.flats:
        current = create_flat_correct_pipeline(args, graph, processing_node=processing_node)
    else:
        if make_reader:
            current = get_task('read')
            set_node_props(current, args)
            if not args.projections:
                raise RuntimeError('--projections not set')
            setup_read_task(current, args.projections, args)
        if args.absorptivity:
            absorptivity = get_task('calculate', processing_node=processing_node)
            absorptivity.props.expression = 'v <= 0 ? 0.0f : -log(v)'
            if current:
                graph.connect_nodes(current, absorptivity)
            current = absorptivity

    if args.transpose_input:
        transpose = get_task('transpose')
        if current:
            graph.connect_nodes(current, transpose)
        current = transpose
        tmp = args.width
        args.width = args.height
        args.height = tmp

    if cone_beam_weight and not np.all(np.isinf(args.source_position_y)):
        # Cone beam projection weight
        LOG.debug('Enabling cone beam weighting')
        weight = get_task('cone-beam-projection-weight', processing_node=processing_node)
        weight.props.source_distance = (-np.array(args.source_position_y)).tolist()
        weight.props.detector_distance = args.detector_position_y
        weight.props.center_position_x = args.center_position_x or [args.width / 2. + (args.width % 2) * 0.5]
        weight.props.center_position_z = args.center_position_z or [args.height / 2. + (args.height % 2) * 0.5]
        weight.props.axis_angle_x = args.axis_angle_x
        if current:
            graph.connect_nodes(current, weight)
        current = weight

    if args.energy is not None and args.propagation_distance is not None:
        pr_first, pr_last = create_phase_retrieval_pipeline(args, graph,
                                                            processing_node=processing_node)
        if current:
            graph.connect_nodes(current, pr_first)
        current = pr_last

    if args.projection_filter != 'none':
        pf_first, pf_last = create_projection_filtering_pipeline(args, graph,
                                                                 processing_node=processing_node)
        if current:
            graph.connect_nodes(current, pf_first)
        current = pf_last

    return current


def run_preprocessing(args):
    graph = Ufo.TaskGraph()
    sched = Ufo.Scheduler()
    pm = Ufo.PluginManager()

    out_task = get_writer(args)
    current = create_preprocessing_pipeline(args, graph)
    graph.connect_nodes(current, out_task)

    sched.run(graph)
