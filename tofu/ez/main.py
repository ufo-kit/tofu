"""
Created on Apr 5, 2018
@author: sergei gasilov
"""

import logging
import os
from tofu.util import get_filenames, read_image
import warnings

warnings.filterwarnings("ignore")
import time

#from shutil import rmtree

from tofu.ez.ctdir_walker import WalkCTdirs
from tofu.ez.tofu_cmd_gen import tofu_cmds
from tofu.ez.ufo_cmd_gen import ufo_cmds
from tofu.ez.find_axis_cmd_gen import findCOR_cmds
from tofu.ez.util import *

# from tofu.util import get_filenames


LOG = logging.getLogger(__name__)


def get_CTdirs_list(inpath, fdt_names, args):
    """
    Determines whether directories containing CT data are valid.
    Returns list of subdirectories with valid CT data
    :param inpath: Path to the CT directory containing subdirectories with flats/darks/tomo (and flats2 if used)
    :param fdt_names: Names of the directories which store flats/darks/tomo (and flats2 if used)
    :param args: Arguments from the GUI
    :return: W.ctsets: List of "good" CTSets and W.lvl0: Path to root of CT sets
    """
    # Constructor call to create WalkCTDirs object
    W = WalkCTdirs(inpath, fdt_names, args)
    # Find any directories containing "tomo" directory
    W.findCTdirs()
    # If "Use common flats/darks across multiple experiments" is enabled
    if args.main_config_common_flats_darks:
        logging.debug("Use common darks/flats")
        logging.debug("Path to darks: " + str(args.main_config_darks_path))
        logging.debug("Path to flats: " + str(args.main_config_flats_path))
        logging.debug("Path to flats2: " + str(args.main_config_flats2_path))
        logging.debug("Use flats2: " + str(args.main_config_flats2_checkbox))
        # Determine whether paths to common flats/darks/flats2 exist
        if not W.checkCommonFDT():
            print("Invalid path to common flats/darks")
            return W.ctsets, W.lvl0
        else:
            LOG.debug("Paths to common flats/darks exist")
            # Check whether directories contain only .tif files
            if not W.checkCommonFDTFiles():
                return W.ctsets, W.lvl0
            else:
                # Sort good bad sets
                W.SortBadGoodSets()
                return W.ctsets, W.lvl0
    # If "Use common flats/darks across multiple experiments" is not enabled
    else:
        LOG.debug("Use flats/darks in same directory as tomo")
        # Check if common flats/darks/flats2 are type 3 or 4
        W.checkCTdirs()
        # Need to check if common flats/darks contain only .tif files
        W.checkCTfiles()
        W.SortBadGoodSets()
        return W.ctsets, W.lvl0


def frmt_ufo_cmds(cmds, ctset, out_pattern, ax, args, Tofu, Ufo, FindCOR, nviews, WH):
    """formats list of processing commands for a CT set"""
    # two helper variables to mark that PR/FFC has been done at some step
    swiFFC = True  # FFC is always required required
    swiPR = args.main_pr_phase_retrieval  # PR is an optional operation

    ####### PREPROCESSING #########
    flat_file_for_mask = os.path.join(args.main_config_temp_dir, 'flat.tif')
    if args.main_filters_remove_spots:
        if not args.main_config_common_flats_darks:
            flatdir = os.path.join(ctset[0], Tofu._fdt_names[1])
        elif args.main_config_common_flats_darks:
            flatdir = args.main_config_flats_path
        cmd = make_copy_of_flat(flatdir, flat_file_for_mask, args.main_config_dry_run)
        cmds.append(cmd)
    if args.main_config_preprocess:
        cmds.append('echo " - Applying filter(s) to images "')
        cmds_prepro = Ufo.get_pre_cmd(ctset, args.main_config_preprocess_command,
                                      args.main_config_temp_dir,
                                      args.main_config_dry_run, args)
        cmds.extend(cmds_prepro)
        # reset location of input data
        ctset = (args.main_config_temp_dir, ctset[1])
    ###################################################
    if args.main_filters_remove_spots:  # generate commands to remove sci. spots from projections
        cmds.append('echo " - Flat-correcting and removing large spots"')
        cmds_inpaint = Ufo.get_inp_cmd(ctset, args.main_config_temp_dir, args, WH[0], nviews, flat_file_for_mask)
        # reset location of input data
        ctset = (args.main_config_temp_dir, ctset[1])
        cmds.extend(cmds_inpaint)
        swiFFC = False  # no need to do FFC anymore

    ######## PHASE-RETRIEVAL #######
    # Do PR separately if sinograms must be generate or if vertical ROI is defined
    if args.main_pr_phase_retrieval and args.main_filters_ring_removal:  # or (args.main_pr_phase_retrieval and args.main_region_select_rows):
        if swiFFC:  # we still need need flat correction #Inpaint No
            cmds.append('echo " - Phase retrieval with flat-correction"')
            if args.advanced_ffc_sinFFC:
                cmds.append(Tofu.get_pr_sinFFC_cmd(ctset, args, nviews, WH[0]))
                cmds.append(Tofu.get_pr_tofu_cmd_sinFFC(ctset, args, nviews, WH))
            elif not args.advanced_ffc_sinFFC:
                cmds.append(Tofu.get_pr_tofu_cmd(ctset, args, nviews, WH[0]))
        else:  # Inpaint Yes
            cmds.append('echo " - Phase retrieval from flat-corrected projections"')
            cmds.extend(Ufo.get_pr_ufo_cmd(args, nviews, WH))
        swiPR = False  # no need to do PR anymore
        swiFFC = False  # no need to do FFC anymore

    # if args.PR and args.vcrop: # have to reset location of input data
    #    ctset = (args.tmpdir, ctset[1])

    ################# RING REMOVAL #######################
    if args.main_filters_ring_removal:
        # Generate sinograms first
        if swiFFC:  # we still need to do flat-field correction
            if args.advanced_ffc_sinFFC:
                # Create flat corrected images using sinFFC
                cmds.append(Tofu.get_sinFFC_cmd(ctset, args, nviews, WH[0]))
                # Feed the flat corrected images to sino gram generation
                cmds.append(Tofu.get_sinos_noffc_cmd(ctset[0], args.main_config_temp_dir, args, nviews, WH))
            elif not args.advanced_ffc_sinFFC:
                cmds.append('echo " - Make sinograms with flat-correction"')
                cmds.append(Tofu.get_sinos_ffc_cmd(ctset, args.main_config_temp_dir, args, nviews, WH))
        else:  # we do not need flat-field correction
            cmds.append('echo " - Make sinograms without flat-correction"')
            cmds.append(Tofu.get_sinos_noffc_cmd(ctset[0], args.main_config_temp_dir, args, nviews, WH))
        swiFFC = False
        # Filter sinograms
        if args.main_filters_ring_removal_ufo_lpf:
            if args.main_filters_ring_removal_ufo_lpf_1d_or_2d:
                cmds.append('echo " - Ring removal - ufo 1d stripes filter"')
                cmds.append(Ufo.get_filter1d_sinos_cmd(args.main_config_temp_dir,
                            args.main_filters_ring_removal_ufo_lpf_sigma_horizontal, nviews))
            else:
                cmds.append('echo " - Ring removal - ufo 2d stripes filter"')
                cmds.append(Ufo.get_filter2d_sinos_cmd(args.main_config_temp_dir, \
                            args.main_filters_ring_removal_ufo_lpf_sigma_horizontal,
                            args.main_filters_ring_removal_ufo_lpf_sigma_vertical,
                                                       nviews, WH[1]))
        else:
            cmds.append('echo " - Ring removal - sarepy filter(s)"')
            # note - calling an external program, not an ufo-kit script
            tmp = os.path.dirname(os.path.abspath(__file__))
            path_to_filt = os.path.join(tmp, "RR_external.py")
            if os.path.isfile(path_to_filt):
                tmp = os.path.join(args.main_config_temp_dir, "sinos")
                cmdtmp = 'python {} --sinos {} --mws {} --mws2 {} --snr {} --sort_only {}' \
                    .format(path_to_filt, tmp,
                            args.main_filters_ring_removal_sarepy_window_size,
                            args.main_filters_ring_removal_sarepy_window,
                            args.main_filters_ring_removal_sarepy_SNR,
                            int(not args.main_filters_ring_removal_sarepy_wide))
                cmds.append(cmdtmp)
            else:
                cmds.append('echo "Omitting RR because file with filter does not exist"')
        if not args.main_config_keep_temp:
            cmds.append("rm -rf {}".format(os.path.join(args.main_config_temp_dir, "sinos")))
        # Convert filtered sinograms back to projections
        cmds.append('echo " - Generating proj from filtered sinograms"')
        cmds.append(Tofu.get_sinos2proj_cmd(args, WH[0]))
        # reset location of input data
        ctset = (args.main_config_temp_dir, ctset[1])

    # Finally - call to tofu reco
    cmds.append('echo " - CT with axis {}; ffc:{}, PR:{}"'.format(ax, swiFFC, swiPR))
    if args.advanced_ffc_sinFFC and swiFFC:
        cmds.append(Tofu.get_sinFFC_cmd(ctset, args, nviews, WH[0]))
        cmds.append(
            Tofu.get_reco_cmd_sinFFC(ctset, out_pattern, ax, args, nviews, WH, swiFFC, swiPR)
        )
    else:  # If not using sinFFC
        cmds.append(Tofu.get_reco_cmd(ctset, out_pattern, ax, args, nviews, WH, swiFFC, swiPR))

    return nviews, WH


def fmt_nlmdn_ufo_cmd(inpath: str, outpath: str, args):
    """
    :param inp: Path to input directory before NLMDN applied
    :param out: Path to output directory after NLMDN applied
    :param args: List of args
    :return:
    """
    cmd = 'ufo-launch read path={}'.format(inpath)
    cmd += ' ! non-local-means patch-radius={}'.format(args.advanced_nlmdn_patch_radius)
    cmd += ' search-radius={}'.format(args.advanced_nlmdn_sim_search_radius)
    cmd += ' h={}'.format(args.advanced_nlmdn_smoothing_control)
    cmd += ' sigma={}'.format(args.advanced_nlmdn_noise_std)
    cmd += ' window={}'.format(args.advanced_nlmdn_window)
    cmd += ' fast={}'.format(args.advanced_nlmdn_fast)
    cmd += ' estimate-sigma={}'.format(args.advanced_nlmdn_estimate_sigma)
    cmd += ' ! write filename={}'.format(enquote(outpath))
    if not args.advanced_nlmdn_save_bigtiff:
        cmd += " bytes-per-file=0 tiff-bigtiff=False"
    return cmd

def execute_reconstruction(args, fdt_names):
    # array with the list of commands
    cmds = []
    # clean temporary directory or create if it doesn't exist
    if not os.path.exists(args.main_config_temp_dir):
        os.makedirs(args.main_config_temp_dir)
    # else:
    #    clean_tmp_dirs(args.main_config_temp_dir, fdt_names)

    if args.main_region_clip_histogram:
        if args.main_region_histogram_min > args.main_region_histogram_max:
            raise ValueError('hmin must be smaller than hmax to convert to 8bit without contrast inversion')

    # get list of all good CT directories to be reconstructed

    print('*********** Analyzing input directory ************')
    W, lvl0 = get_CTdirs_list(args.main_config_input_dir, fdt_names, args)
    # W is an array of tuples (path, type)
    # get list of already reconstructed sets
    recd_sets = findSlicesDirs(args.main_config_output_dir)
    # initialize command generators
    FindCOR = findCOR_cmds(fdt_names)
    Tofu = tofu_cmds(fdt_names)
    Ufo = ufo_cmds(fdt_names)
    # populate list of reconstruction commands
    print("*********** AXIS INFO ************")
    for i, ctset in enumerate(W):
        # ctset is a tuple containing a path and a type (3 or 4)
        if not already_recd(ctset[0], lvl0, recd_sets):
            # determine initial number of projections and their shape
            path2proj = os.path.join(ctset[0], fdt_names[2])
            nviews, WH, multipage = get_dims(path2proj)
            # If args.main_cor_axis_search_method == 4 then bypass axis search and use image midpoint
            if args.main_cor_axis_search_method != 4:
                if (args.main_region_select_rows and bad_vert_ROI(multipage, path2proj,
                                args.main_region_first_row, args.main_region_number_rows)):
                    print('{}\t{}'.format('CTset:', ctset[0]))
                    print('{:>30}\t{}'.format('Axis:', 'na'))
                    print('Vertical ROI does not contain any rows.')
                    print("{:>30}\t{}, dimensions: {}".format("Number of projections:", nviews, WH))
                    continue
                # Find axis of rotation using auto: correlate first/last projections
                if args.main_cor_axis_search_method == 1:
                    ax = FindCOR.find_axis_corr(ctset,
                                    args.main_region_select_rows,
                                    args.main_region_first_row,
                                    args.main_region_number_rows, multipage, args)
                # Find axis of rotation using auto: minimize STD of a slice
                elif args.main_cor_axis_search_method == 2:
                    cmds.append("echo \"Cleaning axis-search in tmp directory\"")
                    os.system('rm -rf {}'.format(os.path.join(args.main_config_temp_dir, 'axis-search')))
                    ax = FindCOR.find_axis_std(ctset,
                                               args.main_config_temp_dir,
                                               args.main_cor_axis_search_interval,
                                               args.main_cor_recon_patch_size,
                                               args.main_cor_search_row_start,
                                               nviews, args, WH)
                else:
                    ax = args.main_cor_axis_column + i * args.main_cor_axis_increment_step
            # If args.main_cor_axis_search_method == 4 then bypass axis search and use image midpoint
            elif args.main_cor_axis_search_method == 4:
                ax = FindCOR.find_axis_image_midpoint(ctset, multipage, WH)
                print("Bypassing axis search and using image midpoint: {}".format(ax))

            setid = ctset[0][len(lvl0) + 1:]
            out_pattern = os.path.join(args.main_config_output_dir, setid, 'sli/sli')
            cmds.append('echo ">>>>> PROCESSING {}"'.format(setid))
            # rm files in temporary directory first of all to
            # format paths correctly and to avoid problems
            # when reconstructing ct sets with variable number of rows or projections
            cmds.append('echo "Cleaning temporary directory"'.format(setid))
            clean_tmp_dirs(args.main_config_temp_dir, fdt_names)
            # call function which formats commands for this data set
            nviews, WH = frmt_ufo_cmds(cmds, ctset, out_pattern, \
                                       ax, args, Tofu, Ufo, FindCOR, nviews, WH)
            save_params(args, setid, ax, nviews, WH)
            print('{}\t{}'.format('CTset:', ctset[0]))
            print('{:>30}\t{}'.format('Axis:', ax))
            print("{:>30}\t{}, dimensions: {}".format("Number of projections:", nviews, WH))
            # tmp = "Number of projections: {}, dimensions: {}".format(nviews, WH)
            # cmds.append("echo \"{}\"".format(tmp))
            if args.advanced_nlmdn_apply_after_reco:
                logging.debug("Using Non-Local Means Denoising")
                nlmdn_input = out_pattern
                head, tail = os.path.split(out_pattern)
                slidir = os.path.dirname(head)
                nlmdn_output = os.path.join(slidir+"-nlmdn", "sli-nlmdn-%04i.tif")
                cmds.append(fmt_nlmdn_ufo_cmd(slidir, nlmdn_output, args))
        else:
            print("{} has been already reconstructed".format(ctset[0]))
    # execute commands = start reconstruction
    start = time.time()
    print("*********** PROCESSING ************")
    for cmd in cmds:
        if not args.main_config_dry_run:
            os.system(cmd)
        else:
            print(cmd)
    if not args.main_config_keep_temp:
        clean_tmp_dirs(args.main_config_temp_dir, fdt_names)

    print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print("*** Done. Total processing time {} sec.".format(int(time.time() - start)))
    print("*** Waiting for the next job...........")
    # cmnds, axes = get_ufo_cmnds(W, tmpdir, recodir, fol, axes = None, dryrun = False)


def already_recd(ctset, indir, recd_sets):
    x = False
    if ctset[len(indir) + 1 :] in recd_sets:
        x = True
    return x


def findSlicesDirs(lvl0):
    recd_sets = []
    for root, dirs, files in os.walk(lvl0):
        for name in dirs:
            if name == "sli":
                recd_sets.append(root[len(lvl0) + 1 :])
    return recd_sets
