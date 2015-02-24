import os
import re
import logging
import glob
import tempfile
import argparse
import sys
import numpy as np
from gi.repository import Ufo
from . import tifffile
from tofu.flatcorrect import create_pipeline
from tofu.util import set_node_props, get_filenames, next_power_of_two


LOG = logging.getLogger(__name__)


def get_output_name(output_path):
    abs_path = os.path.abspath(output_path)

    if re.search(r"%[0-9]*i", output_path):
        return abs_path

    return os.path.join(abs_path, 'slice-%05i.tif')


def tomo(params):
    # Create reader and writer
    pm = Ufo.PluginManager()

    def get_task(name, **kwargs):
        task = pm.get_task(name)
        task.set_properties(**kwargs)
        return task

    reader = get_task('read')
    reader.props.path = params.input
    set_node_props(reader, params)

    if params.dry_run:
        writer = get_task('null')
    else:
        outname = get_output_name(params.output)
        writer = get_task('write', filename=outname)
        LOG.debug("Write to {}".format(outname))

    # Setup graph depending on the chosen method and input data
    g = Ufo.TaskGraph()

    if params.from_projections:
        if params.end:
            count = len(range(params.start, params.end, params.step))
        else:
            count = len(get_filenames(params.input))

        LOG.debug("num_projections = {}".format(count))
        sino_output = get_task('transpose-projections', number=count)

        if params.darks and params.flats:
            g.connect_nodes(create_pipeline(params, g), sino_output)
        else:
            g.connect_nodes(reader, sino_output)

        if params.height:
            # Sinogram height is the one needed for further padding
            params.height = count
    else:
        sino_output = reader

    if params.method == 'fbp':
        fft = get_task('fft', dimensions=1)
        ifft = get_task('ifft', dimensions=1)
        fltr = get_task('filter')
        bp = get_task('backproject')

        if params.axis:
            bp.props.axis_pos = params.axis

        if params.angle:
            bp.props.angle_step = params.angle

        if params.offset:
            bp.props.angle_offset = params.offset

        if params.width and params.height:
            # Pad the image with its extent to prevent reconstuction ring
            pad = get_task('pad')
            crop = get_task('cut-roi')
            setup_padding(pad, crop, params.width, params.height)

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

    if params.method == 'sart':
        proj = pm.get_plugin ("ufo_ir_cl_projector_new",
                              "libufoir_cl_projector.so")
        proj.set_properties (model = "Joseph")

        geometry = pm.get_plugin ("ufo_ir_parallel_geometry_new",
                                  "libufoir_parallel_geometry.so")
        geometry.set_properties (angle_step = params.angle * 180.0 / np.pi,
                                 num_angles = params.num_angles)

        method = pm.get_plugin ("ufo_ir_sart_method_new",
                                "libufoir_sart_method.so")
        method.set_properties (relaxation_factor = params.relaxation_factor,
                               max_iterations = params.max_iterations)

        ir = get_task('ir',
                       method=method,
                       projector=proj,
                       geometry=geometry)

        g.connect_nodes(sino_output, ir)
        g.connect_nodes(ir, writer)

    if params.method == 'dfi':
        oversampling = params.oversampling or 1

        pad = get_task('zeropad', oversampling=oversampling)
        fft = get_task('fft', dimensions=1, auto_zeropadding=0)
        dfi = get_task('dfi-sinc')
        ifft = get_task('ifft', dimensions=2)
        swap_forward = get_task('swap-quadrants')
        swap_backward = get_task('swap-quadrants')

        g.connect_nodes(sino_output, pad)
        g.connect_nodes(pad, fft)
        g.connect_nodes(fft, dfi)
        g.connect_nodes(dfi, swap_forward)
        g.connect_nodes(swap_forward, ifft)
        g.connect_nodes(ifft, swap_backward)
        g.connect_nodes(swap_backward, writer)

    resources = Ufo.Resources(device_type=Ufo.DeviceType.GPU)
    arch = Ufo.ArchGraph(resources=resources)
    nodes = arch.get_gpu_nodes()
    sched = Ufo.FixedScheduler()
    sched.set_gpu_nodes(arch, nodes)

    # if params.remote:
    #     sched.set_properties(remotes=params.remote)

    if hasattr(sched.props, 'enable_tracing'):
        LOG.debug("Use tracing: {}".format(params.enable_tracing))
        sched.props.enable_tracing = params.enable_tracing

    sched.run(g)


def lamino(params):
    # Create reader and writer
    pm = Ufo.PluginManager()

    pad = pm.get_task('padding-2d')
    rec = pm.get_task('lamino-bp')
    ramp = pm.get_task('lamino-ramp')
    conv = pm.get_task('lamino-conv')
    fft1 = pm.get_task('fft')
    fft2 = pm.get_task('fft')
    ifft = pm.get_task('ifft')
    writer = pm.get_task('write')

    if params.downsample > 1:
        downsample = pm.get_task('downsample')
        downsample.set_properties(factor=params.downsample)

    writer.set_properties(filename=params.output)

    vx, vy, vz = params.bbox
    width, height = params.size
    pad_width, pad_height = params.pad

    xpad = (pad_width - width) / 2 / params.downsample
    ypad = (pad_height - height) / 2 / params.downsample

    pad.set_properties(xl=xpad, xr=xpad, yt=ypad, yb=ypad, mode='brep')
    ramp.set_properties(width=pad_width / params.downsample,
                        height=pad_height / params.downsample,
                        fwidth=vx, theta=params.tilt, tau=params.tau)

    rec.set_properties(theta=params.tilt, angle_step=params.angle, psi=params.psi,
                       proj_ox=params.axis[0] / params.downsample,
                       proj_oy=params.axis[1] / params.downsample,
                       vol_sx=vx, vol_sy=vy, vol_sz=vz,
                       vol_ox=vx / 2, vol_oy=vy / 2, vol_oz=vz / 2)

    fft1.set_properties(dimensions=2)
    fft2.set_properties(dimensions=2)
    ifft.set_properties(dimensions=2)

    g = Ufo.TaskGraph()

    if params.darks and params.flats:
        first = create_pipeline(params, g)
    else:
        radios = pm.get_task('read')
        set_node_props(radios, params)
        radios.set_properties(path=params.input)
        first = radios

    # Padding and filtering
    if params.downsample > 1:
        g.connect_nodes(first, downsample)
        g.connect_nodes(downsample, pad)
    else:
        g.connect_nodes(first, pad)

    g.connect_nodes(pad, fft1)
    g.connect_nodes(ramp, fft2)
    g.connect_nodes_full(fft1, conv, 0)
    g.connect_nodes_full(fft2, conv, 1)
    g.connect_nodes(conv, ifft)

    # Reconstruction
    g.connect_nodes(ifft, rec)
    g.connect_nodes(rec, writer)

    sched = Ufo.Scheduler()
    sched.set_properties(expand=False)
    sched.run(g)


def read_tiff(filename):
    tif = tifffile.TiffFile(filename)
    arr = np.copy(tif.asarray())
    tif.close()
    return arr


def estimate_center(params):
    if params.from_projections:
        sys.exit("Cannot estimate axis from projections")

    sinos = sorted(glob.glob(os.path.join(params.input, '*.tif')))

    if not sinos:
        sys.exit("No sinograms found in {}".format(params.input))

    # Use a sinogram that probably has some interesting data
    filename = sinos[len(sinos) / 2]
    sinogram = read_tiff(filename)
    initial_width = sinogram.shape[1]
    m0 = np.mean(np.sum(sinogram, axis=1))

    center = initial_width / 2.0
    width = initial_width / 2.0
    new_center = center
    tmp_dir = tempfile.mkdtemp()
    tmp_output = os.path.join(tmp_dir, 'slice-0.tif')

    params.input = filename
    params.output = os.path.join(tmp_dir, 'slice-%i.tif')

    def heaviside(A):
        return (A >= 0.0) * 1.0

    def get_score(guess, m0):
        # Run reconstruction with new guess
        params.axis = guess
        tomo(params)

        # Analyse reconstructed slice
        result = read_tiff(tmp_output)
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
