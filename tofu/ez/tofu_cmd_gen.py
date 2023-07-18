#!/bin/python
"""
Created on Apr 6, 2018
@author: gasilos
"""
import os
import numpy as np
from tofu.ez.ufo_cmd_gen import fmt_in_out_path
from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.ez.util import make_inpaths, fmt_in_out_path


def check_lamino():
    cmd = ''
    if not SECTIONS['cone-beam-weight']['axis-angle-x']['value'][0] == '':
        cmd += ' --axis-angle-x {}'.format(SECTIONS['cone-beam-weight']['axis-angle-x']['value'][0])
    if not SECTIONS['general-reconstruction']['overall-angle']['value'] == '':
        cmd += ' --overall-angle {}'.format(SECTIONS['general-reconstruction']['overall-angle']['value'])
    if not SECTIONS['cone-beam-weight']['center-position-z']['value'][0] == '':
        cmd += ' --center-position-z {}'.format(SECTIONS['cone-beam-weight']['center-position-z']['value'][0])
    if not SECTIONS['general-reconstruction']['axis-angle-y']['value'][0] == '':
        cmd += ' --axis-angle-y {}'.format(SECTIONS['general-reconstruction']['axis-angle-y']['value'][0])
    return cmd

def gpu_optim():
    cmd = ''
    if SECTIONS['general']['verbose']['value']:
        cmd += ' --verbose'
    if EZVARS['advanced']['enable-optimization']['value']:
        cmd += ' --slice-memory-coeff={}'.format(SECTIONS['general-reconstruction']['slice-memory-coeff']['value'])
        if not SECTIONS['general-reconstruction']['slices-per-device']['value'] is None:
            cmd += ' --slices-per-device {}'.format(SECTIONS['general-reconstruction']['slices-per-device']['value'])
        if not SECTIONS['general-reconstruction']['data-splitting-policy']['value'] is None:
            cmd += ' --data-splitting-policy {}'.format(
                SECTIONS['general-reconstruction']['data-splitting-policy']['value'])
    return cmd

def check_8bit(cmd, gray256, bit, hmin, hmax):
    if gray256:
        cmd += " --output-bitdepth {}".format(bit)
        # cmd += " --output-minimum \" {}\" --output-maximum \" {}\""\
        # .format(hmin, hmax)
        cmd += ' --output-minimum " {}" --output-maximum " {}"'.format(hmin, hmax)
    return cmd

def check_vcrop(cmd, vcrop, y, yheight, ystep, ori_height):
    if vcrop:
        cmd += " --y {} --height {} --y-step {}".format(y, yheight, ystep)
    else:
        cmd += " --height {}".format(ori_height)
    return cmd

def check_bigtif(cmd, swi):
    if not swi:
        cmd += " --output-bytes-per-file 0"
    return cmd

def get_1step_ct_cmd(ctset, out_pattern, ax, nviews, wh):
    # direct CT reconstruction from input dir to output dir;
    # obsolete, replaced by tofu reco, see get_reco_cmd() lower
    indir = make_inpaths(ctset[0], ctset[1])
    # correct location of proj folder in case if prepro was done
    in_proj_dir, quatsch = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'],
                                           ctset[0], EZVARS['inout']['tomo-dir']['value'], False)
    indir[2] = os.path.join(os.path.split(indir[2])[0], os.path.split(in_proj_dir)[1])
    # format command
    cmd = "tofu tomo --absorptivity --fix-nan-and-inf"
    cmd += " --darks {} --flats {} --projections {}".format(indir[0], indir[1], indir[2])
    if ctset[1] == 4:  # must be equivalent to len(indir)>3
        cmd += " --flats2 {}".format(indir[3])
    cmd += " --output {}".format(out_pattern)
    cmd += " --axis {}".format(ax)
    cmd += " --offset {}".format(SECTIONS['general-reconstruction']['volume-angle-z']['value'][0])
    cmd += " --number {}".format(nviews)
    if SECTIONS['reading']['step']['value'] > 0.0:
        cmd += ' --angle {}'.format(SECTIONS['reading']['step']['value'])
    cmd = check_vcrop(cmd, EZVARS['inout']['input_ROI']['value'],
                           SECTIONS['reading']['y']['value'],
                           SECTIONS['reading']['height']['value'],
                           SECTIONS['reading']['y-step']['value'], wh[0])
    cmd = check_8bit(cmd, EZVARS['inout']['clip_hist']['value'],
                          SECTIONS['general']['output-bitdepth']['value'],
                          SECTIONS['general']['output-minimum']['value'],
                          SECTIONS['general']['output-maximum']['value'])
    cmd = check_bigtif(cmd, EZVARS['inout']['bigtiff-output']['value'])
    return cmd

def get_ct_proj_cmd( out_pattern, ax, nviews, wh):
    # CT reconstruction from pre-processed and flat-corrected projections
    in_proj_dir, quatsch = fmt_in_out_path(
        EZVARS['inout']['tmp-dir']['value'], "obsolete;if-you-need-fix-it", EZVARS['inout']['tomo-dir']['value'], False
    )
    cmd = "tofu tomo --projections {}".format(in_proj_dir)
    cmd += " --output {}".format(out_pattern)
    cmd += " --axis {}".format(ax)
    cmd += " --offset {}".format(SECTIONS['general-reconstruction']['volume-angle-z']['value'][0])
    cmd += " --number {}".format(nviews)
    if SECTIONS['reading']['step']['value'] > 0.0:
        cmd += ' --angle {}'.format(SECTIONS['reading']['step']['value'])
    cmd = check_vcrop(cmd, EZVARS['inout']['input_ROI']['value'],
                           SECTIONS['reading']['y']['value'],
                           SECTIONS['reading']['height']['value'],
                           SECTIONS['reading']['y-step']['value'], wh[0])
    cmd = check_8bit(cmd, EZVARS['inout']['clip_hist']['value'],
                          SECTIONS['general']['output-bitdepth']['value'],
                          SECTIONS['general']['output-minimum']['value'],
                          SECTIONS['general']['output-maximum']['value'])
    cmd = check_bigtif(cmd, EZVARS['inout']['bigtiff-output']['value'])
    return cmd

def get_ct_sin_cmd(out_pattern, ax, nviews, wh):
    sinos_dir = os.path.join(EZVARS['inout']['tmp-dir']['value'], 'sinos-filt')
    cmd = 'tofu tomo --sinograms {}'.format(sinos_dir)
    cmd += ' --output {}'.format(out_pattern)
    cmd += ' --axis {}'.format(ax)
    cmd += ' --offset {}'.format(SECTIONS['general-reconstruction']['volume-angle-z']['value'][0])
    if EZVARS['inout']['input_ROI']['value']:
        cmd += ' --number {}'.format(int(SECTIONS['reading']['height']['value'] / SECTIONS['reading']['y-step']['value']))
    else:
        cmd += " --number {}".format(wh[0])
    cmd += " --height {}".format(nviews)
    if SECTIONS['reading']['step']['value'] > 0.0:
        cmd += ' --angle {}'.format(SECTIONS['reading']['step']['value'])
    cmd = check_8bit(cmd, EZVARS['inout']['clip_hist']['value'],
                          SECTIONS['general']['output-bitdepth']['value'],
                          SECTIONS['general']['output-minimum']['value'],
                          SECTIONS['general']['output-maximum']['value'])
    cmd = check_bigtif(cmd, EZVARS['inout']['bigtiff-output']['value'])
    return cmd

def get_sinos_ffc_cmd(ctset, tmpdir, nviews, wh):
    indir = make_inpaths(ctset[0], ctset[1])
    in_proj_dir, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'],
                                    ctset[0], EZVARS['inout']['tomo-dir']['value'], False)
    cmd = 'tofu sinos --absorptivity --fix-nan-and-inf'
    cmd += ' --darks {} --flats {} '.format(indir[0], indir[1])
    if ctset[1] == 4:
        cmd += " --flats2 {}".format(indir[3])
    cmd += " --projections {}".format(in_proj_dir)
    cmd += " --output {}".format(os.path.join(tmpdir, "sinos/sin-%04i.tif"))
    cmd += " --number {}".format(nviews)
    cmd = check_vcrop(cmd, EZVARS['inout']['input_ROI']['value'],
                           SECTIONS['reading']['y']['value'],
                           SECTIONS['reading']['height']['value'],
                           SECTIONS['reading']['y-step']['value'], wh[0])
    if not EZVARS['RR']['use-ufo']['value']:
        # because second RR algorithm does not know how to work with multipage tiffs
        cmd += " --output-bytes-per-file 0"
    if not EZVARS['flat-correction']['dark-scale']['value'] == "":
        cmd += ' --dark-scale {}'.format(EZVARS['flat-correction']['dark-scale']['value'])
    if not EZVARS['flat-correction']['flat-scale']['value'] == "":
        cmd += ' --flat-scale {}'.format(EZVARS['flat-correction']['flat-scale']['value'])
    return cmd

def get_sinos_noffc_cmd(ctsetpath, tmpdir, nviews, wh):
    in_proj_dir, out_pattern = fmt_in_out_path(
        EZVARS['inout']['tmp-dir']['value'], ctsetpath, EZVARS['inout']['tomo-dir']['value'], False
    )
    cmd = "tofu sinos"
    cmd += " --projections {}".format(in_proj_dir)
    cmd += " --output {}".format(os.path.join(tmpdir, "sinos/sin-%04i.tif"))
    cmd += " --number {}".format(nviews)
    cmd = check_vcrop(cmd, EZVARS['inout']['input_ROI']['value'],
                           SECTIONS['reading']['y']['value'],
                           SECTIONS['reading']['height']['value'],
                           SECTIONS['reading']['y-step']['value'],
                           wh[0])
    if not EZVARS['RR']['use-ufo']['value']:
        # because second RR algorithm does not know how to work with multipage tiffs
        cmd += " --output-bytes-per-file 0"
    return cmd

def get_sinos2proj_cmd(proj_height):
    quatsch, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'], 'quatsch', EZVARS['inout']['tomo-dir']['value'], True)
    cmd = 'tofu sinos'
    cmd += ' --projections {}'.format(os.path.join(EZVARS['inout']['tmp-dir']['value'], 'sinos-filt'))
    cmd += ' --output {}'.format(out_pattern)
    if not EZVARS['inout']['input_ROI']['value']:
        cmd += ' --number {}'.format(proj_height)
    else:
        cmd += ' --number {}'.format(int(SECTIONS['reading']['height']['value'] / SECTIONS['reading']['y-step']['value']))
    return cmd

def get_sinFFC_cmd(ctset):
    indir = make_inpaths(ctset[0], ctset[1])
    in_proj_dir, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'],
                                               ctset[0], EZVARS['inout']['tomo-dir']['value'])
    cmd = 'bmit_sin --fix-nan'
    cmd += ' --darks {} --flats {} --projections {}'.format(indir[0], indir[1], in_proj_dir)
    if ctset[1] == 4:
        cmd += ' --flats2 {}'.format(indir[3])
    cmd += ' --output {}'.format(os.path.dirname(out_pattern))
    cmd += ' --method {}'.format(EZVARS['flat-correction']['smart-ffc-method']['value'])
    cmd += ' --multiprocessing'
    cmd += ' --eigen-pco-repetitions {}'.format(EZVARS['flat-correction']['eigen-pco-reps']['value'])
    cmd += ' --eigen-pco-downsample {}'.format(EZVARS['flat-correction']['eigen-pco-downsample']['value'])
    cmd += ' --downsample {}'.format(EZVARS['flat-correction']['downsample']['value'])
    return cmd

def get_pr_sinFFC_cmd(ctset):
    indir = make_inpaths(ctset[0], ctset[1])
    in_proj_dir, out_pattern = fmt_in_out_path(
        EZVARS['inout']['tmp-dir']['value'], ctset[0], EZVARS['inout']['tomo-dir']['value'])
    cmd = 'bmit_sin --fix-nan'
    cmd += ' --darks {} --flats {} --projections {}'.format(indir[0], indir[1], in_proj_dir)
    if ctset[1] == 4:
        cmd += ' --flats2 {}'.format(indir[3])
    cmd += ' --output {}'.format(os.path.dirname(out_pattern))
    cmd += ' --method {}'.format(EZVARS['flat-correction']['smart-ffc-method']['value'])
    cmd += ' --multiprocessing'
    cmd += ' --eigen-pco-repetitions {}'.format(EZVARS['flat-correction']['eigen-pco-reps']['value'])
    cmd += ' --eigen-pco-downsample {}'.format(EZVARS['flat-correction']['eigen-pco-downsample']['value'])
    cmd += ' --downsample {}'.format(EZVARS['flat-correction']['downsample']['value'])
    return cmd

def get_pr_tofu_cmd_sinFFC(ctset):
    # indir will format paths to flats darks and tomo2 correctly even if they were
    # pre-processed, however path to the input directory with projections
    # cannot be formatted with that command correctly
    # indir = make_inpaths(ctset[0], ctset[1])
    # so we need a separate "universal" command which considers all previous steps
    in_proj_dir, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'],
                                               ctset[0], EZVARS['inout']['tomo-dir']['value'])
    # Phase retrieval
    cmd = 'tofu preprocess --delta 1e-6'
    cmd += ' --energy {} --propagation-distance {}' \
           ' --pixel-size {} --regularization-rate {:0.2f}' \
        .format(SECTIONS['retrieve-phase']['energy']['value'],
                SECTIONS['retrieve-phase']['propagation-distance']['value'][0],
                SECTIONS['retrieve-phase']['pixel-size']['value'],
                SECTIONS['retrieve-phase']['regularization-rate']['value'])
    cmd += ' --projections {}'.format(in_proj_dir)
    cmd += ' --output {}'.format(out_pattern)
    cmd += ' --projection-crop-after filter'
    return cmd

def get_pr_tofu_cmd(ctset):
    # indir will format paths to flats darks and tomo2 correctly even if they were
    # pre-processed, however path to the input directory with projections
    # cannot be formatted with that command correctly
    indir = make_inpaths(ctset[0], ctset[1])
    # so we need a separate "universal" command which considers all previous steps
    in_proj_dir, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'],
                                               ctset[0], EZVARS['inout']['tomo-dir']['value'])
    cmd = 'tofu preprocess --fix-nan-and-inf --projection-filter none --delta 1e-6'
    cmd += ' --darks {} --flats {} --projections {}'.format(indir[0], indir[1], in_proj_dir)
    if ctset[1] == 4:
        cmd += ' --flats2 {}'.format(indir[3])
    cmd += ' --output {}'.format(out_pattern)
    cmd += ' --energy {} --propagation-distance {}' \
           ' --pixel-size {} --regularization-rate {:0.2f}' \
        .format(SECTIONS['retrieve-phase']['energy']['value'], SECTIONS['retrieve-phase']['propagation-distance']['value'][0],
                SECTIONS['retrieve-phase']['pixel-size']['value'], SECTIONS['retrieve-phase']['regularization-rate']['value'])
    if not EZVARS['flat-correction']['dark-scale']['value'] is None:
        cmd += ' --dark-scale {}'.format(EZVARS['flat-correction']['dark-scale']['value'])
    if not EZVARS['flat-correction']['flat-scale']['value'] is None:
        cmd += ' --flat-scale {}'.format(EZVARS['flat-correction']['flat-scale']['value'])
    return cmd

def get_reco_cmd(ctset, out_pattern, ax, nviews, wh, ffc, pr):
    # direct CT reconstruction from input dir to output dir;
    # or CT reconstruction after preprocessing only
    indir = make_inpaths(ctset[0], ctset[1])
    # correct location of proj folder in case if prepro was done
    in_proj_dir, quatsch = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'],
                                           ctset[0], EZVARS['inout']['tomo-dir']['value'], False)
    cmd = 'tofu reco'
    # Laminography ?
    if EZVARS['advanced']['more-reco-params']['value'] is True:
        cmd += check_lamino()
    elif EZVARS['advanced']['more-reco-params']['value'] is False:
        cmd += ' --overall-angle 180'
    ##############
    cmd += '  --projections {}'.format(in_proj_dir)
    cmd += ' --output {}'.format(out_pattern)
    if ffc:
        cmd += ' --fix-nan-and-inf'
        cmd += ' --darks {} --flats {}'.format(indir[0], indir[1])
        if ctset[1] == 4:  # must be equivalent to len(indir)>3
            cmd += ' --flats2 {}'.format(indir[3])
        if not pr:
            cmd += ' --absorptivity'
        if not EZVARS['flat-correction']['dark-scale']['value'] is None:
            cmd += ' --dark-scale {}'.format(EZVARS['flat-correction']['dark-scale']['value'])
        if not EZVARS['flat-correction']['flat-scale']['value'] is None:
            cmd += ' --flat-scale {}'.format(EZVARS['flat-correction']['flat-scale']['value'])
    if pr:
        cmd += (
            " --disable-projection-crop"
            " --delta 1e-6"
            " --energy {} --propagation-distance {}"
            " --pixel-size {} --regularization-rate {:0.2f}" \
                .format(SECTIONS['retrieve-phase']['energy']['value'], SECTIONS['retrieve-phase']['propagation-distance']['value'][0],
                        SECTIONS['retrieve-phase']['pixel-size']['value'], SECTIONS['retrieve-phase']['regularization-rate']['value'])
        )
    cmd += " --center-position-x {}".format(ax)
    # if args.nviews==0:
    cmd += " --number {}".format(nviews)
    # elif args.nviews>0:
    #    cmd += ' --number {}'.format(args.nviews)
    cmd += ' --volume-angle-z {:0.5f}'.format(SECTIONS['general-reconstruction']['volume-angle-z']['value'][0])
    # rows-slices to be reconstructed
    # full ROI
    b = int(np.ceil(wh[0] / 2.0))
    a = -int(wh[0] / 2.0)
    c = 1
    if EZVARS['inout']['input_ROI']['value']:
        if EZVARS['RR']['enable-RR']['value']:
            h2 = SECTIONS['reading']['height']['value'] / SECTIONS['reading']['y-step']['value'] / 2.0
            b = np.ceil(h2)
            a = -int(h2)
        else:
            h2 = int(wh[0] / 2.0)
            a = SECTIONS['reading']['y']['value'] - h2
            b = SECTIONS['reading']['y']['value'] + SECTIONS['reading']['height']['value'] - h2
            c = SECTIONS['reading']['y-step']['value']
    cmd += ' --region={},{},{}'.format(a, b, c)
    # crop of reconstructed slice in the axial plane
    b = wh[1] / 2
    if EZVARS['inout']['output-ROI']['value']:
        if EZVARS['inout']['output-x']['value'] != 0 or EZVARS['inout']['output-width']['value'] != 0:
            cmd += ' --x-region={},{},{}'.format(EZVARS['inout']['output-x']['value'] - b,
                    EZVARS['inout']['output-x']['value'] + EZVARS['inout']['output-width']['value'] - b, 1)
        if EZVARS['inout']['output-y']['value'] != 0 or EZVARS['inout']['output-height']['value'] != 0:
            cmd += ' --y-region={},{},{}'.format(EZVARS['inout']['output-y']['value'] - b,
                    EZVARS['inout']['output-y']['value'] + EZVARS['inout']['output-height']['value'] - b, 1)
    # cmd = check_vcrop(cmd, EZVARS['inout']['input_ROI']['value'], SECTIONS['reading']['y']['value'], SECTIONS['reading']['height']['value'], SECTIONS['reading']['y-step']['value'], wh[0])
    cmd = check_8bit(cmd, EZVARS['inout']['clip_hist']['value'],
                          SECTIONS['general']['output-bitdepth']['value'],
                          SECTIONS['general']['output-minimum']['value'],
                          SECTIONS['general']['output-maximum']['value'])
    cmd = check_bigtif(cmd, EZVARS['inout']['bigtiff-output']['value'])
    # Optimization
    cmd += gpu_optim()
    return cmd
