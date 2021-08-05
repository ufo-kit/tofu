'''
Created on Apr 20, 2020

@author: gasilos
'''
import os
import tifffile
import yaml
import numpy as np
import tofu.ez.GUI.params as parameters
from tofu.util import (get_filenames, get_first_filename, get_image_shape, read_image)


def get_dims(pth):
    # get number of projections and projections dimensions
    first_proj = get_first_filename(pth)
    multipage = False
    try:
        shape = get_image_shape(first_proj)
    except:
        raise ValueError('Failed to determine size and number of projections in {}'.format(pth))
    if len(shape) == 2:  # single page input
        return len(get_filenames(pth)), [shape[-2], shape[-1]], multipage
    elif len(shape) == 3:  # multipage input
        nviews = 0
        for i in get_filenames(pth):
            nviews += get_image_shape(i)[0]
        multipage = True
        return nviews, [shape[-2], shape[-1]], multipage
    return -6, [-6, -6]

def bad_vert_ROI(multipage, path2proj, y, height):
    if multipage:
        with tifffile.TiffFile(get_filenames(path2proj)[0]) as tif:
            proj = tif.pages[0].asarray().astype(np.float)
    else:
        proj = read_image(get_filenames(path2proj)[0]).astype(np.float)
    y_region = slice(y, min(y + height, proj.shape[0]), 1)
    proj = proj[y_region, :]
    if proj.shape[0] == 0:
        return True
    else:
        return False

def make_copy_of_flat(flatdir, flat_copy_name, dryrun):
    first_flat_file = get_first_filename(flatdir)
    try:
        shape = get_image_shape(first_flat_file)
    except:
        raise ValueError('Failed to determine size and number of flats in {}'.format(flatdir))
    cmd = ""
    if len(shape) == 2:
        last_flat_file = get_filenames(flatdir)[-1]
        cmd = "cp {} {}".format(last_flat_file, flat_copy_name)
    else:
        flat = read_image(get_filenames(flatdir)[-1])[-1]
        if dryrun:
            cmd = "echo Will save a copy of flat into \"{}\"".format(flat_copy_name)
        else:
            tifffile.imsave(flat_copy_name, flat)
    return cmd

def clean_tmp_dirs(tmpdir, fdt_names):
    tmp_pattern = ['proj', 'sino', 'mask', 'flat', 'dark', 'radi']
    tmp_pattern += fdt_names
    # clean directories in tmpdir if their names match pattern
    if os.path.exists(tmpdir):
        for filename in os.listdir(tmpdir):
            if filename[:4] in tmp_pattern:
                os.system('rm -rf {}'.format(os.path.join(tmpdir, filename)))

def enquote(string, escape=False):
    addition = '\\"' if escape else '"'

    return addition + string + addition


def save_params(args, ctsetname, ax, nviews, WH):
    if not args.dryrun and not os.path.exists(args.outdir):
        os.makedirs(args.outdir)
    tmp = os.path.join(args.outdir, ctsetname)
    if not args.dryrun and not os.path.exists(tmp):
        os.makedirs(tmp)
    if not args.dryrun and args.parfile:
        # Dump the params .yaml file
        try:
            yaml_output_filepath = os.path.join(tmp, 'parameters.yaml')
            yaml_output = open(yaml_output_filepath, 'w')
            yaml.dump(parameters.params, yaml_output)
        except FileNotFoundError:
            print("Something went wrong when exporting the .yaml parameters file")

        # Dump the reco.params output file 
        fname = os.path.join(tmp, 'reco.params')
        f = open(fname, 'w')
        f.write('*** General ***\n')
        f.write('Input directory {}\n'.format(args.indir))
        if ctsetname == '':
            ctsetname = '.'
        f.write('CT set {}\n'.format(ctsetname))
        if args.ax == 1 or args.ax == 2:
            f.write('Center of rotation {} (auto estimate)\n'.format(ax))
        else:
            f.write('Center of rotation {} (user defined)\n'.format(ax))
        f.write('Dimensions of projections {} x {} (height x width)\n'.format(WH[0], WH[1]))
        f.write('Number of projections {}\n'.format(nviews))
        f.write('*** Preprocessing ***\n')
        tmp = 'None'
        if args.pre:
            tmp = args.pre_cmd
        f.write('  '+tmp+'\n')
        f.write('*** Image filters ***\n')
        if args.inp:
            f.write(' Remove large spots enabled\n')
            f.write('  threshold {}\n'.format(args.inp_thr))
            f.write('  sigma {}\n'.format(args.inp_sig))
        else:
            f.write('  Remove large spots disabled\n')
        if args.PR:
            f.write(' Phase retreival enabled\n')
            f.write('  energy {} keV\n'.format(args.energy))
            f.write('  pixel size {:0.1f} um\n'.format(args.pixel * 1e6))
            f.write('  sample-detector distance {} m\n'.format(args.z))
            f.write('  delta/beta ratio {:0.0f}\n'.format(10 ** args.log10db))
        else:
            f.write('  Phase retreival disabled\n')
        f.write('*** Ring removal ***\n')
        if args.RR:
            if args.RR_ufo:
                tmp = '2D'
                if args.RR_ufo_1d:
                    tmp = '1D'
                f.write('  RR with ufo {} stripes filter\n'.format(tmp))
                f.write(f'   sigma horizontal {args.RR_sig_hor}')
                f.write(f'   sigma vertical {args.RR_sig_ver}')
            else:
                if args.RR_srp_wide:
                    tmp = '  RR with ufo sarepy remove wide filter, '
                    tmp += 'window {}, SNR {}\n'.format(args.RR_srp_wide_wind, args.RR_srp_wide_snr)
                    f.write(tmp)
                f.write('  RR with ufo sarepy sorting filter, window {}\n'.format(args.RR_srp_wind_sort))
        else:
            f.write('RR disabled\n')
        f.write('*** Region of interest ***\n')
        if args.vcrop:
            f.write('Vertical ROI defined\n')
            f.write('  first row {}\n'.format(args.y))
            f.write('  height {}\n'.format(args.yheight))
            f.write('  reconstruct every {}th row\n'.format(args.ystep))
        else:
            f.write('Vertical ROI: all rows\n')
        if args.crop:
            f.write('ROI in slice plane defined\n')
            f.write('  x {}\n'.format(args.x0))
            f.write('  width {}\n'.format(args.dx))
            f.write('  y {}\n'.format(args.y0))
            f.write('  height {}\n'.format(args.dy))
        else:
            f.write('ROI in slice plane not defined\n')
        f.write('*** Reconstructed values ***\n')
        if args.gray256:
            f.write('  {} bit\n'.format(args.bit))
            f.write('  Min value in 32-bit histogram {}\n'.format(args.hmin))
            f.write('  Max value in 32-bit histogram {}\n'.format(args.hmax))
        else:
            f.write('  32bit, histogram untouched\n')
        f.write('*** Optional reco parameters ***\n')
        if args.a0 > 0:
            f.write('  Rotate volume by: {:0.3f} deg\n'.format(args.a0))
        f.close()
