"""Visualize frequency filters produced by UFO preprocessing tasks."""
import copy
import logging
import sys

import gi
import numpy as np

try:
    gi.require_version('Ufo', '0.0')
except ValueError:
    gi.require_version('Ufo', '1.0')

from gi.repository import Ufo

from tofu import config
from tofu.tasks import get_memory_in, get_memory_out, get_task


LOG = logging.getLogger(__name__)
RESOURCES = None
METHOD_COLORS = {
    'tie': 'C0',
    'ctf': 'C1',
    'qp': 'C2',
    'qp2': 'C3',
    'ict': 'C4',
}


def is_power_of_two(value):
    return value > 0 and value & (value - 1) == 0


def powers_of_two(minimum=2, maximum=1048576):
    value = minimum
    while value <= maximum:
        yield value
        value <<= 1


def closest_power_of_two(value, minimum=2, maximum=1048576):
    values = list(powers_of_two(minimum=minimum, maximum=maximum))
    return min(values, key=lambda candidate: abs(candidate - value))


def _set_phase_retrieval_props(task, args):
    task.props.method = args.retrieval_method
    task.props.energy = args.energy
    if len(args.propagation_distance) == 1:
        task.props.distance = [args.propagation_distance[0]]
    else:
        task.props.distance_x = args.propagation_distance[0]
        task.props.distance_y = args.propagation_distance[1]
    task.props.pixel_size = args.pixel_size
    task.props.regularization_rate = args.regularization_rate
    task.props.thresholding_rate = args.thresholding_rate
    task.props.ict_alpha = args.ict_alpha
    task.props.ict_alpha_threshold = args.ict_alpha_threshold
    task.props.frequency_cutoff = args.frequency_cutoff
    task.props.output_filter = True


def validate_args(args):
    errors = []
    if args.width is None or args.width <= 0:
        errors.append("width must be greater than 0")
    elif not is_power_of_two(args.width):
        errors.append("width must be a power of 2")
    if args.height is None or args.height <= 0:
        errors.append("height must be greater than 0")
    elif not is_power_of_two(args.height):
        errors.append("height must be a power of 2")
    if args.energy is None or args.energy <= 0:
        errors.append("energy must be greater than 0")
    if args.pixel_size is None or args.pixel_size <= 0:
        errors.append("pixel size must be greater than 0")
    if args.propagation_distance is None:
        errors.append("distance must be specified")
    else:
        distances = tuple(args.propagation_distance)
        if len(distances) not in (1, 2):
            errors.append("distance must contain one value or x,y")
        elif any(distance <= 0 for distance in distances):
            errors.append("distance must be greater than 0")
    if errors:
        raise ValueError("; ".join(errors))


def validate_result_args(args):
    args = copy.deepcopy(args)
    args.width = 2
    args.height = 2
    validate_args(args)


def apply_tune_defaults(args):
    def option_was_given(name):
        option = '--{}'.format(name)
        return any(arg == option or arg.startswith(option + '=') for arg in sys.argv[1:])

    if getattr(args, 'width', None) is None and not option_was_given('width'):
        args.width = 1024
    if getattr(args, 'height', None) is None and not option_was_given('height'):
        args.height = 1024
    if getattr(args, 'energy', None) is None and not option_was_given('energy'):
        args.energy = 15
    if (getattr(args, 'propagation_distance', None) is None
            and not option_was_given('propagation-distance')):
        args.propagation_distance = (0.1,)
    if (getattr(args, 'ict_alpha_threshold', 0.0) == 0.0
            and not option_was_given('ict-alpha-threshold')):
        args.ict_alpha_threshold = 1e30
    if (getattr(args, 'frequency_cutoff', 1e30) == 1e30
            and not option_was_given('frequency-cutoff')):
        args.frequency_cutoff = 1e30
    if (getattr(args, 'sharpen_method', 'laplace') == 'laplace'
            and not option_was_given('sharpen-method')):
        args.sharpen_method = 'lorentz'


def get_single_tiff_sequence_info(path):
    from tofu.util import TiffSequenceReader, get_filenames

    filenames = get_filenames(path)
    if len(filenames) != 1 or not filenames[0].lower().endswith(('.tif', '.tiff')):
        return None

    with TiffSequenceReader(filenames[0]) as reader:
        image = reader.read(0)
        return {
            'number': reader.num_images,
            'height': image.shape[-2],
            'width': image.shape[-1],
        }


def _set_sharpening_props(task, args):
    task.props.method = args.sharpen_method
    task.props.strength = args.sharpen_strength
    task.props.lorentz_fwhm = args.sharpen_lorentz_fwhm
    task.props.max_boost = args.sharpen_max_boost


def create_tune_filter_graph(args, sharpen=False):
    """Create a UFO graph that writes the requested filter image to memory-out.

    The graph starts with a unit complex spectrum. ``retrieve-phase`` and,
    optionally, ``frequency-sharpen`` multiply that spectrum in frequency
    space. The memory-out buffer stores complex-interleaved values.
    """
    graph = Ufo.TaskGraph()

    spectrum = np.ones((args.height, args.width), dtype=np.complex64)
    source = get_memory_in(spectrum)
    retrieve_phase = get_task('retrieve-phase')
    memory_out = get_memory_out(2 * args.width, args.height)
    _set_phase_retrieval_props(retrieve_phase, args)
    retrieve_phase.props.output_filter = False

    graph.connect_nodes(source, retrieve_phase)
    previous = retrieve_phase

    if sharpen:
        sharpen_task = get_task('frequency-sharpen')
        _set_sharpening_props(sharpen_task, args)
        graph.connect_nodes(previous, sharpen_task)
        previous = sharpen_task

    graph.connect_nodes(previous, memory_out)

    return graph, memory_out


def get_filter_data(args, sharpen=False):
    """Run the visualization graph and return the memory-out NumPy array."""
    validate_args(args)

    global RESOURCES
    graph, memory_out = create_tune_filter_graph(args, sharpen=sharpen)
    scheduler = Ufo.Scheduler()
    if RESOURCES is None:
        RESOURCES = Ufo.Resources()
    scheduler.set_resources(RESOURCES)
    scheduler.run(graph)

    return np.array(memory_out.np_array, copy=True)


def get_filter_data_by_method(args):
    """Run one filter graph per selected phase-retrieval method."""
    methods = getattr(args, 'retrieval_methods', None)
    if methods is None:
        methods = [args.retrieval_method]
    result = {}
    for method in methods:
        method_args = copy.deepcopy(args)
        method_args.retrieval_method = method
        visibility = getattr(args, 'curve_visibility', {}).get(method, {})
        if not visibility:
            visibility = {'phase': True, 'sharpened': getattr(args, 'sharpen', False)}
        result[method] = {}
        if visibility.get('phase', True):
            result[method]['phase'] = get_filter_data(method_args, sharpen=False)
        if visibility.get('sharpened', False):
            result[method]['sharpened'] = get_filter_data(method_args, sharpen=True)

    return result


def _prepare_processing_args(args, sharpen):
    from tofu.util import determine_shape, next_power_of_two

    args = copy.deepcopy(args)
    args.sharpen = sharpen
    defaults = {
        'projection_filter': 'none',
        'projection_filter_scale': 1.0,
        'projection_filter_cutoff': 0.5,
        'projection_crop_after': 'backprojection',
        'retrieval_padded_width': 0,
        'retrieval_padded_height': 0,
        'retrieval_padding_mode': 'clamp_to_edge',
        'tie_approximate_logarithm': False,
        'tie_approximate_point': 0.75,
        'delta': None,
        'start': 0,
        'number': 1,
        'step': 1,
        'y': 0,
        'y_step': 1,
        'bitdepth': 32,
        'resize': None,
        'transpose_input': False,
        'darks': None,
        'flats': None,
    }
    for name, value in defaults.items():
        if not hasattr(args, name):
            setattr(args, name, value)
    if args.number is None:
        args.number = 1
    # Result processing follows the selected projection dimensions, not the
    # tune filter dimensions. The phase retrieval pipeline then pads
    # to power-of-two sizes before FFT.
    args.width = None
    args.height = None
    width, height = determine_shape(args, path=args.projections, do_raise=True)
    args.width = width
    args.height = height
    args.retrieval_padded_width = next_power_of_two(width)
    args.retrieval_padded_height = next_power_of_two(height)

    return args


def create_result_graph(args, sharpen=False, phase_retrieval=True):
    from tofu.preprocess import create_phase_retrieval_pipeline, create_preprocessing_pipeline
    from tofu.util import set_node_props, setup_read_task

    args = _prepare_processing_args(args, sharpen)
    if not phase_retrieval:
        args.energy = None
        args.propagation_distance = None
        args.absorptivity = True
    graph = Ufo.TaskGraph()
    memory_out = get_memory_out(args.width, args.height)
    if phase_retrieval:
        reader = get_task('read')
        set_node_props(reader, args)
        setup_read_task(reader, args.projections, args)
        first, last = create_phase_retrieval_pipeline(args, graph)
        graph.connect_nodes(reader, first)
        graph.connect_nodes(last, memory_out)
    else:
        last = create_preprocessing_pipeline(
            args, graph, cone_beam_weight=False)
        graph.connect_nodes(last, memory_out)

    return graph, memory_out


def get_result_data(args, sharpen=False, phase_retrieval=True):
    if phase_retrieval:
        validate_result_args(args)
    if not getattr(args, 'projections', None):
        raise ValueError("projections must be specified")

    global RESOURCES
    graph, memory_out = create_result_graph(
        args, sharpen=sharpen, phase_retrieval=phase_retrieval)
    scheduler = Ufo.Scheduler()
    if RESOURCES is None:
        RESOURCES = Ufo.Resources()
    scheduler.set_resources(RESOURCES)
    scheduler.run(graph)

    return np.array(memory_out.np_array, copy=True)


def get_result_data_by_method(args):
    methods = getattr(args, 'retrieval_methods', None)
    if methods is None:
        methods = [args.retrieval_method]
    if not methods:
        return {'absorption': {
            'phase': get_result_data(args, sharpen=False, phase_retrieval=False)
        }}
    result = {}
    for method in methods:
        method_args = copy.deepcopy(args)
        method_args.retrieval_method = method
        visibility = getattr(args, 'curve_visibility', {}).get(method, {})
        if not visibility:
            visibility = {'phase': True, 'sharpened': getattr(args, 'sharpen', False)}
        result[method] = {}
        if visibility.get('phase', True):
            result[method]['phase'] = get_result_data(method_args, sharpen=False)
        if visibility.get('sharpened', False):
            result[method]['sharpened'] = get_result_data(method_args, sharpen=True)

    return result


def get_reconstruction_projection_region(reco_args, width, height, slice_number):
    from tofu import genreco

    geometry_args = copy.deepcopy(reco_args)
    geometry_args.width = width
    geometry_args.height = height
    geometry_args.center_position_z = [0.5]
    geometry_args.z = slice_number
    geometry_args.region = (slice_number, slice_number + 1, 1)
    genreco._fill_missing_args(geometry_args)
    genreco._convert_angles_to_rad(geometry_args)
    geometry = genreco.CTGeometry(geometry_args)
    xmin, ymin, xmax, ymax = geometry.compute_height(region=geometry_args.region)

    return int(xmin), int(ymin), int(xmax), int(ymax)


def _prepare_reconstruction_args(args, sharpen, phase_retrieval=True):
    from tofu import config
    from tofu.util import determine_shape, next_power_of_two

    reco_args = config.Params(sections=config.GEN_RECO_PARAMS).get_defaults()
    for name, value in vars(args).items():
        setattr(reco_args, name, copy.deepcopy(value))

    reco_args.sharpen = sharpen if phase_retrieval else False
    reco_args.output = getattr(reco_args, 'output', 'tofu-tune-reco.tif')
    reco_args.output_bytes_per_file = 0
    reco_args.store_type = 'float'
    reco_args.result_type = 'float'
    reco_args.compute_type = 'float'
    reco_args.delta = 1e-6
    reco_args.retrieval_padding_mode = 'clamp_to_edge'
    reco_args.disable_projection_crop = True
    if not phase_retrieval:
        reco_args.energy = None
        reco_args.propagation_distance = None
        reco_args.absorptivity = True

    tiff_info = get_single_tiff_sequence_info(reco_args.projections)
    if tiff_info:
        if reco_args.number is None:
            reco_args.number = tiff_info['number']
    if phase_retrieval:
        distance = reco_args.propagation_distance[0]
        wavelength = get_wavelength(reco_args.energy)
        half_height = get_fresnel_required_half_height(
            reco_args.energy, distance, reco_args.pixel_size)
    else:
        distance = None
        wavelength = None
        half_height = 0
    slice_number = getattr(reco_args, 'reconstruction_slice', 0)
    reco_args.width = None
    reco_args.height = None
    width, height = determine_shape(reco_args, path=reco_args.projections, do_raise=True)
    if height <= 0:
        raise ValueError("projection height must be greater than 0")
    if slice_number < 0 or slice_number >= height:
        raise ValueError(
            "requested reconstruction slice {} is outside the projection height "
            "range [0, {})".format(slice_number, height))
    projection_xmin, projection_ymin, projection_xmax, projection_ymax = (
        get_reconstruction_projection_region(reco_args, width, height, slice_number))
    required_y = projection_ymin - half_height
    required_stop = projection_ymax + half_height - (1 if phase_retrieval else 0)
    missing_before = max(0, -required_y)
    missing_after = max(0, required_stop - height)
    if missing_before or missing_after:
        margin_name = "phase-retrieval margin" if phase_retrieval else "geometry projection region"
        LOG.warning(
            "Cannot read the full vertical %s around the "
            "geometry projection region for slice %d: projection_y=%d:%d, "
            "half_height=%d, projection_height=%d, missing_before=%d px, "
            "missing_after=%d px. Clamping the read window to the data range.",
            margin_name, slice_number, projection_ymin, projection_ymax, half_height,
            height, missing_before, missing_after)
    reader_y = min(max(required_y, 0), height)
    reader_stop = min(max(required_stop, reader_y + 1), height)
    reader_height = reader_stop - reader_y
    local_z = slice_number - reader_y
    reco_args.y = reader_y
    reco_args.height = reader_height
    reco_args.center_position_z = [0.5 - reader_y]
    reco_args.z = slice_number
    reco_args.width = width
    reco_args.retrieval_padded_width = next_power_of_two(width)
    reco_args.retrieval_padded_height = next_power_of_two(reco_args.height)

    reco_args.region = (slice_number, slice_number + 1, 1)
    LOG.debug(
        "Reconstruction vertical region: phase_retrieval=%s, wavelength=%s m, distance=%s m, "
        "pixel_size=%g m, fresnel_half_height=%d px, requested_slice=%d, "
        "projection_height=%d, geometry_projection_x=%d:%d, "
        "geometry_projection_y=%d:%d, required_reader_y=%d, "
        "required_reader_stop=%d, reader_y=%d, reader_height=%d, local_z=%d, "
        "center_position_z=%s, z=%s, region=%s",
        phase_retrieval, wavelength, distance, reco_args.pixel_size, half_height, slice_number,
        height, projection_xmin, projection_xmax, projection_ymin, projection_ymax,
        required_y, required_stop, reco_args.y, reco_args.height, local_z,
        reco_args.center_position_z, reco_args.z, reco_args.region)
    LOG.debug(
        "Reconstruction args: width=%d, number=%s, image_step=%s, "
        "retrieval_padded_width=%d, retrieval_padded_height=%d, "
        "retrieval_padding_mode=%s, disable_projection_crop=%s, "
        "overall_angle=%s, center_position_x=%s, axis_angle_x=%s, axis_angle_y=%s",
        reco_args.width, reco_args.number, getattr(reco_args, 'image_step', None),
        reco_args.retrieval_padded_width, reco_args.retrieval_padded_height,
        reco_args.retrieval_padding_mode, reco_args.disable_projection_crop,
        reco_args.overall_angle, reco_args.center_position_x,
        reco_args.axis_angle_x, reco_args.axis_angle_y)

    return reco_args


def create_reconstruction_graph(args, sharpen=False, gpu=None, phase_retrieval=True):
    from tofu import genreco
    from tofu.util import get_reconstructed_cube_shape, get_reconstruction_regions

    args = _prepare_reconstruction_args(args, sharpen, phase_retrieval=phase_retrieval)
    genreco._fill_missing_args(args)
    genreco._convert_angles_to_rad(args)
    LOG.debug(
        "Reconstruction angles after degree-to-radian conversion: "
        "overall_angle=%s, axis_angle_x=%s, axis_angle_y=%s",
        args.overall_angle, args.axis_angle_x, args.axis_angle_y)
    genreco.set_projection_filter_scale(args)
    x_region, y_region, z_region = get_reconstruction_regions(args, store=True, dtype=float)
    x_region = [float(value) for value in x_region]
    y_region = [float(value) for value in y_region]
    z_region = [float(value) for value in z_region]
    slice_width, slice_height, num_slices = get_reconstructed_cube_shape(
        x_region, y_region, z_region)
    if num_slices != 1:
        raise ValueError("reconstruction visualization expects exactly one slice")

    graph = Ufo.TaskGraph()
    _source, backproject = genreco.setup_graph(
        args, graph, x_region, y_region, z_region, gpu=gpu, do_output=False)
    memory_out = get_memory_out(slice_width, slice_height)
    graph.connect_nodes(backproject, memory_out)

    return graph, memory_out


def get_reconstruction_data(args, sharpen=False, phase_retrieval=True):
    if phase_retrieval:
        validate_result_args(args)
    if not getattr(args, 'projections', None):
        raise ValueError("projections must be specified")

    global RESOURCES
    if RESOURCES is None:
        RESOURCES = Ufo.Resources()
    gpu_nodes = RESOURCES.get_gpu_nodes()
    if not gpu_nodes:
        raise RuntimeError("No UFO GPU nodes available")
    graph, memory_out = create_reconstruction_graph(
        args, sharpen=sharpen, gpu=gpu_nodes[0], phase_retrieval=phase_retrieval)
    scheduler = Ufo.FixedScheduler()
    scheduler.set_resources(RESOURCES)
    scheduler.run(graph)

    return np.array(memory_out.np_array, copy=True)


def get_reconstruction_data_by_method(args):
    methods = getattr(args, 'retrieval_methods', None)
    if methods is None:
        methods = [args.retrieval_method]
    if not methods:
        return {'absorption': {
            'phase': get_reconstruction_data(args, sharpen=False, phase_retrieval=False)
        }}
    result = {}
    for method in methods:
        method_args = copy.deepcopy(args)
        method_args.retrieval_method = method
        visibility = getattr(args, 'curve_visibility', {}).get(method, {})
        if not visibility:
            visibility = {'phase': True, 'sharpened': getattr(args, 'sharpen', False)}
        result[method] = {}
        if visibility.get('phase', True):
            result[method]['phase'] = get_reconstruction_data(method_args, sharpen=False)
        if visibility.get('sharpened', False):
            result[method]['sharpened'] = get_reconstruction_data(method_args, sharpen=True)

    return result


def plot_first_row(data, args=None, output=None, show=True):
    """Plot the first row of *data* and optionally save it to *output*."""
    import matplotlib.pyplot as plt

    x, row = get_first_half_frequency_row(data, args=args)
    fig, ax = plt.subplots()
    ax.plot(x, row)
    ax.set_xlabel(r"Fresnel phase $\pi \lambda d u^2$")
    ax.set_ylabel("Filter value")
    ax.set_title("Phase retrieval and sharpening filters")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()

    if output:
        fig.savefig(output)
        LOG.info("Saved plot to %s", output)
    if show:
        plt.show()

    return fig, ax


def get_wavelength(energy):
    return 6.62606896e-34 * 299792458 / (energy * 1.60217733e-16)


def get_fresnel_required_half_height(energy, distance, pixel_size):
    fresnel_length = get_wavelength(energy) * distance / (2 * pixel_size ** 2)

    return max(16, int(np.ceil(fresnel_length)))


def get_ict_argument(frequencies, args):
    if args is None or args.energy is None or args.propagation_distance is None:
        return frequencies
    distance = args.propagation_distance[0]
    wavelength = get_wavelength(args.energy)

    return np.pi * wavelength * distance * frequencies * frequencies / (args.pixel_size ** 2)


def get_max_ict_argument(energy, distance, pixel_size):
    wavelength = get_wavelength(energy)

    return np.pi * wavelength * distance * 0.25 / (pixel_size ** 2)


def get_first_half_frequency_row(data, args=None):
    """Return x/y values for the positive half of the filter row."""
    real_row = data[0, ::2]
    row = real_row[:real_row.size // 2]
    frequencies = np.linspace(0.0, 0.5, row.size, endpoint=False)
    x = get_ict_argument(frequencies, args)

    return x, row


def get_percentile_levels(data, lower=0.5, upper=99.5):
    finite = np.asarray(data)[np.isfinite(data)]
    if finite.size == 0:
        return None
    low, high = np.percentile(finite, (lower, upper))
    if not np.isfinite(low) or not np.isfinite(high):
        return None
    if low == high:
        span = abs(low) * 1e-6 or 1.0
        low -= span
        high += span

    return float(low), float(high)


def get_parameter_help(name, preferred_sections=()):
    key = name.replace('_', '-')
    sections = list(preferred_sections) + [
        section for section in config.SECTIONS if section not in preferred_sections
    ]
    for section in sections:
        params = config.SECTIONS[section]
        if key in params:
            return params[key].get('help')

    return None


def set_parameter_tooltip(widget, name, preferred_sections=()):
    tooltip = get_parameter_help(name, preferred_sections=preferred_sections)
    if tooltip:
        widget.setToolTip(tooltip)


def format_region(region):
    def format_value(value):
        value = float(value)
        if value.is_integer():
            return str(int(value))

        return "{:.6g}".format(value)

    return ",".join(format_value(value) for value in region)


def format_scalar(value, default=0.0):
    if value is None:
        value = default
    elif isinstance(value, (list, tuple, np.ndarray)):
        value = value[0] if len(value) else default
    value = float(value)
    if value.is_integer():
        return str(int(value))

    return "{:.6g}".format(value)


def parse_region(text, name):
    parts = [part.strip() for part in text.split(',')]
    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError("{} must be specified as from,to,step".format(name))
    try:
        region = tuple(float(part) for part in parts)
    except ValueError:
        raise ValueError("{} must contain numeric from,to,step values".format(name))
    if region[2] == 0:
        raise ValueError("{} step must not be zero".format(name))
    if region[1] == -1:
        return region
    if not len(np.arange(*region)):
        raise ValueError("{} does not select any pixels".format(name))

    return region


def make_default_region(length):
    return (-float(length / 2), float(length / 2 + length % 2), 1.0)


def expand_display_region(region, length):
    if region[1] == -1:
        return make_default_region(length)

    return tuple(float(value) for value in region)


def reset_profile_line_roi(roi, width, height):
    previous = roi.blockSignals(True)
    y = max((height - 1) / 2.0, 0.0)
    state = roi.saveState()
    state['pos'] = (0, 0)
    state['points'] = [(0, y), (max(width - 1, 0), y)]
    roi.setState(state)
    roi.blockSignals(previous)


def make_profile_line_roi(pg, positions, pen):
    from PyQt5 import QtCore

    class ProfileLineROI(pg.LineSegmentROI):
        def movePoint(self, handle, pos, modifiers=None, finish=True, coords='parent'):
            if modifiers is None:
                modifiers = QtCore.Qt.KeyboardModifier.NoModifier
            if modifiers & QtCore.Qt.KeyboardModifier.ShiftModifier:
                try:
                    index = self.indexOfHandle(handle)
                except IndexError:
                    index = None
                if index in (0, 1):
                    point = pg.Point(pos)
                    if coords == 'scene':
                        point = self.mapSceneToParent(point)
                    elif coords != 'parent':
                        raise Exception("New point location must be given in either "
                                        "'parent' or 'scene' coordinates.")

                    other = self.mapToParent(self.getHandles()[1 - index].pos())
                    dx = point.x() - other.x()
                    dy = point.y() - other.y()
                    if abs(dx) >= abs(dy):
                        point.setY(other.y())
                    else:
                        point.setX(other.x())

                    pos = point
                    coords = 'parent'

            return super().movePoint(handle, pos, modifiers, finish=finish, coords=coords)

    return ProfileLineROI(positions, pen=pen)


class FloatSlider:
    """Small helper around a QSlider for floating point values."""
    LABEL_WIDTH = 135
    VALUE_WIDTH = 88
    SLIDER_MIN_WIDTH = 160

    def __init__(self, parent, layout, label, attr, minimum, maximum, steps=1000,
                 scale='linear', display=None, tooltip=None):
        from PyQt5 import QtCore, QtGui, QtWidgets

        self.value_changed = parent.value_changed
        self.attr = attr
        self.minimum = minimum
        self.maximum = maximum
        self.steps = steps
        self.scale = scale
        self.display = display or (lambda value: "{:.6g}".format(value))
        self._updating = False
        self._follow_maximum = False
        self.label = QtWidgets.QLabel(label)
        self.label.setFixedWidth(self.LABEL_WIDTH)
        self.label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.value_edit = QtWidgets.QLineEdit()
        self.value_edit.setFixedWidth(self.VALUE_WIDTH)
        self.value_edit.setAlignment(QtCore.Qt.AlignRight)
        self.validator = QtGui.QDoubleValidator()
        self.validator.setNotation(QtGui.QDoubleValidator.ScientificNotation)
        self.value_edit.setValidator(self.validator)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, steps)
        self.slider.setMinimumWidth(self.SLIDER_MIN_WIDTH)
        self.slider.valueChanged.connect(self.on_slider_changed)
        self.value_edit.textEdited.connect(self.on_text_edited)
        self.value_edit.returnPressed.connect(self.on_editing_finished)
        if tooltip:
            for widget in (self.label, self.value_edit, self.slider):
                widget.setToolTip(tooltip)

        row = QtWidgets.QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        row.addWidget(self.label)
        row.addWidget(self.slider, 1)
        row.addWidget(self.value_edit)
        layout.addLayout(row)

    def slider_value(self):
        fraction = self.slider.value() / self.steps
        if self.scale == 'log':
            log_min = np.log10(self.minimum)
            log_max = np.log10(self.maximum)
            return 10 ** (log_min + fraction * (log_max - log_min))

        return self.minimum + fraction * (self.maximum - self.minimum)

    def raw_value(self):
        try:
            return float(self.value_edit.text())
        except ValueError:
            return self.slider_value()

    def value(self):
        return min(max(self.raw_value(), self.minimum), self.maximum)

    def set_value(self, value):
        if value is None:
            value = self.minimum
        self._follow_maximum = float(value) > self.maximum
        value = min(max(float(value), self.minimum), self.maximum)
        self._set_slider_from_value(value)
        self.value_edit.setText(self.display(value))

    def set_range(self, minimum, maximum):
        value = self.raw_value()
        at_upper_end = value >= self.maximum
        follow_maximum = self._follow_maximum or at_upper_end
        self.minimum = minimum
        self.maximum = maximum
        if follow_maximum:
            value = maximum
        self.set_value(min(max(value, minimum), maximum))
        self._follow_maximum = follow_maximum

    def _set_slider_from_value(self, value):
        if self.scale == 'log':
            fraction = ((np.log10(value) - np.log10(self.minimum)) /
                        (np.log10(self.maximum) - np.log10(self.minimum)))
        else:
            fraction = (value - self.minimum) / (self.maximum - self.minimum)
        self._updating = True
        self.slider.setValue(round(fraction * self.steps))
        self._updating = False

    def on_slider_changed(self):
        if self._updating:
            return
        self._follow_maximum = False
        self.value_edit.setText(self.display(self.slider_value()))
        self.value_changed.emit()

    def on_text_edited(self, text):
        try:
            value = float(text)
        except ValueError:
            return
        self._follow_maximum = False
        if self.minimum <= value <= self.maximum:
            self._set_slider_from_value(value)

    def on_editing_finished(self):
        self.value_changed.emit()


class FilterWorker:
    """Run one UFO filter computation on a background QThread."""
    def __init__(self, args, request_id):
        from PyQt5 import QtCore

        class Worker(QtCore.QObject):
            finished = QtCore.pyqtSignal(int, object)
            failed = QtCore.pyqtSignal(int, str)

            def run(self):
                try:
                    self.finished.emit(request_id, get_filter_data_by_method(args))
                except Exception as exc:
                    self.failed.emit(request_id, str(exc))

        self.thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)


class ResultWorker:
    """Run one projection-processing request on a background QThread."""
    def __init__(self, args, request_id):
        from PyQt5 import QtCore

        class Worker(QtCore.QObject):
            finished = QtCore.pyqtSignal(int, object)
            failed = QtCore.pyqtSignal(int, str)

            def run(self):
                try:
                    self.finished.emit(request_id, get_result_data_by_method(args))
                except Exception as exc:
                    self.failed.emit(request_id, str(exc))

        self.thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)


class ReconstructionWorker:
    """Run one reconstructed-slice request on a background QThread."""
    def __init__(self, args, request_id):
        from PyQt5 import QtCore

        class Worker(QtCore.QObject):
            finished = QtCore.pyqtSignal(int, object)
            failed = QtCore.pyqtSignal(int, str)

            def run(self):
                try:
                    self.finished.emit(request_id, get_reconstruction_data_by_method(args))
                except Exception as exc:
                    self.failed.emit(request_id, str(exc))

        self.thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)


class InteractiveWindow:
    def __init__(self, args):
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
        from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
        from matplotlib.figure import Figure
        from PyQt5 import QtCore, QtWidgets

        class SignalEmitter(QtCore.QObject):
            value_changed = QtCore.pyqtSignal()

        self.args = copy.deepcopy(args)
        apply_tune_defaults(self.args)
        self._signals = SignalEmitter()
        self.value_changed = self._signals.value_changed
        self.value_changed.connect(self.schedule_update)
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        self.window = QtWidgets.QMainWindow()
        self.window.setWindowTitle("Tofu tune")
        self.window.closeEvent = self.on_main_window_close
        central = QtWidgets.QWidget()
        self.window.setCentralWidget(central)

        main_layout = QtWidgets.QHBoxLayout(central)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter)
        controls = QtWidgets.QWidget()
        controls.setMinimumWidth(390)
        controls_layout = QtWidgets.QVBoxLayout(controls)
        controls_layout.setContentsMargins(8, 8, 8, 8)
        controls_layout.setSpacing(8)
        splitter.addWidget(controls)

        self.figure = Figure(figsize=(7, 4))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self.window)
        self.axes = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.09, right=0.98, bottom=0.11, top=0.94)
        plot_widget = QtWidgets.QWidget()
        plot_layout = QtWidgets.QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self.canvas, 1)

        self.sliders = []
        self.sliders_by_attr = {}
        self.method_curve_buttons = {}
        self.sharpen_method_buttons = {}
        self._thread_refs = []
        self._busy = False
        self._pending = False
        self._request_id = 0
        self._last_data = None
        self._has_plot = False
        self._auto_xlim = None
        self._auto_ylim = None
        self._force_keep_view = False
        self._image_windows = []
        self._image_viewers = {}
        self._result_windows = []
        self._result_tabs = {}
        self._result_busy = False
        self._result_pending = False
        self._result_request_id = 0
        self._result_args = None
        self._last_result_data = None
        self._result_status = {}
        self._result_viewers = {}
        self._result_profile_plots = {}
        self._result_profile_rois = {}
        self._result_auto_level_windows = set()
        self._reco_windows = []
        self._reco_tabs = {}
        self._reco_status = {}
        self._reco_viewers = {}
        self._reco_profile_plots = {}
        self._reco_profile_rois = {}
        self._reco_region_rois = {}
        self._reco_busy = False
        self._reco_pending = False
        self._reco_request_id = 0
        self._reco_args = None
        self._last_reco_data = None
        self._last_reco_args = None
        self._current_reco_worker_args = None
        self._hide_reco_region_rois_on_next_update = False
        self._reco_auto_level_windows = set()
        self._syncing_image_view = False
        self._syncing_image_profile = False

        self.status = QtWidgets.QLabel()
        self.update_timer = QtCore.QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.setInterval(150)
        self.update_timer.timeout.connect(self.request_update)
        self.reco_update_timer = QtCore.QTimer()
        self.reco_update_timer.setSingleShot(True)
        self.reco_update_timer.setInterval(1000)
        self.reco_update_timer.timeout.connect(self.request_scheduled_reconstruction_update)

        self.view_tabs = QtWidgets.QTabWidget()
        self.view_tabs.addTab(plot_widget, "Filters")
        result_panel = self._create_image_data_panel(
            'result', "Select projections to show processed results",
            popout_title="Processed phase retrieval results")
        reco_panel = self._create_image_data_panel(
            'reco', "Select projections to show reconstructed slice",
            popout_title="Reconstructed phase retrieval results")
        self.result_view_index = self.view_tabs.addTab(result_panel, "Projection")
        self.reco_view_index = self.view_tabs.addTab(reco_panel, "Reconstruction")
        splitter.addWidget(self.view_tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([540, 1060])

        tabs = QtWidgets.QTabWidget()
        filter_tab = QtWidgets.QWidget()
        filter_tab_layout = QtWidgets.QVBoxLayout(filter_tab)
        filter_tab_layout.setContentsMargins(0, 0, 0, 0)
        filter_scroll = QtWidgets.QScrollArea()
        filter_scroll.setWidgetResizable(True)
        filter_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        filter_content = QtWidgets.QWidget()
        filter_layout = QtWidgets.QVBoxLayout(filter_content)
        filter_layout.setContentsMargins(4, 4, 4, 4)
        filter_layout.setSpacing(10)
        self._add_phase_controls(filter_layout)
        self._add_sharpening_controls(filter_layout)
        filter_layout.addStretch(1)
        self._add_size_controls(filter_layout)
        self._add_plot_controls(filter_layout)
        filter_scroll.setWidget(filter_content)
        filter_tab_layout.addWidget(filter_scroll)
        reco_tab = QtWidgets.QWidget()
        reco_tab_layout = QtWidgets.QVBoxLayout(reco_tab)
        reco_tab_layout.setContentsMargins(0, 0, 0, 0)
        reco_scroll = QtWidgets.QScrollArea()
        reco_scroll.setWidgetResizable(True)
        reco_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        reco_content = QtWidgets.QWidget()
        reco_layout = QtWidgets.QVBoxLayout(reco_content)
        self._add_reconstruction_controls(reco_layout)
        reco_layout.addStretch(1)
        reco_scroll.setWidget(reco_content)
        reco_tab_layout.addWidget(reco_scroll)
        tabs.addTab(filter_tab, "Filters")
        tabs.addTab(reco_tab, "Reconstruction")
        controls_layout.addWidget(tabs, 1)
        self._update_ict_range_sliders()
        controls_layout.addWidget(self.status)

        self.window.resize(1400, 820)
        self.window.show()
        self.schedule_update()

    def _add_size_controls(self, layout):
        from PyQt5 import QtCore, QtWidgets

        group = QtWidgets.QGroupBox("Dimensions")
        group_layout = QtWidgets.QFormLayout(group)
        group_layout.setContentsMargins(10, 8, 10, 10)
        group_layout.setHorizontalSpacing(10)
        group_layout.setVerticalSpacing(6)
        group_layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.width_box = QtWidgets.QComboBox()
        self.height_box = QtWidgets.QComboBox()
        self.width_box.setFixedWidth(FloatSlider.VALUE_WIDTH)
        self.height_box.setFixedWidth(FloatSlider.VALUE_WIDTH)
        for value in powers_of_two():
            self.width_box.addItem(str(value), value)
            self.height_box.addItem(str(value), value)
        self._set_size_box_value(self.width_box, self.args.width or 4096)
        self._set_size_box_value(self.height_box, self.args.height or 2048)
        self.width_box.currentIndexChanged.connect(self.schedule_update)
        self.height_box.currentIndexChanged.connect(self.schedule_update)
        set_parameter_tooltip(self.width_box, 'width', preferred_sections=('general',))
        set_parameter_tooltip(self.height_box, 'height', preferred_sections=('reading',))
        group_layout.addRow("Width", self.width_box)
        group_layout.addRow("Height", self.height_box)
        layout.addWidget(group)

    def _set_size_box_value(self, box, value):
        value = closest_power_of_two(value)
        index = box.findData(value)
        if index >= 0:
            box.setCurrentIndex(index)

    def _size_box_value(self, box):
        return int(box.currentData())

    def _add_plot_controls(self, layout):
        from PyQt5 import QtCore, QtGui, QtWidgets

        group = QtWidgets.QGroupBox("Plot")
        group_layout = QtWidgets.QFormLayout(group)
        group_layout.setContentsMargins(10, 8, 10, 10)
        group_layout.setHorizontalSpacing(10)
        group_layout.setVerticalSpacing(6)
        group_layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.fix_y_box = QtWidgets.QCheckBox("Fix Y limits")
        self.y_min_edit = QtWidgets.QLineEdit()
        self.y_max_edit = QtWidgets.QLineEdit()
        self.y_min_edit.setFixedWidth(FloatSlider.VALUE_WIDTH)
        self.y_max_edit.setFixedWidth(FloatSlider.VALUE_WIDTH)
        self.y_min_edit.setAlignment(QtCore.Qt.AlignRight)
        self.y_max_edit.setAlignment(QtCore.Qt.AlignRight)
        validator = QtGui.QDoubleValidator()
        validator.setNotation(QtGui.QDoubleValidator.ScientificNotation)
        self.y_min_edit.setValidator(validator)
        self.y_max_edit.setValidator(validator)
        self.y_min_edit.setText("0")
        self.y_max_edit.setText("1")
        self.fix_y_box.toggled.connect(self.redraw_last_plot)
        self.y_min_edit.returnPressed.connect(self.redraw_last_plot)
        self.y_max_edit.returnPressed.connect(self.redraw_last_plot)
        autoscale_button = QtWidgets.QPushButton("Autoscale view")
        autoscale_button.clicked.connect(self.autoscale_view)
        image_button = QtWidgets.QPushButton("Show 2D filters")
        image_button.clicked.connect(self.show_2d_filters)
        group_layout.addRow(self.fix_y_box)
        group_layout.addRow("Y min", self.y_min_edit)
        group_layout.addRow("Y max", self.y_max_edit)
        group_layout.addRow(autoscale_button)
        group_layout.addRow(image_button)
        layout.addWidget(group)

    def _add_phase_controls(self, layout):
        from PyQt5 import QtCore, QtWidgets

        group = QtWidgets.QGroupBox("Phase retrieval")
        group_layout = QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(10, 8, 10, 10)
        group_layout.setSpacing(8)
        methods = QtWidgets.QGroupBox("Curves")
        method_layout = QtWidgets.QGridLayout(methods)
        method_layout.setContentsMargins(10, 8, 10, 10)
        method_layout.setHorizontalSpacing(14)
        method_layout.setVerticalSpacing(4)
        method_layout.setColumnStretch(0, 1)
        method_layout.addWidget(QtWidgets.QLabel("Method"), 0, 0)
        phase_label = QtWidgets.QLabel("Phase")
        phase_label.setAlignment(QtCore.Qt.AlignCenter)
        sharpened_label = QtWidgets.QLabel("Sharpened")
        sharpened_label.setAlignment(QtCore.Qt.AlignCenter)
        method_layout.addWidget(phase_label, 0, 1)
        method_layout.addWidget(sharpened_label, 0, 2)
        for method in ('tie', 'ctf', 'qp', 'qp2', 'ict'):
            row = method_layout.rowCount()
            phase_button = QtWidgets.QCheckBox()
            sharpened_button = QtWidgets.QCheckBox()
            phase_button.toggled.connect(self.schedule_update)
            sharpened_button.toggled.connect(lambda _checked: self.schedule_update(preserve_view=True))
            method_layout.addWidget(QtWidgets.QLabel(method), row, 0)
            method_layout.addWidget(phase_button, row, 1, alignment=QtCore.Qt.AlignCenter)
            method_layout.addWidget(sharpened_button, row, 2, alignment=QtCore.Qt.AlignCenter)
            self.method_curve_buttons[method] = {
                'phase': phase_button,
                'sharpened': sharpened_button
            }
        buttons = self.method_curve_buttons.get(
            self.args.retrieval_method, self.method_curve_buttons['tie'])
        buttons['phase'].setChecked(True)
        if self.args.sharpen:
            buttons['sharpened'].setChecked(True)
        tooltip = get_parameter_help('retrieval-method', preferred_sections=('retrieve-phase',))
        if tooltip:
            methods.setToolTip(tooltip)
        group_layout.addWidget(methods)

        specs = (
            ("Energy [keV]", 'energy', 1.0, 100.0, 'linear'),
            ("Distance [m]", 'propagation_distance', 0.001, 2.0, 'linear'),
            ("Pixel size [m]", 'pixel_size', 1e-8, 1e-4, 'log'),
            ("log10(delta / beta)", 'regularization_rate', 0.0, 6.0, 'linear'),
            ("Thresholding", 'thresholding_rate', 0.0, 1.0, 'linear'),
            ("ICT alpha", 'ict_alpha', 1e-6, 1e6, 'log'),
            ("ICT alpha threshold", 'ict_alpha_threshold', 0.0, np.pi, 'linear'),
            ("Frequency cutoff", 'frequency_cutoff', 0.0, np.pi, 'linear'),
        )
        for label, attr, minimum, maximum, scale in specs:
            tooltip = get_parameter_help(attr, preferred_sections=('retrieve-phase',))
            slider = FloatSlider(self, group_layout, label, attr, minimum, maximum,
                                 scale=scale, tooltip=tooltip)
            value = getattr(self.args, attr)
            if attr == 'propagation_distance' and value is not None:
                value = value[0]
            slider.set_value(value)
            self.sliders.append(slider)
            self.sliders_by_attr[attr] = slider
        layout.addWidget(group)

    def _add_sharpening_controls(self, layout):
        from PyQt5 import QtWidgets

        group = QtWidgets.QGroupBox("Sharpening")
        group_layout = QtWidgets.QVBoxLayout(group)
        group_layout.setContentsMargins(10, 8, 10, 10)
        group_layout.setSpacing(8)

        methods = QtWidgets.QGroupBox("Method")
        set_parameter_tooltip(methods, 'sharpen-method', preferred_sections=('sharpening',))
        method_layout = QtWidgets.QHBoxLayout(methods)
        method_layout.setContentsMargins(10, 8, 10, 10)
        method_layout.setSpacing(12)
        for method in ('laplace', 'discrete-laplace', 'lorentz'):
            button = QtWidgets.QRadioButton(method)
            set_parameter_tooltip(button, 'sharpen-method', preferred_sections=('sharpening',))
            button.toggled.connect(self.schedule_update)
            method_layout.addWidget(button)
            self.sharpen_method_buttons[method] = button
        method_layout.addStretch(1)
        self.sharpen_method_buttons.get(
            self.args.sharpen_method, self.sharpen_method_buttons['laplace']).setChecked(True)
        group_layout.addWidget(methods)

        specs = (
            ("Strength", 'sharpen_strength', 0.0, 5.0, 'linear'),
            ("Lorentz FWHM", 'sharpen_lorentz_fwhm', 0.01, 10.0, 'linear'),
            ("Max boost", 'sharpen_max_boost', 0.0, 10.0, 'linear'),
        )
        for label, attr, minimum, maximum, scale in specs:
            tooltip = get_parameter_help(attr, preferred_sections=('sharpening',))
            slider = FloatSlider(self, group_layout, label, attr, minimum, maximum,
                                 scale=scale, tooltip=tooltip)
            slider.set_value(getattr(self.args, attr))
            self.sliders.append(slider)
            self.sliders_by_attr[attr] = slider
        layout.addWidget(group)

    def _add_reconstruction_controls(self, layout):
        from PyQt5 import QtGui, QtWidgets

        group = QtWidgets.QGroupBox("Reconstructed slice")
        group_layout = QtWidgets.QFormLayout(group)

        self.reco_path_label = QtWidgets.QLabel("No projections selected")
        self.reco_path_label.setWordWrap(True)
        choose_button = QtWidgets.QPushButton("Select projections...")
        choose_button.setToolTip("Flat-corrected projections in a single tif file")
        choose_button.clicked.connect(self.select_reconstruction_projections)
        show_button = QtWidgets.QPushButton("Show reconstructed slice")
        show_button.clicked.connect(self.show_reconstruction)
        self.reco_auto_update_box = QtWidgets.QCheckBox("Auto reconstruct on parameter change")
        self.reco_auto_update_box.setChecked(True)
        self.reco_auto_update_box.toggled.connect(self.schedule_update)

        self.reco_slice_box = self._make_spin_box(0, maximum=1000000000)
        self.reco_slice_box.setToolTip("Detector row to reconstruct")
        self.reco_slice_box.lineEdit().setToolTip(self.reco_slice_box.toolTip())
        self.reco_number_box = self._make_spin_box(getattr(self.args, 'number', None),
                                                   minimum=0, special="auto", param='number',
                                                   preferred_sections=('reading',))
        self.reco_image_step_box = self._make_spin_box(getattr(self.args, 'image_step', 1),
                                                       minimum=1, param='image-step',
                                                       preferred_sections=('reading',))

        double_validator = QtGui.QDoubleValidator()
        double_validator.setNotation(QtGui.QDoubleValidator.ScientificNotation)
        self.reco_center_x_edit = QtWidgets.QLineEdit()
        self.reco_overall_angle_edit = QtWidgets.QLineEdit()
        self.reco_axis_angle_x_edit = QtWidgets.QLineEdit(
            format_scalar(getattr(self.args, 'axis_angle_x', 0.0)))
        self.reco_axis_angle_y_edit = QtWidgets.QLineEdit(
            format_scalar(getattr(self.args, 'axis_angle_y', 0.0)))
        self.reco_x_region_edit = QtWidgets.QLineEdit(
            format_region(getattr(self.args, 'x_region', (0, -1, 1))))
        self.reco_y_region_edit = QtWidgets.QLineEdit(
            format_region(getattr(self.args, 'y_region', (0, -1, 1))))
        for edit in (self.reco_center_x_edit, self.reco_overall_angle_edit,
                     self.reco_axis_angle_x_edit, self.reco_axis_angle_y_edit):
            edit.setValidator(double_validator)
            edit.returnPressed.connect(self.schedule_update)
        for edit in (self.reco_x_region_edit, self.reco_y_region_edit):
            edit.returnPressed.connect(self.schedule_update)
        self.reco_center_x_edit.setPlaceholderText("auto")
        self.reco_overall_angle_edit.setText("180")
        set_parameter_tooltip(self.reco_center_x_edit, 'center-position-x',
                              preferred_sections=('cone-beam-weight',))
        set_parameter_tooltip(self.reco_overall_angle_edit, 'overall-angle',
                              preferred_sections=('general-reconstruction',))
        set_parameter_tooltip(self.reco_axis_angle_x_edit, 'axis-angle-x',
                              preferred_sections=('cone-beam-weight',
                                                  'general-reconstruction'))
        set_parameter_tooltip(self.reco_axis_angle_y_edit, 'axis-angle-y',
                              preferred_sections=('general-reconstruction',))
        set_parameter_tooltip(self.reco_x_region_edit, 'x-region',
                              preferred_sections=('general-reconstruction',))
        set_parameter_tooltip(self.reco_y_region_edit, 'y-region',
                              preferred_sections=('general-reconstruction',))

        reset_region_button = QtWidgets.QPushButton("Reset region")
        reset_region_button.clicked.connect(self.reset_reconstruction_region)

        group_layout.addRow(choose_button)
        group_layout.addRow("Projections", self.reco_path_label)
        group_layout.addRow(self.reco_auto_update_box)
        group_layout.addRow("Slice", self.reco_slice_box)
        group_layout.addRow("Number", self.reco_number_box)
        group_layout.addRow("Image step", self.reco_image_step_box)
        group_layout.addRow("Center X", self.reco_center_x_edit)
        group_layout.addRow("Overall angle [deg]", self.reco_overall_angle_edit)
        group_layout.addRow("Axis angle X [deg]", self.reco_axis_angle_x_edit)
        group_layout.addRow("Axis angle Y [deg]", self.reco_axis_angle_y_edit)
        group_layout.addRow("X region", self.reco_x_region_edit)
        group_layout.addRow("Y region", self.reco_y_region_edit)
        group_layout.addRow(reset_region_button)
        group_layout.addRow(show_button)
        layout.addWidget(group)

    def _make_spin_box(self, value, minimum=0, maximum=1000000000, special=None,
                       param=None, preferred_sections=()):
        from PyQt5 import QtWidgets

        box = QtWidgets.QSpinBox()
        box.setRange(minimum, maximum)
        box.setKeyboardTracking(False)
        if special is not None:
            box.setSpecialValueText(special)
        box.setValue(value if value is not None else minimum)
        box.lineEdit().returnPressed.connect(self.schedule_update)
        if param:
            set_parameter_tooltip(box, param, preferred_sections=preferred_sections)
            set_parameter_tooltip(box.lineEdit(), param, preferred_sections=preferred_sections)

        return box

    def _set_optional_size_box_value(self, box, value):
        index = box.findData(value)
        if index >= 0:
            box.setCurrentIndex(index)

    def _set_optional_spin_box_value(self, box, value):
        if value is None:
            return
        previous = box.blockSignals(True)
        box.setValue(value)
        box.blockSignals(previous)

    def _set_reconstruction_slice_height(self, height):
        previous = self.reco_slice_box.blockSignals(True)
        self.reco_slice_box.setRange(0, max(0, height - 1))
        self.reco_slice_box.setValue(height // 2)
        self.reco_slice_box.blockSignals(previous)

    def reset_reconstruction_region(self):
        self.reco_x_region_edit.setText("0,-1,1")
        self.reco_y_region_edit.setText("0,-1,1")
        self.reset_reconstruction_region_rois()
        self.schedule_update()

    def schedule_update(self, *args, preserve_view=False):
        if preserve_view:
            self._force_keep_view = True
        self.update_timer.start()
        if getattr(self, '_reco_args', None):
            if self.reco_auto_update_box.isChecked():
                self.reco_update_timer.start()
            else:
                self.reco_update_timer.stop()

    def request_scheduled_reconstruction_update(self):
        if not self._reco_args or not self.reco_auto_update_box.isChecked():
            return
        self.request_reconstruction_update(self._current_args())

    def _update_ict_range_sliders(self):
        energy = self.sliders_by_attr['energy'].raw_value()
        distance = self.sliders_by_attr['propagation_distance'].raw_value()
        pixel_size = self.sliders_by_attr['pixel_size'].raw_value()
        if energy <= 0 or distance <= 0 or pixel_size <= 0:
            return
        maximum = get_max_ict_argument(energy, distance, pixel_size)

        for attr in ('ict_alpha_threshold', 'frequency_cutoff'):
            self.sliders_by_attr[attr].set_range(0.0, maximum)

    def _current_args(self):
        self._update_ict_range_sliders()
        args = copy.deepcopy(self.args)
        args.width = self._size_box_value(self.width_box)
        args.height = self._size_box_value(self.height_box)
        selected_methods = []
        curve_visibility = {}
        for method, buttons in self.method_curve_buttons.items():
            show_phase = buttons['phase'].isChecked()
            show_sharpened = buttons['sharpened'].isChecked()
            curve_visibility[method] = {
                'phase': show_phase,
                'sharpened': show_sharpened
            }
            if show_phase or show_sharpened:
                selected_methods.append(method)
        args.retrieval_methods = selected_methods
        args.curve_visibility = curve_visibility
        if selected_methods:
            args.retrieval_method = selected_methods[0]
        for method, button in self.sharpen_method_buttons.items():
            if button.isChecked():
                args.sharpen_method = method
        for slider in self.sliders:
            value = slider.raw_value()
            if slider.attr == 'propagation_distance':
                value = (value,)
            setattr(args, slider.attr, value)

        return args

    def _optional_float(self, edit):
        text = edit.text().strip()
        if not text:
            return None
        return float(text)

    def _optional_spin_value(self, box):
        return None if box.value() == box.minimum() and box.specialValueText() else box.value()

    def _current_reconstruction_args(self, base_args=None):
        args = copy.deepcopy(base_args if base_args is not None else self._current_args())
        if self._reco_args:
            args.projections = self._reco_args.projections
        args.reconstruction_slice = self.reco_slice_box.value()
        args.number = self._optional_spin_value(self.reco_number_box)
        args.image_step = self.reco_image_step_box.value()
        center_x = self._optional_float(self.reco_center_x_edit)
        args.center_position_x = None if center_x is None else [center_x]
        args.center_position_z = [0.5]
        overall_angle = self._optional_float(self.reco_overall_angle_edit)
        args.overall_angle = overall_angle
        args.axis_angle_x = [self._optional_float(self.reco_axis_angle_x_edit) or 0.0]
        args.axis_angle_y = [self._optional_float(self.reco_axis_angle_y_edit) or 0.0]
        args.x_region = parse_region(self.reco_x_region_edit.text(), "x region")
        args.y_region = parse_region(self.reco_y_region_edit.text(), "y region")
        args.delta = 1e-6
        args.retrieval_padding_mode = 'clamp_to_edge'
        args.disable_projection_crop = True

        return args

    def request_update(self):
        self._pending_args = self._current_args()
        try:
            validate_args(self._pending_args)
        except ValueError as exc:
            self.status.setText(str(exc))
            self._pending = False
            return
        if self._busy:
            self._pending = True
        else:
            self._start_worker(self._pending_args)
        if self._result_args:
            self.request_result_update(self._pending_args)

    def _start_worker(self, args):
        self._busy = True
        self._pending = False
        self._request_id += 1
        request_id = self._request_id
        self.status.setText("Computing...")
        self._current_worker_args = args
        worker = FilterWorker(args, request_id)
        worker.worker.finished.connect(self.on_data_ready)
        worker.worker.failed.connect(self.on_failed)
        worker.thread.finished.connect(lambda: self._thread_refs.remove(worker)
                                       if worker in self._thread_refs else None)
        self._thread_refs.append(worker)
        worker.thread.start()

    def on_data_ready(self, request_id, data):
        if request_id == self._request_id:
            self.update_plot(data, self._current_worker_args)
        self._finish_worker()

    def on_failed(self, request_id, message):
        if request_id == self._request_id:
            self.status.setText(message)
        self._finish_worker()

    def _finish_worker(self):
        self._busy = False
        if self._pending:
            self._start_worker(self._pending_args)

    def request_result_update(self, args):
        if not self._result_args:
            return
        result_args = copy.deepcopy(args)
        result_args.projections = self._result_args.projections
        self._pending_result_args = result_args
        if self._result_busy:
            self._result_pending = True
            return
        self._start_result_worker(result_args)

    def _start_result_worker(self, args):
        self._result_busy = True
        self._result_pending = False
        self._result_request_id += 1
        request_id = self._result_request_id
        self.status.setText("Computing results...")
        for label in self._result_status.values():
            label.setText("Computing results...")
        worker = ResultWorker(args, request_id)
        worker.worker.finished.connect(self.on_result_data_ready)
        worker.worker.failed.connect(self.on_result_failed)
        worker.thread.finished.connect(lambda: self._thread_refs.remove(worker)
                                       if worker in self._thread_refs else None)
        self._thread_refs.append(worker)
        worker.thread.start()

    def on_result_data_ready(self, request_id, data):
        if request_id == self._result_request_id:
            self._last_result_data = data
            self.update_result_views()
        self._finish_result_worker()

    def on_result_failed(self, request_id, message):
        if request_id == self._result_request_id:
            self.status.setText(message)
            for label in self._result_status.values():
                label.setText(message)
        self._finish_result_worker()

    def _finish_result_worker(self):
        self._result_busy = False
        if self._result_pending:
            self._start_result_worker(self._pending_result_args)
        elif self._last_result_data is not None:
            self.status.setText("Ready")

    def request_reconstruction_update(self, args):
        if not self._reco_args:
            return
        try:
            reco_args = self._current_reconstruction_args(args)
        except ValueError as exc:
            self.status.setText(str(exc))
            for label in self._reco_status.values():
                label.setText(str(exc))
            return
        self._pending_reco_args = reco_args
        if self._reco_busy:
            self._reco_pending = True
            return
        self._start_reconstruction_worker(reco_args)

    def _start_reconstruction_worker(self, args):
        self._reco_busy = True
        self._reco_pending = False
        self._reco_request_id += 1
        request_id = self._reco_request_id
        self.status.setText("Computing reconstructed slice...")
        for label in self._reco_status.values():
            label.setText("Computing reconstructed slice...")
        self._current_reco_worker_args = copy.deepcopy(args)
        worker = ReconstructionWorker(args, request_id)
        worker.worker.finished.connect(self.on_reconstruction_data_ready)
        worker.worker.failed.connect(self.on_reconstruction_failed)
        worker.thread.finished.connect(lambda: self._thread_refs.remove(worker)
                                       if worker in self._thread_refs else None)
        self._thread_refs.append(worker)
        worker.thread.start()

    def on_reconstruction_data_ready(self, request_id, data):
        if request_id == self._reco_request_id:
            self._last_reco_data = data
            self._last_reco_args = self._current_reco_worker_args
            self.update_reconstruction_views()
        self._finish_reconstruction_worker()

    def on_reconstruction_failed(self, request_id, message):
        if request_id == self._reco_request_id:
            self.status.setText(message)
            for label in self._reco_status.values():
                label.setText(message)
        self._finish_reconstruction_worker()

    def _finish_reconstruction_worker(self):
        self._reco_busy = False
        if self._reco_pending:
            self._start_reconstruction_worker(self._pending_reco_args)
        elif self._last_reco_data is not None:
            self.status.setText("Ready")

    def update_plot(self, data_by_method, args):
        self._last_data = data_by_method
        self._last_args = copy.deepcopy(args)
        self.redraw_last_plot()
        self.update_2d_filter_views()
        self.status.setText("Ready")

    def redraw_last_plot(self):
        if self._last_data is None:
            return
        keep_x_limits = False
        keep_y_limits = False
        if self._has_plot:
            x_limits = self.axes.get_xlim()
            y_limits = self.axes.get_ylim()
            keep_x_limits = (
                self._force_keep_view or (
                    self._auto_xlim is not None and
                    not np.allclose(x_limits, self._auto_xlim)
                )
            )
            keep_y_limits = (
                self._force_keep_view or (
                    self._auto_ylim is not None and
                    not np.allclose(y_limits, self._auto_ylim)
                )
            )
        else:
            x_limits = y_limits = None
        self.axes.clear()
        if not self._last_data:
            self.axes.text(0.5, 0.5, "Select at least one phase retrieval method",
                           ha='center', va='center', transform=self.axes.transAxes)
            self._has_plot = False
            self._auto_xlim = None
            self._auto_ylim = None
            self._force_keep_view = False
        else:
            for method, curves in self._last_data.items():
                color = METHOD_COLORS.get(method)
                if 'phase' in curves:
                    x, row = get_first_half_frequency_row(curves['phase'], args=self._last_args)
                    self.axes.plot(x, row, color=color, label=method)
                if 'sharpened' in curves:
                    x, row = get_first_half_frequency_row(curves['sharpened'], args=self._last_args)
                    self.axes.plot(x, row, linestyle=':', color=color,
                                   label='{} sharpened'.format(method))
            self.axes.legend(loc='best')
        self.axes.set_xlabel(r"Fresnel phase $\pi \lambda d u^2$")
        self.axes.set_ylabel("Filter value")
        self.axes.set_title("Phase retrieval and sharpening filters")
        self.axes.grid(True, alpha=0.25)
        if self._last_data:
            self.axes.relim()
            self.axes.autoscale_view()
            new_auto_xlim = self.axes.get_xlim()
            new_auto_ylim = self.axes.get_ylim()
            if self.fix_y_box.isChecked():
                try:
                    y_min = float(self.y_min_edit.text())
                    y_max = float(self.y_max_edit.text())
                except ValueError:
                    y_min = y_max = None
                if y_min is not None and y_min < y_max:
                    self.axes.set_ylim(y_min, y_max)
            elif keep_y_limits:
                self.axes.set_ylim(y_limits)
            if keep_x_limits:
                self.axes.set_xlim(x_limits)
            self._auto_xlim = new_auto_xlim
            self._auto_ylim = new_auto_ylim
            self._force_keep_view = False
            self._has_plot = True
        self.canvas.draw_idle()

    def autoscale_view(self):
        self._has_plot = False
        self.redraw_last_plot()

    def show_2d_filters(self):
        if not self._last_data:
            self.status.setText("No filter data to display")
            return

        import pyqtgraph as pg
        from PyQt5 import QtWidgets

        window = QtWidgets.QWidget()
        window.setWindowTitle("2D phase retrieval and sharpening filters")
        layout = QtWidgets.QVBoxLayout(window)
        tabs = QtWidgets.QTabWidget()
        layout.addWidget(tabs)
        viewer_entries = []

        for method, curves in self._last_data.items():
            for curve_name, data in curves.items():
                image = np.fft.fftshift(data[:, ::2])
                view = pg.ImageView()
                view.setImage(image.T)
                view.getImageItem().resetTransform()
                view.getView().setAspectLocked(True, ratio=1)
                label = method if curve_name == 'phase' else '{} sharpened'.format(method)
                tab = QtWidgets.QWidget()
                tab_layout = QtWidgets.QVBoxLayout(tab)
                tab_layout.addWidget(view)
                tabs.addTab(tab, label)
                viewer_entries.append((method, curve_name, view))

        if tabs.count() == 0:
            self.status.setText("No visible filter curves to display")
            window.deleteLater()
            return

        window.resize(900, 700)
        window.show()
        self._image_windows.append(window)
        self._image_viewers[window] = viewer_entries
        window.destroyed.connect(lambda _obj: self._image_windows.remove(window)
                                 if window in self._image_windows else None)
        window.destroyed.connect(lambda _obj: self._image_viewers.pop(window, None))

    def select_reconstruction_projections(self):
        from PyQt5 import QtWidgets

        selected = self._select_projection_path(
            "Select projections for reconstruction",
            preferred=getattr(self._reco_args, 'projections', None))
        if not selected:
            return None
        old_reco_path = getattr(self._reco_args, 'projections', None)
        old_result_path = getattr(self._result_args, 'projections', None)
        if selected != old_reco_path or selected != old_result_path:
            self.reset_image_data_view('result')
            self.reset_image_data_view('reco')
        args = self._current_args()
        args.projections = selected
        tiff_info = get_single_tiff_sequence_info(selected)
        if tiff_info:
            self._set_optional_spin_box_value(self.reco_number_box, tiff_info['number'])
            self._set_reconstruction_slice_height(tiff_info['height'])
        self._reco_args = args
        result_args = self._current_args()
        result_args.projections = selected
        self._result_args = result_args
        self.reco_path_label.setText(selected)
        self.view_tabs.setCurrentIndex(self.result_view_index)
        self.request_result_update(result_args)
        return selected

    def _select_projection_path(self, title, preferred=None):
        from PyQt5 import QtWidgets

        dialog = QtWidgets.QFileDialog(self.window, title)
        dialog.setFileMode(QtWidgets.QFileDialog.AnyFile)
        if preferred:
            dialog.selectFile(preferred)
        elif self._reco_args and self._reco_args.projections:
            dialog.selectFile(self._reco_args.projections)
        elif self._result_args and self._result_args.projections:
            dialog.selectFile(self._result_args.projections)
        if not dialog.exec_():
            return None
        selected = dialog.selectedFiles()
        if not selected:
            return None
        return selected[0]

    def show_reconstruction(self):
        if not self._reco_args or not self._reco_args.projections:
            if not self.select_reconstruction_projections():
                return

        try:
            args = self._current_reconstruction_args(self._current_args())
        except ValueError as exc:
            self.status.setText(str(exc))
            for label in self._reco_status.values():
                label.setText(str(exc))
            return

        self.view_tabs.setCurrentIndex(self.reco_view_index)
        self.request_reconstruction_update(args)

    def _image_data(self, kind):
        return self._last_result_data if kind == 'result' else self._last_reco_data

    def _data_windows(self, kind):
        return self._result_windows if kind == 'result' else self._reco_windows

    def _data_tabs(self, kind):
        return self._result_tabs if kind == 'result' else self._reco_tabs

    def _data_status(self, kind):
        return self._result_status if kind == 'result' else self._reco_status

    def _data_viewers(self, kind):
        return self._result_viewers if kind == 'result' else self._reco_viewers

    def _data_profile_plots(self, kind):
        return self._result_profile_plots if kind == 'result' else self._reco_profile_plots

    def _data_profile_rois(self, kind):
        return self._result_profile_rois if kind == 'result' else self._reco_profile_rois

    def _data_region_rois(self, kind):
        return {} if kind == 'result' else self._reco_region_rois

    def _data_auto_level_windows(self, kind):
        return self._result_auto_level_windows if kind == 'result' else self._reco_auto_level_windows

    def reset_image_data_view(self, kind):
        if kind == 'result':
            self._last_result_data = None
            placeholder = "Select projections to show processed results"
        else:
            self._last_reco_data = None
            placeholder = "Select projections to show reconstructed slice"

        for window, tabs in list(self._data_tabs(kind).items()):
            viewers = self._data_viewers(kind).get(window, {})
            rois = self._data_profile_rois(kind).get(window, {})
            region_rois = self._data_region_rois(kind).get(window, {})
            for key, (view, tab) in list(viewers.items()):
                roi = rois.pop(key, None)
                if roi is not None:
                    view.getView().removeItem(roi)
                region_roi = region_rois.pop(key, None)
                if region_roi is not None:
                    view.getView().removeItem(region_roi)
                index = tabs.indexOf(tab)
                if index >= 0:
                    tabs.removeTab(index)
                tab.deleteLater()
            viewers.clear()
            region_rois.clear()
            plot = self._data_profile_plots(kind).get(window)
            if plot is not None:
                plot.clear()
            status = self._data_status(kind).get(window)
            if status is not None:
                status.setText(placeholder)
            self._data_auto_level_windows(kind).add(window)

    def _create_image_data_panel(self, kind, status_text, popout_title=None, window=None):
        from PyQt5 import QtCore, QtGui, QtWidgets
        import pyqtgraph as pg

        panel = QtWidgets.QWidget()
        key = window or panel
        layout = QtWidgets.QVBoxLayout(panel)
        status = QtWidgets.QLabel(status_text)
        header = QtWidgets.QHBoxLayout()
        levels_button = QtWidgets.QPushButton("Reset greyscale")
        levels_button.clicked.connect(lambda: self.reset_image_levels(kind, key))
        sync_button = QtWidgets.QPushButton("Sync all")
        sync_button.clicked.connect(lambda: self.sync_current_image_view(kind, key))
        tabs = QtWidgets.QTabWidget()
        tabs._tofu_tune_window = key
        tabs._tofu_tune_kind = kind
        profile_plot = pg.PlotWidget()
        profile_plot.setBackground('w')
        profile_plot.setMinimumHeight(150)
        profile_plot.setLabel('bottom', 'Distance [pixel]')
        profile_plot.setLabel('left', 'Grey value')
        profile_plot.showGrid(x=True, y=True, alpha=0.18)
        for axis_name in ('bottom', 'left'):
            axis = profile_plot.getAxis(axis_name)
            axis.setPen(pg.mkPen((90, 96, 105), width=1))
            axis.setTextPen(pg.mkPen((35, 39, 47)))
        tabs.currentChanged.connect(lambda _index: self.update_image_profile(kind, key))
        header.addWidget(status, 1)
        header.addWidget(levels_button)
        header.addWidget(sync_button)
        if popout_title:
            popout_button = QtWidgets.QPushButton("Pop out")
            popout_button.clicked.connect(
                lambda: self.pop_out_image_data_view(kind, popout_title, status.text()))
            header.addWidget(popout_button)
        layout.addLayout(header)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(tabs)
        splitter.addWidget(profile_plot)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([520, 160])
        layout.addWidget(splitter, 1)
        shortcut_parent = window or panel
        left_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Left), shortcut_parent)
        right_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Right), shortcut_parent)
        left_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        right_shortcut.setContext(QtCore.Qt.WidgetWithChildrenShortcut)
        left_shortcut.activated.connect(lambda: self.switch_image_tab(kind, key, -1))
        right_shortcut.activated.connect(lambda: self.switch_image_tab(kind, key, 1))
        panel._tofu_tune_shortcuts = [left_shortcut, right_shortcut]

        tabs_by_window = self._data_tabs(kind)
        status_by_window = self._data_status(kind)
        profile_plots = self._data_profile_plots(kind)
        auto_level_windows = self._data_auto_level_windows(kind)

        tabs_by_window[key] = tabs
        status_by_window[key] = status
        profile_plots[key] = profile_plot
        auto_level_windows.add(key)

        return panel

    def pop_out_image_data_view(self, kind, title, status_text):
        from PyQt5 import QtWidgets

        window = QtWidgets.QWidget()
        window.setWindowTitle(title)
        layout = QtWidgets.QVBoxLayout(window)
        panel = self._create_image_data_panel(kind, status_text, window=window)
        layout.addWidget(panel)
        window.resize(900, 700)
        window.show()

        windows = self._data_windows(kind)
        tabs_by_window = self._data_tabs(kind)
        status_by_window = self._data_status(kind)
        viewers_by_window = self._data_viewers(kind)
        profile_plots = self._data_profile_plots(kind)
        profile_rois = self._data_profile_rois(kind)
        region_rois = self._data_region_rois(kind)
        auto_level_windows = self._data_auto_level_windows(kind)

        windows.append(window)
        window.destroyed.connect(lambda _obj: windows.remove(window)
                                 if window in windows else None)
        window.destroyed.connect(lambda _obj: tabs_by_window.pop(window, None))
        window.destroyed.connect(lambda _obj: status_by_window.pop(window, None))
        window.destroyed.connect(lambda _obj: viewers_by_window.pop(window, None))
        window.destroyed.connect(lambda _obj: profile_plots.pop(window, None))
        window.destroyed.connect(lambda _obj: profile_rois.pop(window, None))
        window.destroyed.connect(lambda _obj: region_rois.pop(window, None))
        window.destroyed.connect(lambda _obj: auto_level_windows.discard(window))
        tabs = tabs_by_window.get(window)
        if tabs is not None and self._image_data(kind):
            self.populate_image_tabs(kind, tabs)

        return window

    def reset_image_levels(self, kind, window):
        key = self._current_image_key(kind, window)
        view, _viewers = self._current_image_view(kind, window)
        data_by_method = self._image_data(kind)
        if key is None or view is None or not data_by_method:
            self._data_auto_level_windows(kind).add(window)
            tabs = self._data_tabs(kind).get(window)
            if tabs is not None and data_by_method:
                self.populate_image_tabs(kind, tabs)
            return

        data = data_by_method.get(key[0], {}).get(key[1])
        levels = get_percentile_levels(data) if data is not None else None
        if levels is None:
            return
        self._syncing_image_view = True
        try:
            view.setLevels(*levels)
        finally:
            self._syncing_image_view = False
        self.sync_image_levels_from_view(kind, window, view)

    def apply_current_image_levels(self, kind, window):
        current_view, viewers = self._current_image_view(kind, window)
        if current_view is None:
            return

        self.sync_image_levels_from_view(kind, window, current_view)

    def sync_image_levels_from_view(self, kind, window, source_view):
        if self._syncing_image_view:
            return

        viewers = self._data_viewers(kind).get(window, {})
        self._syncing_image_view = True
        try:
            levels = source_view.getLevels()
            for view, _tab in viewers.values():
                if view is not source_view:
                    view.setLevels(*levels)
        finally:
            self._syncing_image_view = False

    def connect_image_level_sync(self, kind, window, view):
        histogram = view.getHistogramWidget()
        item = getattr(histogram, 'item', histogram)
        signals = (
            getattr(item, 'sigLevelsChanged', None),
            getattr(item, 'sigLevelChangeFinished', None),
        )
        for signal in signals:
            if signal is not None:
                signal.connect(lambda *args, sync_kind=kind, sync_window=window,
                               sync_view=view:
                               self.sync_image_levels_from_view(
                                   sync_kind, sync_window, sync_view))

    def sync_image_view_range_from_view(self, kind, window, source_view):
        if self._syncing_image_view:
            return

        viewers = self._data_viewers(kind).get(window, {})
        x_range, y_range = source_view.getView().viewRange()
        self._syncing_image_view = True
        try:
            for view, _tab in viewers.values():
                if view is not source_view:
                    view.getView().setRange(xRange=x_range, yRange=y_range, padding=0)
        finally:
            self._syncing_image_view = False

    def connect_image_view_range_sync(self, kind, window, view):
        view.getView().sigRangeChanged.connect(
            lambda *args, sync_kind=kind, sync_window=window, sync_view=view:
                self.sync_image_view_range_from_view(
                    sync_kind, sync_window, sync_view))

    def connect_image_view_sync(self, kind, window, view):
        self.connect_image_level_sync(kind, window, view)
        self.connect_image_view_range_sync(kind, window, view)

    def apply_current_image_view(self, kind, window):
        current_view, viewers = self._current_image_view(kind, window)
        if current_view is None:
            return

        self.sync_image_view_range_from_view(kind, window, current_view)

    def apply_current_image_profile(self, kind, window):
        current_key = self._current_image_key(kind, window)
        self.sync_image_profile_from_key(kind, window, current_key)

    def sync_image_profile_from_key(self, kind, window, source_key):
        if self._syncing_image_profile or source_key is None:
            return

        rois = self._data_profile_rois(kind).get(window, {})
        current_roi = rois.get(source_key)
        if current_roi is None:
            return

        state = current_roi.saveState()
        self._syncing_image_profile = True
        try:
            for key, roi in rois.items():
                if key != source_key:
                    previous = roi.blockSignals(True)
                    roi.setState(state)
                    roi.blockSignals(previous)
        finally:
            self._syncing_image_profile = False
        self.update_image_profile(kind, window)

    def on_image_profile_changed(self, kind, window, key):
        if self._syncing_image_profile:
            return
        self.update_image_profile(kind, window)
        self.sync_image_profile_from_key(kind, window, key)

    def sync_current_image_view(self, kind, window):
        self.apply_current_image_levels(kind, window)
        self.apply_current_image_view(kind, window)
        self.apply_current_image_profile(kind, window)
        if kind == 'reco':
            self.apply_current_image_region(kind, window)

    def apply_current_image_region(self, kind, window):
        current_key = self._current_image_key(kind, window)
        rois = self._data_region_rois(kind).get(window, {})
        current_roi = rois.get(current_key)
        if current_roi is None:
            return

        state = current_roi.saveState()
        for key, roi in rois.items():
            if key != current_key:
                roi.setState(state)

    def update_image_interaction_mode(self, *args):
        for window in list(self._reco_viewers):
            for roi in self._reco_profile_rois.get(window, {}).values():
                roi.setVisible(True)
            for roi in self._reco_region_rois.get(window, {}).values():
                roi.setVisible(False)
            self.update_image_profile('reco', window)

    def reset_reconstruction_region_rois(self):
        for window, viewers in list(self._reco_viewers.items()):
            rois = self._reco_region_rois.get(window, {})
            for key, roi in rois.items():
                view = viewers.get(key, (None, None))[0]
                data = self._image_data('reco').get(key[0], {}).get(key[1])
                if view is not None and data is not None:
                    height, width = data.shape
                    self._set_region_roi_to_full(roi, width, height)
                    roi.setVisible(False)

    def switch_image_tab(self, kind, window, step):
        tabs = self._data_tabs(kind).get(window)
        if tabs is None or tabs.count() == 0:
            return
        tabs.setCurrentIndex((tabs.currentIndex() + step) % tabs.count())

    def _current_image_view(self, kind, window):
        tabs = self._data_tabs(kind).get(window)
        viewers = self._data_viewers(kind).get(window, {})
        if tabs is None or not viewers:
            return None, viewers

        current_tab = tabs.currentWidget()
        for view, tab in viewers.values():
            if tab is current_tab:
                return view, viewers

        return None, viewers

    def _current_image_key(self, kind, window):
        tabs = self._data_tabs(kind).get(window)
        viewers = self._data_viewers(kind).get(window, {})
        if tabs is None or not viewers:
            return None

        current_tab = tabs.currentWidget()
        for key, (_view, tab) in viewers.items():
            if tab is current_tab:
                return key

        return None

    def update_image_profile(self, kind, window):
        plot = self._data_profile_plots(kind).get(window)
        key = self._current_image_key(kind, window)
        if plot is None:
            return
        data_by_method = self._image_data(kind)
        if key is None or not data_by_method:
            plot.clear()
            return

        method, curve_name = key
        data = data_by_method.get(method, {}).get(curve_name)
        roi = self._data_profile_rois(kind).get(window, {}).get(key)
        viewers = self._data_viewers(kind).get(window, {})
        view = viewers.get(key, (None, None))[0]
        if data is None or roi is None or view is None:
            plot.clear()
            return

        displayed = np.asarray(data).T
        values = roi.getArrayRegion(displayed, view.getImageItem(), axes=(0, 1))
        if values is None:
            plot.clear()
            return
        values = np.asarray(values).squeeze()
        plot.clear()
        if values.size == 0:
            return
        import pyqtgraph as pg
        plot.plot(np.arange(values.size), values,
                  pen=pg.mkPen((31, 119, 180), width=2),
                  antialias=True)
        plot.enableAutoRange(x=True, y=True)
        plot.autoRange(padding=0.03)

    def _current_reco_display_regions(self, data):
        args = self._last_reco_args or self._current_reconstruction_args(self._current_args())
        height, width = data.shape
        x_region = expand_display_region(args.x_region, width)
        y_region = expand_display_region(args.y_region, height)

        return x_region, y_region

    def _set_region_roi_to_full(self, roi, width, height):
        previous = roi.blockSignals(True)
        roi.setPos([0, 0], update=False)
        roi.setSize([max(width, 1), max(height, 1)], update=True)
        roi.blockSignals(previous)

    def handle_reconstruction_region_drag(self, view, window, key, event):
        from PyQt5 import QtCore

        if event.button() != QtCore.Qt.LeftButton or not (
                event.modifiers() & QtCore.Qt.ControlModifier):
            event.ignore()
            return

        roi = self._reco_region_rois.get(window, {}).get(key)
        data = self._image_data('reco').get(key[0], {}).get(key[1])
        if roi is None or data is None:
            event.ignore()
            return

        height, width = data.shape
        view_box = view.getView()
        start = view_box.mapSceneToView(event.buttonDownScenePos())
        current = view_box.mapSceneToView(event.scenePos())
        x0 = max(0.0, min(float(start.x()), float(current.x()), float(width - 1)))
        x1 = min(float(width), max(float(start.x()), float(current.x()), 1.0))
        y0 = max(0.0, min(float(start.y()), float(current.y()), float(height - 1)))
        y1 = min(float(height), max(float(start.y()), float(current.y()), 1.0))
        previous = roi.blockSignals(True)
        roi.setPos([x0, y0], update=False)
        roi.setSize([max(x1 - x0, 1.0), max(y1 - y0, 1.0)], update=True)
        roi.blockSignals(previous)
        roi.setVisible(True)
        event.accept()
        if event.isFinish():
            self.update_reconstruction_region_from_roi(window, key)

    def install_reconstruction_region_drag_handler(self, view, window, key):
        view_box = view.getView()
        original_mouse_drag = view_box.mouseDragEvent

        def mouse_drag_event(event, axis=None):
            from PyQt5 import QtCore

            if event.button() == QtCore.Qt.LeftButton and (
                    event.modifiers() & QtCore.Qt.ControlModifier):
                self.handle_reconstruction_region_drag(view, window, key, event)
                return

            original_mouse_drag(event, axis=axis)

        view_box.mouseDragEvent = mouse_drag_event

    def install_projection_slice_click_handler(self, view, window, key):
        from PyQt5 import QtCore

        view_box = view.getView()
        original_mouse_click = view_box.mouseClickEvent

        def mouse_click_event(event):
            if event.button() == QtCore.Qt.LeftButton and (
                    event.modifiers() & QtCore.Qt.ControlModifier):
                data = self._image_data('result').get(key[0], {}).get(key[1])
                if data is None:
                    event.ignore()
                    return
                height, _width = data.shape
                position = view_box.mapSceneToView(event.scenePos())
                slice_number = int(np.floor(float(position.y())))
                slice_number = min(max(slice_number, 0), max(height - 1, 0))
                previous = self.reco_slice_box.blockSignals(True)
                self.reco_slice_box.setValue(slice_number)
                self.reco_slice_box.blockSignals(previous)
                self.schedule_update()
                event.accept()
                return

            original_mouse_click(event)

        view_box.mouseClickEvent = mouse_click_event

    def update_reconstruction_region_from_roi(self, window, key):
        roi = self._reco_region_rois.get(window, {}).get(key)
        data = self._image_data('reco').get(key[0], {}).get(key[1])
        if roi is None or data is None:
            return

        height, width = data.shape
        x_region, y_region = self._current_reco_display_regions(data)
        pos = roi.pos()
        size = roi.size()
        x0 = max(0.0, min(float(pos.x()), float(pos.x() + size.x()), float(width - 1)))
        x1 = min(float(width), max(float(pos.x()), float(pos.x() + size.x()), 1.0))
        y0 = max(0.0, min(float(pos.y()), float(pos.y() + size.y()), float(height - 1)))
        y1 = min(float(height), max(float(pos.y()), float(pos.y() + size.y()), 1.0))
        x_start_px = int(np.floor(x0))
        x_stop_px = int(np.ceil(x1))
        y_start_px = int(np.floor(y0))
        y_stop_px = int(np.ceil(y1))
        if x_stop_px <= x_start_px:
            x_stop_px = min(width, x_start_px + 1)
        if y_stop_px <= y_start_px:
            y_stop_px = min(height, y_start_px + 1)

        x_start, _x_stop, x_step = x_region
        y_start, _y_stop, y_step = y_region
        new_x_region = (
            x_start + x_start_px * x_step,
            x_start + x_stop_px * x_step,
            x_step)
        new_y_region = (
            y_start + y_start_px * y_step,
            y_start + y_stop_px * y_step,
            y_step)
        self.reco_x_region_edit.setText(format_region(new_x_region))
        self.reco_y_region_edit.setText(format_region(new_y_region))
        self._hide_reco_region_rois_on_next_update = True
        self.schedule_update()

    def update_2d_filter_views(self):
        if not self._last_data:
            return
        for entries in list(self._image_viewers.values()):
            for method, curve_name, view in entries:
                curves = self._last_data.get(method, {})
                data = curves.get(curve_name)
                if data is not None:
                    image = np.fft.fftshift(data[:, ::2])
                    view.setImage(image.T, autoLevels=False)

    def populate_image_tabs(self, kind, tabs):
        import pyqtgraph as pg
        from PyQt5 import QtCore, QtWidgets

        data_by_method = self._image_data(kind)
        if not data_by_method:
            return

        window = getattr(tabs, '_tofu_tune_window', tabs.parentWidget())
        viewers = self._data_viewers(kind).setdefault(window, {})
        rois = self._data_profile_rois(kind).setdefault(window, {})
        region_rois = self._data_region_rois(kind).setdefault(window, {})
        auto_level_windows = self._data_auto_level_windows(kind)
        desired_keys = set()
        current_view, _current_viewers = self._current_image_view(kind, window)
        inherited_levels = current_view.getLevels() if current_view is not None else None
        inherited_view_range = (
            current_view.getView().viewRange() if current_view is not None else None)
        inherited_profile_shape = (
            getattr(current_view, '_tofu_tune_shape', None)
            if current_view is not None else None)
        current_key = self._current_image_key(kind, window)
        current_profile_roi = rois.get(current_key)
        inherited_profile_state = (
            current_profile_roi.saveState() if current_profile_roi is not None else None)

        for method, curves in data_by_method.items():
            for curve_name, data in curves.items():
                label = method if curve_name == 'phase' else '{} sharpened'.format(method)
                key = (method, curve_name)
                desired_keys.add(key)
                if key not in viewers:
                    is_new_view = True
                    view = pg.ImageView()
                    view.getImageItem().resetTransform()
                    view.getView().setAspectLocked(True, ratio=1)
                    tab = QtWidgets.QWidget()
                    tab_layout = QtWidgets.QVBoxLayout(tab)
                    tab_layout.addWidget(view)
                    tabs.addTab(tab, label)
                    viewers[key] = (view, tab)
                    height, width = data.shape
                    shape_changed = True
                    y = height / 2.0
                    roi = make_profile_line_roi(
                        pg, [[0, y], [max(width - 1, 0), y]],
                        pen=pg.mkPen('y', width=2))
                    roi.sigRegionChanged.connect(
                        lambda *args, profile_kind=kind, profile_window=window,
                        profile_key=key:
                            self.on_image_profile_changed(
                                profile_kind, profile_window, profile_key))
                    view.getView().addItem(roi)
                    rois[key] = roi
                    if kind == 'reco':
                        region_roi = pg.RectROI(
                            [0, 0], [max(width, 1), max(height, 1)],
                            pen=pg.mkPen('y', width=2))
                        region_roi.setAcceptedMouseButtons(QtCore.Qt.NoButton)
                        region_roi.setVisible(False)
                        view.getView().addItem(region_roi)
                        region_rois[key] = region_roi
                        self.install_reconstruction_region_drag_handler(view, window, key)
                    if kind == 'result':
                        self.install_projection_slice_click_handler(view, window, key)
                    self.connect_image_view_sync(kind, window, view)
                    if inherited_view_range is not None:
                        x_range, y_range = inherited_view_range
                    else:
                        x_range = y_range = None
                    reset_levels = inherited_levels is None or window in auto_level_windows
                else:
                    is_new_view = False
                    view = viewers[key][0]
                    old_shape = getattr(view, '_tofu_tune_shape', None)
                    shape_changed = old_shape != data.shape
                    if not shape_changed:
                        x_range, y_range = view.getView().viewRange()
                    else:
                        x_range = y_range = None
                    reset_levels = window in auto_level_windows

                self._syncing_image_view = True
                try:
                    view.setImage(data.T, autoLevels=False)
                    view._tofu_tune_shape = data.shape
                    if kind == 'reco':
                        profile_roi = rois.get(key)
                        if profile_roi is not None:
                            height, width = data.shape
                            can_inherit_profile = (
                                inherited_profile_state is not None
                                and inherited_profile_shape == data.shape)
                            if is_new_view and can_inherit_profile:
                                previous = profile_roi.blockSignals(True)
                                profile_roi.setState(inherited_profile_state)
                                profile_roi.blockSignals(previous)
                            elif shape_changed:
                                reset_profile_line_roi(profile_roi, width, height)
                            elif can_inherit_profile:
                                previous = profile_roi.blockSignals(True)
                                profile_roi.setState(inherited_profile_state)
                                profile_roi.blockSignals(previous)
                        region_roi = region_rois.get(key)
                        if region_roi is not None:
                            height, width = data.shape
                            self._set_region_roi_to_full(region_roi, width, height)
                            if self._hide_reco_region_rois_on_next_update:
                                region_roi.setVisible(False)
                    if reset_levels:
                        levels = get_percentile_levels(data)
                        if levels is not None:
                            view.setLevels(*levels)
                    elif inherited_levels is not None:
                        view.setLevels(*inherited_levels)
                    if x_range is not None:
                        view.getView().setRange(xRange=x_range, yRange=y_range, padding=0)
                    elif kind == 'reco' and shape_changed:
                        height, width = data.shape
                        view.getView().setRange(
                            xRange=(0, max(width - 1, 0)),
                            yRange=(0, max(height - 1, 0)),
                            padding=0.02)
                finally:
                    self._syncing_image_view = False

        for key in list(viewers):
            if key not in desired_keys:
                view, tab = viewers.pop(key)
                roi = rois.pop(key, None)
                if roi is not None:
                    view.getView().removeItem(roi)
                region_roi = region_rois.pop(key, None)
                if region_roi is not None:
                    view.getView().removeItem(region_roi)
                index = tabs.indexOf(tab)
                if index >= 0:
                    tabs.removeTab(index)
                tab.deleteLater()
        self.update_image_interaction_mode()
        if kind == 'reco' and self._hide_reco_region_rois_on_next_update:
            for roi in region_rois.values():
                roi.setVisible(False)
        self.update_image_profile(kind, window)

    def update_image_data_views(self, kind, empty_text):
        tabs_by_window = self._data_tabs(kind)
        status_by_window = self._data_status(kind)
        for window, tabs in list(tabs_by_window.items()):
            self.populate_image_tabs(kind, tabs)
            self._data_auto_level_windows(kind).discard(window)
            if window in status_by_window:
                if tabs.count():
                    status_by_window[window].setText("Ready")
                else:
                    status_by_window[window].setText(empty_text)

    def update_result_views(self):
        self.update_image_data_views('result', "No result images to display")

    def update_reconstruction_views(self):
        self.update_image_data_views('reco', "No reconstructed slices to display")
        self._hide_reco_region_rois_on_next_update = False

    def on_main_window_close(self, event):
        for window in list(self._image_windows):
            window.close()
        for window in list(self._result_windows):
            window.close()
        for window in list(self._reco_windows):
            window.close()
        event.accept()

    def run(self):
        return self.app.exec_()


def run_interactive(args):
    window = InteractiveWindow(args)

    return window.run()


def run(args):
    """Open the interactive tuning window."""
    return run_interactive(args)
