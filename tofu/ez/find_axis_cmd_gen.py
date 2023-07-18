#!/bin/python
"""
Created on Apr 6, 2018

@author: gasilos
"""
import glob, os, tifffile
import numpy as np
from tofu.ez.evaluate_sharpness import process as process_metrics
from tofu.ez.util import enquote, make_inpaths
from tofu.util import get_filenames, read_image, determine_shape
from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.ez.tofu_cmd_gen import check_lamino, gpu_optim

def find_axis_std(ctset, tmpdir, ax_range, p_width, nviews, wh):
    indir = make_inpaths(ctset[0], ctset[1])
    cmd = 'tofu reco'
    if EZVARS['advanced']['more-reco-params']['value'] is True:
        cmd += check_lamino()
    elif EZVARS['advanced']['more-reco-params']['value'] is False:
        cmd += " --overall-angle 180"
    cmd += " --darks {} --flats {} --projections {}".format(
        indir[0], indir[1], enquote(indir[2])
    )
    cmd += " --number {}".format(nviews)
    if EZVARS['COR']['min-std-apply-pr']['value']:
        cmd += f" --disable-projection-crop --delta 1e-6" \
            f" --energy {SECTIONS['retrieve-phase']['energy']['value']} " \
            f" --propagation-distance {SECTIONS['retrieve-phase']['propagation-distance']['value'][0]}" \
            f" --pixel-size {SECTIONS['retrieve-phase']['pixel-size']['value']} " \
            f" --regularization-rate {SECTIONS['retrieve-phase']['regularization-rate']['value']:0.2f}"
    else:
        cmd += " --absorptivity --fix-nan-and-inf"
    if ctset[1] == 4:
        cmd += " --flats2 {}".format(indir[3])
    out_pattern = os.path.join(tmpdir, "axis-search/sli")
    cmd += " --output {}".format(enquote(out_pattern))
    cmd += " --x-region={},{},{}".format(int(-p_width / 2), int(p_width / 2), 1)
    cmd += " --y-region={},{},{}".format(int(-p_width / 2), int(p_width / 2), 1)
    image_height = wh[0]
    ax_range_list = ax_range.split(",")
    range_min = ax_range_list[0]
    range_max = ax_range_list[1]
    step = ax_range_list[2]
    range_string = str(range_min) + "," + str(range_max) + "," + str(step)
    cmd += " --region={}".format(range_string)
    res = [float(num) for num in ax_range.split(",")]
    cmd += " --output-bytes-per-file 0"
    cmd += ' --z-parameter center-position-x'
    cmd += ' --z {}'.format(EZVARS['COR']['search-row']['value'] - int(image_height/2))
    cmd += gpu_optim()
    print(cmd)
    os.system(cmd)
    points, maximum = evaluate_images_simp(out_pattern + "*.tif", "msag")
    return res[0] + res[2] * maximum

def find_axis_corr(ctset, vcrop, y, height, multipage):
    indir = make_inpaths(ctset[0], ctset[1])
    """Use correlation to estimate center of rotation for tomography."""
    from scipy.signal import fftconvolve

    def flat_correct(flat, radio):
        nonzero = np.where(radio != 0)
        result = np.zeros_like(radio)
        result[nonzero] = flat[nonzero] / radio[nonzero]
        # log(1) = 0
        result[result <= 0] = 1

        return np.log(result)

    if multipage:
        with tifffile.TiffFile(get_filenames(indir[2])[0]) as tif:
            first = tif.pages[0].asarray().astype(float)
        with tifffile.TiffFile(get_filenames(indir[2])[-1]) as tif:
            last = tif.pages[-1].asarray().astype(float)
        with tifffile.TiffFile(get_filenames(indir[0])[-1]) as tif:
            dark = tif.pages[-1].asarray().astype(float)
        with tifffile.TiffFile(get_filenames(indir[1])[0]) as tif:
            flat1 = tif.pages[-1].asarray().astype(float) - dark
    else:
        first = read_image(get_filenames(indir[2])[0]).astype(float)
        last = read_image(get_filenames(indir[2])[-1]).astype(float)
        dark = read_image(get_filenames(indir[0])[-1]).astype(float)
        flat1 = read_image(get_filenames(indir[1])[-1]) - dark

    first = flat_correct(flat1, first - dark)

    if ctset[1] == 4:
        if multipage:
            with tifffile.TiffFile(get_filenames(indir[3])[0]) as tif:
                flat2 = tif.pages[-1].asarray().astype(float) - dark
        else:
            flat2 = read_image(get_filenames(indir[3])[-1]) - dark
        last = flat_correct(flat2, last - dark)
    else:
        last = flat_correct(flat1, last - dark)

    if vcrop:
        y_region = slice(y, min(y + height, first.shape[0]), 1)
        first = first[y_region, :]
        last = last[y_region, :]

    width = first.shape[1]
    first = first - first.mean()
    last = last - last.mean()

    conv = fftconvolve(first, last[::-1, :], mode="same")
    center = np.unravel_index(conv.argmax(), conv.shape)[1]

    return (width / 2.0 + center) / 2.0

# Find midpoint width of image and return its value
def find_axis_image_midpoint(height_width):
    return height_width[1] // 2


def evaluate_images_simp(
    input_pattern,
    metric,
    num_images_for_stats=0,
    out_prefix=None,
    fwhm=None,
    blur_fwhm=None,
    verbose=False,
):
    # simplified version of original evaluate_images function
    # from Tomas's optimize_parameters script
    names = sorted(glob.glob(input_pattern))
    res = process_metrics(
        names,
        num_images_for_stats=num_images_for_stats,
        metric_names=(metric,),
        out_prefix=out_prefix,
        fwhm=fwhm,
        blur_fwhm=blur_fwhm,
    )[metric]
    return res, np.argmax(res)
