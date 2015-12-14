import argparse
import ConfigParser as configparser
import sys
from collections import OrderedDict
from tofu.util import positive_int, tupleize, range_list


NAME = "reco.conf"
SECTIONS = OrderedDict()

SECTIONS['general'] = {
    'config': {
        'default': NAME,
        'type': str,
        'help': "File name of configuration",
        'metavar': 'FILE'},
    'verbose': {
        'default': False,
        'help': 'Verbose output',
        'action': 'store_true'},
    'enable-tracing': {
        'default': False,
        'help': "Enable tracing and store result in .PID.json",
        'action': 'store_true'},
    'input': {
        'default': '.',
        'type': str,
        'help': "Location with sinograms or projections",
        'metavar': 'PATH'},
    'output': {
        'default': '.',
        'type': str,
        'help': "Path to location or format-specified file path "
                "for storing reconstructed slices",
        'metavar': 'PATH'},
    'width': {
        'default': None,
        'type': positive_int,
        'help': "Input width"},
    'remotes': {
        'default': [],
        'type': str,
        'help': "Addresses to remote ufo-nodes",
        'nargs': '+'},
    'generate-input': {
        'default': False,
        'type': bool,
        'help': "Ignore input field and generate input data"}}

SECTIONS['reading'] = {
    'y': {
        'type': positive_int,
        'default': 0,
        'help': 'Vertical coordinate from where to start reading the input image'},
    'height': {
        'default': None,
        'type': positive_int,
        'help': "Number of rows which will be read"},
    'y-step': {
        'type': positive_int,
        'default': 1,
        'help': "Read every \"step\" row from the input"},
    'start': {
        'type': positive_int,
        'default': 0,
        'help': 'Offset to the first read file'},
    'number': {
        'type': positive_int,
        'default': None,
        'help': 'Number of files to read'},
    'step': {
        'type': positive_int,
        'default': 1,
        'help': 'Read every \"step\" file'}}

SECTIONS['flat-correction'] = {
    'darks': {
        'default': '',
        'type': str,
        'help': "Location with darks",
        'metavar': 'PATH'},
    'dark-scale': {
        'default': 1,
        'type': float,
        'help': "Scaling dark"},
    'reduction-mode': {
        'default': "Average",
        'type': str,
        'help': "Flat-field correction options: Average (darks) or median (flats)"},
    'fix-nan-and-inf': {
        'default': False,
        'help': "Fix nan and inf",
        'action': 'store_true'},
    'flats': {
        'default': '',
        'type': str,
        'help': "Location with flats",
        'metavar': 'PATH'},
    'flats2': {
        'default': '',
        'type': str,
        'help': "Location with flats 2 for interpolation correction",
        'metavar': 'PATH'},
    'absorptivity': {
        'default': False,
        'action': 'store_true',
        'help': 'Do absorption correction'}}

SECTIONS['sinos'] = {
    'pass-size': {
        'type': positive_int,
        'default': 0,
        'help': 'Number of sinograms to process per pass'}}

SECTIONS['reconstruction'] = {
    'angle': {
        'default': None,
        'type': float,
        'help': "Angle step between projections in radians"},
    'projection-filter': {
        'default': 'ramp-fromreal',
        'type': str,
        'help': "Projection filter",
        'choices': ['ramp', 'ramp-fromreal', 'butterworth', 'faris-byer']}}

SECTIONS['tomographic-reconstruction'] = {
    'axis': {
        'default': None,
        'type': float,
        'help': "Axis position"},
    'dry-run': {
        'default': False,
        'help': "Reconstruct without writing data",
        'action': 'store_true'},
    'offset': {
        'default': 0.0,
        'type': float,
        'help': "Angle offset of first projection in radians"},
    'method': {
        'default': 'fbp',
        'type': str,
        'help': "Reconstruction method",
        'choices': ['fbp', 'dfi', 'sart', 'sirt', 'sbtv', 'asdpocs']}}

SECTIONS['laminographic-reconstruction'] = {
    'axis': {
        'default': None,
        'required': True,
        'type': tupleize(2, float),
        'help': "Axis position"},
    'bbox': {
        'default': None,
        'required': True,
        'type': tupleize(3, int),
        'help': "Bounding box of reconstructed volume"},
    'downsample': {
        'default': 1,
        'type': positive_int,
        'help': "Downsampling factor"},
    'pad': {
        'default': None,
        'required': True,
        'type': tupleize(2, int),
        'help': "Final padded size of input"},
    'tau': {
        'default': 1,
        'type': float,
        'help': "Pixel size in microns"},
    'tilt': {
        'default': None,
        'required': True,
        'type': float,
        'help': "Tilt angle of sample in radians"},
    'psi': {
        'default': 0.0,
        'type': float,
        'help': "Axis misalignment angle in radians"}}

SECTIONS['fbp'] = {
    'crop-width': {
        'default': None,
        'type': positive_int,
        'help': "Width of final slice"},
    'from-projections': {
        'default': False,
        'help': "Reconstruct from projections instead of sinograms",
        'action': 'store_true'}}

SECTIONS['dfi'] = {
    'oversampling': {
        'default': None,
        'type': positive_int,
        'help': "Oversample factor"}}

SECTIONS['ir'] = {
    'num-iterations': {
        'default': 10,
        'type': positive_int,
        'help': "Maximum number of iterations"}}

SECTIONS['sart'] = {
    'relaxation-factor': {
        'default': 0.25,
        'type': float,
        'help': "Relaxation factor"},
    'num-angles': {
        'default': None,
        'type': positive_int,
        'help': "Sinogram height"}}

SECTIONS['sbtv'] = {
    'lambda': {
        'default': 0.1,
        'type': float,
        'help': "Lambda"},
    'mu': {
        'default': 0.5,
        'type': float,
        'help': "mu"}}

SECTIONS['gui'] = {
    'enable-cropping': {
        'default': False,
        'help': "Enable cropping width",
        'action': 'store_true'},
    'show-2d': {
        'default': False,
        'help': "Show 2D slices with pyqtgraph",
        'action': 'store_true'},
    'show-3d': {
        'default': False,
        'help': "Show 3D slices with pyqtgraph",
        'action': 'store_true'},
    'last-dir': {
        'default': '.',
        'type': str,
        'help': "Path of the last used directory",
        'metavar': 'PATH'},
    'deg0': {
        'default': '.',
        'type': str,
        'help': "Location with 0 deg projection",
        'metavar': 'PATH'},
    'deg180': {
        'default': '.',
        'type': str,
        'help': "Location with 180 deg projection",
        'metavar': 'PATH'},
    'ffc-correction': {
        'default': False,
        'help': "Enable darks or flats correction",
        'action': 'store_true'},
    'num-flats': {
        'default': 0,
        'type': int,
        'help': "Number of flats for ffc correction."}}

SECTIONS['estimate'] = {
    'estimate-method': {
        'type': str,
        'default': 'reconstruction',
        'help': 'Rotation axis estimation algorithm',
        'choices': ['reconstruction', 'correlation']}}

SECTIONS['perf'] = {
    'num-runs': {
        'default': 3,
        'type': positive_int,
        'help': "Number of runs"},
    'width-range': {
        'default': '1024',
        'type': range_list,
        'help': "Width or range of widths of generated projections"},
    'height-range': {
        'default': '1024',
        'type': range_list,
        'help': "Height or range of heights of generated projections"},
    'num-projection-range': {
        'default': '512',
        'type': range_list,
        'help': "Number or range of number of projections"}}


def get_config_name():
    """Get the command line --config option."""
    name = NAME
    for i, arg in enumerate(sys.argv):
        if arg.startswith('--config'):
            if arg == '--config':
                return sys.argv[i + 1]
            else:
                name = sys.argv[i].split('--config')[1]
                if name[0] == '=':
                    name = name[1:]
                return name

    return name


def parse_known_args(parser, subparser=False):
    """Parse arguments from file and then override by the ones specified on the command line. Use
    *parser* for parsing and is *subparser* is True take into account that there is a value on the
    command line specifying the subparser.
    """
    if len(sys.argv) > 1:
        subparser_value = [sys.argv[1]] if subparser else []
        config_values = config_to_list(config_name=get_config_name())
        values = subparser_value + config_values + sys.argv[1:]
    else:
        values = ""
    args = parser.parse_known_args(values)[0]

    return args


def config_to_list(config_name=NAME):
    """Read arguments from config file and convert them to a list of keys and values as sys.argv
    does when they are specified on the command line. *config_name* is the file name of the config
    file.
    """
    result = []
    config = configparser.ConfigParser()
    if config.read([config_name]):
        for section in SECTIONS:
            for name, opts in SECTIONS[section].items():
                if config.has_option(section, name):
                    value = config.get(section, name)
                    if value is not '' and value != 'None':
                        action = SECTIONS[section][name].get('action', None)
                        if action == 'store_true':
                            # Only the key is on the command line for this action
                            if value == 'True':
                                result.append('--{}'.format(name))
                        else:
                            result.append('--{}={}'.format(name, value))

    return result


class Params(object):
    def __init__(self, sections=()):
        self.sections = sections + ('general', 'reading')

    def add_parser_args(self, parser):
        for section in self.sections:
            for name in sorted(SECTIONS[section]):
                opts = SECTIONS[section][name]
                parser.add_argument('--{}'.format(name), **opts)

    def add_arguments(self, parser):
        self.add_parser_args(parser)
        return parser

    def get_defaults(self):
        parser = argparse.ArgumentParser()
        self.add_arguments(parser)

        return parser.parse_args('')


class TomoParams(Params):
    def __init__(self, sections=()):
        sections = ('flat-correction', 'reconstruction', 'tomographic-reconstruction', 'fbp', 'dfi',
                    'ir', 'sart', 'sbtv') + sections
        super(TomoParams, self).__init__(sections=sections)


class LaminoParams(Params):
    def __init__(self):
        sections = ('flat-correction', 'reconstruction', 'laminographic-reconstruction')
        super(LaminoParams, self).__init__(sections=sections)


def write(config_file, args=None, sections=None):
    """Write *config_file* with values from *args* if they are specified, otherwise use the
    defaults. If *sections* are specified, write values from *args* only to those sections, use the
    defaults on the remaining ones.
    """
    cfg = configparser.ConfigParser()
    for section in SECTIONS:
        cfg.add_section(section)
        for name, opts in SECTIONS[section].items():
            if args and sections and section in sections and hasattr(args, name.replace('-', '_')):
                value = getattr(args, name.replace('-', '_'))
            else:
                value = opts['default'] if opts['default'] is not None else ''
            prefix = '# ' if value is '' else ''
            if name != 'config':
                cfg.set(section, prefix + name, value)

    with open(config_file, 'wb') as config_file:
        cfg.write(config_file)


def _str_to_bool(value):
    """Convert a string *value* into a boolean."""
    result = None
    if value == 'True':
        result = True
    elif value == 'False':
        result = False
    else:
        raise ValueError("'{}' not recognized, must be 'True' or 'False'".format(value))

    return result
