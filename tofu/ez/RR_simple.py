#!/usr/bin/env python2
'''
Created on Aug 3, 2018

@author: SGasilov
'''
import glob
import os
import argparse
from tofu.util import read_image
import numpy as np
from tofu.util import get_filenames
import multiprocessing as mp
from functools import partial
from scipy.ndimage import median_filter
from scipy.ndimage import binary_dilation
import tifffile

def write_tiff(file_name, data):
    """
    The default TIFF writer which uses :py:mod:`tifffile` module.
    Return the written file name.
    """
    tifffile.imsave(file_name, data)

    return file_name

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sinos', type=str, help='Input directory')
    parser.add_argument('--mws', type=int, help='Window size for small rings (sorting algorithm)')
    parser.add_argument('--mws2', type=int, help='Window size for large rings')
    parser.add_argument('--snr', type=int, help='Median window size along columns')
    parser.add_argument('--sort_only', type=int, help='Only sorting or both')
    return parser.parse_args()


def RR_wide_sort(mws, mws2, snr, odir, fname):
    filt_sin_name = os.path.join(odir, os.path.split(fname)[1])
    im = read_image(fname).astype(np.float32)
    im = remove_large_stripe(im, snr, mws2)
    im = remove_stripe_based_sorting(im, mws)
    write_tiff(filt_sin_name, im.astype(np.float32))


def RR_sort(mws, odir, fname):
    filt_sin_name = os.path.join(odir, os.path.split(fname)[1])
    write_tiff(filt_sin_name,
               remove_stripe_based_sorting(read_image(fname).astype(np.float32), mws).astype(np.float32))


def remove_stripe_based_sorting(sinogram, size, dim=1):
    # taken from sarepy, Author: Nghia T. Vo https://doi.org/10.1364/OE.26.028396
    """
    Remove stripe artifacts in a sinogram using the sorting technique,
    algorithm 3 in Ref. [1]. Angular direction is along the axis 0.

    Parameters
    ----------
    sinogram : array_like
        2D array. Sinogram image.
    size : int
        Window size of the median filter.
    dim : {1, 2}, optional
        Dimension of the window.
    """
    sinogram = np.transpose(sinogram)
    (nrow, ncol) = sinogram.shape
    list_index = np.arange(0.0, ncol, 1.0)
    mat_index = np.tile(list_index, (nrow, 1))
    mat_comb = np.asarray(np.dstack((mat_index, sinogram)))
    mat_sort = np.asarray(
        [row[row[:, 1].argsort()] for row in mat_comb])
    if dim == 2:
        mat_sort[:, :, 1] = median_filter(mat_sort[:, :, 1], (size, size))
    else:
        mat_sort[:, :, 1] = median_filter(mat_sort[:, :, 1], (size, 1))
    mat_sort_back = np.asarray(
        [row[row[:, 0].argsort()] for row in mat_sort])
    return np.transpose(mat_sort_back[:, :, 1])


def detect_stripe(list_data, snr):
    # taken from sarepy, Author: Nghia T. Vo https://doi.org/10.1364/OE.26.028396
    """
    Locate stripe positions using Algorithm 4 in Ref. [1].

    Parameters
    ----------
    list_data : array_like
        1D array. Normalized data.
    snr : float
        Ratio used to segment stripes from background noise.
    """
    npoint = len(list_data)
    list_sort = np.sort(list_data)
    listx = np.arange(0, npoint, 1.0)
    ndrop = np.int16(0.25 * npoint)
    (slope, intercept) = np.polyfit(listx[ndrop:-ndrop - 1], list_sort[ndrop:-ndrop - 1], 1)
    y_end = intercept + slope * listx[-1]
    noise_level = np.abs(y_end - intercept)
    noise_level = np.clip(noise_level, 1e-6, None)
    val1 = np.abs(list_sort[-1] - y_end) / noise_level
    val2 = np.abs(intercept - list_sort[0]) / noise_level
    list_mask = np.zeros(npoint, dtype=np.float32)
    if val1 >= snr:
        upper_thresh = y_end + noise_level * snr * 0.5
        list_mask[list_data > upper_thresh] = 1.0
    if val2 >= snr:
        lower_thresh = intercept - noise_level * snr * 0.5
        list_mask[list_data <= lower_thresh] = 1.0
    return list_mask


def remove_large_stripe(sinogram, size, snr=3, drop_ratio=0.1, norm=True):
    # taken from sarepy, Author: Nghia T. Vo https://doi.org/10.1364/OE.26.028396
    """
    Remove large stripes, algorithm 5 in Ref. [1], by: locating stripes,
    normalizing to remove full stripes, and using the sorting technique
    (Ref. [1]) to remove partial stripes. Angular direction is along the
    axis 0.

    Parameters
    ----------
    sinogram : array_like
        2D array. Sinogram image
    snr : float
        Ratio used to segment stripes from background noise.
    size : int
        Window size of the median filter.
    drop_ratio : float, optional
        Ratio of pixels to be dropped, which is used to reduce the false
        detection of stripes.
    norm : bool, optional
        Apply normalization if True.
    """
    sinogram = np.copy(sinogram)  # Make it mutable
    drop_ratio = np.clip(drop_ratio, 0.0, 0.8)
    (nrow, ncol) = sinogram.shape
    ndrop = int(0.5 * drop_ratio * nrow)
    sino_sort = np.sort(sinogram, axis=0)
    sino_smooth = median_filter(sino_sort, (1, size))
    list1 = np.mean(sino_sort[ndrop:nrow - ndrop], axis=0)
    list2 = np.mean(sino_smooth[ndrop:nrow - ndrop], axis=0)
    list_fact = np.divide(list1, list2,
                         out=np.ones_like(list1), where=list2 != 0)
    list_mask = detect_stripe(list_fact, snr)
    list_mask = np.float32(binary_dilation(list_mask, iterations=1))
    mat_fact = np.tile(list_fact, (nrow, 1))
    if norm is True:
        sinogram = sinogram / mat_fact  # Normalization
    sino_tran = np.transpose(sinogram)
    list_index = np.arange(0.0, nrow, 1.0)
    mat_index = np.tile(list_index, (ncol, 1))
    mat_comb = np.asarray(np.dstack((mat_index, sino_tran)))
    mat_sort = np.asarray(
        [row[row[:, 1].argsort()] for row in mat_comb])
    mat_sort[:, :, 1] = np.transpose(sino_smooth)
    mat_sort_back = np.asarray(
        [row[row[:, 0].argsort()] for row in mat_sort])
    sino_cor = np.transpose(mat_sort_back[:, :, 1])
    listx_miss = np.where(list_mask > 0.0)[0]
    sinogram[:, listx_miss] = sino_cor[:, listx_miss]
    return sinogram

def main():
    args = parse_args()
    sinos=get_filenames(os.path.join(args.sinos, '*.tif'))
    #create output directory
    wdir = os.path.split(args.sinos)[0]
    odir = os.path.join(wdir, 'sinos-filt')
    if not os.path.exists(odir):
        os.makedirs(odir)
    pool = mp.Pool(processes=mp.cpu_count())
    if args.sort_only:
        exec_func = partial(RR_sort, args.mws, odir)
    else:
        exec_func = partial(RR_wide_sort, args.mws, args.mws2, args.snr, odir)
    pool.map(exec_func, sinos)


if __name__ == '__main__':
    main()
