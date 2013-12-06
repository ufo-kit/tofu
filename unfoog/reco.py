import os
import sys
import re
import glob
import argparse
import logging
import numpy as np
import ConfigParser as configparser
from gi.repository import Ufo
from . import tifffile


LOG = logging.getLogger(__name__)


def get_output_name(output_path):
    abs_path = os.path.abspath(output_path)

    if re.search(r"%[0-9]*i", output_path):
        return abs_path

    return os.path.join(abs_path, 'slice-%05i.tif')


def run(cfg_parser, input_path, output_path, axis=None, angle_step=None,
        darks=None, flats=None, first_slice=None, last_slice=None,
        from_projections=False, method='fbp',
        include=None, enable_tracing=False, dry_run=False):

    cargs = {}

    if include:
        config = Ufo.Config(paths=include)
        cargs['config'] = config

    # Create reader and writer
    pm = Ufo.PluginManager(**cargs)

    def get_task(name, **kwargs):
        task = pm.get_task(name)
        task.set_properties(**kwargs)
        return task

    reader = get_task('reader', path=input_path)

    if first_slice != None:
        reader.props.nth = first_slice

        if last_slice:
            reader.props.count = last_slice - first_slice

    if dry_run:
        writer = get_task('null')
    else:
        outname = get_output_name(output_path)
        writer = get_task('writer', filename=outname)
        LOG.debug("Write to {}".format(outname))

    # Setup graph depending on the chosen method and input data
    g = Ufo.TaskGraph()

    if from_projections:
        if last_slice != None and first_slice != None:
            count = last_slice - first_slice
        else:
            count = len(glob.glob(input_path))

        LOG.debug("num_projections = {}".format(count))
        sino_output = get_task('sino-generator', num_projections=count)

        if darks and flats:
            dark_reader = get_task('reader', path=flats)
            flat_reader = get_task('reader', path=darks)
            correction = get_task('flat-field-correction')
            g.connect_nodes_full(reader, correction, 0)
            g.connect_nodes_full(dark_reader, correction, 1)
            g.connect_nodes_full(flat_reader, correction, 2)
            g.connect_nodes(correction, sino_output)
        else:
            g.connect_nodes(reader, sino_output)
    else:
        sino_output = reader

    if method == 'fbp':
        fft = get_task('fft', dimensions=1)
        ifft = get_task('ifft', dimensions=1)
        fltr = get_task('filter')
        bp = get_task('backproject')

        if axis:
            bp.props.axis_pos = axis

        if angle_step:
            bp.props.angle_step = angle_step

        crop_width = cfg_parser.get_config('fbp', 'crop_width')

        if crop_width:
            ifft.props.crop_width = int(crop_width)
            LOG.debug("Cropping to {} pixels".format(ifft.props.crop_width))

        g.connect_nodes(sino_output, fft)
        g.connect_nodes(fft, fltr)
        g.connect_nodes(fltr, ifft)
        g.connect_nodes(ifft, bp)
        g.connect_nodes(bp, writer)

    if method == 'sart':
        art = get_task('art',
                       method='sart',
                       projector='joseph',
                       regularizer='tv',
                       max_iterations=5,
                       max_regularizer_iterations=20,
                       posc=False)

        if angle_step:
            art.props.angle_step = angle_step

        g.connect_nodes(sino_output, art)
        g.connect_nodes(art, writer)

    if method == 'dfi':
        oversampling = int(cfg_parser.get_config('dfi', 'oversampling') or 1)

        cut = get_task('cut-sinogram', center_of_rotation=axis)
        pad = get_task('zeropadding', oversampling=oversampling)
        fft = get_task('fft', dimensions=1, auto_zeropadding=0)
        dfi = get_task('dfi-sinc')
        ifft = get_task('ifft', dimensions=2)
        swap_forward = get_task('swap-quadrants')
        swap_backward = get_task('swap-quadrants')

        g.connect_nodes(sino_output, cut)
        g.connect_nodes(cut, pad)
        g.connect_nodes(pad, fft)
        g.connect_nodes(fft, dfi)
        g.connect_nodes(dfi, swap_forward)
        g.connect_nodes(swap_forward, ifft)
        g.connect_nodes(ifft, swap_backward)
        g.connect_nodes(swap_backward, writer)

    sched = Ufo.Scheduler()

    if hasattr(sched.props, 'enable_tracing'):
        LOG.debug("Use tracing: {}".format(enable_tracing))
        sched.props.enable_tracing = enable_tracing

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
