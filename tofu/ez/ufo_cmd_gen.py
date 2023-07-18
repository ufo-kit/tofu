#!/bin/python
"""
Created on Apr 6, 2018
@author: gasilos
"""
import os
from tofu.util import next_power_of_two
from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.ez.util import enquote, make_inpaths, fmt_in_out_path


def make_outpaths(lvl0, flats2):
    """
    Creates a list of paths to flats/darks/tomo directories in tmp data
    only used in one place to format paths in the temporary directory
    :param lvl0: Root of directory containing flats/darks/tomo
    :param flats2: The type of directory: 3 contains flats/darks/tomo 4 contains flats/darks/tomo/flats2
    :return: List of paths to the filtered darks/flats/tomo and flats2 (if used)
    """
    indir = []
    for i in [EZVARS['inout']['darks-dir']['value'],
              EZVARS['inout']['flats-dir']['value'],
              EZVARS['inout']['tomo-dir']['value']]:
        indir.append(os.path.join(lvl0, i))
    if flats2 - 3:
        indir.append(os.path.join(lvl0, EZVARS['inout']['flats2-dir']['value']))
    return indir

def check_vcrop(cmd, vcrop, y, yheight, ystep):
    if vcrop:
        cmd += " --y {} --height {} --y-step {}".format(y, yheight, ystep)
    return cmd

def check_bigtif(cmd, swi):
    if not swi:
        cmd += " bytes-per-file=0"
    return cmd

def get_pr_ufo_cmd(nviews, wh):
    in_proj_dir, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'], "quatsch",
                                               EZVARS['inout']['tomo-dir']['value'])
    cmds = []
    pad_width = next_power_of_two(wh[1] + 50)
    pad_height = next_power_of_two(wh[0] + 50)
    pad_x = (pad_width - wh[1]) / 2
    pad_y = (pad_height - wh[0]) / 2
    cmd = 'ufo-launch read path={} height={} number={}'.format(in_proj_dir, wh[0], nviews)
    cmd += ' ! pad x={} width={} y={} height={}'.format(pad_x, pad_width, pad_y, pad_height)
    cmd += ' addressing-mode=clamp_to_edge'
    cmd += ' ! fft dimensions=2 ! retrieve-phase'
    cmd += ' energy={} distance={} pixel-size={} regularization-rate={:0.2f}' \
        .format(SECTIONS['retrieve-phase']['energy']['value'],
                SECTIONS['retrieve-phase']['propagation-distance']['value'][0],
                SECTIONS['retrieve-phase']['pixel-size']['value'],
                SECTIONS['retrieve-phase']['regularization-rate']['value'])
    cmd += ' ! ifft dimensions=2 crop-width={} crop-height={}' \
        .format(pad_width, pad_height)
    cmd += ' ! crop x={} width={} y={} height={}'.format(pad_x, wh[1], pad_y, wh[0])
    cmd += ' ! opencl kernel=\'absorptivity\' ! opencl kernel=\'fix_nan_and_inf\' !'
    cmd += ' write filename={}'.format(enquote(out_pattern))
    cmds.append(cmd)
    if not EZVARS['inout']['keep-tmp']['value']:
        cmds.append('rm -rf {}'.format(in_proj_dir))
    return cmds

def get_filter1d_sinos_cmd(tmpdir, RR, nviews):
    sin_in = os.path.join(tmpdir, 'sinos')
    out_pattern = os.path.join(tmpdir, 'sinos-filt/sin-%04i.tif')
    pad_height = next_power_of_two(nviews + 500)
    pad_y = (pad_height - nviews) / 2
    cmd = 'ufo-launch read path={}'.format(sin_in)
    cmd += ' ! pad y={} height={}'.format(pad_y, pad_height)
    cmd += ' addressing-mode=clamp_to_edge'
    cmd += ' ! transpose ! fft dimensions=1 !  filter-stripes1d strength={}'.format(RR)
    cmd += ' ! ifft dimensions=1 ! transpose'
    cmd += ' ! crop y={} height={}'.format(pad_y, nviews)
    cmd += ' ! write filename={}'.format(enquote(out_pattern))
    return cmd

def get_filter2d_sinos_cmd(tmpdir, sig_hor, sig_ver, nviews, w):
    sin_in = os.path.join(tmpdir, "sinos")
    out_pattern = os.path.join(tmpdir, "sinos-filt/sin-%04i.tif")
    pad_height = next_power_of_two(nviews + 500)
    pad_y = (pad_height - nviews) / 2
    pad_width = next_power_of_two(w + 500)
    pad_x = (pad_width - w) / 2
    cmd = "ufo-launch read path={}".format(sin_in)
    cmd += " ! pad x={} width={} y={} height={}".format(pad_x, pad_width, pad_y, pad_height)
    cmd += " addressing-mode=mirrored_repeat"
    cmd += " ! fft dimensions=2 ! filter-stripes horizontal-sigma={} vertical-sigma={}".format(
        sig_hor, sig_ver
    )
    cmd += " ! ifft dimensions=2 crop-width={} crop-height={}".format(pad_width, pad_height)
    cmd += " ! crop x={} width={} y={} height={}".format(pad_x, w, pad_y, nviews)
    cmd += " ! write filename={}".format(enquote(out_pattern))
    return cmd

def get_pre_cmd( ctset, pre_cmd, tmpdir):
    indir = make_inpaths(ctset[0], ctset[1])
    outdir = make_outpaths(tmpdir, ctset[1])
    # add index to the name of the output directory with projections
    # if enabled preprocessing is always the first step
    outdir[2] = os.path.join(tmpdir, "proj-step1")
    # we also must create this directory to format paths correctly
    if not os.path.exists(outdir[2]):
        os.makedirs(outdir[2])
    cmds = []
    for i, fol in enumerate(indir):
        in_pattern = os.path.join(fol, "*.tif")
        out_pattern = os.path.join(outdir[i], "frame-%04i.tif")
        cmds.append("ufo-launch")
        cmds[i] += " read path={} ! ".format(enquote(in_pattern))
        cmds[i] += pre_cmd
        cmds[i] += " ! write filename={}".format(enquote(out_pattern))
    return cmds

def get_inp_cmd(ctset, tmpdir, N, nviews):
    indir = make_inpaths(ctset[0], ctset[1])
    cmds = []
    ######### CREATE MASK #########
    flat1_file = os.path.join(tmpdir, "flat1.tif")
    mask_file = os.path.join(tmpdir, "mask.tif")
    # generate mask
    cmd = 'tofu find-large-spots --images {}'.format(flat1_file)
    cmd += ' --spot-threshold {} --gauss-sigma {}'.format(
                    SECTIONS['find-large-spots']['spot-threshold']['value'],
                    SECTIONS['find-large-spots']['gauss-sigma']['value'])
    cmd += ' --output {} --output-bytes-per-file 0'.format(mask_file)
    cmds.append(cmd)
    ######### FLAT-CORRECT #########
    in_proj_dir, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'], ctset[0],
                                               EZVARS['inout']['tomo-dir']['value'])
    if EZVARS['flat-correction']['smart-ffc']['value']:
        cmd = 'bmit_sin --fix-nan'
        cmd += ' --darks {} --flats {}'.format(indir[0], indir[1])
        cmd += ' --projections {}'.format(in_proj_dir)
        cmd += ' --output {}'.format(os.path.dirname(out_pattern))
        cmd += ' --multiprocessing'
        #cmd += ' --output {}'.format(out_pattern)
        if ctset[1] == 4:
            cmd += ' --flats2 {}'.format(indir[3])
        # Add options for eigen-pco-repetitions etc.
        cmd += ' --eigen-pco-repetitions {}'.format(EZVARS['flat-correction']['eigen-pco-reps']['value'])
        cmd += ' --eigen-pco-downsample {}'.format(EZVARS['flat-correction']['eigen-pco-downsample']['value'])
        cmd += ' --downsample {}'.format(EZVARS['flat-correction']['downsample']['value'])
        #if not SECTIONS['retrieve-phase']['enable-phase']['value']:
        #    cmd += ' --absorptivity' ????
        #    Todo: check if takes neglog? or only computes transmission?
        #    in case of latter add absorptivity and fix nans
        cmds.append(cmd)
    elif not EZVARS['flat-correction']['smart-ffc']['value']:
        cmd = 'tofu flatcorrect --fix-nan-and-inf'
        cmd += ' --darks {} --flats {}'.format(indir[0], indir[1])
        cmd += ' --projections {}'.format(in_proj_dir)
        cmd += ' --output {}'.format(out_pattern)
        if ctset[1] == 4:
            cmd += ' --flats2 {}'.format(indir[3])
        if not SECTIONS['retrieve-phase']['enable-phase']['value']:
            cmd += ' --absorptivity --fix-nan-and-inf'
        if not EZVARS['flat-correction']['dark-scale']['value'] == "":
            cmd += ' --dark-scale {}'.format(EZVARS['flat-correction']['dark-scale']['value'])
        if not EZVARS['flat-correction']['flat-scale']['value'] == "":
            cmd += ' --flat-scale {}'.format(EZVARS['flat-correction']['flat-scale']['value'])
        cmds.append(cmd)
    if not EZVARS['inout']['keep-tmp']['value'] and EZVARS['inout']['preprocess']['value']:
        cmds.append('rm -rf {}'.format(indir[0]))
        cmds.append('rm -rf {}'.format(indir[1]))
        cmds.append('rm -rf {}'.format(in_proj_dir))
        if len(indir) > 3:
            cmds.append("rm -rf {}".format(indir[3]))
    ######### INPAINT #########
    in_proj_dir, out_pattern = fmt_in_out_path(EZVARS['inout']['tmp-dir']['value'], ctset[0],
                                               EZVARS['inout']['tomo-dir']['value'])
    cmd = "ufo-launch [read path={} height={} number={}".format(in_proj_dir, N, nviews)
    cmd += ", read path={}]".format(mask_file)
    cmd += " ! horizontal-interpolate ! "
    cmd += "write filename={}".format(enquote(out_pattern))
    cmds.append(cmd)
    if not EZVARS['inout']['keep-tmp']['value']:
        cmds.append("rm -rf {}".format(in_proj_dir))
    return cmds

def get_crop_sli(out_pattern):
    cmd = 'ufo-launch read path={}/*.tif ! '.format(os.path.dirname(out_pattern))
    cmd += 'crop x={} width={} y={} height={} ! '. \
        format(EZVARS['inout']['output-x']['value'], EZVARS['inout']['output-width']['value'],
               EZVARS['inout']['output-y']['value'], EZVARS['inout']['output-height']['value'])
    cmd += 'write filename={}'.format(out_pattern)
    if EZVARS['inout']['clip_hist']['value']:
        cmd += ' bits=8 rescale=False'
    return cmd

def fmt_nlmdn_ufo_cmd(inpath: str, outpath: str):
    """
    :param inp: Path to input directory before NLMDN applied
    :param out: Path to output directory after NLMDN applied
    :return:
    """
    cmd = 'ufo-launch read path={}'.format(inpath)
    cmd += ' ! non-local-means patch-radius={}'.format(EZVARS['nlmdn']['patch-radius']['value'])
    cmd += ' search-radius={}'.format(EZVARS['nlmdn']['search-radius']['value'])
    cmd += ' h={}'.format(EZVARS['nlmdn']['h']['value'])
    cmd += ' sigma={}'.format(EZVARS['nlmdn']['sigma']['value'])
    cmd += ' window={}'.format(EZVARS['nlmdn']['window']['value'])
    cmd += ' fast={}'.format(EZVARS['nlmdn']['fast']['value'])
    cmd += ' estimate-sigma={}'.format(EZVARS['nlmdn']['estimate-sigma']['value'])
    cmd += ' ! write filename={}'.format(enquote(outpath))
    if not EZVARS['nlmdn']['bigtiff_output']['value']:
        cmd += " bytes-per-file=0 tiff-bigtiff=False"
    if EZVARS['inout']['clip_hist']['value']:
        cmd += f" bits={SECTIONS['general']['output-bitdepth']['value']} rescale=False"
    return cmd