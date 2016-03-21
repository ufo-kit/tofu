import os
import logging
import glob
import tempfile
import sys
import numpy as np
from gi.repository import Ufo
from tofu.preprocess import create_flat_correct_pipeline
from tofu.util import (set_node_props, setup_read_task,get_filenames,
                       next_power_of_two, read_image, determine_shape)


LOG = logging.getLogger(__name__)


def tomo(params):
    # Create reader and writer
    pm = Ufo.PluginManager()

    if params.projections and params.sinograms:
        LOG.error("Cannot specify both --projections and --sinograms.")
        sys.exit(1)

    def get_task(name, **kwargs):
        task = pm.get_task(name)
        task.set_properties(**kwargs)
        return task

    if params.projections is None and params.sinograms is None:
        if params.width is None and params.height is None:
            LOG.error("You have to specify --width and --height when generating data.")
            sys.exit(1)

        width, height = params.width, params.height
        reader = get_task('dummy-data', width=width, height=height, number=params.number or 1)
    else:
        reader = get_task('read')
        set_node_props(reader, params)
        setup_read_task(reader, params.projections or params.sinograms, params)
        width, height = determine_shape(params)

    if params.dry_run:
        writer = get_task('null', download=True)
    else:
        outname = params.output
        writer = get_task('write', filename=outname)
        LOG.debug("Write to {}".format(outname))

    # Setup graph depending on the chosen method and input data
    g = Ufo.TaskGraph()

    if params.projections is not None:
        if params.number:
            count = len(range(params.start, params.start + params.number, params.step))
        else:
            count = len(get_filenames(params.projections))

        LOG.debug("num_projections = {}".format(count))
        sino_output = get_task('transpose-projections', number=count)

        if params.darks and params.flats:
            g.connect_nodes(create_flat_correct_pipeline(params, g), sino_output)
        else:
            g.connect_nodes(reader, sino_output)

        if height:
            # Sinogram height is the one needed for further padding
            height = count
    else:
        sino_output = reader

    if params.method == 'fbp':
        fft = get_task('fft', dimensions=1)
        ifft = get_task('ifft', dimensions=1)
        fltr = get_task('filter', filter=params.projection_filter)
        bp = get_task('backproject')

        if params.axis:
            bp.props.axis_pos = params.axis

        if params.angle:
            bp.props.angle_step = params.angle

        if params.offset:
            bp.props.angle_offset = params.offset

        if width and height:
            # Pad the image with its extent to prevent reconstuction ring
            pad = get_task('pad')
            crop = get_task('crop')
            setup_padding(pad, crop, width, height)

            LOG.debug("Padding to {}x{} pixels".format(pad.props.width, pad.props.height))

            g.connect_nodes(sino_output, pad)
            g.connect_nodes(pad, fft)
            g.connect_nodes(fft, fltr)
            g.connect_nodes(fltr, ifft)
            g.connect_nodes(ifft, crop)
            g.connect_nodes(crop, bp)
        else:
            if params.crop_width:
                ifft.props.crop_width = int(params.crop_width)
                LOG.debug("Cropping to {} pixels".format(ifft.props.crop_width))

            g.connect_nodes(sino_output, fft)
            g.connect_nodes(fft, fltr)
            g.connect_nodes(fltr, ifft)
            g.connect_nodes(ifft, bp)

        g.connect_nodes(bp, writer)

    if params.method in ('sart', 'sirt', 'sbtv', 'asdpocs'):
        projector = pm.get_task_from_package('ir', 'parallel-projector')
        projector.set_properties(model='joseph', is_forward=False)

        if params.axis:
            projector.set_properties(axis_position=params.axis or width / 2.)

        if params.angle:
            projector.set_properties(step=params.angle)

        method = pm.get_task_from_package('ir', params.method)
        method.set_properties(projector=projector, num_iterations=params.num_iterations)

        if params.method in ('sart', 'sirt'):
            method.set_properties(relaxation_factor=params.relaxation_factor)

        if params.method == 'sbtv':
            # FIXME: the lambda keyword is preventing from the following
            # assignment ...
            # method.props.lambda = params.lambda
            method.set_properties(mu=params.mu)

        g.connect_nodes(sino_output, method)
        g.connect_nodes(method, writer)

    if params.method == 'dfi':
        oversampling = params.oversampling or 1
        axis = params.axis or width / 2.

        pad = get_task('zeropad', center_of_rotation=axis, oversampling=oversampling)
        fft = get_task('fft', dimensions=1, auto_zeropadding=0)
        dfi = get_task('dfi-sinc')
        ifft = get_task('ifft', dimensions=2)
        swap_forward = get_task('swap-quadrants')
        swap_backward = get_task('swap-quadrants')

        if params.angle:
            dfi.props.angle_step = params.angle

        g.connect_nodes(sino_output, pad)
        g.connect_nodes(pad, fft)
        g.connect_nodes(fft, dfi)
        g.connect_nodes(dfi, swap_forward)
        g.connect_nodes(swap_forward, ifft)
        g.connect_nodes(ifft, swap_backward)
        g.connect_nodes(swap_backward, writer)

    scheduler = Ufo.Scheduler()

    if hasattr(scheduler.props, 'enable_tracing'):
        LOG.debug("Use tracing: {}".format(params.enable_tracing))
        scheduler.props.enable_tracing = params.enable_tracing

    scheduler.run(g)

    return scheduler.props.time


def estimate_center(params):
    if params.estimate_method == 'reconstruction':
        axis = estimate_center_by_reconstruction(params)
    else:
        axis = estimate_center_by_correlation(params)

    return axis


def estimate_center_by_reconstruction(params):
    if params.projections is not None:
        sys.exit("Cannot estimate axis from projections")

    sinos = sorted(glob.glob(os.path.join(params.sinograms, '*.tif')))

    if not sinos:
        sys.exit("No sinograms found in {}".format(params.sinograms))

    # Use a sinogram that probably has some interesting data
    filename = sinos[len(sinos) / 2]
    sinogram = read_image(filename)
    initial_width = sinogram.shape[1]
    m0 = np.mean(np.sum(sinogram, axis=1))

    center = initial_width / 2.0
    width = initial_width / 2.0
    new_center = center
    tmp_dir = tempfile.mkdtemp()
    tmp_output = os.path.join(tmp_dir, 'slice-0.tif')

    params.sinograms = filename
    params.output = os.path.join(tmp_dir, 'slice-%i.tif')

    def heaviside(A):
        return (A >= 0.0) * 1.0

    def get_score(guess, m0):
        # Run reconstruction with new guess
        params.axis = guess
        tomo(params)

        # Analyse reconstructed slice
        result = read_image(tmp_output)
        Q_IA = float(np.sum(np.abs(result)) / m0)
        Q_IN = float(-np.sum(result * heaviside(-result)) / m0)
        LOG.info("Q_IA={}, Q_IN={}".format(Q_IA, Q_IN))
        return Q_IA

    def best_center(center, width):
        trials = [center + (width / 4.0) * x for x in range(-2, 3)]
        scores = [(guess, get_score(guess, m0)) for guess in trials]
        LOG.info(scores)
        best = sorted(scores, cmp=lambda x, y: cmp(x[1], y[1]))
        return best[0][0]

    for i in range(params.num_iterations):
        LOG.info("Estimate iteration: {}".format(i))
        new_center = best_center(new_center, width)
        LOG.info("Currently best center: {}".format(new_center))
        width /= 2.0

    try:
        os.remove(tmp_output)
        os.removedirs(tmp_dir)
    except OSError:
        LOG.info("Could not remove {} or {}".format(tmp_output, tmp_dir))

    return new_center


def estimate_center_by_correlation(params):
    """Use correlation to estimate center of rotation for tomography."""
    def flat_correct(flat, radio):
        nonzero = np.where(radio != 0)
        result = np.zeros_like(radio)
        result[nonzero] = flat[nonzero] / radio[nonzero]
        # log(1) = 0
        result[result <= 0] = 1

        return np.log(result)

    first = read_image(get_filenames(params.projections)[0]).astype(np.float)
    last_index = params.start + params.number if params.number else -1
    last = read_image(get_filenames(params.projections)[last_index]).astype(np.float)

    if params.darks and params.flats:
        dark = read_image(get_filenames(params.darks)[0]).astype(np.float)
        flat = read_image(get_filenames(params.flats)[0]) - dark
        first = flat_correct(flat, first - dark)
        last = flat_correct(flat, last - dark)

    height = params.height if params.height else -1
    y_region = slice(params.y, min(params.y + height, first.shape[0]), params.y_step)
    first = first[y_region, :]
    last = last[y_region, :]

    return compute_rotation_axis(first, last)


def compute_rotation_axis(first_projection, last_projection):
    """
    Compute the tomographic rotation axis based on cross-correlation technique.
    *first_projection* is the projection at 0 deg, *last_projection* is the projection
    at 180 deg.
    """
    from scipy.signal import fftconvolve
    width = first_projection.shape[1]
    first_projection = first_projection - first_projection.mean()
    last_projection = last_projection - last_projection.mean()

    # The rotation by 180 deg flips the image horizontally, in order
    # to do cross-correlation by convolution we must also flip it
    # vertically, so the image is transposed and we can apply convolution
    # which will act as cross-correlation
    convolved = fftconvolve(first_projection, last_projection[::-1, :], mode='same')
    center = np.unravel_index(convolved.argmax(), convolved.shape)[1]

    return (width / 2.0 + center) / 2


def setup_padding(pad, crop, width, height):
    padding = next_power_of_two(width + 32) - width
    pad.props.width = width + padding
    pad.props.height = height
    pad.props.x = padding / 2
    pad.props.y = 0
    pad.props.addressing_mode = 'clamp_to_edge'

    # crop to original width after filtering
    crop.props.width = width
    crop.props.height = height
    crop.props.x = padding / 2
    crop.props.y = 0
