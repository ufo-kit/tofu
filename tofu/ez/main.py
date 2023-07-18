"""
Created on Apr 5, 2018
@author: sergei gasilov
"""

import logging
import os
import warnings
warnings.filterwarnings("ignore")
import time

from tofu.ez.ctdir_walker import WalkCTdirs
from tofu.ez.tofu_cmd_gen import *
from tofu.ez.ufo_cmd_gen import *
from tofu.ez.find_axis_cmd_gen import *
from tofu.ez.util import *
from tofu.ez.image_read_write import TiffSequenceReader
from tifffile import imwrite
from tofu.ez.params import EZVARS
from tofu.config import SECTIONS

LOG = logging.getLogger(__name__)


def get_CTdirs_list(inpath, fdt_names):
    """
    Determines whether directories containing CT data are valid.
    Returns list of subdirectories with valid CT data
    :param inpath: Path to the CT directory containing subdirectories with flats/darks/tomo (and flats2 if used)
    :param fdt_names: Names of the directories which store flats/darks/tomo (and flats2 if used)
    :return: W.ctsets: List of "good" CTSets and W.lvl0: Path to root of CT sets
    """
    # Constructor call to create WalkCTDirs object
    W = WalkCTdirs(inpath, fdt_names)
    # Find any directories containing "tomo" directory
    W.findCTdirs()
    # If "Use common flats/darks across multiple experiments" is enabled
    if EZVARS['inout']['shared-flatsdarks']['value']:
        logging.debug("Use common darks/flats")
        logging.debug("Path to darks: " + str(EZVARS['inout']['path2-shared-darks']['value']))
        logging.debug("Path to flats: " + str(EZVARS['inout']['path2-shared-flats']['value']))
        logging.debug("Path to flats2: " + str(EZVARS['inout']['path2-shared-flats2']['value']))
        logging.debug("Use flats2: " + str(EZVARS['inout']['shared-flats-after']['value']))
        # Determine whether paths to common flats/darks/flats2 exist
        if not W.checkcommonfdt():
            print("Invalid path to common flats/darks")
            return W.ctsets, W.lvl0
        else:
            LOG.debug("Paths to common flats/darks exist")
            # Check whether directories contain only .tif files
            if not W.checkcommonfdtFiles():
                return W.ctsets, W.lvl0
            else:
                # Sort good bad sets
                W.sortbadgoodsets()
                return W.ctsets, W.lvl0
    # If "Use common flats/darks across multiple experiments" is not enabled
    else:
        LOG.debug("Use flats/darks in same directory as tomo")
        # Check if common flats/darks/flats2 are type 3 or 4
        W.checkCTdirs()
        # Need to check if common flats/darks contain only .tif files
        W.checkCTfiles()
        W.sortbadgoodsets()
        return W.ctsets, W.lvl0


def frmt_ufo_cmds(cmds, ctset, out_pattern, ax, nviews, wh):
    """formats list of processing commands for a CT set"""
    # two helper variables to note that PR/FFC has been done at some step
    swiFFC = True  # FFC is always required
    swiPR = SECTIONS['retrieve-phase']['enable-phase']['value']  # PR is an optional operation

    ####### PREPROCESSING #########
    #if we need to use shared flat/darks we have to do it only once so we need to keep track of that
    #will be set to False in util/make_inpaths as soon as it was used
    add_value_to_dict_entry(EZVARS['inout']['shared-df-used'], False)
    if EZVARS['filters']['rm_spots']['value']:
        # copy one flat to tmpdir now as path might change if preprocess is enabled
        if not EZVARS['inout']['shared-flatsdarks']['value']:
            tsr = TiffSequenceReader(os.path.join(ctset[0],
                                     EZVARS['inout']['flats-dir']['value']))
        else:
            tsr = TiffSequenceReader(os.path.join(ctset[0],
                                     EZVARS['inout']['path2-shared-flats']['value']))
        flat1 = tsr.read(tsr.num_images - 1)  # taking the last flat
        tsr.close()
        flat1_file = os.path.join(EZVARS['inout']['tmp-dir']['value'], "flat1.tif")
        imwrite(flat1_file, flat1)
    if EZVARS['inout']['preprocess']['value']:
        cmds.append('echo " - Applying filter(s) to images "')
        cmds_prepro = get_pre_cmd(ctset, EZVARS['inout']['preprocess-command']['value'],
                                      EZVARS['inout']['tmp-dir']['value'])
        cmds.extend(cmds_prepro)
        # reset location of input data
        ctset = (EZVARS['inout']['tmp-dir']['value'], ctset[1])
        #add_value_to_dict_entry(EZVARS['inout']['shared-df-used'], True)
    ###################################################
    if EZVARS['filters']['rm_spots']['value']:  # generate commands to remove sci. spots from projections
        cmds.append('echo " - Flat-correcting and removing large spots"')
        cmds_inpaint = get_inp_cmd(ctset, EZVARS['inout']['tmp-dir']['value'], wh[0], nviews)
        # reset location of input data
        ctset = (EZVARS['inout']['tmp-dir']['value'], ctset[1])
        #add_value_to_dict_entry(EZVARS['inout']['shared-df-used'], True)
        cmds.extend(cmds_inpaint)
        swiFFC = False  # no need to do FFC anymore

    ######## PHASE-RETRIEVAL #######
    # Do PR separately if sinograms must be generate
    # todo? also if vertical ROI is defined to speed up the phase retrieval
    if SECTIONS['retrieve-phase']['enable-phase']['value'] and EZVARS['RR']['enable-RR']['value']:
        # or (SECTIONS['retrieve-phase']['enable-phase']['value'] and EZVARS['inout']['input_ROI']['value']):
        if swiFFC:  # we still need need flat correction #Inpaint No
            cmds.append('echo " - Phase retrieval with flat-correction"')
            if EZVARS['flat-correction']['smart-ffc']['value']:
                cmds.append(get_pr_sinFFC_cmd(ctset))
                cmds.append(get_pr_tofu_cmd_sinFFC(ctset))
            elif not EZVARS['flat-correction']['smart-ffc']['value']:
                cmds.append(get_pr_tofu_cmd(ctset))
            #add_value_to_dict_entry(EZVARS['inout']['shared-df-used'], True)
        else:  # Inpaint Yes
            cmds.append('echo " - Phase retrieval from flat-corrected projections"')
            cmds.extend(get_pr_ufo_cmd(nviews, wh))
        swiPR = False  # no need to do PR anymore
        swiFFC = False  # no need to do FFC anymore

    ################# RING REMOVAL #######################
    if EZVARS['RR']['enable-RR']['value']:
        # Generate sinograms first
        if swiFFC:  # we still need to do flat-field correction
            if EZVARS['flat-correction']['smart-ffc']['value']:
                # Create flat corrected images using sinFFC
                cmds.append(get_sinFFC_cmd(ctset))
                # Feed the flat corrected images to sino gram generation
                cmds.append(get_sinos_noffc_cmd(ctset[0], EZVARS['inout']['tmp-dir']['value'], nviews, wh))
            elif not EZVARS['flat-correction']['smart-ffc']['value']:
                cmds.append('echo " - Make sinograms with flat-correction"')
                cmds.append(get_sinos_ffc_cmd(ctset, EZVARS['inout']['tmp-dir']['value'], nviews, wh))
        else:  # we do not need flat-field correction
            cmds.append('echo " - Make sinograms without flat-correction"')
            cmds.append(get_sinos_noffc_cmd(ctset[0], EZVARS['inout']['tmp-dir']['value'], nviews, wh))
        swiFFC = False
        # Filter sinograms
        if EZVARS['RR']['use-ufo']['value']:
            if EZVARS['RR']['ufo-2d']['value']:
                cmds.append('echo " - Ring removal - ufo 1d stripes filter"')
                cmds.append(get_filter1d_sinos_cmd(EZVARS['inout']['tmp-dir']['value'],
                            EZVARS['RR']['sx']['value'], nviews))
            else:
                cmds.append('echo " - Ring removal - ufo 2d stripes filter"')
                cmds.append(get_filter2d_sinos_cmd(EZVARS['inout']['tmp-dir']['value'], \
                            EZVARS['RR']['sx']['value'],
                            EZVARS['RR']['sy']['value'],
                                                       nviews, wh[1]))
        else:
            cmds.append('echo " - Ring removal - sarepy filter(s)"')
            # note - calling an external program, not an ufo-kit script
            tmp = os.path.dirname(os.path.abspath(__file__))
            path_to_filt = os.path.join(tmp, "RR_external.py")
            if os.path.isfile(path_to_filt):
                tmp = os.path.join(EZVARS['inout']['tmp-dir']['value'], "sinos")
                cmdtmp = 'python {} --sinos {} --mws {} --mws2 {} --snr {} --sort_only {}' \
                    .format(path_to_filt, tmp,
                            EZVARS['RR']['spy-narrow-window']['value'],
                            EZVARS['RR']['spy-wide-window']['value'],
                            EZVARS['RR']['spy-wide-SNR']['value'],
                            int(not EZVARS['RR']['spy-rm-wide']['value']))
                cmds.append(cmdtmp)
            else:
                cmds.append('echo "Omitting RR because file with filter does not exist"')
        if not EZVARS['inout']['keep-tmp']['value']:
            cmds.append("rm -rf {}".format(os.path.join(EZVARS['inout']['tmp-dir']['value'], "sinos")))
        # Convert filtered sinograms back to projections
        cmds.append('echo " - Generating proj from filtered sinograms"')
        cmds.append(get_sinos2proj_cmd(wh[0]))
        # reset location of input data
        ctset = (EZVARS['inout']['tmp-dir']['value'], ctset[1])

    # Finally - call to tofu reco
    cmds.append('echo " - CT with axis {}; ffc:{}, PR:{}"'.format(ax, swiFFC, swiPR))
    if EZVARS['flat-correction']['smart-ffc']['value'] and swiFFC:
        cmds.append(get_sinFFC_cmd(ctset))
        cmds.append(get_reco_cmd(ctset, out_pattern, ax, nviews, wh, False, swiPR))
    else:  # If not using sinFFC
        cmds.append(get_reco_cmd(ctset, out_pattern, ax, nviews, wh, swiFFC, swiPR))

    return nviews, wh

#TODO: get rid of fdt_names everywhere - work directly with EZVARS instead
def execute_reconstruction(fdt_names):
    # array with the list of commands
    cmds = []
    # create temporary directory
    if not os.path.exists(EZVARS['inout']['tmp-dir']['value']):
        os.makedirs(EZVARS['inout']['tmp-dir']['value'])

    if EZVARS['inout']['clip_hist']['value']:
        if SECTIONS['general']['output-minimum']['value'] > SECTIONS['general']['output-maximum']['value']:
            raise ValueError('hmin must be smaller than hmax to convert to 8bit without contrast inversion')

    # get list of all good CT directories to be reconstructed

    print('*********** Analyzing input directory ************')
    W, lvl0 = get_CTdirs_list(EZVARS['inout']['input-dir']['value'], fdt_names)
    # W is an array of tuples (path, type)
    # get list of already reconstructed sets
    recd_sets = findSlicesDirs(EZVARS['inout']['output-dir']['value'])
    # initialize command generators
    # populate list of reconstruction commands
    print("*********** AXIS INFO ************")
    for i, ctset in enumerate(W):
        # ctset is a tuple containing a path and a type (3 or 4)
        if not already_recd(ctset[0], lvl0, recd_sets):
            # determine initial number of projections and their shape
            path2proj = os.path.join(ctset[0], fdt_names[2])
            nviews, wh, multipage = get_dims(path2proj)
            # If EZVARS['COR']['search-method']['value'] == 4 then bypass axis search and use image midpoint
            if EZVARS['COR']['search-method']['value'] != 4:
                if (EZVARS['inout']['input_ROI']['value'] and bad_vert_ROI(multipage, path2proj,
                                SECTIONS['reading']['y']['value'], SECTIONS['reading']['height']['value'])):
                    print('{}\t{}'.format('CTset:', ctset[0]))
                    print('{:>30}\t{}'.format('Axis:', 'na'))
                    print('Vertical ROI does not contain any rows.')
                    print("{:>30}\t{}, dimensions: {}".format("Number of projections:", nviews, wh))
                    continue
                # Find axis of rotation using auto: correlate first/last projections
                if EZVARS['COR']['search-method']['value'] == 1:
                    ax = find_axis_corr(ctset,
                                    EZVARS['inout']['input_ROI']['value'],
                                    SECTIONS['reading']['y']['value'],
                                    SECTIONS['reading']['height']['value'], multipage)
                # Find axis of rotation using auto: minimize STD of a slice
                elif EZVARS['COR']['search-method']['value'] == 2:
                    cmds.append("echo \"Cleaning axis-search in tmp directory\"")
                    os.system('rm -rf {}'.format(os.path.join(EZVARS['inout']['tmp-dir']['value'], 'axis-search')))
                    ax = find_axis_std(ctset,  EZVARS['inout']['tmp-dir']['value'],
                                               EZVARS['COR']['search-interval']['value'],
                                               EZVARS['COR']['patch-size']['value'],
                                               nviews, wh)
                else:
                    ax = EZVARS['COR']['user-defined-ax']['value'] + i * EZVARS['COR']['user-defined-dax']['value']
            # If EZVARS['COR']['search-method']['value'] == 4 then bypass axis search and use image midpoint
            elif EZVARS['COR']['search-method']['value'] == 4:
                ax = find_axis_image_midpoint(ctset, multipage, wh)
                print("Bypassing axis search and using image midpoint: {}".format(ax))

            setid = ctset[0][len(lvl0) + 1:]
            out_pattern = os.path.join(EZVARS['inout']['output-dir']['value'], setid, 'sli/sli')
            cmds.append('echo ">>>>> PROCESSING {}"'.format(setid))
            # rm files in temporary directory first of all to
            # format paths correctly and to avoid problems
            # when reconstructing ct sets with variable number of rows or projections
            cmds.append('echo "Cleaning temporary directory"'.format(setid))
            clean_tmp_dirs(EZVARS['inout']['tmp-dir']['value'], fdt_names)
            # call function which formats commands for this data set
            nviews, wh = frmt_ufo_cmds(cmds, ctset, out_pattern, ax, nviews, wh)
            save_params(setid, ax, nviews, wh)
            print('{}\t{}'.format('CTset:', ctset[0]))
            print('{:>30}\t{}'.format('Axis:', ax))
            print("{:>30}\t{}, dimensions: {}".format("Number of projections:", nviews, wh))
            # tmp = "Number of projections: {}, dimensions: {}".format(nviews, wh)
            # cmds.append("echo \"{}\"".format(tmp))
            if EZVARS['nlmdn']['do-after-reco']['value']:
                logging.debug("Using Non-Local Means Denoising")
                head, tail = os.path.split(out_pattern)
                slidir = os.path.dirname(os.path.join(head, 'sli'))
                nlmdn_output = os.path.join(slidir+"-nlmdn", "sli-nlmdn-%04i.tif")
                cmds.append(fmt_nlmdn_ufo_cmd(slidir, nlmdn_output))
        else:
            print("{} has been already reconstructed".format(ctset[0]))
    # execute commands = start reconstruction
    start = time.time()
    print("*********** PROCESSING ************")
    for cmd in cmds:
        if not EZVARS['inout']['dryrun']['value']:
            os.system(cmd)
        else:
            print(cmd)
    if not EZVARS['inout']['keep-tmp']['value']:
        clean_tmp_dirs(EZVARS['inout']['tmp-dir']['value'], fdt_names)

    print("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    print("*** Done. Total processing time {} sec.".format(int(time.time() - start)))
    print("*** Waiting for the next job...........")


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
