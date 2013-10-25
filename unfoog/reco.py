#!/usr/bin/env python

import os
import sys
import re
import glob
import argparse
import logging
import numpy as np
import ConfigParser as configparser
from gi.repository import Ufo


LOG = logging.getLogger(__name__)


def get_output_name(output_path):
    abs_path = os.path.abspath(output_path)

    if re.search(r"%[0-9]*i", output_path):
        return abs_path

    return os.path.join(abs_path, 'slice-%05i.tif')


def run(args, cfg_parser):
    cargs = {}

    if args.include:
        config = Ufo.Config(paths=args.include)
        cargs['config'] = config

    # Create reader and writer
    pm = Ufo.PluginManager(**cargs)

    def get_task(name, **kwargs):
        task = pm.get_task(name)
        task.set_properties(**kwargs)
        return task

    reader = get_task('reader', path=args.input)

    if args.first_slice != None:
        reader.props.nth = args.first_slice

        if args.last_slice:
            reader.props.count = args.last_slice - args.first_slice

    if args.dry_run:
        writer = get_task('null')
    else:
        outname = get_output_name(args.output)
        writer = get_task('writer', filename=outname)
        LOG.info("Write to {}".format(outname))


    # Setup graph depending on the chosen method and input data
    g = Ufo.TaskGraph()

    if args.from_projections:
        if args.last_slice != None and args.first_slice != None:
            count = args.last_slice - args.first_slice
        else:
            count = len(glob.glob(args.input))

        LOG.info("num_projections = {}".format(count))
        sino_output = get_task('sino-generator', num_projections=count)

        if args.darks and args.flats:
            dark_reader = get_task('reader', path=args.flats)
            flat_reader = get_task('reader', path=args.darks)
            correction = get_task('flat-field-correction')
            g.connect_nodes_full(reader, correction, 0)
            g.connect_nodes_full(dark_reader, correction, 1)
            g.connect_nodes_full(flat_reader, correction, 0)
            g.connect_nodes(correction, sino_output)
        else:
            g.connect_nodes(reader, sino_output)
    else:
        sino_output = reader

    if args.method == 'fbp':
        fft = get_task('fft', dimensions=1)
        ifft = get_task('ifft', dimensions=1)
        fltr = get_task('filter')
        bp = get_task('backproject')

        if args.axis:
            bp.props.axis_pos = args.axis

        if args.angle_step:
            bp.props.angle_step = args.angle_step

        crop_width = cfg_parser.get_config('fbp', 'crop_width')

        if crop_width:
            ifft.props.crop_width = int(crop_width)
            LOG.info("Cropping to {} pixels".format(ifft.props.crop_width))

        g.connect_nodes(sino_output, fft)
        g.connect_nodes(fft, fltr)
        g.connect_nodes(fltr, ifft)
        g.connect_nodes(ifft, bp)
        g.connect_nodes(bp, writer)

    if args.method == 'sart':
        art = get_task('art',
                       method='sart',
                       projector='joseph',
                       regularizer='tv',
                       max_iterations=5,
                       max_regularizer_iterations=20,
                       posc=False)

        if args.angle_step:
            art.props.angle_step = args.angle_step

        g.connect_nodes(sino_output, art)
        g.connect_nodes(art, writer)

    if args.method == 'dfi':
        oversampling = int(cfg_parser.get_config('dfi', 'oversampling') or 1)

        cut = get_task('cut-sinogram', center_of_rotation=args.axis)
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
        LOG.info("Use tracing: {}".format(args.enable_tracing))
        sched.props.enable_tracing = args.enable_tracing

    sched.run(g)
