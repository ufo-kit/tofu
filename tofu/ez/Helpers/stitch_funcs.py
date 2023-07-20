"""
Last modified on Apr 1, 2022
@author: sergei gasilov
"""

import glob
import os
import shutil

import numpy as np
import tifffile
from tofu.util import read_image, get_image_shape, get_filenames
from tofu.ez.image_read_write import TiffSequenceReader, get_image_dtype
import multiprocessing as mp
from functools import partial
import time

import sys

try:
    from mpi4py import MPI
except ImportError:
    print("You must install openmpi/mpi4py in order to stitch half acq. mode data",
          file=sys.stderr)

from tofu.ez.params import EZVARS

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

def prepare(parameters, dir_type: int, ctdir: str):
    """
    :param parameters: GUI params
    :param dir_type 1 if CTDir containing Z00-Z0N slices - 2 if parent directory containing CTdirs each containing Z slices:
    :param ctdir Name of the ctdir - blank string if not using multiple ctdirs:
    :return:
    """
    hmin, hmax = 0.0, 0.0
    if parameters['ezstitch_clip_histo']:
        if parameters['ezstitch_histo_min'] == parameters['ezstitch_histo_max']:
            raise ValueError(' - Define hmin and hmax correctly in order to convert to 8bit')
        else:
            hmin, hmax = parameters['ezstitch_histo_min'], parameters['ezstitch_histo_max']
    start, stop, step = [int(value) for value in parameters['ezstitch_start_stop_step'].split(',')]
    if not os.path.exists(parameters['ezstitch_output_dir']):
        os.makedirs(parameters['ezstitch_output_dir'])
    Vsteps = sorted(os.listdir(os.path.join(parameters['ezstitch_input_dir'], ctdir)))
    #determine input data type
    if dir_type == 1:
        tmp = os.path.join(parameters['ezstitch_input_dir'], Vsteps[0], parameters['ezstitch_type_image'], '*.tif')
        tmp = sorted(glob.glob(tmp))[0]
    elif dir_type == 2:
        tmp = os.path.join(parameters['ezstitch_input_dir'], ctdir, Vsteps[0], parameters['ezstitch_type_image'], '*.tif')
        tmp = sorted(glob.glob(tmp))[0]
    indtype_digit, indtype = get_image_dtype(tmp)


    if parameters['ezstitch_stitch_orthogonal']:
        for vstep in Vsteps:
            if dir_type == 1:
                in_name = os.path.join(parameters['ezstitch_input_dir'], vstep, parameters['ezstitch_type_image'])
                out_name = os.path.join(parameters['ezstitch_temp_dir'], vstep, parameters['ezstitch_type_image'], 'sli-%04i.tif')
            elif dir_type == 2:
                in_name = os.path.join(parameters['ezstitch_input_dir'], ctdir, vstep, parameters['ezstitch_type_image'])
                out_name = os.path.join(parameters['ezstitch_temp_dir'], ctdir, vstep, parameters['ezstitch_type_image'], 'sli-%04i.tif')
            cmd = 'tofu sinos --projections {} --output {}'.format(in_name, out_name)
            cmd += " --y {} --height {} --y-step {}".format(start, stop-start, step)
            cmd += " --output-bytes-per-file 0"
            if indtype_digit == '8' or indtype_digit == '16':
                cmd += f" --output-bitdepth {indtype_digit}"
            print(cmd)
            os.system(cmd)
            time.sleep(10)
        indir = parameters['ezstitch_temp_dir']
    else:
        indir = parameters['ezstitch_input_dir']
    return indir, hmin, hmax, start, stop, step, indtype


def exec_sti_mp(start, step, N, Nnew, Vsteps, indir, dx, M, parameters, ramp, hmin, hmax, indtype, ctdir, dir_type, j):
    index = start+j*step
    Large = np.empty((Nnew*len(Vsteps)+dx, M), dtype=np.float32)
    for i, vstep in enumerate(Vsteps[:-1]):
        if dir_type == 1:
            tmp = os.path.join(indir, Vsteps[i], parameters['ezstitch_type_image'], '*.tif')
            tmp1 = os.path.join(indir, Vsteps[i+1], parameters['ezstitch_type_image'], '*.tif')
        elif dir_type == 2:
            tmp = os.path.join(indir, ctdir, Vsteps[i], parameters['ezstitch_type_image'], '*.tif')
            tmp1 = os.path.join(indir, ctdir, Vsteps[i + 1], parameters['ezstitch_type_image'], '*.tif')
        if parameters['ezstitch_stitch_orthogonal']:
            tmp = sorted(glob.glob(tmp))[j]
            tmp1 = sorted(glob.glob(tmp1))[j]
        else:
            tmp = sorted(glob.glob(tmp))[index]
            tmp1 = sorted(glob.glob(tmp1))[index]
        first = read_image(tmp)
        second = read_image(tmp1)
        # sample moved downwards
        if parameters['ezstitch_sample_moved_down']:
            first, second = np.flipud(first), np.flipud(second)

        k = np.mean(first[N - dx:, :]) / np.mean(second[:dx, :])
        second = second * k

        a, b, c = i*Nnew, (i+1)*Nnew, (i+2)*Nnew
        Large[a:b, :] = first[:N-dx, :]
        Large[b:b+dx, :] = np.transpose(np.transpose(first[N-dx:, :])*(1 - ramp) +
                                        np.transpose(second[:dx, :]) * ramp)
        Large[b+dx:c+dx, :] = second[dx:, :]

    pout = os.path.join(parameters['ezstitch_output_dir'],
                        ctdir,
                        parameters['ezstitch_type_image']+'-sti-{:>04}.tif'.format(index))
    if not parameters['ezstitch_clip_histo']:
        tifffile.imwrite(pout, Large.astype(indtype))
    else:
        Large = 255.0/(hmax-hmin) * (np.clip(Large, hmin, hmax) - hmin)
        tifffile.imwrite(pout, Large.astype(np.uint8))

def main_sti_mp(parameters):
    #Check whether indir is CTdir or parent containing CTdirs
    #if indir + some z00 subdir + sli + *.tif does not exist then use original
    subdirs = sorted(os.listdir(parameters['ezstitch_input_dir']))
    if os.path.exists(os.path.join(parameters['ezstitch_input_dir'], subdirs[0], parameters['ezstitch_type_image'])):
        dir_type = 1
        ctdir = ""
        print(" - Using CT directory containing slices")
        if parameters['ezstitch_stitch_orthogonal']:
            print(" - Creating orthogonal sections")
        indir, hmin, hmax, start, stop, step, indtype = prepare(parameters, dir_type, "")
        dx = int(parameters['ezstitch_num_overlap_rows'])
        # second: stitch them
        Vsteps = sorted(os.listdir(indir))
        tmp = glob.glob(os.path.join(indir, Vsteps[0], parameters['ezstitch_type_image'], '*.tif'))[0]
        first = read_image(tmp)
        N, M = first.shape
        Nnew = N - dx
        ramp = np.linspace(0, 1, dx)

        J = range((stop - start) // step)
        pool = mp.Pool(processes=mp.cpu_count())
        # ??? IT was OK back in 2.7 but now can crash
        # if pool size is larger than array being multiprocessed?
        exec_func = partial(exec_sti_mp, start, step, N, Nnew, \
                            Vsteps, indir, dx, M, parameters, ramp, hmin, hmax, indtype, ctdir, dir_type)
        print(" - Adjusting and stitching")
        # start = time.time()
        pool.map(exec_func, J)
        print("========== Done ==========")
    else:
        second_subdirs = sorted(os.listdir(os.path.join(parameters['ezstitch_input_dir'], subdirs[0])))
        if os.path.exists(os.path.join(parameters['ezstitch_input_dir'], subdirs[0], second_subdirs[0], parameters['ezstitch_type_image'])):
            print(" - Using parent directory containing CT directories, each of which contains slices")
            dir_type = 2
            #For each subdirectory do the same thing
            for ctdir in subdirs:
                print("-> Working on " + str(ctdir))
                if not os.path.exists(os.path.join(parameters['ezstitch_output_dir'], ctdir)):
                    os.makedirs(os.path.join(parameters['ezstitch_output_dir'], ctdir))
                if parameters['ezstitch_stitch_orthogonal']:
                    print(" - Creating orthogonal sections")
                indir, hmin, hmax, start, stop, step, indtype = prepare(parameters, dir_type, ctdir)
                dx = int(parameters['ezstitch_num_overlap_rows'])
                # second: stitch them
                Vsteps = sorted(os.listdir(os.path.join(indir, ctdir)))
                tmp = glob.glob(os.path.join(indir, ctdir, Vsteps[0], parameters['ezstitch_type_image'], '*.tif'))[0]
                first = read_image(tmp)
                N, M = first.shape
                Nnew = N - dx
                ramp = np.linspace(0, 1, dx)

                J = range(int((stop - start) / step))
                pool = mp.Pool(processes=mp.cpu_count())
                exec_func = partial(exec_sti_mp, start, step, N, Nnew, \
                                    Vsteps, indir, dx, M, parameters, ramp, hmin, hmax, indtype, ctdir, dir_type)
                print(" - Adjusting and stitching")
                # start = time.time()
                pool.map(exec_func, J)
                print("========== Done ==========")
                # Clear temp directory
                clear_tmp(parameters)
        else:
            print("Invalid input directory")
        complete_message()


def make_buf(tmp, l, a, b):
    first = read_image(tmp)
    N, M = first[a:b, :].shape
    return np.empty((N*l, M), dtype=first.dtype), N, first.dtype


def exec_conc_mp(start, step, example_im, l, parameters, zfold, indir, ctdir, j):
    index = start+j*step
    Large, N, dtype = make_buf(example_im, l, parameters['ezstitch_first_row'], parameters['ezstitch_last_row'])
    for i, vert in enumerate(zfold):
        tmp = os.path.join(indir, ctdir, vert, parameters['ezstitch_type_image'], '*.tif')
        if parameters['ezstitch_stitch_orthogonal']:
            fname=sorted(glob.glob(tmp))[j]
        else:
            fname=sorted(glob.glob(tmp))[index]
        frame = read_image(fname)[parameters['ezstitch_first_row']:parameters['ezstitch_last_row'], :]
        if parameters['ezstitch_sample_moved_down']:
            Large[i*N:N*(i+1), :] = np.flipud(frame)
        else:
            Large[i*N:N*(i+1), :] = frame

    pout = os.path.join(parameters['ezstitch_output_dir'], ctdir, parameters['ezstitch_type_image']+'-sti-{:>04}.tif'.format(index))
    #print "input data type {:}".format(dtype)
    tifffile.imwrite(pout, Large)


def main_conc_mp(parameters):
    # Check whether indir is CTdir or parent containing CTdirs
    # if indir + some z00 subdir + sli + *.tif does not exist then use original
    subdirs = sorted(os.listdir(parameters['ezstitch_input_dir']))
    if os.path.exists(os.path.join(parameters['ezstitch_input_dir'], subdirs[0], parameters['ezstitch_type_image'])):
        dir_type = 1
        ctdir = ""
        print(" - Using CT directory containing slices")
        if parameters['ezstitch_stitch_orthogonal']:
            print(" - Creating orthogonal sections")
        #start = time.time()
        indir, hmin, hmax, start, stop, step, indtype = prepare(parameters, dir_type, ctdir)
        subdirs = [dI for dI in os.listdir(parameters['ezstitch_input_dir']) if os.path.isdir(os.path.join(parameters['ezstitch_input_dir'], dI))]
        zfold = sorted(subdirs)
        l = len(zfold)
        tmp = glob.glob(os.path.join(indir, zfold[0], parameters['ezstitch_type_image'], '*.tif'))
        J = range((stop-start)//step)
        pool = mp.Pool(processes=mp.cpu_count())
        exec_func = partial(exec_conc_mp, start, step, tmp[0], l, parameters, zfold, indir, ctdir)
        print(" - Concatenating")
        #start = time.time()
        pool.map(exec_func, J)
        #print "Images stitched in {:.01f} sec".format(time.time()-start)
        print("============ Done ============")
    else:
        second_subdirs = sorted(os.listdir(os.path.join(parameters['ezstitch_input_dir'], subdirs[0])))
        if os.path.exists(os.path.join(parameters['ezstitch_input_dir'], subdirs[0], second_subdirs[0], parameters['ezstitch_type_image'])):
            print(" - Using parent directory containing CT directories, each of which contains slices")
            dir_type = 2
            for ctdir in subdirs:
                print(" == Working on " + str(ctdir) + " ==")
                if not os.path.exists(os.path.join(parameters['ezstitch_output_dir'], ctdir)):
                    os.makedirs(os.path.join(parameters['ezstitch_output_dir'], ctdir))
                if parameters['ezstitch_stitch_orthogonal']:
                    print("   - Creating orthogonal sections")
                # start = time.time()
                indir, hmin, hmax, start, stop, step, indtype = prepare(parameters, dir_type, ctdir)
                zfold = sorted(os.listdir(os.path.join(indir, ctdir)))
                l = len(zfold)
                tmp = glob.glob(os.path.join(indir, ctdir, zfold[0], parameters['ezstitch_type_image'], '*.tif'))
                J = range((stop - start) // step)
                pool = mp.Pool(processes=mp.cpu_count())
                exec_func = partial(exec_conc_mp, start, step, tmp[0], l, parameters, zfold, indir, ctdir)
                print("   - Concatenating")
                # start = time.time()
                pool.map(exec_func, J)
                # print "Images stitched in {:.01f} sec".format(time.time()-start)
                print("============ Done ============")
                #Clear temp directory
                clear_tmp(parameters)
    complete_message()


############################## HALF ACQ ##############################
def stitch(first, second, axis, crop):
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
    second = np.clip(second * k, np.iinfo(np.uint16).min, np.iinfo(np.uint16).max).astype(np.uint16)

    result[:, :w - dx] = first[:, :w - dx]
    result[:, w - dx:w] = first[:, w - dx:] * (1 - ramp) + second[:, :dx] * ramp
    result[:, w:] = second[:, dx:]

    return result[:, slice(int(crop), int(2*(w - axis) - crop), 1)]

############################## HALF ACQ ##############################
def stitch_float32_output(first, second, axis, crop):
    print(f"Stitching two halves with axis {axis}, cropping by {crop}")
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

    result[:, :w - dx] = first[:, :w - dx]
    result[:, w - dx:w] = first[:, w - dx:] * (1 - ramp) + second[:, :dx] * ramp
    result[:, w:] = second[:, dx:] * k

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


def main_360_mp_depth2(parameters):
    ctdirs, lvl0 = findCTdirs(parameters['360multi_input_dir'], EZVARS['inout']['tomo-dir']['value'])
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

    tmp = len(parameters['360multi_input_dir'])
    ctdirs_rel_paths = []
    for i in range(num_sets):
        ctdirs_rel_paths.append(ctdirs[i][tmp+1:len(ctdirs[i])])
    print(f"Found the {num_sets} directories in the input with relative paths: {ctdirs_rel_paths}")

    # prepare axis and crop arrays
    dax = np.round(np.linspace(parameters['360multi_bottom_axis'], parameters['360multi_top_axis'], num_sets))
    if parameters['360multi_manual_axis']:
        #print(parameters['360multi_axis_dict'])
        dax = np.array(list(parameters['360multi_axis_dict'].values()))[:num_sets]
    print(f'Overlaps: {dax}')
    # compute crop:
    cra = np.max(dax)-dax
    # Axis on the right ? Must open one file to find out ><
    tmpname = os.path.join(parameters['360multi_input_dir'], ctdirs_rel_paths[0])
    subdirs = [dI for dI in os.listdir(tmpname) if os.path.isdir(os.path.join(tmpname, dI))]
    M = get_image_shape(get_filenames(os.path.join(tmpname, subdirs[0]))[0])[-1]
    if np.min(dax) > M//2:
        cra = dax - np.min(dax)
    print(f'Crop by: {cra}')

    for i, ctdir in enumerate(ctdirs):
        print("================================================================")
        print(" -> Working On: " + str(ctdir))
        print(f"    axis position {dax[i]}, margin to crop {cra[i]} pixels")

        main_360_mp_depth1(ctdir,
                    os.path.join(parameters['360multi_output_dir'], ctdirs_rel_paths[i]),
                    dax[i], cra[i])
        # print(ctdir, os.path.join(parameters['360multi_output_dir'], ctdirs_rel_paths[i]), dax[i], cra[i])







def clear_tmp(parameters):
    tmp_dirs = os.listdir(parameters['ezstitch_temp_dir'])
    for tmp_dir in tmp_dirs:
        shutil.rmtree(os.path.join(parameters['ezstitch_temp_dir'], tmp_dir))


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
