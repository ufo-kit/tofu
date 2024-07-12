"""
Created on Apr 20, 2020

@author: gasilos
"""
import os, glob, tifffile
from tofu.ez.params import EZVARS, EZVARS_aux
from tofu.config import SECTIONS
from tofu.util import get_filenames, get_first_filename, get_image_shape, read_image, restrict_value, tupleize
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
import argparse
from tofu.util import TiffSequenceReader
import numpy as np
import yaml
import logging

def get_dims(pth):
    # get number of projections and projections dimensions
    first_proj = get_first_filename(pth)
    multipage = False
    try:
        shape = get_image_shape(first_proj)
    except:
        raise ValueError("Failed to determine size and number of projections in {}".format(pth))
    if len(shape) == 2:  # single page input
        return len(get_filenames(pth)), [shape[-2], shape[-1]], multipage
    elif len(shape) == 3:  # multipage input
        nviews = 0
        for i in get_filenames(pth):
            nviews += get_image_shape(i)[0]
        multipage = True
        return nviews, [shape[-2], shape[-1]], multipage
    return -6, [-6, -6]

def get_data_cube_info(pth):
    im_names = glob.glob(os.path.join(pth, '*.tif'))
    nslices = len(im_names)
    im = read_image(im_names[0])
    N, M = im.shape
    tmp = im.dtype
    bit = 0; dt = 'unsupported'
    if tmp == 'uint8':
        bit = 8; dt = 'uint8'
    elif tmp == 'uint16':
        bit = 16; dt = 'uint16'
    elif tmp == 'float32':
        bit = 32; dt = 'float32'
    ram_amount_bytes = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    n_per_pass = int(0.9 * ram_amount_bytes / (N * M * 4))
    return nslices, N, M, bit, dt, n_per_pass

def bad_vert_ROI(multipage, path2proj, y, height):
    if multipage:
        with tifffile.TiffFile(get_filenames(path2proj)[0]) as tif:
            proj = tif.pages[0].asarray().astype(float)
    else:
        proj = read_image(get_filenames(path2proj)[0]).astype(float)
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
        raise ValueError("Failed to determine size and number of flats in {}".format(flatdir))
    cmd = ""
    if len(shape) == 2:
        last_flat_file = get_filenames(flatdir)[-1]
        cmd = "cp {} {}".format(last_flat_file, flat_copy_name)
    else:
        flat = read_image(get_filenames(flatdir)[-1])[-1]
        if dryrun:
            cmd = 'echo Will save a copy of flat into "{}"'.format(flat_copy_name)
        else:
            tifffile.imwrite(flat_copy_name, flat)

    # something isn't right in this logic? It used to work but then
    # stopped to create a copy of flat correctly. Going to point to all flats simply
    return cmd


def clean_tmp_dirs(tmpdir, fdt_names):
    tmp_pattern = ["proj", "sino", "mask", "flat", "dark", "radi"]
    tmp_pattern += fdt_names
    # clean directories in tmpdir if their names match pattern
    if os.path.exists(tmpdir):
        for filename in os.listdir(tmpdir):
            if filename[:4] in tmp_pattern:
                os.system("rm -rf {}".format(os.path.join(tmpdir, filename)))

def make_inpaths(lvl0, flats2):
    """
    Creates a list of paths to flats/darks/tomo directories
    :param lvl0: Root of directory containing flats/darks/tomo
    :param flats2: The type of directory: 3 contains flats/darks/tomo 4 contains flats/darks/tomo/flats2
    :return: List of abs paths to the directories containing darks/flats/tomo and flats2 (if used)
    """
    indir = []
    # If using flats/darks/flats2 in same dir as tomo
    # or darks/flats were processed and are already in temporary directory
    if not EZVARS['inout']['shared-flatsdarks']['value'] or \
                EZVARS['inout']['shared-df-used']['value']:
        for i in [EZVARS['inout']['darks-dir']['value'],
                  EZVARS['inout']['flats-dir']['value'],
                  EZVARS['inout']['tomo-dir']['value']]:
            indir.append(os.path.join(lvl0, i))
        if flats2 - 3:
            indir.append(os.path.join(lvl0, EZVARS['inout']['flats2-dir']['value']))
        return indir
    # If using common flats/darks/flats2 across multiple reconstructions
    # and that is the first occasion when they are required
    elif EZVARS['inout']['shared-flatsdarks']['value'] and \
            not EZVARS['inout']['shared-df-used']['value']:
        indir.append(EZVARS['inout']['path2-shared-darks']['value'])
        indir.append(EZVARS['inout']['path2-shared-flats']['value'])
        indir.append(os.path.join(lvl0, EZVARS['inout']['tomo-dir']['value']))
        if EZVARS['inout']['shared-flats-after']['value']:
            indir.append(EZVARS['inout']['path2-shared-flats2']['value'])
        if (EZVARS['COR']['search-method']['value'] != 1) and (EZVARS['COR']['search-method']['value'] != 2):
            # if axis search is using shared darks/flats, we still have to use them once more for ffc
            add_value_to_dict_entry(EZVARS['inout']['shared-df-used'], True)
        return indir

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

def enquote(string, escape=False):
    addition = '\\"' if escape else '"'

    return addition + string + addition

def extract_values_from_dict(dict):
    """Return a list of values to be saved as a text file"""
    new_dict = {}
    for key1 in dict.keys():
        new_dict[key1] = {}
        for key2 in dict[key1].keys():
            dict_entry = dict[key1][key2]
            if 'value' in dict_entry:
                new_dict[key1][key2] = {}
                value_type = type(dict_entry['value'])
                #print(key1, key2, dict_entry)
                if dict_entry['value'] is None:
                    new_dict[key1][key2]['value'] = None
                elif value_type is list or value_type is tuple:
                    new_dict[key1][key2]['value'] = str(reverse_tupleize()(dict_entry['value']))
                else:                      
                    new_dict[key1][key2]['value'] = dict_entry['value']
            if key1 == 'axes-list':
                new_dict[key1][key2] = dict_entry
    return new_dict

def import_values_from_dict(dict, imported_dict):
    """Import a list of values from an imported dictionary"""
    for key1 in imported_dict.keys():
        if key1 == 'axes-list':
            for key2 in imported_dict[key1].keys():
                dict[key1][key2] = imported_dict[key1][key2]
        else:
            for key2 in imported_dict[key1].keys():
                add_value_to_dict_entry(dict[key1][key2], imported_dict[key1][key2]['value'])


def export_values(filePath, param_sections):
    """Export the values of EZVARS and SECTIONS as a YAML file"""
    combined_dict = {}
    for i in param_sections:
        if i == 'ezvars_aux':
            try:
                combined_dict['ezvars_aux'] = extract_values_from_dict(EZVARS_aux)
            except:
                print("Error: cannot import EZVARS_aux section")
                return 1
        if i == 'tofu':
            try:
                combined_dict['sections'] = extract_values_from_dict(SECTIONS)
            except:
                print("Error: cannot import TOFU section")
                return 1
        if i == 'ezvars':
            try:
                combined_dict['ezvars'] = extract_values_from_dict(EZVARS)
            except:
                print("Error: cannot import EZVARS section")
                return 1
    print("Exporting values to: " + str(filePath))
    #print(combined_dict)
    write_yaml(filePath, combined_dict)
    print("Finished exporting")
    return 0
    
def import_values(filePath, param_sections):
    """Import EZVARS and SECTIONS from a YAML file"""
    #param_sections options: ['ezvars', 'tofu', 'ezvars_aux']
    print("Importing values from: " +str(filePath))
    yaml_data = dict(read_yaml(filePath))
    for i in param_sections:
        if i == 'ezvars':
            try:
                import_values_from_dict(EZVARS, yaml_data['ezvars'])
            except:
                print("Error: cannot import EZVARS section")
                return 1
        if i == 'tofu':
            try:
                import_values_from_dict(SECTIONS, yaml_data['sections'])
            except:
                print("Error: cannot import TOFU section")
                return 1
        if i == 'ezvars_aux':
            try:
                import_values_from_dict(EZVARS_aux, yaml_data['ezvars_aux'])
            except:
                print("Error: cannot import EZVARS_aux section")
                return 1
    print("Finished importing")
    return 0
    #print(yaml_data)

def save_params(ctsetname, ax, nviews, wh):
    if not EZVARS['inout']['dryrun']['value'] and not os.path.exists(EZVARS['inout']['output-dir']['value']):
        os.makedirs(EZVARS['inout']['output-dir']['value'])
    tmp = os.path.join(EZVARS['inout']['output-dir']['value'], ctsetname)
    if not EZVARS['inout']['dryrun']['value'] and not os.path.exists(tmp):
        os.makedirs(tmp)
    if not EZVARS['inout']['dryrun']['value'] and EZVARS['inout']['save-params']['value']:
        # Dump the params .yaml file
        try:
            filepath = os.path.join(tmp, "tofuez_all_parameters.yaml")
            export_values(filepath, ['ezvars', 'tofu', 'ezvars_aux'])
            
        except FileNotFoundError:
            print("Something went wrong when exporting the .yaml parameters file")

        # Dump the reco.params output file
        fname = os.path.join(tmp, 'reco_params_simple.txt')
        f = open(fname, 'w')
        f.write('*** General ***\n')
        f.write('Input directory {}\n'.format(EZVARS['inout']['input-dir']['value']))
        if ctsetname == '':
            ctsetname = '.'
        f.write('CT set {}\n'.format(ctsetname))
        if EZVARS['COR']['search-method']['value'] == 1 or EZVARS['COR']['search-method']['value'] == 2:
            f.write('Center of rotation {} (auto estimate)\n'.format(ax))
        elif EZVARS['COR']['search-method']['value'] == 3:
            f.write('Center of rotation {} (user defined)\n'.format(ax))
        else:
            f.write('Center of rotation {} (half acq mode data)\n'.format(ax))
        f.write('Dimensions of projections {} x {} (height x width)\n'.format(wh[0], wh[1]))
        f.write('Number of projections {}\n'.format(nviews))
        f.write('*** Preprocessing ***\n')
        tmp = 'None'
        if EZVARS['inout']['preprocess']['value']:
            tmp = EZVARS['inout']['preprocess-command']['value']
        f.write('  '+tmp+'\n')
        f.write('*** Image filters ***\n')
        if EZVARS['filters']['rm_spots']['value']:
            f.write(' Remove large spots enabled\n')
            f.write('  threshold {}\n'.format(SECTIONS['find-large-spots']['spot-threshold']['value']))
            f.write('  sigma {}\n'.format(SECTIONS['find-large-spots']['gauss-sigma']['value']))
            if EZVARS['filters']['rm_spots_use_median']['value']:
                f.write('  Median filter was used to find spots\n')
                # for i in SECTIONS['find-large-spots'].keys():
                #     f.write(f"\t{i}\t{SECTIONS['find-large-spots'][i]['value']}\n")
                f.write(f"\tMedian width {SECTIONS['find-large-spots']['median-width']['value']}\n")
                f.write(f"\tDilation disk radius {SECTIONS['find-large-spots']['dilation-disk-radius']['value']}\n")
                f.write(f"\tGrow threshold {SECTIONS['find-large-spots']['grow-threshold']['value']}\n")
                f.write(f"\tThreshold mode {SECTIONS['find-large-spots']['spot-threshold-mode']['value']}\n")
                f.write(f"\tMedian direction {SECTIONS['find-large-spots']['median-direction']['value']}\n")
        else:
            f.write('  Remove large spots disabled\n')
        if EZVARS['retrieve-phase']['apply-pr']['value']:
            f.write(' Phase retrieval enabled\n')
            f.write('  energy {} keV\n'.format(SECTIONS['retrieve-phase']['energy']['value']))
            f.write('  pixel size {:0.1f} um\n'.format(SECTIONS['retrieve-phase']['pixel-size']['value'] * 1e6))
            f.write('  sample-detector distance {} m\n'.format(SECTIONS['retrieve-phase']['propagation-distance']['value'][0]))
            f.write(f" delta/beta ratio {10**SECTIONS['retrieve-phase']['regularization-rate']['value']}\n")
        else:
            f.write('  Phase retrieval disabled\n')
        f.write('*** Ring removal ***\n')
        if EZVARS['RR']['enable-RR']['value']:
            if EZVARS['RR']['use-ufo']['value']:
                tmp = '2D'
                if EZVARS['RR']['ufo-2d']['value']:
                    tmp = '1D'
                f.write('  RR with ufo {} stripes filter\n'.format(tmp))
                f.write(f'   sigma horizontal {EZVARS["RR"]["sx"]["value"]}')
                f.write(f'   sigma vertical {EZVARS["RR"]["sy"]["value"]}')
            else:
                if EZVARS['RR']['spy-rm-wide']['value']:
                    tmp = '  RR with ufo sarepy remove wide filter, '
                    tmp += 'window {}, SNR {}\n'.format(
                        EZVARS['RR']['spy-wide-window']['value'],
                        EZVARS['RR']['spy-wide-SNR']['value'])
                    f.write(tmp)
                f.write('  '
                        'RR with ufo sarepy sorting filter, window {}\n'.
                        format(EZVARS['RR']['spy-narrow-window']['value'])
                        )
        else:
            f.write('RR disabled\n')
        f.write('*** Region of interest ***\n')
        if EZVARS['inout']['input_ROI']['value']:
            f.write('Vertical ROI defined\n')
            f.write('  first row {}\n'.format(SECTIONS['reading']['y']['value']))
            f.write('  height {}\n'.format(SECTIONS['reading']['height']['value']))
            f.write('  reconstruct every {}th row\n'.format(SECTIONS['reading']['y-step']['value']))
        else:
            f.write('Vertical ROI: all rows\n')
        if EZVARS['inout']['output-ROI']['value']:
            f.write('ROI in slice plane defined\n')
            f.write('  x {}\n'.format(EZVARS['inout']['output-x']['value']))
            f.write('  width {}\n'.format(EZVARS['inout']['output-width']['value']))
            f.write('  y {}\n'.format(EZVARS['inout']['output-y']['value']))
            f.write('  height {}\n'.format(EZVARS['inout']['output-height']['value']))
        else:
            f.write('ROI in slice plane not defined\n')
        f.write('*** Reconstructed values ***\n')
        if EZVARS['inout']['clip_hist']['value']:
            f.write('  {} bit\n'.format(SECTIONS['general']['output-bitdepth']['value']))
            f.write('  Min value in 32-bit histogram {}\n'.format(SECTIONS['general']['output-minimum']['value']))
            f.write('  Max value in 32-bit histogram {}\n'.format(SECTIONS['general']['output-maximum']['value']))
        else:
            f.write('  32bit, histogram untouched\n')
        f.write('*** Optional reco parameters ***\n')
        if SECTIONS['general-reconstruction']['volume-angle-z']['value'][0] > 0:
            f.write('  Rotate volume by: {:0.3f} deg\n'.format(SECTIONS['general-reconstruction']['volume-angle-z']['value'][0]))
        f.close()



### ALL The following was added by Philmo Gu. I moved it to tofu/ez/utils. .

# The important function
def add_value_to_dict_entry(dict_entry, value):
    """Add a value to a dictionary entry. An empty string will insert the ezdefault value"""
    if 'action' in dict_entry:
        # no 'type' can be defined in dictionary entries with 'action' key
        dict_entry['value'] = bool(value)
        return
    elif value == '' or value == None:
        # takes default value if empty string or null
        if dict_entry['ezdefault'] is None:
            dict_entry['value'] = dict_entry['ezdefault']
        else:
            dict_entry['value'] = dict_entry['type'](dict_entry['ezdefault'])
    else:
        try:
            dict_entry['value'] = dict_entry['type'](value)
        except argparse.ArgumentTypeError:  # Outside of range of type
            dict_entry['value'] = dict_entry['type'](value, clamp=True)
        except ValueError:  # int can't convert string with decimal (e.g. "1.0" -> 1)
            dict_entry['value'] = dict_entry['type'](float(value))


# Few things are helpful but most are not used or not fully implemented

def get_ascii_validator():
    """Returns a validator that only allows the input of visible ASCII characters"""
    regexp = "[-A-Za-z0-9_]*"
    return QRegExpValidator(QRegExp(regexp))


def get_alphabet_lowercase_validator():
    """Returns a validator that only allows the input of lowercase ASCII characters"""
    regexp = "[a-z]*"
    return QRegExpValidator(QRegExp(regexp))


def get_int_validator():
    """Returns a validator that only allows the input of integers"""
    # Note: QIntValidator allows commas, which is undesirable
    regexp = "[\-]?[0-9]*"
    return QRegExpValidator(QRegExp(regexp))


def get_double_validator():
    """Returns a validator that only allows the input of floating point number"""
    # Note: QDoubleValidator allows commas before period, which is undesirable
    regexp = "[\-]?[0-9]*[.]?[0-9]*"
    return QRegExpValidator(QRegExp(regexp))


def get_tuple_validator():
    """Returns a validator that only allows a tuple of floating point numbers"""
    regexp = "[-0-9,.]*"
    return QRegExpValidator(QRegExp(regexp))


def load_values_from_ezdefault(dict):
    """Add or replace values from ezdefault in a dictionary"""
    for key1 in dict.keys():
        for key2 in dict[key1].keys():
            dict_entry = dict[key1][key2]
            if 'ezdefault' in dict_entry:
                add_value_to_dict_entry(dict_entry, '')  # Add default value


def restrict_tupleize(limits, num_items=None, conv=float, dtype=tuple):
    """Convert a string of numbers separated by commas to tuple with *dtype* and make sure it is within *limits* (included) specified as tuple
    (min, max). If one of the limits values is None it is ignored."""

    def check(value=None, clamp=False):
        if value is None:
            return limits
        results = tupleize(num_items, conv, dtype)(value)
        for v in results:
            restrict_value(limits, dtype=conv)(v, clamp)
        return results

    return check

def reverse_tupleize(num_items=None, conv=float):
    """Convert a tuple into a comma-separted string of *value*"""

    def combine_to_string(value):
        """Combine a tuple of numbers into a comma-separated string"""

        result = ""
        if num_items and len(result) != num_items:
            # A certain number of output is expected
            raise argparse.ArgumentTypeError('Expected {} items'.format(num_items))

        if (len(value) == 0):
            # No tuple to convert into string
            return result

        # Tuple with non-zero lengthh
        for v in value:
            result = result + "," + str(conv(v))
        result = result[1:]  # Remove the erroneous first period
        return result

    return combine_to_string

def get_median_flat(path2flat):
    tsr = TiffSequenceReader(path2flat)
    tmp = tsr.read(0)
    data = np.empty((tsr.num_images, tmp.shape[0], tmp.shape[1]), np.uint16)
    for i in range(tsr.num_images):
        data[i, :, :] = tsr.read(i)
    tsr.close()
    x = np.median(data, axis=0)
    del data
    return x

def get_mean_flat(path2flat):
    tsr = TiffSequenceReader(path2flat)
    tmp = tsr.read(0)
    data = np.empty((tsr.num_images, tmp.shape[0], tmp.shape[1]), np.uint16)
    for i in range(tsr.num_images):
        data[i, :, :] = tsr.read(i)
    tsr.close()
    x = np.mean(data, axis=0)
    del data
    return x

def read_yaml(filePath):
    with open(filePath) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
        return data

def write_yaml(filePath, params):
    try:
        file = open(filePath, "w")
    except FileNotFoundError:
        print('Cannot write yaml file')
    else:
        yaml.dump(params, file)
        file.close()

def check_that_num_failed(vals):
    vals = vals.split(',')
    # check that all comma separated entries
    # in the input string
    for i in range(len(vals)):
        try:
            float(vals[i])
        except:
            return 1
    return 0


def get_fdt_names():
    return [EZVARS['inout']['darks-dir']['value'],
            EZVARS['inout']['flats-dir']['value'],
            EZVARS['inout']['tomo-dir']['value'],
            EZVARS['inout']['flats2-dir']['value']]
