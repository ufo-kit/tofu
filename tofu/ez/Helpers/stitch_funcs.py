"""
Last modified on Apr 1, 2022
@author: sergei gasilov
"""

import glob
import os
import shutil
import numpy as np
import tifffile
from tofu.util import read_image, get_image_shape, get_filenames, TiffSequenceReader
from tofu.ez.util import get_data_cube_info
from tofu.ez.image_read_write import get_image_dtype
import multiprocessing as mp
from functools import partial
import time
from tofu.ez.ufo_cmd_gen import fmt_stitch_cmd
from skimage.metrics import structural_similarity as ssim
from tofu.ez.params import EZVARS_aux, EZVARS
import sys

try:
    from mpi4py import MPI
except ImportError:
    print("Ufo-launch GPU filter will be used to stitch half acq mode data",
          file=sys.stderr)


def findCTdirs(root: str, tomo_name: str):
    """
    Walks directories rooted at "Input ctset" location
    Appends their absolute path to ctdir if they contain a ctset with same name as "tomo" entry in GUI
    """
    lvl0 = os.path.abspath(root)
    ctdirs = []
    for root, dirs, files in os.walk(lvl0):
        for name in dirs:
            if name == tomo_name:
                ctdirs.append(root)
    ctdirs.sort()
    return ctdirs, lvl0


def make_ort_sections(ctset_path):
    """
    :param parameters: GUI params
    :param dir_type 1 if CTDir containing Z00-Z0N slices - 2 if parent directory containing CTdirs each containing Z slices:
    :param ctdir Name of the ctdir - blank string if not using multiple ctdirs:
    :return:
    """
    Vsteps = sorted(os.listdir(ctset_path))
    #determine input data type
    tmp = os.path.join(ctset_path, Vsteps[0], EZVARS_aux['vert-sti']['subdir-name']['value'])
    nslices, N, M, indtype_digit, indtype, npasses = get_data_cube_info(tmp)

    if EZVARS_aux['vert-sti']['ort']['value']:
        print(" - Creating orthogonal sections")
        for vstep in Vsteps:
            in_name = os.path.join(ctset_path, vstep, EZVARS_aux['vert-sti']['subdir-name']['value'])
            out_name = os.path.join(EZVARS_aux['vert-sti']['tmp-dir']['value'],
                                    vstep, EZVARS_aux['vert-sti']['subdir-name']['value'], 'sli-%04i.tif')
            # todo: size check and num-passes argument
            cmd = 'tofu sinos --projections {} --output {}'.format(in_name, out_name)
            cmd += " --y {} --height {} --y-step {}".format(EZVARS_aux['vert-sti']['start']['value'], 
                        EZVARS_aux['vert-sti']['stop']['value'] - EZVARS_aux['vert-sti']['start']['value'],
                        EZVARS_aux['vert-sti']['step']['value'])
            cmd += " --output-bytes-per-file 0"
            if indtype_digit == '8' or indtype_digit == '16':
                cmd += f" --output-bitdepth {indtype_digit}"
            cmd += f" --pass-size {npasses}"
            print(cmd)
            os.system(cmd)
            time.sleep(10)
        indir = EZVARS_aux['vert-sti']['tmp-dir']['value']
    else:
        indir = EZVARS_aux['vert-sti']['input-dir']['value']
    return indir, indtype

def find_depth_level_to_CT_sets(input_dir, slice_dir):
    subdirs = sorted(os.listdir(input_dir))
    tmp = os.path.join(input_dir, subdirs[0], slice_dir)
    if os.path.exists(tmp):
        return 1, tmp
    second_subdirs = sorted(os.listdir(os.path.join(tmp, subdirs[0])))
    tmp = os.path.join(input_dir, subdirs[0], second_subdirs[0], slice_dir)
    if os.path.exists(tmp):
        return 2, tmp
    return 0, ""

def load_an_image_from_the_input_dir(input_dir, slice_dir):
    return 0

def main_sti_mp():
    #Check whether indir is CTdir or parent containing CTdirs
    #if indir + some z00 subdir + sli + *.tif does not exist then use original
    if not os.path.exists(EZVARS_aux['vert-sti']['output-dir']['value']):
        os.makedirs(EZVARS_aux['vert-sti']['output-dir']['value'])
    subdirs = sorted(os.listdir(EZVARS_aux['vert-sti']['input-dir']['value']))
    if os.path.exists(os.path.join(EZVARS_aux['vert-sti']['input-dir']['value'], subdirs[0],
                                   EZVARS_aux['vert-sti']['subdir-name']['value'])):
        print(" - Working with one CT directory which contains multiple vertical views")
        if EZVARS_aux['vert-sti']['task_type']['value'] == 0:
            sti_one_set(EZVARS_aux['vert-sti']['input-dir']['value'],
                        EZVARS_aux['vert-sti']['output-dir']['value'])
        else:
            conc_one_set(EZVARS_aux['vert-sti']['input-dir']['value'],
                            EZVARS_aux['vert-sti']['output-dir']['value'])
    else:
        second_subdirs = sorted(os.listdir(os.path.join(EZVARS_aux['vert-sti']['input-dir']['value'], subdirs[0])))
        if os.path.exists(os.path.join(EZVARS_aux['vert-sti']['input-dir']['value'], subdirs[0],
                                       second_subdirs[0], EZVARS_aux['vert-sti']['subdir-name']['value'])):
            print(" - Working with several CT directories which contain multiple vertical views")
            for ctdir in subdirs:
                print(f"-> Working on {str(ctdir)} dataset")
                indir = os.path.join(EZVARS_aux['vert-sti']['input-dir']['value'], ctdir)
                outdir = os.path.join(EZVARS_aux['vert-sti']['output-dir']['value'], ctdir)
                if not os.path.exists(outdir):
                    os.makedirs(outdir)
                if EZVARS_aux['vert-sti']['task_type']['value'] == 0:
                    sti_one_set(indir, outdir)
                else:
                    conc_one_set(indir, outdir)


def sti_one_set(in_dir_path, out_dir_path):
    indir, indtype = make_ort_sections(in_dir_path)
    outfilepattern = os.path.join(out_dir_path, EZVARS_aux['vert-sti']['subdir-name']['value'] + '-sti-{:>04}.tif')
    dx = int(EZVARS_aux['vert-sti']['num_olap_rows']['value'])
    # second: stitch them
    Vsteps = sorted(os.listdir(indir))
    tmp = glob.glob(os.path.join(indir, Vsteps[0], EZVARS_aux['vert-sti']['subdir-name']['value'], '*.tif'))[0]
    first = read_image(tmp)
    N, M = first.shape
    Nnew = N - dx
    ramp = np.linspace(0, 1, dx)

    J = range((EZVARS_aux['vert-sti']['stop']['value'] - EZVARS_aux['vert-sti']['start']['value']) //
              EZVARS_aux['vert-sti']['step']['value'])
    pool = mp.Pool(processes=mp.cpu_count())
    exec_func = partial(exec_sti_mp, indir, outfilepattern, N, Nnew, Vsteps, dx, M, ramp, indtype)
    print(" - Adjusting tiles and stitching")
    # start = time.time()
    pool.map(exec_func, J)
    print("========== Done ==========")


def exec_sti_mp(indir, pout, N, Nnew, Vsteps, dx, M, ramp, indtype, j):
    index = EZVARS_aux['vert-sti']['start']['value'] + j*EZVARS_aux['vert-sti']['step']['value']
    Large = np.empty((Nnew*len(Vsteps)+dx, M), dtype=np.float32)
    for i, vstep in enumerate(Vsteps[:-1]):
        tmp = os.path.join(indir, Vsteps[i], EZVARS_aux['vert-sti']['subdir-name']['value'], '*.tif')
        tmp1 = os.path.join(indir, Vsteps[i+1], EZVARS_aux['vert-sti']['subdir-name']['value'], '*.tif')
        if EZVARS_aux['vert-sti']['ort']['value']:
            tmp = sorted(glob.glob(tmp))[j]
            tmp1 = sorted(glob.glob(tmp1))[j]
        else:
            tmp = sorted(glob.glob(tmp))[index]
            tmp1 = sorted(glob.glob(tmp1))[index]
        first = read_image(tmp)
        second = read_image(tmp1)
        # sample moved downwards
        if EZVARS_aux['vert-sti']['flipud']['value']:
            first, second = np.flipud(first), np.flipud(second)

        k = np.mean(first[N - dx:, :]) / np.mean(second[:dx, :])
        second = second * k

        a, b, c = i*Nnew, (i+1)*Nnew, (i+2)*Nnew
        Large[a:b, :] = first[:N-dx, :]
        Large[b:b+dx, :] = np.transpose(np.transpose(first[N-dx:, :])*(1 - ramp) +
                                        np.transpose(second[:dx, :]) * ramp)
        Large[b+dx:c+dx, :] = second[dx:, :]

    pout = pout.format(index)
    if not EZVARS_aux['vert-sti']['clip_hist']['value'] and \
            (indtype == 'uint8' or indtype == 'uint16'):
        Large = np.clip(Large, np.iinfo(indtype).min, np.iinfo(indtype).max).astype(indtype)
        tifffile.imwrite(pout, Large.astype(indtype))
    elif EZVARS_aux['vert-sti']['clip_hist']['value']:
        Large = 255.0/(EZVARS_aux['vert-sti']['max_int_val']['value'] -
                       EZVARS_aux['vert-sti']['min_int_val']['value']) * \
                (np.clip(Large, EZVARS_aux['vert-sti']['min_int_val']['value'],
                         EZVARS_aux['vert-sti']['max_int_val']['value']) -
                        EZVARS_aux['vert-sti']['min_int_val']['value'])
        tifffile.imwrite(pout, Large.astype(np.uint8))
    else:
        tifffile.imwrite(pout, Large.astype(np.float32))


def conc_one_set(indir, pout):
    indir, indtype = make_ort_sections(indir)
    outfilepattern = os.path.join(pout, EZVARS_aux['vert-sti']['subdir-name']['value'] + '-sti-{:>04}.tif')
    zfold = sorted(os.listdir(indir))
    l = len(zfold)
    tmp = glob.glob(os.path.join(indir, zfold[0], EZVARS_aux['vert-sti']['subdir-name']['value'], '*.tif'))
    J = range((EZVARS_aux['vert-sti']['stop']['value'] - EZVARS_aux['vert-sti']['start']['value']) //
              EZVARS_aux['vert-sti']['step']['value'])
    pool = mp.Pool(processes=mp.cpu_count())
    exec_func = partial(exec_conc_mp, tmp[0], l, zfold, indir, outfilepattern, indtype)
    print("   - Concatenating")
    # start = time.time()
    pool.map(exec_func, J)
    # print "Images stitched in {:.01f} sec".format(time.time()-start)
    print("============ Done ============")


def exec_conc_mp(example_im, l, zfold, indir, pout, indtype, j):
    index = EZVARS_aux['vert-sti']['start']['value'] + j*EZVARS_aux['vert-sti']['step']['value']
    Large, N, dtype = make_buf(example_im, l, EZVARS_aux['vert-sti']['conc_row_top']['value'],
                               EZVARS_aux['vert-sti']['conc_row_bottom']['value'])
    for i, vert in enumerate(zfold):
        tmp = os.path.join(indir, vert, EZVARS_aux['vert-sti']['subdir-name']['value'], '*.tif')
        if EZVARS_aux['vert-sti']['ort']['value']:
            fname = sorted(glob.glob(tmp))[j]
        else:
            fname = sorted(glob.glob(tmp))[index]
        frame = read_image(fname)[EZVARS_aux['vert-sti']['conc_row_top']['value']:
                                  EZVARS_aux['vert-sti']['conc_row_bottom']['value'], :]
        if EZVARS_aux['vert-sti']['flipud']['value']:
            Large[i*N:N*(i+1), :] = np.flipud(frame)
        else:
            Large[i*N:N*(i+1), :] = frame
    tifffile.imwrite(pout.format(index), Large.astype(indtype))


def make_buf(tmp, l, a, b):
    first = read_image(tmp)
    N, M = first[a:b, :].shape
    return np.empty((N*l, M), dtype=first.dtype), N, first.dtype


############################## HALF ACQ ##############################
def stitch(first, second, axis, crop, check_16bit_range=True):
    h, w = first.shape
    if axis > w // 2:
        axis = w - axis
        first = np.fliplr(first)
        second = np.fliplr(second)
    dx = int(2 * axis + 0.5)
    tmp = np.copy(first)
    first = second
    second = tmp
    result = np.empty((h, 2 * w - dx), dtype=first.dtype)
    ramp = np.linspace(0, 1, dx)

    # Mean values of the overlapping regions must match, which corrects flat-field inconsistency
    # between the two projections
    # We clip the values in second so that there are no saturated pixel overflow problems
    k = np.mean(first[:, w - dx:]) / np.mean(second[:, :dx])
    if check_16bit_range:
        second = np.clip(second * k, np.iinfo(np.uint16).min, np.iinfo(np.uint16).max).astype(np.uint16)

    result[:, :w - dx] = first[:, :w - dx]
    result[:, w - dx:w] = first[:, w - dx:] * (1 - ramp) + second[:, :dx] * ramp
    result[:, w:] = second[:, dx:]

    return result[:, slice(int(crop), int(2*(w - axis) - crop), 1)]


def main_360_mp_depth1(indir, outdir, ax, cro):
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    subdirs = [dI for dI in os.listdir(indir) \
            if os.path.isdir(os.path.join(indir, dI))]

    for i, sdir in enumerate(subdirs):
        print(f"Stitching images in {sdir}")
        tfs = TiffSequenceReader(os.path.join(indir, sdir))
        if tfs.num_images < 2:
            print("Warning: less than 2 files, skipping this dir")
            continue
        else:
            print(f"{tfs.num_images//2} pairs will be stitched in {sdir}")
        tfs.close()

        os.makedirs(os.path.join(outdir, sdir))
        out_fmt = os.path.join(outdir, sdir, 'sti-{:>04}.tif')

        tmp = os.path.dirname(os.path.abspath(__file__))
        path_to_script = os.path.join(tmp, "halfacqmode-mpi-stitch.py")
        if os.path.isfile(path_to_script):
            tstart = time.time()
            child_comm = MPI.COMM_WORLD.Spawn(
                sys.executable,
                [path_to_script, f"{ax}", f"{cro}", os.path.join(indir, sdir), out_fmt],
                maxprocs=12)
            child_comm.Disconnect()
            print(f"Child finished in {time.time() - tstart} yay!")
        else:
            print('Cannot see the script for parallel stitching of bigtiff files')
            break
    print("========== Done ==========")

def main_360sti_ufol_depth1(indir, outdir, ax, cro):
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    subdirs = [dI for dI in os.listdir(indir) \
            if os.path.isdir(os.path.join(indir, dI))]

    for i, sdir in enumerate(subdirs):
        print(f"Stitching images in {sdir}")
        inpath = os.path.join(indir, sdir)
        numfiles = len(sorted(glob.glob(os.path.join(inpath, '*.tif'))))
        tfs = TiffSequenceReader(inpath)
        numim = tfs.num_images
        if numim < 2:
            print("Warning: less than 2 images, skipping this dir")
            continue
        if (numfiles > 1) and (numfiles != numim):
            print("Warning: cannot work with several bigtiff files. Input must be either"
                  "one bigtiff container or single tif per each image")
            continue
        bigtiff = False
        if numfiles == 1:
            bigtiff = True
        numpairs = numim // 2
        print(f"{numpairs} pairs will be stitched in {sdir}")
        im = tfs.read(0)
        tfs.close()
        h, w = im.shape
        bits = 32
        if im.dtype == 'uint8':
            bits = 8
        elif im.dtype == 'uint16':
            bits = 16,
        outpath = os.path.join(outdir, sdir)
        cmd = fmt_stitch_cmd(inpath, bigtiff, bits, outpath, numpairs, w, ax, cro)
        #print(cmd)
        os.system(cmd)


def main_360_mp_depth2():
    ctdirs, lvl0 = findCTdirs(EZVARS_aux['stitch360']['input-dir']['value'],
                                EZVARS['inout']['tomo-dir']['value'])
    num_sets = len(ctdirs)

    if num_sets < 1:
        print(f"Didn't find any CT dirs in the input. Check directory structure and permissions. \n" 
              f"Program expects to see a number of subdirectories in the input each of with \n" 
              f"contains at least one directory with CT projections (currently name set to "
              f"{EZVARS['inout']['tomo-dir']['value']}. \n"+
              f"The tif files in all " \
              f" {EZVARS['inout']['tomo-dir']['value']}, "
              f" {EZVARS['inout']['flats-dir']['value']}, "
              f" {EZVARS['inout']['darks-dir']['value']} \n"
              f"subdirectories will be stitched to convert half-acquisition mode scans to ordinary \n"
              f"180-deg parallel-beam scans")
        return

    tmp = len(EZVARS_aux['stitch360']['input-dir']['value'])
    ctdirs_rel_paths = []
    for i in range(num_sets):
        ctdirs_rel_paths.append(ctdirs[i][tmp+1:len(ctdirs[i])])
    print(f"Found the {num_sets} directories in the input with relative paths: {ctdirs_rel_paths}")

    # make_ort_sections axis and crop arrays
    if EZVARS_aux['stitch360']['olap_switch']['value'] == 0:
        dax = np.round(np.linspace(EZVARS_aux['stitch360']['olap_min']['value'],
                               EZVARS_aux['stitch360']['olap_max']['value'], num_sets)).astype(np.int16)
    else:
        #dax = np.array(list(parameters['360multi_axis_dict'].values()), np.int16)[:num_sets]
        dax = EZVARS_aux['stitch360']['olap_list']['value'].split(',')
        for i in range(len(dax)):
            dax[i] = int(dax[i])
    print(f'Overlaps: {dax}')
    # compute crop:
    cra = np.max(dax)-dax
    # Axis on the right ? Must open one file to find out ><
    tmpname = os.path.join(EZVARS_aux['stitch360']['input-dir']['value'], ctdirs_rel_paths[0])
    subdirs = [dI for dI in os.listdir(tmpname) if os.path.isdir(os.path.join(tmpname, dI))]
    M = get_image_shape(get_filenames(os.path.join(tmpname, subdirs[0]))[0])[-1]
    if np.min(dax) > M//2:
        cra = dax - np.min(dax)
    print(f'Crop by: {cra}')

    for i, ctdir in enumerate(ctdirs):
        print("================================================================")
        print(" -> Working On: " + str(ctdir))
        print(f"    axis position {dax[i]}, margin to crop {cra[i]} pixels")

        #main_360_mp_depth1
        main_360sti_ufol_depth1(ctdir,
            os.path.join(EZVARS_aux['stitch360']['output-dir']['value'], ctdirs_rel_paths[i]),
                           int(dax[i]), int(cra[i]))

        # print(ctdir, os.path.join(parameters['360multi_output_dir'], ctdirs_rel_paths[i]), dax[i], cra[i])


def check_last_index(axis_list):
    """
    Return the index of item in list immediately before first 'None' type
    :param axis_list:
    :return: the index of last non-None value
    """
    last_index = 0
    for index, item in enumerate(axis_list):
        if item == 'None':
            last_index = index - 1
            return last_index
        last_index = index
    return last_index

def find_vert_olap_all_vsteps(ctset_path, ind_z00, ind_start_z01, ind_stop_z01):
    Vsteps = sorted(os.listdir(ctset_path))
    num_vsteps = len(Vsteps)
    olaps = np.zeros((num_vsteps-1, 1))
    for i in range(num_vsteps-1):
        # if os.path.exists(os.path.join(EZVARS_aux['vert-sti']['input-dir']['value'], subdirs[0],
        #                            EZVARS_aux['vert-sti']['subdir-name']['value'])):
        z00_name = os.path.join(ctset_path, Vsteps[i],
                                EZVARS_aux['vert-sti']['subdir-name']['value'])
        z01_name = os.path.join(ctset_path, Vsteps[i+1],
                                EZVARS_aux['vert-sti']['subdir-name']['value'])
        olaps[i] = find_vert_overlap(z00_name, z01_name, ind_z00, ind_start_z01, ind_stop_z01)
    return np.median(olaps) #ind_start_z01+olaps-ind_z00

def find_vert_olap_2_vsteps(ctset_path, ind_z00, ind_start_z01, ind_stop_z01):
    #taking two sub-scans near the center of the sample
    vsteps = sorted(os.listdir(ctset_path))
    num_vsteps = len(vsteps)
    z00_name = os.path.join(ctset_path, vsteps[num_vsteps//2-1],
                            EZVARS_aux['vert-sti']['subdir-name']['value'])
    z01_name = os.path.join(ctset_path, vsteps[num_vsteps//2],
                            EZVARS_aux['vert-sti']['subdir-name']['value'])
    print(f"Estimating overlap between {vsteps[num_vsteps//2-1]} and {vsteps[num_vsteps//2]} "
          f"scans in {ctset_path}")
    tmp = find_vert_overlap(z00_name, z01_name, ind_z00, ind_start_z01, ind_stop_z01)
    print(f"Estimated overlap is {tmp} rows")
    return tmp


def find_vert_overlap(z00_name, z01_name, ind_z00, ind_start_z01, ind_stop_z01):
    tmp = os.path.join(z00_name, '*.tif')
    im0 = read_image(sorted(glob.glob(tmp))[ind_z00])
    tsr = TiffSequenceReader(z01_name)
    num_ref_im = ind_stop_z01 - ind_start_z01
    ssim_ind = np.zeros((num_ref_im, 1))
    #TODO: must be parallelized
    for i in range(num_ref_im):
        im1 = tsr.read(ind_start_z01 + i)
        ssim_ind[i] = ssim(im0, im1, data_range=(max(im0.max(), im1.max()) -
                                                   min(im0.min(), im1.min())))
        print(f"Similarity with slice {ind_start_z01 + i} = {ssim_ind[i]}")
    print(f"The most similar slice to {ind_z00} is {ind_start_z01 + np.argmax(ssim_ind)}")
    M = len(sorted(glob.glob(tmp)))
    # olap = ind_start_z01 + np.argmax(ssim_ind) - ind_z00
    if ind_z00 < M//2:
        return M - (ind_start_z01 + np.argmax(ssim_ind) - ind_z00)
    else:
        return (ind_start_z01 + np.argmax(ssim_ind)) - (M - ind_z00)

# def find_ver_overlap_mp(z00_name, z01_name, ind_z00, ind_start_z01, ind_stop_z01):
#     tmp = os.path.join(z00_name, '*.tif')
#     im0 = read_image(sorted(glob.glob(tmp))[ind_z00])
#     N, M = im0.shape
#     tsr = TiffSequenceReader(z01_name)
#     num_ref_im = ind_stop_z01 - ind_start_z01
#     A = np.zeros((num_ref_im, N, M))
#     ssim_ind = np.zeros((num_ref_im, 1))
#     for i in range(num_ref_im):
#         im1 = tsr.read(ind_start_z01 + i)
#         A[i,:,:] = im1
#     del(A)

# def comp_ssim(im0, A, i):
#     ssim_ind = ssim(im0, A[i,:,:], data_range=(max(im0.max(), A[i,:,:].max()) -
#                                              min(im0.min(), A[i,:,:].min())))
#     print(f"Similarity with slice {i} = {ssim_ind}")
#     return [i, ssim_ind]
#
#
#     nslices = len(sorted(glob.glob(tmp)))
#     # olap = ind_start_z01 + np.argmax(ssim_ind) - ind_z00
#     if ind_z00 < nslices // 2:
#         return nslices - (ind_start_z01 + np.argmax(ssim_ind) - ind_z00)
#     else:
#         return (ind_start_z01 + np.argmax(ssim_ind)) - (nslices - ind_z00)


def complete_message():
    print("             __.-/|")
    print("             \\`o_O'")
    print("              =( )=  +-----+")
    print("                U|   | FIN |")
    print("      /\\  /\\   / |   +-----+")
    print("     ) /^\\) ^\\/ _)\\     |")
    print("     )   /^\\/   _) \\    |")
    print("     )   _ /  / _)  \\___|_")
    print(" /\\  )/\\/ ||  | )_)\\___,|))")
    print("<  >      |(,,) )__)    |")
    print(" ||      /    \\)___)\\")
    print(" | \\____(      )___) )____")
    print("  \\______(_______;;;)__;;;)")

