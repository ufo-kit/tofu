#!/bin/python
"""
Created on Apr 6, 2018
@author: gasilos
"""
import glob
import os
from tofu.util import get_filenames, read_image, next_power_of_two
from tofu.ez.util import enquote


def fmt_in_out_path(tmpdir, indir, raw_proj_dir_name, croutdir=True):
    # suggests input and output path to directory with proj
    # depending on number of processing steps applied so far
    li = sorted(glob.glob(os.path.join(tmpdir, "proj-step*")))
    proj_dirs = [d for d in li if os.path.isdir(d)]
    Nsteps = len(proj_dirs)
    in_proj_dir, out_proj_dir = "qqq", "qqq"
    if Nsteps == 0:  # no projections in temporary directory
        in_proj_dir = os.path.join(indir, raw_proj_dir_name)
        out_proj_dir = "proj-step1"
    elif Nsteps > 0:  # there are directories proj-stepX in tmp dir
        in_proj_dir = proj_dirs[-1]
        out_proj_dir = "{}{}".format(in_proj_dir[:-1], Nsteps + 1)
    else:
        raise ValueError("Something is wrong with in/out filenames")
    # physically create output directory
    tmp = os.path.join(tmpdir, out_proj_dir)
    if croutdir and not os.path.exists(tmp):
        os.makedirs(tmp)
    # return names of input directory and output pattern with abs path
    return in_proj_dir, os.path.join(tmp, "proj-%04i.tif")


class ufo_cmds(object):
    """
    Generates partially formatted ufo-launch and tofu commands
    Parameters are included in the string; pathnames must be added
    """

    def __init__(self, fol):
        self._fdt_names = fol

    def make_inpaths(self, lvl0, flats2, args):
        """
        Creates a list of paths to flats/darks/tomo directories
        :param lvl0: Root of directory containing flats/darks/tomo
        :param flats2: The type of directory: 3 contains flats/darks/tomo 4 contains flats/darks/tomo/flats2
        :return: List of paths to the directories containing darks/flats/tomo and flats2 (if used)
        """
        indir = []
        # If using flats/darks/flats2 in same dir as tomo
        if not args.main_config_common_flats_darks:
            for i in self._fdt_names[:3]:
                indir.append(os.path.join(lvl0, i))
            if flats2 - 3:
                indir.append(os.path.join(lvl0, self._fdt_names[3]))
            return indir
        # If using common flats/darks/flats2 across multiple reconstructions
        elif args.main_config_common_flats_darks:
            indir.append(args.main_config_darks_path)
            indir.append(args.main_config_flats_path)
            indir.append(os.path.join(lvl0, self._fdt_names[2]))
            if args.main_config_flats2_checkbox:
                indir.append(args.main_config_flats2_path)
            return indir

    def check_vcrop(self, cmd, vcrop, y, yheight, ystep):
        if vcrop:
            cmd += " --y {} --height {} --y-step {}".format(y, yheight, ystep)
        return cmd

    def check_bigtif(self, cmd, swi):
        if not swi:
            cmd += " bytes-per-file=0"
        return cmd

    def get_pr_ufo_cmd(self, args, nviews, WH):
        # in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir,args.main_config_input_dir,self._fdt_names[2])
        in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir,
                                                   "quatsch", self._fdt_names[2])
        cmds = []
        pad_width = next_power_of_two(WH[1] + 50)
        pad_height = next_power_of_two(WH[0] + 50)
        pad_x = (pad_width - WH[1]) / 2
        pad_y = (pad_height - WH[0]) / 2
        cmd = 'ufo-launch read path={} height={} number={}'.format(in_proj_dir, WH[0], nviews)
        cmd += ' ! pad x={} width={} y={} height={}'.format(pad_x, pad_width, pad_y, pad_height)
        cmd += ' addressing-mode=clamp_to_edge'
        cmd += ' ! fft dimensions=2 ! retrieve-phase'
        cmd += ' energy={} distance={} pixel-size={} regularization-rate={:0.2f}' \
            .format(args.main_pr_photon_energy, args.main_pr_detector_distance,
                    args.main_pr_pixel_size, args.main_pr_delta_beta_ratio)
        cmd += ' ! ifft dimensions=2 crop-width={} crop-height={}' \
            .format(pad_width, pad_height)
        cmd += ' ! crop x={} width={} y={} height={}'.format(pad_x, WH[1], pad_y, WH[0])
        cmd += ' ! opencl kernel=\'absorptivity\' ! opencl kernel=\'fix_nan_and_inf\' !'
        cmd += ' write filename={}'.format(enquote(out_pattern))
        cmds.append(cmd)
        if not args.main_config_keep_temp:
            cmds.append('rm -rf {}'.format(in_proj_dir))
        return cmds

    def get_filter1d_sinos_cmd(self, tmpdir, RR, nviews):
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

    def get_filter2d_sinos_cmd(self, tmpdir, sig_hor, sig_ver, nviews, w):
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

    def get_pre_cmd(self, ctset, pre_cmd, tmpdir, dryrun, args):
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        outdir = self.make_inpaths(tmpdir, ctset[1], args)
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

    def get_inp_cmd(self, ctset, tmpdir, args, N, nviews, any_flat):
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        outdir = self.make_inpaths(tmpdir, ctset[1], args)
        cmds = []
        ######### CREATE MASK #########
        mask_file = os.path.join(tmpdir, "mask.tif")
        # generate mask
        cmd = 'tofu find-large-spots --images {}'.format(any_flat)
        cmd += ' --spot-threshold {} --gauss-sigma {}'.format(
                        args.main_filters_remove_spots_threshold,
                        args.main_filters_remove_spots_blur_sigma)
        cmd += ' --output {} --output-bytes-per-file 0'.format(mask_file)
        cmds.append(cmd)
        ######### FLAT-CORRECT #########
        in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir, ctset[0], self._fdt_names[2])
        if args.advanced_ffc_sinFFC:
            cmd = 'bmit_sin --fix-nan'
            cmd += ' --darks {} --flats {}'.format(indir[0], indir[1])
            cmd += ' --projections {}'.format(in_proj_dir)
            cmd += ' --output {}'.format(os.path.dirname(out_pattern))
            cmd += ' --multiprocessing'
            #cmd += ' --output {}'.format(out_pattern)
            if ctset[1] == 4:
                cmd += ' --flats2 {}'.format(indir[3])
            # Add options for eigen-pco-repetitions etc.
            cmd += ' --eigen-pco-repetitions {}'.format(args.advanced_ffc_eigen_pco_reps)
            cmd += ' --eigen-pco-downsample {}'.format(args.advanced_ffc_eigen_pco_downsample)
            cmd += ' --downsample {}'.format(args.advanced_ffc_downsample)
            #if not args.main_pr_phase_retrieval:
            #    cmd += ' --absorptivity'
            cmds.append(cmd)
        elif not args.advanced_ffc_sinFFC:
            cmd = 'tofu flatcorrect --fix-nan-and-inf'
            cmd += ' --darks {} --flats {}'.format(indir[0], indir[1])
            cmd += ' --projections {}'.format(in_proj_dir)
            cmd += ' --output {}'.format(out_pattern)
            if ctset[1] == 4:
                cmd += ' --flats2 {}'.format(indir[3])
            if not args.main_pr_phase_retrieval:
                cmd += ' --absorptivity'
            if not args.advanced_advtofu_aux_ffc_dark_scale == "":
                cmd += ' --dark-scale {}'.format(args.advanced_advtofu_aux_ffc_dark_scale)
            if not args.advanced_advtofu_aux_ffc_flat_scale == "":
                cmd += ' --flat-scale {}'.format(args.advanced_advtofu_aux_ffc_flat_scale)
            cmds.append(cmd)
        if not args.main_config_keep_temp and args.main_config_preprocess:
            cmds.append('rm -rf {}'.format(indir[0]))
            cmds.append('rm -rf {}'.format(indir[1]))
            cmds.append('rm -rf {}'.format(in_proj_dir))
            if len(indir) > 3:
                cmds.append("rm -rf {}".format(indir[3]))
        ######### INPAINT #########
        in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir, ctset[0], self._fdt_names[2])
        cmd = "ufo-launch [read path={} height={} number={}".format(in_proj_dir, N, nviews)
        cmd += ", read path={}]".format(mask_file)
        cmd += " ! horizontal-interpolate ! "
        cmd += "write filename={}".format(enquote(out_pattern))
        cmds.append(cmd)
        if not args.main_config_keep_temp:
            cmds.append("rm -rf {}".format(in_proj_dir))
        return cmds

    def get_crop_sli(self, out_pattern, args):
        cmd = 'ufo-launch read path={}/*.tif ! '.format(os.path.dirname(out_pattern))
        cmd += 'crop x={} width={} y={} height={} ! '. \
            format(args.main_region_crop_x, args.main_region_crop_width,
                   args.main_region_crop_y, args.main_region_crop_height)
        cmd += 'write filename={}'.format(out_pattern)
        if args.main_region_clip_histogram:
            cmd += ' bits=8 rescale=False'
        return cmd
