"""
This script takes as input a CT scan that has been collected in "half-acquisition" mode
and produces a series of reconstructed slices, each of which are generated by cropping and
concatenating opposing projections together over a range of "overlap" values (i.e. the pixel column
at which the images are cropped and concatenated).
The objective is to review this series of images to determine the pixel column at which the axis of rotation
is located (much like the axis search function commonly used in reconstruction software).
"""

import os
import numpy as np
import tifffile

from tofu.ez.params import EZVARS, EZVARS_aux
from tofu.ez.Helpers.stitch_funcs import findCTdirs, stitch
from tofu.util import get_filenames, get_image_shape, TiffSequenceReader
from tofu.ez.ufo_cmd_gen import get_filter2d_sinos_cmd
#from tofu.ez.find_axis_cmd_gen import evaluate_images_simp
from tofu.ez.evaluate_sharpness import evaluate_metrics_360_olap_search

def extract_row(dir_name, row):
    tsr = TiffSequenceReader(dir_name)
    tmp = tsr.read(0)
    (N, M) = tmp.shape
    if (row < 0) or (row > N):
        row = N//2
    num_images = tsr.num_images
    if num_images % 2 == 1:
        # print(f"odd number of images ({num_images}) in {dir_name}, "
        #       f"discarding the last one before stitching pairs")
        num_images-=1
    A = np.empty((num_images, M), dtype=np.uint16)
    for i in range(num_images):
        A[i, :] = tsr.read(i)[row, :]
    tsr.close()
    return A

def find_overlap():
    print("Finding CTDirs...")
    ctdirs, lvl0 = findCTdirs(EZVARS_aux['find360olap']['input-dir']['value'],
                              EZVARS['inout']['tomo-dir']['value'])
    print(ctdirs)
    if len(ctdirs) < 1:
        return None

    olap_estimates = []

    dirdark = EZVARS['inout']['darks-dir']['value']
    dirflats = EZVARS['inout']['flats-dir']['value']
    dirflats2 = EZVARS['inout']['flats2-dir']['value']
    if EZVARS['inout']['shared-flatsdarks']['value']:
        dirdark = EZVARS['inout']['path2-shared-darks']['value']
        dirflats = EZVARS['inout']['path2-shared-flats']['value']
        dirflats2 = EZVARS['inout']['path2-shared-flats2']['value']

    sin_tmp_dir = os.path.join(EZVARS_aux['find360olap']['tmp-dir']['value'], 'sinos')
    if not os.path.exists(sin_tmp_dir):
        os.makedirs(sin_tmp_dir)
    if EZVARS_aux['find360olap']['doRR']['value']:
        sinfilt_tmp_dir = os.path.join(EZVARS_aux['find360olap']['tmp-dir']['value'], 'sinos-filt')
        if not os.path.exists(sinfilt_tmp_dir):
            os.makedirs(sinfilt_tmp_dir)

    ax_range = range(EZVARS_aux['find360olap']['start']['value'],
                     EZVARS_aux['find360olap']['stop']['value'] + EZVARS_aux['find360olap']['step']['value'],
                     EZVARS_aux['find360olap']['step']['value'])

    # flush records from previous run
    EZVARS_aux['axes-list'] = {}
    # concatenate images with various overlap and generate sinograms
    for ctset in ctdirs:
        outerloopdirname = os.path.dirname(ctset)
        if outerloopdirname not in EZVARS_aux['axes-list']:
            EZVARS_aux['axes-list'].update({outerloopdirname: {}})
        index_dir = os.path.basename(os.path.normpath(ctset))
        print(f"Generating slices for ctset {index_dir}")
        # loading:
        try:
            row_flat = np.mean(extract_row(
                os.path.join(ctset, dirflats), EZVARS_aux['find360olap']['row']['value']))
        except:
            print(f"Problem loading flats in {ctset}")
            continue
        try:
            row_dark = np.mean(extract_row(
                os.path.join(ctset, dirdark), EZVARS_aux['find360olap']['row']['value']))
        except:
            print(f"Problem loading darks in {ctset}")
            continue
        try:
            row_tomo = extract_row(
                os.path.join(ctset, EZVARS['inout']['tomo-dir']['value']),
                                   EZVARS_aux['find360olap']['row']['value'])
        except:
            print(f"Problem loading projections from "
                  f"{os.path.join(ctset, EZVARS['inout']['tomo-dir']['value'])}")
            continue
        row_flat2 = None
        tmpstr = os.path.join(ctset, dirflats2)
        if os.path.exists(tmpstr):
            try:
                row_flat2 = np.mean(extract_row(tmpstr, EZVARS_aux['find360olap']['row']['value']))
            except:
                print(f"Problem loading flats2 in {ctset}")

        (num_proj, M) = row_tomo.shape

        print('Flat-field correction...')
        # Flat-correction
        tmp_flat = np.tile(row_flat, (num_proj, 1))
        if row_flat2 is not None:
            tmp_flat2 = np.tile(row_flat2, (num_proj, 1))
            ramp = np.linspace(0, 1, num_proj)
            ramp = np.transpose(np.tile(ramp, (M, 1)))
            tmp_flat = tmp_flat * (1-ramp) + tmp_flat2 * ramp
            del ramp, tmp_flat2

        tmp_dark = np.tile(row_dark, (num_proj, 1))
        tomo_ffc = -np.log((row_tomo - tmp_dark)/np.float32(tmp_flat - tmp_dark))
        del row_tomo, row_dark, row_flat, tmp_flat, tmp_dark
        np.nan_to_num(tomo_ffc, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

        # create interpolated sinogram of flats on the
        # same row as we use for the projections, then flat/dark correction
        print('Creating stitched sinograms...')
        for axis in ax_range:
            cro = EZVARS_aux['find360olap']['stop']['value'] - axis
            if axis > M // 2:
                cro = axis - EZVARS_aux['find360olap']['start']['value']
            A = stitch(
                tomo_ffc[: num_proj//2, :], tomo_ffc[num_proj//2:, ::-1], axis, cro, False)
            tifffile.imwrite(os.path.join(
                sin_tmp_dir, 'sin-axis-' + str(axis).zfill(4) + '.tif'), A.astype(np.float32))

        # formatting reco command
        sin_width = get_image_shape(get_filenames(sin_tmp_dir)[0])[-1]
        sin_height = get_image_shape(get_filenames(sin_tmp_dir)[0])[-2]
        outname = os.path.join(os.path.join(
            EZVARS_aux['find360olap']['output-dir']['value'], index_dir, f"{index_dir}-sli"))
        #old command
        #cmd = f'tofu tomo --axis {sin_width // 2} --output {os.path.join(outname)}'
        # new command to enable slice crop
        # convert sinos to projections first
        nsli = len(ax_range)
        cmd = f'tofu sinos --number {nsli}'
        if EZVARS_aux['find360olap']['doRR']['value']:
            print("Applying ring removal filter")
            rrcmd = get_filter2d_sinos_cmd(EZVARS_aux['find360olap']['tmp-dir']['value'],
                                   EZVARS['RR']['sx']['value'],
                                   EZVARS['RR']['sy']['value'],
                                   sin_height, sin_width)
            os.system(rrcmd)
            cmd += f' --projections {sinfilt_tmp_dir}'
        else:
            cmd += f' --projections {sin_tmp_dir}'
        proj_file_name = os.path.join(EZVARS_aux['find360olap']['tmp-dir']['value'], 'proj.tif')
        cmd += f" --output {proj_file_name}"
        os.system(cmd)
        # now the reco command
        cmd = f'tofu reco --projections {proj_file_name} --output {outname}'
        cmd += f' --overall-angle 180 --center-position-x {sin_width // 2} '
        cmd += f' --number {sin_height} --region={-(nsli//2)},{nsli-nsli//2},{1}'
        p_width = EZVARS_aux['find360olap']['patch-size']['value'] // 2
        cmd += " --x-region={},{},{}".format(int(-p_width), int(p_width), 1)
        cmd += " --y-region={},{},{}".format(int(-p_width), int(p_width), 1)
        print('Reconstructing slices...')
        os.system(cmd)

        # estimating overlap
        #points, maximum = evaluate_images_simp(outname, "std")
        mettxtpref = os.path.join(os.path.join(
            EZVARS_aux['find360olap']['output-dir']['value'], index_dir))

        results = evaluate_metrics_360_olap_search(os.path.dirname(outname), mettxtpref, ax_range,
                                    metrics_1d={"std": np.std}, detrend=True)

        olap_est = int(EZVARS_aux['find360olap']['start']['value'] + \
                   EZVARS_aux['find360olap']['step']['value'] * np.argmax(results['std']))

        print("****************************************")
        print(f"Finished processing: {index_dir}, estimated overlap: {olap_est}")
        EZVARS_aux['axes-list'][outerloopdirname].update({index_dir: olap_est})
        olap_estimates.append(olap_est)
        print("****************************************")

    #shutil.rmtree(EZVARS_aux['find360olap']['tmp-dir'])
    print("Finished processing of all subdirectories in " + str(EZVARS_aux['find360olap']['input-dir']['value']))
    return dict(zip(ctdirs, olap_estimates))

