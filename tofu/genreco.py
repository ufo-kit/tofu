"""General projection-based reconstruction for tomographic/laminographic cone/parallel beam data
sets.
"""
import copy
import itertools
import logging
import os
import time
import numpy as np
from multiprocessing.pool import ThreadPool
from threading import Event, Thread
from gi.repository import Ufo
from .preprocess import create_preprocessing_pipeline
from .util import (fbp_filtering_in_phase_retrieval, get_filtering_padding,
                   get_reconstructed_cube_shape, get_reconstruction_regions,
                   get_filenames, determine_shape, get_scarray_value, Vector)
from .tasks import get_task, get_writer


LOG = logging.getLogger(__name__)
DTYPE_CL_SIZE = {'float': 4,
                 'double': 8,
                 'half': 2,
                 'uchar': 1,
                 'ushort': 2,
                 'uint': 4}


def genreco(args):
    print(args)
    st = time.time()
    if is_output_single_file(args):
        try:
            import ufo.numpy
        except ImportError:
            LOG.error('You must install ufo-python-tools to be able to write single-file output')
            return
    if (args.energy is not None and args.propagation_distance is not None and not
            (args.projection_margin or args.disable_projection_crop)):
        LOG.warning('Phase retrieval without --projection-margin specification or '
                    '--disable-projection-crop may cause convolution artifacts')
    _fill_missing_args(args)
    _convert_angles_to_rad(args)
    set_projection_filter_scale(args)
    x_region, y_region, z_region = get_reconstruction_regions(args, store=True, dtype=float)
    vol_shape = get_reconstructed_cube_shape(x_region, y_region, z_region)
    bpp = DTYPE_CL_SIZE[args.store_type]
    num_voxels = vol_shape[0] * vol_shape[1] * vol_shape[2]
    vol_nbytes = num_voxels * bpp

    resources = [Ufo.Resources()]
    gpus = np.array(resources[0].get_gpu_nodes())
    gpu_indices = np.array(args.gpus or list(range(len(gpus))))
    if min(gpu_indices) < 0 or max(gpu_indices) > len(gpus) - 1:
        raise ValueError('--gpus contains invalid indices')
    
    gpus = gpus[gpu_indices]
    duration = 0
    for i, gpu in enumerate(gpus):
        print('Max mem for {}: {:.2f} GB'.format(i, gpu.get_info(0) / 2. ** 30))

    runs = make_runs(gpus, gpu_indices, x_region, y_region, z_region, bpp,
                     slices_per_device=args.slices_per_device,
                     slice_memory_coeff=args.slice_memory_coeff,
                     data_splitting_policy=args.data_splitting_policy,
                     num_gpu_threads=args.num_gpu_threads)

    for i in range(len(runs[0]) - 1):
        resources.append(Ufo.Resources())

    LOG.info('Number of passes: %d', len(runs))
    LOG.debug('GPUs and regions:')
    for regions in runs:
        LOG.debug('%s', str(regions))

    for i, regions in enumerate(runs):
        duration += _run(resources, args, x_region, y_region, regions, i, vol_nbytes)

    num_gupdates = num_voxels * args.number * 1e-9
    total_duration = time.time() - st
    LOG.debug('UFO duration: %.2f s', duration)
    LOG.debug('Total duration: %.2f s', total_duration)
    LOG.debug('UFO performance: %.2f GUPS', num_gupdates / duration)
    LOG.debug('Total performance: %.2f GUPS', num_gupdates / total_duration)


def make_runs(gpus, gpu_indices, x_region, y_region, z_region, bpp, slices_per_device=None,
              slice_memory_coeff=0.8, data_splitting_policy='one', num_gpu_threads=1):
    gpu_indices = np.array(gpu_indices)
    def _add_region(runs, gpu_index, current, to_process, z_start, z_step):
        current_per_thread = current // num_gpu_threads
        for i in range(num_gpu_threads):
            if i + 1 == num_gpu_threads:
                current_per_thread += current % num_gpu_threads
            z_end = z_start + current_per_thread * z_step
            runs[-1].append((gpu_indices[gpu_index], [z_start, z_end, z_step]))
            z_start = z_end

        return z_start, z_end, to_process - current

    z_start, z_stop, z_step = z_region
    y_start, y_stop, y_step = y_region
    x_start, x_stop, x_step = x_region
    slice_width, slice_height, num_slices = get_reconstructed_cube_shape(x_region, y_region,
                                                                         z_region)

    if slices_per_device:
        slices_per_device = [slices_per_device for i in range(len(gpus))]
    else:
        slices_per_device = get_num_slices_per_gpu(gpus, slice_width, slice_height, bpp,
                                                   slice_memory_coeff=slice_memory_coeff)

    max_slices_per_pass = sum(slices_per_device)
    if not max_slices_per_pass:
        raise RuntimeError('None of the available devices has enough memory to store any slices')
    num_full_passes = num_slices // max_slices_per_pass
    LOG.debug('Number of slices: %d', num_slices)
    LOG.debug('Slices per device %s', slices_per_device)
    LOG.debug('Maximum slices on all GPUs per pass: %d', max_slices_per_pass)
    LOG.debug('Number of passes with full workload: %d', num_slices // max_slices_per_pass)
    sorted_indices = np.argsort(slices_per_device)[-np.count_nonzero(slices_per_device):]
    runs = []
    z_start = z_region[0]
    to_process = num_slices

    # Create passes where all GPUs are fully loaded
    for j in range(num_full_passes):
        runs.append([])
        for i in sorted_indices:
            z_start, z_end, to_process = _add_region(runs, i, slices_per_device[i], to_process,
                                                     z_start, z_step)

    if to_process:
        if data_splitting_policy == 'one':
            # Fill the last pass by maximizing the workload per GPU
            runs.append([])
            for i in sorted_indices[::-1]:
                if not to_process:
                    break
                current = min(slices_per_device[i], to_process)
                z_start, z_end, to_process = _add_region(runs, i, current, to_process,
                                                         z_start, z_step)
        else:
            # Fill the last pass by maximizing the number of GPUs which will work
            num_gpus = len(sorted_indices)
            runs.append([])
            for j, i in enumerate(sorted_indices):
                # Current GPU will either process the maximum number of slices it can. If the number
                # of slices per GPU based on even division between them cannot saturate the GPU, use
                # this number. This way the work will be split evenly between the GPUs.
                current = max(min(slices_per_device[i], (to_process - 1) // (num_gpus - j) + 1), 1)
                z_start, z_end, to_process = _add_region(runs, i, current, to_process,
                                                         z_start, z_step)
                if not to_process:
                    break

    return runs


def get_num_slices_per_gpu(gpus, width, height, bpp, slice_memory_coeff=0.8):
    num_slices = []
    slice_size = width * height * bpp

    for i, gpu in enumerate(gpus):
        max_mem = gpu.get_info(Ufo.GpuNodeInfo.GLOBAL_MEM_SIZE)
        num_slices.append(int(np.floor(max_mem * slice_memory_coeff / slice_size)))

    return num_slices


def _run(resources, args, x_region, y_region, regions, run_number, vol_nbytes):
    """Execute one pass on all possible GPUs with slice ranges given by *regions*. Use separate
    thread per GPU and optimize the read projection regions.
    """
    executors = []
    writer = None
    last = None

    if is_output_single_file(args):
        import tifffile
        bigtiff = vol_nbytes > 2 ** 32 - 2 ** 25
        LOG.debug('Writing BigTiff: %s', bigtiff)
        dirname = os.path.dirname(args.output)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        writer = tifffile.TiffWriter(args.output, append=run_number != 0, bigtiff=bigtiff)

    for index in range(len(regions)):
        gpu_index, region = regions[index]
        region_index = run_number * len(resources) + index
        executors.append(
            Executor(
                resources[index],
                args,
                region,
                x_region,
                y_region,
                gpu_index,
                region_index,
                writer=writer
            )
        )
        if last:
            # Chain up waiting events of subsequent executors
            executors[-1].wait_event = last.finished
        last = executors[-1]

    def start_one(index):
        return executors[index].process()

    st = time.time()

    try:
        with ThreadPool(processes=len(regions)) as pool:
            try:
                pool.map(start_one, list(range(len(regions))))
            except KeyboardInterrupt:
                LOG.info('Processing interrupted')
                for executor in executors:
                    executor.abort()
    finally:
        if writer:
            writer.close()
            LOG.debug('Writer closed')

    return time.time() - st


def setup_graph(args, graph, x_region, y_region, region, source=None, gpu=None, do_output=True,
                index=0, make_reader=True):
    backproject = get_task('general-backproject', processing_node=gpu)

    if do_output:
        if args.dry_run:
            sink = get_task('null', processing_node=gpu, download=True)
        else:
            sink = get_writer(args)
            sink.props.filename = '{}-{:>03}-%04i.tif'.format(args.output, index)

    width = args.width
    height = args.height
    if args.transpose_input:
        tmp = width
        width = height
        height = tmp
    if args.projection_filter != 'none' and args.projection_crop_after == 'backprojection':
        # Take projection padding into account
        if fbp_filtering_in_phase_retrieval(args):
            padding = args.retrieval_padded_width - width
            padding_from = 'phase retrieval'
        else:
            padding = get_filtering_padding(width)
            padding_from = 'default backproject'
        args.center_position_x = [pos + padding / 2 for pos in args.center_position_x]
        if args.z_parameter == 'center-position-x':
            region = [region[0] + padding / 2, region[1] + padding / 2, region[2]]
        LOG.debug('center-position-x after padding: %g (from %s)',
                  args.center_position_x[0], padding_from)

    backproject.props.parameter = args.z_parameter
    if args.burst:
        backproject.props.burst = args.burst
    backproject.props.z = args.z
    backproject.props.region = region
    backproject.props.x_region = x_region
    backproject.props.y_region = y_region
    backproject.props.center_position_x = args.center_position_x
    backproject.props.center_position_z = args.center_position_z
    backproject.props.source_position_x = args.source_position_x
    backproject.props.source_position_y = args.source_position_y
    backproject.props.source_position_z = args.source_position_z
    backproject.props.detector_position_x = args.detector_position_x
    backproject.props.detector_position_y = args.detector_position_y
    backproject.props.detector_position_z = args.detector_position_z
    backproject.props.detector_angle_x = args.detector_angle_x
    backproject.props.detector_angle_y = args.detector_angle_y
    backproject.props.detector_angle_z = args.detector_angle_z
    backproject.props.axis_angle_x = args.axis_angle_x
    backproject.props.axis_angle_y = args.axis_angle_y
    backproject.props.axis_angle_z = args.axis_angle_z
    backproject.props.volume_angle_x = args.volume_angle_x
    backproject.props.volume_angle_y = args.volume_angle_y
    backproject.props.volume_angle_z = args.volume_angle_z
    backproject.props.num_projections = args.number
    backproject.props.compute_type = args.compute_type
    backproject.props.result_type = args.result_type
    backproject.props.store_type = args.store_type
    backproject.props.overall_angle = args.overall_angle
    backproject.props.addressing_mode = args.genreco_padding_mode
    backproject.props.gray_map_min = args.slice_gray_map[0]
    backproject.props.gray_map_max = args.slice_gray_map[1]

    source = create_preprocessing_pipeline(args, graph, source=source,
                                           processing_node=gpu,
                                           cone_beam_weight=not args.disable_cone_beam_weight,
                                           make_reader=make_reader)
    if source:
        graph.connect_nodes(source, backproject)
    else:
        source = backproject

    if do_output:
        graph.connect_nodes(backproject, sink)
        last = sink
    else:
        last = backproject

    return (source, last)


def is_output_single_file(args):
    filename = args.output.lower()

    return not args.dry_run and (filename.endswith('.tif') or filename.endswith('.tiff'))


def set_projection_filter_scale(args):
    is_parallel = np.all(np.isinf(args.source_position_y))
    magnification = (args.source_position_y[0] - args.detector_position_y[0]) / \
        args.source_position_y[0]

    args.projection_filter_scale = 1.
    if is_parallel:
        if np.any(np.array(args.axis_angle_x)):
            LOG.debug('Adjusting filter for parallel beam laminography')
            args.projection_filter_scale = 0.5 * np.cos(args.axis_angle_x[0])
    else:
        args.projection_filter_scale = 0.5
        args.projection_filter_scale /= magnification ** 2
        if np.all(np.array(args.axis_angle_x) == 0):
            LOG.debug('Adjusting filter for cone beam tomography')
            args.projection_filter_scale /= magnification


def _fill_missing_args(args):
    (width, height) = determine_shape(args, args.projections, store=False)
    if args.transpose_input:
        tmp = width
        width = height
        height = tmp
    args.center_position_x = (args.center_position_x or [width / 2.])
    args.center_position_z = (args.center_position_z or [height / 2.])

    if not args.overall_angle:
        args.overall_angle = 360.
        LOG.info('Overall angle not specified, using 360 deg')

    if not args.number:
        if len(args.axis_angle_z) > 1:
            LOG.debug("--number not specified, using length of --axis-angle-z: %d",
                      len(args.axis_angle_z))
            args.number = len(args.axis_angle_z)
        else:
            num_files = len(get_filenames(args.projections))
            if not num_files:
                raise RuntimeError("No files found in `{}'".format(args.projections))
            LOG.debug("--number not specified, using number of files matching "
                      "--projections pattern: %d", num_files)
            args.number = num_files

    if args.dry_run:
        if not args.number:
            raise ValueError('--number must be specified by --dry-run')
        determine_shape(args, args.projections, store=True)
        LOG.info('Dummy data W x H x N: {} x {} x {}'.format(args.width,
                                                             args.height,
                                                             args.number))

    return args


def _convert_angles_to_rad(args):
    names = ['detector_angle', 'axis_angle', 'volume_angle']
    coords = ['x', 'y', 'z']
    angular_z_params = [x[0].replace('_', '-') + '-' + x[1] for x in itertools.product(names, coords)]
    args.overall_angle = np.deg2rad(args.overall_angle)
    if args.z_parameter in angular_z_params:
        LOG.debug('Converting z parameter values to radians')
        args.region = _convert_list_to_rad(args.region)

    for name in names:
        for coord in coords:
            full_name = name + '_' + coord
            values = getattr(args, full_name)
            setattr(args, full_name, _convert_list_to_rad(values))


def _convert_list_to_rad(values):
    return np.deg2rad(np.array(values)).tolist()



def _are_values_equal(values):
    return np.all(np.array(values) == values[0])


class Executor(object):
    """Reconstructs one region.

    :param writer: if not None, we'll be writing to a file shared with other executors and need to
    use *wait_event* to make sure we write our region when the previous executors are finished.
    """
    def __init__(self, resources, args, region, x_region, y_region, gpu_index, region_index,
                 writer=None):
        self.resources = resources
        self.args = args
        self.region = region
        self.gpu_index = gpu_index
        self.x_region = x_region
        self.y_region = y_region
        self.region_index = region_index
        self.writer = writer
        self.output = Ufo.OutputTask() if self.writer else None
        self.scheduler = None
        self.wait_event = None
        self.finished = Event()
        self.abort_requested = False

    def process(self):
        self.scheduler = Ufo.FixedScheduler()
        if hasattr(self.scheduler.props, 'enable_tracing'):
            LOG.debug("Use tracing: {}".format(self.args.enable_tracing))
            self.scheduler.props.enable_tracing = self.args.enable_tracing
        self.scheduler.set_resources(self.resources)
        graph = Ufo.TaskGraph()
        gpu = self.scheduler.get_resources().get_gpu_nodes()[self.gpu_index]
        geometry = CTGeometry(self.args)
        if (len(self.args.center_position_z) == 1 and
                np.modf(self.args.center_position_z[0])[0] == 0 and
                geometry.is_simple_parallel_tomo):
            LOG.info('Simple tomography with integer z center, changing to center_position_z + 0.5 '
                     'to avoid interpolation')
            geometry.args.center_position_z = (geometry.args.center_position_z[0] + 0.5,)
        if not self.args.disable_projection_crop:
            if not self.args.dry_run and (self.args.y or self.args.height or
                                          self.args.transpose_input):
                LOG.debug('--y or --height or --transpose-input specified, '
                          'not optimizing projection region')
            else:
                geometry.optimize_args(region=self.region)
        opt_args = geometry.args
        if self.args.dry_run:
            source = get_task('dummy-data', number=self.args.number, width=self.args.width,
                              height=self.args.height)
        else:
            source = None
        last = setup_graph(opt_args, graph, self.x_region, self.y_region, self.region,
                           source=source, gpu=gpu, index=self.region_index, make_reader=True,
                           do_output=self.writer is None)[-1]
        if self.writer:
            graph.connect_nodes(last, self.output)

        LOG.debug('Device: %d, region: %s', self.gpu_index, self.region)
        thread = Thread(target=self.scheduler.run, args=(graph,))
        thread.setDaemon(True)
        thread.start()

        if self.writer:
            self.consume()

        thread.join()

        return self.scheduler.props.time

    def consume(self):
        import ufo.numpy

        if self.wait_event:
            LOG.debug('Executor of region %s waiting for writing', self.region)
            self.wait_event.wait()

        for i in np.arange(*self.region):
            if self.abort_requested:
                LOG.debug('Abort requested in writing of region %s', self.region)
                return
            buf = self.output.get_output_buffer()
            self.writer.save(ufo.numpy.asarray(buf))
            self.output.release_output_buffer(buf)

        self.finished.set()
        LOG.debug('Executor of region %s finished writing', self.region)

    def abort(self):
        self.abort_requested = True
        if self.scheduler:
            self.scheduler.abort()


class CTGeometry(object):
    def __init__(self, args):
        self.args = copy.deepcopy(args)
        determine_shape(self.args, self.args.projections, store=True)
        get_reconstruction_regions(self.args, store=True, dtype=float)
        self.args.center_position_x = (self.args.center_position_x or [self.args.width / 2.])
        self.args.center_position_z = (self.args.center_position_z or [self.args.height / 2.])

    @property
    def is_parallel(self):
        return np.all(np.isinf(self.args.source_position_y))

    @property
    def is_detector_rotated(self):
        return (np.any(self.args.detector_angle_x) or
                np.any(self.args.detector_angle_y) or
                np.any(self.args.detector_angle_z))

    @property
    def is_axis_rotated(self):
        return (np.any(self.args.axis_angle_x) or
                np.any(self.args.axis_angle_y) or
                np.any(self.args.axis_angle_z))

    @property
    def is_volume_rotated(self):
        return (np.any(self.args.volume_angle_x) or
                np.any(self.args.volume_angle_y) or
                np.any(self.args.volume_angle_z))

    @property
    def is_center_position_x_constant(self):
        return _are_values_equal(self.args.center_position_x)

    @property
    def is_center_position_z_constant(self):
        return _are_values_equal(self.args.center_position_z)

    @property
    def is_center_constant(self):
        return self.is_center_position_x_constant and self.is_center_position_z_constant

    @property
    def is_simple_parallel_tomo(self):
        return (not (self.is_axis_rotated or self.is_detector_rotated or
                     self.is_volume_rotated) and self.is_parallel and
                     self.is_center_constant)


    def optimize_args(self, region=None):
        xmin, ymin, xmax, ymax = self.compute_height(region=region)
        center_position_z = np.array(self.args.center_position_z) - ymin
        self.args.center_position_z = center_position_z.tolist()
        self.args.y = int(ymin)
        self.args.height = int(ymax - ymin)
        LOG.debug('Optimization for region: %s', region or self.args.region)
        LOG.debug('Optimized X: %d - %d, Z: %d - %d', xmin, xmax, ymin, ymax)
        LOG.debug('Optimized Z: %d', self.args.y)
        LOG.debug('Optimized height: %d', self.args.height)
        LOG.debug('Optimized center_position_z: %g - %g', self.args.center_position_z[0],
                  self.args.center_position_z[-1])

    def compute_height(self, region=None):
        extrema = []
        if not region:
            region = self.args.region

        if self.is_simple_parallel_tomo:
            # Simple parallel beam tomography, thus compute only the horizontal crop at rotations
            # which are multiples of 45 degrees
            LOG.debug('Computing optimal projection region from 4 angles')
            projs_per_45 = self.args.number / self.args.overall_angle * np.pi / 4
            stop = 4 if self.args.overall_angle <= np.pi else 8
            indices = projs_per_45 * np.arange(1, stop, 2)
            indices = np.round(indices).astype(int).tolist()
        else:
            LOG.debug('Computing optimal projection region from all angles')
            indices = list(range(self.args.number))

        for i in indices:
            extrema_0 = self._compute_one_parameter(region[0], i)
            extrema_1 = self._compute_one_parameter(region[1], i)
            extrema.append(extrema_0)
            extrema.append(extrema_1)

        minima = np.min(extrema, axis=0)
        maxima = np.max(extrema, axis=0)
        if maxima[-1] == minima[2]:
            # Don't let height be 0
            maxima[-1] += 1
        result = tuple(minima[::2]) + tuple(maxima[1::2])

        return result

    def _compute_one_parameter(self, param_value, index):
        source_position = np.array([get_scarray_value(self.args.source_position_x, index),
                                    get_scarray_value(self.args.source_position_y, index),
                                    get_scarray_value(self.args.source_position_z, index)])
        axis = Vector(x_angle=get_scarray_value(self.args.axis_angle_x, index),
                      y_angle=get_scarray_value(self.args.axis_angle_y, index),
                      z_angle=get_scarray_value(self.args.axis_angle_z, index),
                      position=[get_scarray_value(self.args.center_position_x, index),
                                0,
                                get_scarray_value(self.args.center_position_z, index)])
        detector = Vector(x_angle=get_scarray_value(self.args.detector_angle_x, index),
                          y_angle=get_scarray_value(self.args.detector_angle_y, index),
                          z_angle=get_scarray_value(self.args.detector_angle_z, index),
                          position=[get_scarray_value(self.args.detector_position_x, index),
                                    get_scarray_value(self.args.detector_position_y, index),
                                    get_scarray_value(self.args.detector_position_z, index)])
        volume_angle = Vector(x_angle=get_scarray_value(self.args.volume_angle_x, index),
                              y_angle=get_scarray_value(self.args.volume_angle_y, index),
                              z_angle=get_scarray_value(self.args.volume_angle_z, index))

        z = self.args.z
        if self.args.z_parameter == 'z':
            z = param_value
        elif self.args.z_parameter == 'axis-angle-x':
            axis.x_angle = param_value
        elif self.args.z_parameter == 'axis-angle-y':
            axis.y_angle = param_value
        elif self.args.z_parameter == 'axis-angle-z':
            axis.z_angle = param_value
        elif self.args.z_parameter == 'volume-angle-x':
            volume_angle.x_angle = param_value
        elif self.args.z_parameter == 'volume-angle-y':
            volume_angle.y_angle = param_value
        elif self.args.z_parameter == 'volume-angle-z':
            volume_angle.z_angle = param_value
        elif self.args.z_parameter == 'detector-angle-x':
            detector.x_angle = param_value
        elif self.args.z_parameter == 'detector-angle-y':
            detector.y_angle = param_value
        elif self.args.z_parameter == 'detector-angle-z':
            detector.z_angle = param_value
        elif self.args.z_parameter == 'detector-position-x':
            detector.position[0] = param_value
        elif self.args.z_parameter == 'detector-position-y':
            detector.position[1] = param_value
        elif self.args.z_parameter == 'detector-position-z':
            detector.position[2] = param_value
        elif self.args.z_parameter == 'source-position-x':
            source_position[0] = param_value
        elif self.args.z_parameter == 'source-position-y':
            source_position[1] = param_value
        elif self.args.z_parameter == 'source-position-z':
            source_position[2] = param_value
        elif self.args.z_parameter == 'center-position-x':
            axis.position[0] = param_value
        elif self.args.z_parameter == 'center-position-z':
            axis.position[2] = param_value
        else:
            raise RuntimeError("Unknown z parameter '{}'".format(self.args.z_parameter))

        points = get_extrema(self.args.x_region, self.args.y_region, z)
        if self.args.z_parameter != 'z':
            points_upper = get_extrema(self.args.x_region, self.args.y_region, z + 1)
            points = np.hstack((points, points_upper))
        tomo_angle = float(index) / self.args.number * self.args.overall_angle
        xe, ye = compute_detector_pixels(points, source_position, axis, volume_angle, detector,
                                         tomo_angle)
        return compute_detector_region(xe, ye, (self.args.height, self.args.width),
                                       overhead=self.args.projection_margin)


def project(points, source, detector_normal, detector_offset):
    """Project *points* onto a detector."""
    x, y, z = points
    source_extended = np.tile(source[:, np.newaxis], [1, points.shape[1]])
    detector_normal_extended = np.tile(detector_normal[:, np.newaxis], [1, points.shape[1]])
    denom = np.sum((points - source_extended) * detector_normal_extended, axis=0)
    if np.isinf(source[1]):
        # Parallel beam
        if np.any(detector_normal != np.array([0., -1, 0])):
            # Detector is not perpendicular, compute translation along the beam direction,
            # otherwise don't compute anything because voxels are mapped directly
            # to detector coordinates
            points[1, :] = - (detector_offset +
                              detector_normal[0] * points[0, :] +
                              detector_normal[2] * points[2, :]) / detector_normal[1]
        projected = points
    else:
        # Cone beam
        u = -(detector_offset + np.dot(source, detector_normal)) / denom
        u = np.tile(u, [3, 1])
        projected = source_extended + (points - source_extended) * u

    return projected


def compute_detector_pixels(points, source_position, axis, volume_rotation, detector, tomo_angle):
    """*points* are a list of points along x-direcion, thus the array has height 3.
    *source_position* is a 3-vector, *axis*, *volume_rotation* and *detector* are util.Vector
    instances.
    """
    # Rotate the axis
    detector_normal = np.array((0, -1, 0), dtype=float)
    detector_normal = rotate_z(detector.z_angle, detector_normal)
    detector_normal = rotate_y(detector.y_angle, detector_normal)
    detector_normal = rotate_x(detector.x_angle, detector_normal)
    # Compute d from ax + by + cz + d = 0
    detector_offset = -np.dot(detector.position, detector_normal)

    if np.isinf(source_position[1]):
        # Parallel beam
        voxels = points
    else:
        # Apply magnification
        voxels = -points * source_position[1] / (detector.position[1] - source_position[1])
    # Rotate the volume
    voxels = rotate_z(volume_rotation.z_angle, voxels)
    voxels = rotate_y(volume_rotation.y_angle, voxels)
    voxels = rotate_x(volume_rotation.x_angle, voxels)

    # Rotate around the axis
    voxels = rotate_z(tomo_angle, voxels)

    # Rotate the volume
    voxels = rotate_z(axis.z_angle, voxels)
    voxels = rotate_y(axis.y_angle, voxels)
    voxels = rotate_x(axis.x_angle, voxels)

    # Get the projected pixel
    projected = project(voxels, source_position, detector_normal, detector_offset)

    if np.any(detector_normal != np.array([0., -1, 0])):
        # Detector is not perpendicular
        projected -= np.array([detector.position]).T
        # Reverse rotation => reverse order of transformation matrices and negative angles
        projected = rotate_x(-detector.x_angle, projected)
        projected = rotate_y(-detector.y_angle, projected)
        projected = rotate_z(-detector.z_angle, projected)

    x = projected[0, :] + axis.position[0] - 0.5
    y = projected[2, :] + axis.position[2] - 0.5

    return x, y


def compute_detector_region(x, y, shape, overhead=2):
    """*overhead* specifies how much margin is taken into account around the computed area."""
    def _compute_outlier(extremum_func, values):
        if extremum_func == min:
            round_func = np.floor
            sgn = -1
        else:
            round_func = np.ceil
            sgn = +1

        return int(round_func(extremum_func(values)) + sgn * overhead)

    x_min = min(shape[1], max(0, _compute_outlier(min, x)))
    y_min = min(shape[0], max(0, _compute_outlier(min, y)))
    x_max = max(0, min(shape[1], _compute_outlier(max, x)))
    y_max = max(0, min(shape[0], _compute_outlier(max, y)))

    return (x_min, x_max, y_min, y_max)


def get_extrema(x_region, y_region, z):
    def get_extrema(region):
        return (region[0], region[1])

    product = itertools.product(get_extrema(x_region), get_extrema(y_region), [z])

    return np.array(list(product), dtype=float).T.copy()


def rotate_x(angle, point):
    cos = np.cos(angle)
    sin = np.sin(angle)

    matrix = np.identity(3)
    matrix[1, 1] = cos
    matrix[1, 2] = -sin
    matrix[2, 1] = sin
    matrix[2, 2] = cos

    return np.dot(matrix, point)


def rotate_y(angle, point):
    cos = np.cos(angle)
    sin = np.sin(angle)

    matrix = np.identity(3)
    matrix[0, 0] = cos
    matrix[0, 2] = sin
    matrix[2, 0] = -sin
    matrix[2, 2] = cos

    return np.dot(matrix, point)


def rotate_z(angle, point):
    cos = np.cos(angle)
    sin = np.sin(angle)

    matrix = np.identity(3)
    matrix[0, 0] = cos
    matrix[0, 1] = -sin
    matrix[1, 0] = sin
    matrix[1, 1] = cos

    return np.dot(matrix, point)
