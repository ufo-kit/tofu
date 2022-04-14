#!/bin/python
"""
Created on Apr 6, 2018
@author: gasilos
"""
import os
import numpy as np
from tofu.ez.ufo_cmd_gen import fmt_in_out_path


class tofu_cmds(object):
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

    def check_lamino(self, cmd, args):
        cmd += 'tofu reco'
        if not args.advanced_advtofu_lamino_angle == '':
            cmd += ' --axis-angle-x {}'.format(args.advanced_advtofu_lamino_angle)
        if not args.advanced_adv_tofu_z_axis_rotation == '':
            cmd += ' --overall-angle {}'.format(args.advanced_adv_tofu_z_axis_rotation)
        if not args.advanced_advtofu_center_position_z == '':
            cmd += ' --center-position-z {}'.format(args.advanced_advtofu_center_position_z)
        if not args.advanced_advtofu_y_axis_rotation == '':
            cmd += ' --axis-angle-y {}'.format(args.advanced_advtofu_y_axis_rotation)
        return cmd

    def check_8bit(self, cmd, gray256, bit, hmin, hmax):
        if gray256:
            cmd += " --output-bitdepth {}".format(bit)
            # cmd += " --output-minimum \" {}\" --output-maximum \" {}\""\
            # .format(hmin, hmax)
            cmd += ' --output-minimum " {}" --output-maximum " {}"'.format(hmin, hmax)
        return cmd

    def check_vcrop(self, cmd, vcrop, y, yheight, ystep, ori_height):
        if vcrop:
            cmd += " --y {} --height {} --y-step {}".format(y, yheight, ystep)
        else:
            cmd += " --height {}".format(ori_height)
        return cmd

    def check_bigtif(self, cmd, swi):
        if not swi:
            cmd += " --output-bytes-per-file 0"
        return cmd

    def get_1step_ct_cmd(self, ctset, out_pattern, ax, args, nviews, WH):
        # direct CT reconstruction from input dir to output dir;
        # or CT reconstruction after preprocessing only
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        # correct location of proj folder in case if prepro was done
        in_proj_dir, quatsch = fmt_in_out_path(args.main_config_temp_dir,
                                               ctset[0], self._fdt_names[2], False)
        indir[2] = os.path.join(os.path.split(indir[2])[0], os.path.split(in_proj_dir)[1])
        # format command
        cmd = "tofu tomo --absorptivity --fix-nan-and-inf"
        cmd += " --darks {} --flats {} --projections {}".format(indir[0], indir[1], indir[2])
        if ctset[1] == 4:  # must be equivalent to len(indir)>3
            cmd += " --flats2 {}".format(indir[3])
        cmd += " --output {}".format(out_pattern)
        cmd += " --axis {}".format(ax)
        cmd += " --offset {}".format(args.main_region_rotate_volume_clock)
        cmd += " --number {}".format(nviews)
        if args.step > 0.0:
            cmd += ' --angle {}'.format(args.step)
        cmd = self.check_vcrop(cmd, args.main_region_select_rows,
                               args.main_region_first_row,
                               args.main_region_number_rows,
                               args.main_region_nth_row, WH[0])
        cmd = self.check_8bit(cmd, args.main_region_clip_histogram,
                              args.main_region_bit_depth,
                              args.main_region_histogram_min,
                              args.main_region_histogram_max)
        cmd = self.check_bigtif(cmd, args.main_config_save_multipage_tiff)
        return cmd

    def get_ct_proj_cmd(self, out_pattern, ax, args, nviews, WH):
        # CT reconstruction from pre-processed and flat-corrected projections
        in_proj_dir, quatsch = fmt_in_out_path(
            args.main_config_temp_dir, "obsolete;if-you-need-fix-it", self._fdt_names[2], False
        )
        cmd = "tofu tomo --projections {}".format(in_proj_dir)
        cmd += " --output {}".format(out_pattern)
        cmd += " --axis {}".format(ax)
        cmd += " --offset {}".format(args.main_region_rotate_volume_clock)
        cmd += " --number {}".format(nviews)
        if args.step > 0.0:
            cmd += ' --angle {}'.format(args.step)
        cmd = self.check_vcrop(cmd, args.main_region_select_rows,
                               args.main_region_first_row,
                               args.main_region_number_rows,
                               args.main_region_nth_row, WH[0])
        cmd = self.check_8bit(cmd, args.main_region_clip_histogram,
                              args.main_region_bit_depth,
                              args.main_region_histogram_min,
                              args.main_region_histogram_max)
        cmd = self.check_bigtif(cmd, args.main_config_save_multipage_tiff)
        return cmd

    def get_ct_sin_cmd(self, out_pattern, ax, args, nviews, WH):
        sinos_dir = os.path.join(args.main_config_temp_dir, 'sinos-filt')
        cmd = 'tofu tomo --sinograms {}'.format(sinos_dir)
        cmd += ' --output {}'.format(out_pattern)
        cmd += ' --axis {}'.format(ax)
        cmd += ' --offset {}'.format(args.main_region_rotate_volume_clock)
        if args.main_region_select_rows:
            cmd += ' --number {}'.format(int(args.main_region_number_rows / args.main_region_nth_row))
        else:
            cmd += " --number {}".format(WH[0])
        cmd += " --height {}".format(nviews)
        if args.step > 0.0:
            cmd += ' --angle {}'.format(args.step)
        cmd = self.check_8bit(cmd, args.main_region_clip_histogram,
                              args.main_region_bit_depth,
                              args.main_region_histogram_min,
                              args.main_region_histogram_max)
        cmd = self.check_bigtif(cmd, args.main_config_save_multipage_tiff)
        return cmd

    def get_sinos_ffc_cmd(self, ctset, tmpdir, args, nviews, WH):
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir,
                                        ctset[0], self._fdt_names[2], False)
        cmd = 'tofu sinos --absorptivity --fix-nan-and-inf'
        cmd += ' --darks {} --flats {} '.format(indir[0], indir[1])
        if ctset[1] == 4:
            cmd += " --flats2 {}".format(indir[3])
        cmd += " --projections {}".format(in_proj_dir)
        cmd += " --output {}".format(os.path.join(tmpdir, "sinos/sin-%04i.tif"))
        cmd += " --number {}".format(nviews)
        cmd = self.check_vcrop(cmd, args.main_region_select_rows,
                               args.main_region_first_row,
                               args.main_region_number_rows,
                               args.main_region_nth_row, WH[0])
        if not args.main_filters_ring_removal_ufo_lpf:
            # because second RR algorithm does not know how to work with multipage tiffs
            cmd += " --output-bytes-per-file 0"
        if not args.advanced_advtofu_aux_ffc_dark_scale == "":
            cmd += ' --dark-scale {}'.format(args.advanced_advtofu_aux_ffc_dark_scale)
        if not args.advanced_advtofu_aux_ffc_flat_scale == "":
            cmd += ' --flat-scale {}'.format(args.advanced_advtofu_aux_ffc_flat_scale)
        return cmd

    def get_sinos_noffc_cmd(self, ctsetpath, tmpdir, args, nviews, WH):
        in_proj_dir, out_pattern = fmt_in_out_path(
            args.main_config_temp_dir, ctsetpath, self._fdt_names[2], False
        )
        cmd = "tofu sinos"
        cmd += " --projections {}".format(in_proj_dir)
        cmd += " --output {}".format(os.path.join(tmpdir, "sinos/sin-%04i.tif"))
        cmd += " --number {}".format(nviews)
        cmd = self.check_vcrop(cmd, args.main_region_select_rows,
                               args.main_region_first_row,
                               args.main_region_number_rows,
                               args.main_region_nth_row,
                               WH[0])
        if not args.main_filters_ring_removal_ufo_lpf:
            # because second RR algorithm does not know how to work with multipage tiffs
            cmd += " --output-bytes-per-file 0"
        return cmd

    def get_sinos2proj_cmd(self, args, proj_height):
        quatsch, out_pattern = fmt_in_out_path(args.main_config_temp_dir, 'quatsch', self._fdt_names[2], True)
        cmd = 'tofu sinos'
        cmd += ' --projections {}'.format(os.path.join(args.main_config_temp_dir, 'sinos-filt'))
        cmd += ' --output {}'.format(out_pattern)
        if not args.main_region_select_rows:
            cmd += ' --number {}'.format(proj_height)
        else:
            cmd += ' --number {}'.format(int(args.main_region_number_rows / args.main_region_nth_row))
        return cmd

    def get_sinFFC_cmd(self, ctset, args, nviews, n):
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir,
                                                   ctset[0], self._fdt_names[2])
        cmd = 'bmit_sin --fix-nan'
        cmd += ' --darks {} --flats {} --projections {}'.format(indir[0], indir[1], in_proj_dir)
        if ctset[1] == 4:
            cmd += ' --flats2 {}'.format(indir[3])
        cmd += ' --output {}'.format(os.path.dirname(out_pattern))
        cmd += ' --method {}'.format(args.advanced_ffc_method)
        cmd += ' --multiprocessing'
        cmd += ' --eigen-pco-repetitions {}'.format(args.advanced_ffc_eigen_pco_reps)
        cmd += ' --eigen-pco-downsample {}'.format(args.advanced_ffc_eigen_pco_downsample)
        cmd += ' --downsample {}'.format(args.advanced_ffc_downsample)
        return cmd

    def get_pr_sinFFC_cmd(self, ctset, args, nviews, n):
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        in_proj_dir, out_pattern = fmt_in_out_path(
            args.main_config_temp_dir, ctset[0], self._fdt_names[2])
        cmd = 'bmit_sin --fix-nan'
        cmd += ' --darks {} --flats {} --projections {}'.format(indir[0], indir[1], in_proj_dir)
        if ctset[1] == 4:
            cmd += ' --flats2 {}'.format(indir[3])
        cmd += ' --output {}'.format(os.path.dirname(out_pattern))
        cmd += ' --method {}'.format(args.advanced_ffc_method)
        cmd += ' --multiprocessing'
        cmd += ' --eigen-pco-repetitions {}'.format(args.advanced_ffc_eigen_pco_reps)
        cmd += ' --eigen-pco-downsample {}'.format(args.advanced_ffc_eigen_pco_downsample)
        cmd += ' --downsample {}'.format(args.advanced_ffc_downsample)
        return cmd

    def get_pr_tofu_cmd_sinFFC(self, ctset, args, nviews, WH):
        # indir will format paths to flats darks and tomo2 correctly even if they were
        # pre-processed, however path to the input directory with projections
        # cannot be formatted with that command correctly
        # indir = self.make_inpaths(ctset[0], ctset[1])
        # so we need a separate "universal" command which considers all previous steps
        in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir,
                                                   ctset[0], self._fdt_names[2])
        # Phase retrieval
        cmd = 'tofu preprocess --delta 1e-6'
        cmd += ' --energy {} --propagation-distance {}' \
               ' --pixel-size {} --regularization-rate {:0.2f}' \
            .format(args.main_pr_photon_energy, args.main_pr_detector_distance,
                    args.main_pr_pixel_size, args.main_pr_delta_beta_ratio)
        cmd += ' --projections {}'.format(in_proj_dir)
        cmd += ' --output {}'.format(out_pattern)
        cmd += ' --projection-crop-after filter'
        return cmd

    def get_pr_tofu_cmd(self, ctset, args, nviews, WH):
        # indir will format paths to flats darks and tomo2 correctly even if they were
        # pre-processed, however path to the input directory with projections
        # cannot be formatted with that command correctly
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        # so we need a separate "universal" command which considers all previous steps
        in_proj_dir, out_pattern = fmt_in_out_path(args.main_config_temp_dir,
                                                   ctset[0], self._fdt_names[2])
        cmd = 'tofu preprocess --fix-nan-and-inf --projection-filter none --delta 1e-6'
        cmd += ' --darks {} --flats {} --projections {}'.format(indir[0], indir[1], in_proj_dir)
        if ctset[1] == 4:
            cmd += ' --flats2 {}'.format(indir[3])
        cmd += ' --output {}'.format(out_pattern)
        cmd += ' --energy {} --propagation-distance {}' \
               ' --pixel-size {} --regularization-rate {:0.2f}' \
            .format(args.main_pr_photon_energy, args.main_pr_detector_distance,
                    args.main_pr_pixel_size, args.main_pr_delta_beta_ratio)
        if not args.advanced_advtofu_aux_ffc_dark_scale == "":
            cmd += ' --dark-scale {}'.format(args.advanced_advtofu_aux_ffc_dark_scale)
        if not args.advanced_advtofu_aux_ffc_flat_scale == "":
            cmd += ' --flat-scale {}'.format(args.advanced_advtofu_aux_ffc_flat_scale)
        return cmd

    def get_reco_cmd(self, ctset, out_pattern, ax, args, nviews, WH, ffc, PR):
        # direct CT reconstruction from input dir to output dir;
        # or CT reconstruction after preprocessing only
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        # correct location of proj folder in case if prepro was done
        in_proj_dir, quatsch = fmt_in_out_path(args.main_config_temp_dir,
                                               ctset[0], self._fdt_names[2], False)
        # Laminography
        cmd = ''
        if args.advanced_advtofu_extended_settings is True:
            cmd += self.check_lamino(cmd, args)
        elif args.advanced_advtofu_extended_settings is False:
            cmd = "tofu reco"
            cmd += ' --overall-angle 180'
        ##############
        cmd += '  --projections {}'.format(in_proj_dir)
        cmd += ' --output {}'.format(out_pattern)
        if ffc:
            cmd += ' --fix-nan-and-inf'
            cmd += ' --darks {} --flats {}'.format(indir[0], indir[1])
            if ctset[1] == 4:  # must be equivalent to len(indir)>3
                cmd += ' --flats2 {}'.format(indir[3])
            if not PR:
                cmd += ' --absorptivity'
            if not args.advanced_advtofu_aux_ffc_dark_scale == "":
                cmd += ' --dark-scale {}'.format(args.advanced_advtofu_aux_ffc_dark_scale)
            if not args.advanced_advtofu_aux_ffc_flat_scale == "":
                cmd += ' --flat-scale {}'.format(args.advanced_advtofu_aux_ffc_flat_scale)
        if PR:
            cmd += (
                " --disable-projection-crop"
                " --delta 1e-6"
                " --energy {} --propagation-distance {}"
                " --pixel-size {} --regularization-rate {:0.2f}" \
                    .format(args.main_pr_photon_energy, args.main_pr_detector_distance,
                            args.main_pr_pixel_size, args.main_pr_delta_beta_ratio)
            )
        cmd += " --center-position-x {}".format(ax)
        # if args.nviews==0:
        cmd += " --number {}".format(nviews)
        # elif args.nviews>0:
        #    cmd += ' --number {}'.format(args.nviews)
        cmd += ' --volume-angle-z {:0.5f}'.format(args.main_region_rotate_volume_clock)
        # rows-slices to be reconstructed
        # full ROI
        b = int(np.ceil(WH[0] / 2.0))
        a = -int(WH[0] / 2.0)
        c = 1
        if args.main_region_select_rows:
            if args.main_filters_ring_removal:
                h2 = args.main_region_number_rows / args.main_region_nth_row / 2.0
                b = np.ceil(h2)
                a = -int(h2)
            else:
                h2 = int(WH[0] / 2.0)
                a = args.main_region_first_row - h2
                b = args.main_region_first_row + args.main_region_number_rows - h2
                c = args.main_region_nth_row
        cmd += ' --region={},{},{}'.format(a, b, c)
        # crop of reconstructed slice in the axial plane
        b = WH[1] / 2
        if args.main_region_crop_slices:
            cmd += ' --x-region={},{},{}'.format(args.main_region_crop_x - b,
                        args.main_region_crop_x + args.main_region_crop_width - b, 1)
            cmd += ' --y-region={},{},{}'.format(args.main_region_crop_y - b,
                        args.main_region_crop_y + args.main_region_crop_height - b, 1)
        # cmd = self.check_vcrop(cmd, args.main_region_select_rows, args.main_region_first_row, args.main_region_number_rows, args.main_region_nth_row, WH[0])
        cmd = self.check_8bit(cmd, args.main_region_clip_histogram,
                              args.main_region_bit_depth,
                              args.main_region_histogram_min,
                              args.main_region_histogram_max)
        cmd = self.check_bigtif(cmd, args.main_config_save_multipage_tiff)
        # Optimization
        cmd += ' --slice-memory-coeff={}'.format(args.advanced_optimize_slice_mem_coeff)
        if args.advanced_optimize_verbose_console:
            cmd += ' --verbose'
        if not args.advanced_optimize_num_gpus == '':
            cmd += ' --gpus {}'.format(args.advanced_optimize_num_gpus)
        if not args.advanced_optimize_slices_per_device == '':
            cmd += ' --slices-per-device {}'.format(args.advanced_optimize_slices_per_device)
        return cmd

    def get_reco_cmd_sinFFC(self, ctset, out_pattern, ax, args, nviews, WH, ffc, PR):
        # direct CT reconstruction from input dir to output dir;
        # or CT reconstruction after preprocessing only
        indir = self.make_inpaths(ctset[0], ctset[1], args)
        # correct location of proj folder in case if prepro was done
        in_proj_dir, quatsch = fmt_in_out_path(args.main_config_temp_dir,
                                        ctset[0], self._fdt_names[2], False)
        # in_proj_dir, quatsch = fmt_in_out_path(args.tmpdir,args.indir, self._fdt_names[2], False)
        # indir[2]=os.path.join(os.path.split(indir[2])[0], os.path.split(in_proj_dir)[1])
        # format command
        cmd = "tofu reco"
        # Laminography
        if args.advanced_advtofu_extended_settings:
            cmd += self.check_lamino(cmd, args)
        else:
            cmd += " --overall-angle 180"
        ##############
        cmd += "  --projections {}".format(in_proj_dir)
        cmd += " --output {}".format(out_pattern)
        if PR:
            cmd += ' --disable-projection-crop' \
                   ' --delta 1e-6' \
                   ' --energy {} --propagation-distance {}' \
                   ' --pixel-size {} --regularization-rate {:0.2f}' \
                .format(args.main_pr_photon_energy, args.main_pr_detector_distance,
                        args.main_pr_pixel_size, args.main_pr_delta_beta_ratio)
        cmd += ' --center-position-x {}'.format(ax)
        # if args.nviews==0:
        cmd += " --number {}".format(nviews)
        # elif args.nviews>0:
        #    cmd += ' --number {}'.format(args.nviews)
        cmd += " --volume-angle-z {:0.5f}".format(args.main_region_rotate_volume_clock)
        # rows-slices to be reconstructed
        # full ROI
        b = int(np.ceil(WH[0] / 2.0))
        a = -int(WH[0] / 2.0)
        c = 1
        if args.main_region_select_rows:
            if args.main_filters_ring_removal:
                h2 = args.main_region_number_rows / args.main_region_nth_row / 2.0
                b = np.ceil(h2)
                a = -int(h2)
            else:
                h2 = int(WH[0] / 2.0)
                a = args.main_region_first_row - h2
                b = args.main_region_first_row + args.main_region_number_rows - h2
                c = args.main_region_nth_row
        cmd += ' --region={},{},{}'.format(a, b, c)
        # crop of reconstructed slice in the axial plane
        b = WH[1] / 2
        if args.main_region_crop_slices:
            cmd += ' --x-region={},{},{}'.format(args.main_region_crop_x - b,
                            args.main_region_crop_x + args.main_region_crop_width - b, 1)
            cmd += ' --y-region={},{},{}'.format(args.main_region_crop_y - b,
                            args.main_region_crop_y + args.main_region_crop_height - b, 1)
        # cmd = self.check_vcrop(cmd, args.main_region_select_rows, args.main_region_first_row, args.main_region_number_rows, args.main_region_nth_row, WH[0])
        cmd = self.check_8bit(cmd, args.main_region_clip_histogram,
                              args.main_region_bit_depth,
                              args.main_region_histogram_min,
                              args.main_region_histogram_max)
        cmd = self.check_bigtif(cmd, args.main_config_save_multipage_tiff)
        # Optimization
        cmd += ' --slice-memory-coeff={}'.format(args.advanced_optimize_slice_mem_coeff)
        if args.advanced_optimize_verbose_console:
            cmd += ' --verbose'
        if not args.advanced_optimize_num_gpus == '':
            cmd += ' --gpus {}'.format(args.advanced_optimize_num_gpus)
        if not args.advanced_optimize_slices_per_device == '':
            cmd += ' --slices-per-device {}'.format(args.advanced_optimize_slices_per_device)
        return cmd
