"""
Created on Apr 20, 2020

@author: gasilos
"""
import os, glob, tifffile
from tofu.ez.params import EZVARS
from tofu.config import SECTIONS
from tofu.ez.yaml_in_out import read_yaml, write_yaml
from tofu.util import get_filenames, get_first_filename, get_image_shape, read_image, restrict_value, tupleize
from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QRegExpValidator
import argparse

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
    return new_dict                   

def import_values_from_dict(dict, imported_dict):
    """Import a list of values from an imported dictionary"""
    for key1 in imported_dict.keys():
        for key2 in imported_dict[key1].keys():
            add_value_to_dict_entry(dict[key1][key2],imported_dict[key1][key2]['value'])

def export_values(filePath):
    """Export the values of EZVARS and SECTIONS as a YAML file"""
    combined_dict = {}
    combined_dict['sections'] = extract_values_from_dict(SECTIONS)
    combined_dict['ezvars'] = extract_values_from_dict(EZVARS)
    print("Exporting values to: " + str(filePath))
    #print(combined_dict)
    write_yaml(filePath, combined_dict)
    print("Finished exporting")
    
def import_values(filePath):
    """Import EZVARS and SECTIONS from a YAML file"""
    print("Importing values from: " +str(filePath))
    yaml_data = dict(read_yaml(filePath))
    import_values_from_dict(EZVARS,yaml_data['ezvars'])
    import_values_from_dict(SECTIONS,yaml_data['sections'])
    print("Finished importing")
    #print(yaml_data)

def import_values_from_params(self, params):
    """
    Import parameter values into their corresponding dictionary entries
    """             
    print("Entering parameter values into dictionary entries")
    map_param_to_dict_entries = self.createMapFromParamsToDictEntry()
    for p in params:
        dict_entry = map_param_to_dict_entries[str(p)]
        add_value_to_dict_entry(dict_entry, params[str(p)], False)

def export_values(filePath):
    """Export the values of EZVARS and SECTIONS as a YAML file"""
    combined_dict = {}
    combined_dict['sections'] = extract_values_from_dict(SECTIONS)
    combined_dict['ezvars'] = extract_values_from_dict(EZVARS)
    print("Exporting values to: " + str(filePath))
    #print(combined_dict)
    write_yaml(filePath, combined_dict)
    print("Finished exporting")
    
def import_values(filePath):
    """Import EZVARS and SECTIONS from a YAML file"""
    print("Importing values from: " +str(filePath))
    yaml_data = dict(read_yaml(filePath))
    import_values_from_dict(EZVARS,yaml_data['ezvars'])
    import_values_from_dict(SECTIONS,yaml_data['sections'])
    print("Finished importing")
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
            yaml_output_filepath = os.path.join(tmp, "parameters.yaml")
            export_values(yaml_output_filepath)
            
        except FileNotFoundError:
            print("Something went wrong when exporting the .yaml parameters file")

        # Dump the reco.params output file
        fname = os.path.join(tmp, 'reco.params')
        f = open(fname, 'w')
        f.write('*** General ***\n')
        f.write('Input directory {}\n'.format(EZVARS['inout']['input-dir']['value']))
        if ctsetname == '':
            ctsetname = '.'
        f.write('CT set {}\n'.format(ctsetname))
        if EZVARS['COR']['search-method']['value'] == 1 or EZVARS['COR']['search-method']['value'] == 2:
            f.write('Center of rotation {} (auto estimate)\n'.format(ax))
        else:
            f.write('Center of rotation {} (user defined)\n'.format(ax))
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
        else:
            f.write('  Remove large spots disabled\n')
        if EZVARS['retrieve-phase']['apply-pr']['value']:
            f.write(' Phase retrieval enabled\n')
            f.write('  energy {} keV\n'.format(SECTIONS['retrieve-phase']['energy']['value']))
            f.write('  pixel size {:0.1f} um\n'.format(SECTIONS['retrieve-phase']['pixel-size']['value'] * 1e6))
            f.write('  sample-detector distance {} m\n'.format(SECTIONS['retrieve-phase']['propagation-distance']['value'][0]))
            f.write('  delta/beta ratio {}\n'.format(SECTIONS['retrieve-phase']['regularization-rate']['value']))
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



