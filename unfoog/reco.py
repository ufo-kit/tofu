import os
import re
import logging
import numpy as np
from gi.repository import Ufo
from . import tifffile
from unfoog.util import check_input, set_reader, get_filenames


LOG = logging.getLogger(__name__)


def get_output_name(output_path):
    abs_path = os.path.abspath(output_path)

    if re.search(r"%[0-9]*i", output_path):
        return abs_path

    return os.path.join(abs_path, 'slice-%05i.tif')


def tomo(params):
    cargs = {}

    #if params.include:
    #    config = Ufo.Config(paths=params.include)
    #    cargs['config'] = config

    # Create reader and writer
    pm = Ufo.PluginManager(**cargs)

    def get_task(name, **kwargs):
        task = pm.get_task(name)
        task.set_properties(**kwargs)
        return task

    reader = get_task('reader')
    reader.props.path = params.input
    reader.props.y_step = params.y_step

    if params.dry_run:
        writer = get_task('null')
    else:
        outname = get_output_name(params.output)
        writer = get_task('writer', filename=outname)
        LOG.debug("Write to {}".format(outname))

    # Setup graph depending on the chosen method and input data
    g = Ufo.TaskGraph()

    if params.from_projections:
        count = len(get_filenames(params.input))

        LOG.debug("num_projections = {}".format(count))
        sino_output = get_task('sino-generator', num_projections=count)

        if params.darks and params.flats and params.correction == True:
            dark_reader = get_task('reader', path=params.flats)
            flat_reader = get_task('reader', path=params.darks)
            correction = get_task('flat-field-correction')
            g.connect_nodes_full(reader, correction, 0)
            g.connect_nodes_full(dark_reader, correction, 1)
            g.connect_nodes_full(flat_reader, correction, 2)
            g.connect_nodes(correction, sino_output)
        else:
            g.connect_nodes(reader, sino_output)
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

        if params.crop_width and params.enable_cropping == True:
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

        pad = get_task('zeropadding', oversampling=oversampling)
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

    if params.use_gpu:
        resources = Ufo.Resources(device_type=Ufo.DeviceType.GPU)
        arch = Ufo.ArchGraph(resources=resources)
        nodes = arch.get_gpu_nodes()
        sched = Ufo.FixedScheduler()
        sched.set_gpu_nodes(arch, nodes)
    else:
        sched = Ufo.Scheduler()

    # if params.remote:
    #     sched.set_properties(remotes=params.remote)

    if hasattr(sched.props, 'enable_tracing'):
        LOG.debug("Use tracing: {}".format(params.enable_tracing))
        sched.props.enable_tracing = params.enable_tracing

    sched.run(g)


def lamino(params):
    if params.region:
        check_input(params.input, params.region)
    cargs = {}

    if params.include:
        config = Ufo.Config(paths=params.include)
        cargs['config'] = config

    # Create reader and writer
    pm = Ufo.PluginManager(**cargs)

    radios = pm.get_task('reader')
    set_reader(radios, params.input, region=params.region)
    pad = pm.get_task('padding-2d')
    rec = pm.get_task('lamino-bp')
    ramp = pm.get_task('lamino-ramp')
    conv = pm.get_task('lamino-conv')
    fft1 = pm.get_task('fft')
    fft2 = pm.get_task('fft')
    ifft = pm.get_task('ifft')
    writer = pm.get_task('writer')

    if params.downsample > 1:
        downsample = pm.get_task('downsample')
        downsample.set_properties(factor=params.downsample)

    radios.set_properties(path=params.input)
    writer.set_properties(filename=params.output)

    vx, vy, vz = params.bbox

    xpad = (params.pad[0] - params.width) / 2 / params.downsample
    ypad = (params.pad[1] - params.height) / 2 / params.downsample

    pad.set_properties(xl=xpad, xr=xpad, yt=ypad, yb=ypad, mode='brep')
    ramp.set_properties(width=params.pad[0] / params.downsample,
                        height=params.pad[1] / params.downsample,
                        fwidth=vx, theta=params.tilt, tau=params.tau)

    rec.set_properties(theta=params.tilt, angle_step=params.angle, psi=params.offset,
                       proj_ox=params.axis[0] / params.downsample,
                       proj_oy=params.axis[1] / params.downsample,
                       vol_sx=vx, vol_sy=vy, vol_sz=vz,
                       vol_ox=vx/2, vol_oy=vy/2, vol_oz=vz/2)

    fft1.set_properties(dimensions=2)
    fft2.set_properties(dimensions=2)
    ifft.set_properties(dimensions=2)

    g = Ufo.TaskGraph()

    # Padding and filtering
    if params.downsample > 1:
        g.connect_nodes(radios, downsample)
        g.connect_nodes(downsample, pad)
    else:
        g.connect_nodes(radios, pad)

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


def estimate_center(cfg_parser, filename, n_iterations=10):
    def heaviside(A):
        return (A >= 0.0) * 1.0

    def get_score(guess, m0):
        outname_template = '/tmp/foobarfoo-%05i.tif'
        run(cfg_parser, filename, outname_template, axis=guess)
        result = read_tiff('/tmp/foobarfoo-00000.tif')
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

    # Use a sinogram that probably has some interesting data
    sinogram = read_tiff(filename)
    initial_width = sinogram.shape[1]
    m0 = np.mean(np.sum(sinogram, axis=1))

    center = initial_width / 2.0
    width = initial_width / 2.0
    new_center = center

    for i in range(n_iterations):
        LOG.info("Estimate iteration: {}".format(i))
        new_center = best_center(new_center, width)
        LOG.info("Currently best center: {}".format(new_center))
        width /= 2.0

    return new_center
