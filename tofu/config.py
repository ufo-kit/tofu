import re
import ConfigParser as configparser
from collections import defaultdict
from tofu.util import positive_int


NAME = "reco.conf"
TEMPLATE = """[general]
{disable}axis =
{disable}offset = 0.0
{disable}input = {input}
{disable}region = {region}
{disable}output = {output}

[reading]
{disable}y = 0
{disable}height =
{disable}y_step = 1
{disable}start = 0
{disable}end =
{disable}step = 1

## Reconstruct from projections instead of sinograms
{disable_fp}from_projections = {from_projections}
## Flat-field correction will not be performed if these are missing
#darks = path/to/darks
#flats = path/to/flats

[reconstruction]
{disable}axis = {axis}
{disable}angle = {angle}
# crop_width = 128
# method = 'fbp'        # or 'sart' or 'dfi'
# oversampling = 2

[lamino]
# tilt = 0.1            # Tilt angle
# tau = 10              # Pixel size in microns
# width = 2048          # Width of input
# height = 2048         # Height of input
# downsample = 2        # Downsampling factor
# bbox = 256 256 256    # Reconstruction box
# pad = 0 0             # Padding added around input
"""

SECTIONS = {
    'general': {
        'config': {
            'default': NAME,
            'type': str,
            'help': "File name of configuration",
            'metavar': 'FILE'
            },
        'enable_tracing': {
            'default': False,
            'help': "Enable tracing and store result in .PID.json",
            'action': 'store_true'
            },
        'input': {
            'default': '.',
            'type': str,
            'help': "Location with sinograms or projections",
            'metavar': 'PATH'
            },
        'output': {
            'default': '.',
            'type': str,
            'help': "Path to location or format-specified file path "
                    "for storing reconstructed slices",
            'metavar': 'PATH'
            },
        'width': {
            'default': None,
            'type': positive_int,
            'help': "Input width"
            },
        },
    'reading': {
        'y': {
            'type': positive_int,
            'default': 0,
            'help': 'Vertical coordinate from where to start reading the input image'
            },
        'height': {
            'default': None,
            'type': positive_int,
            'help': "Number of rows which will be read"
            },
        'y_step': {
            'type': positive_int,
            'default': 1,
            'help': "Read every \"step\" row from the input"
            },
        'start': {
            'type': positive_int,
            'default': 0,
            'help': 'Offset to the first read file'
            },
        'end': {
            'type': positive_int,
            'default': None,
            'help': 'The files will be read until \"end\" - 1 index'
            },
        'step': {
            'type': positive_int,
            'default': 1,
            'help': 'Read every \"step\" file',
            },
        },
    'reconstruction' : {
        'dry_run': {
            'default': False,
            'help': "Reconstruct without writing data",
            'action': 'store_true'
            },
        'angle': {
            'default': None,
            'type': float,
            'help': "Angle step between projections in radians"
            },
        'axis': {
            'default': None,
            'type': float,
            'help': "Axis position",
            },
        'offset': {
            'default': 0.0,
            'type': float,
            'help': "Angle offset of first projection in radians"
            },
        'method': {
            'default': 'fbp',
            'type': str,
            'help': "Reconstruction method",
            'choices': ['fbp', 'sart', 'dfi'],
            },
        },
    'fbp': {
        'crop_width': {
            'default': None,
            'type': positive_int,
            'help': "Width of final slice"
            },
        'from_projections': {
            'default': False,
            'help': "Reconstruct from projections instead of sinograms",
            'action': 'store_true'
            }
        },
    'dfi': {
        'oversampling': {
            'default': None,
            'type': positive_int,
            'help': "Oversample factor"
            }
        },
    'sart': {
        'max_iterations': {
            'default': 2,
            'type': int,
            'help': "Maximum number of iterations"
            },
        'relaxation_factor': {
            'default': 0.25,
            'type': float,
            'help': "Relaxation factor"
            },
        'num_angles': {
            'default': None,
            'type': positive_int,
            'help': "Sinogram height"
            },
        },
    'lamino': {
        'bbox': {
            'default': None,
            'type': int,
            'help': "Bounding box of reconstructed volume",
            'nargs': '+',
            'action': 'append'
            },
        'downsample': {
            'default': 1,
            'type': positive_int,
            'help': "Downsampling factor"
            },
        'pad': {
            'default': None,
            'type': int,
            'help': "Final padded size of input",
            'nargs': '+',
            'action': 'append'
            },
        'tau': {
            'default': None,
            'type': float,
            'help': "Pixel size in microns"
            },
        'tilt': {
            'default': None,
            'type': float,
            'help': "Tilt angle of sample in radians"
            },
        'include': {
            'default': '.',
            'type': str,
            'help': "Paths to search for plugins and kernel files",
            'nargs': '*',
            'metavar': 'PATH'
            },
        },
    'flat-correction' : {
        'darks': {
            'default': '',
            'type': str,
            'help': "Location with darks",
            'metavar': 'PATH'
            },
        'dark_scale': {
            'default': 1,
            'type': float,
            'help': "Scaling dark",
            },
        'reduction_mode': {
            'default': "Average",
            'type': str,
            'help': "Flat-field correction options: Average (darks) or median (flats)"
            },
        'fix_nan_and_inf': {
            'default': True,
            'help': "Fix nan and inf",
            'action': 'store_true'
            },
        'flats': {
            'default': '',
            'type': str,
            'help': "Location with flats",
            'metavar': 'PATH'
            },
        'flats2': {
            'default': '',
            'type': str,
            'help': "Location with flats 2 for interpolation correction",
            'metavar': 'PATH'
            },
        'absorptivity': {
            'action': 'store_true',
            'help': 'Do absorption correction'
            },
        },
    'sinos' : {
        'pass_size': {
            'type': positive_int,
            'default': 0,
            'help': 'Number of sinograms to process per pass'
            },
        },
    'gui' : {
        'enable_cropping': {
            'default': False,
            'help': "Enable cropping width",
            'action': 'store_true'
            },
        'show_2d': {
            'default': False,
            'help': "Show 2D slices with pyqtgraph",
            'action': 'store_true'
            },
        'show_3d': {
            'default': False,
            'help': "Show 3D slices with pyqtgraph",
            'action': 'store_true'
            },
        'last_dir': {
            'default': '.',
            'type': str,
            'help': "Path of the last used directory",
            'metavar': 'PATH'
            },
        'deg0': {
            'default': '.',
            'type': str,
            'help': "Location with 0 deg projection",
            'metavar': 'PATH'
            },
        'deg180': {
            'default': '.',
            'type': str,
            'help': "Location with 180 deg projection",
            'metavar': 'PATH'
            },
        'ffc_correction': {
            'default': False,
            'help': "Enable darks or flats correction",
            'action': 'store_true'
            },
        'num_flats': {
            'default': 0,
            'type': int,
            'help': "Number of flats for ffc correction."
            },
        }
    }


class DefaultConfigParser(configparser.ConfigParser):
    def value(self, section, option, default=None, target=None):
        try:
            v = self.get(section, option)
            if target and v:
                return target(v)
            return v

        except (configparser.NoOptionError, configparser.NoSectionError):
            return default


class Params(object):
    def __init__(self, sections=(), config_name=NAME):
        self._config = DefaultConfigParser()
        self._config.read([config_name])
        self._params = defaultdict(dict)
        self._sections = sections + ('general', 'reading')
        self.read_sections()

    @property
    def file_params(self):
        return {key: value for section in self._params
                for key, value in self._params[section].items()}

    def read_sections(self):
        for section in self._sections:
            for name, opts in SECTIONS[section].items():
                default = opts.get('default', None)
                vtype = opts.get('type', None)
                value = self._config.value(section, name, default, vtype)
                setattr(self, name, value)
                self._params[section][name] = value

    def add_parser_args(self, parser, sections):
        for section in sections:
            for name in sorted(SECTIONS[section]):
                opts = SECTIONS[section][name]
                parser.add_argument('--{}'.format(name), **opts)

    def add_arguments(self, parser):
        self.add_parser_args(parser, self._sections)
        return parser
        
    def update(self, args):
        for k, v in args.__dict__.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def write(self, config_name=NAME):
        with open(config_name, 'w') as f:
            for section, names in SECTIONS.items():
                f.write('[{}]\n'.format(section))
                for name in names:
                    if hasattr(self, name):
                        value = getattr(self, name)
                        if value is not None:
                            f.write('{} = {}\n'.format(name, value))


class TomoParams(Params):
    def __init__(self, sections=(), config_name=NAME):
        sections = ('flat-correction', 'reconstruction', 'fbp', 'dfi', 'sart') + sections
        super(TomoParams, self).__init__(sections=sections, config_name=config_name)

        self.method = self._config.value('general', 'method', 'fbp')
        self.from_projections = self._config.value('fbp', 'from_projections', False)
        self.crop_width = self._config.value('fbp', 'crop_width', target=int)
        self.oversampling = self._config.value('dfi', 'oversampling', target=int)
        self.axis = self._config.value('general', 'axis', target=float)


class LaminoParams(Params):
    def __init__(self):
        sections = ('flat-correction', 'reconstruction', 'lamino')
        super(LaminoParams, self).__init__(sections=sections)

        self.axis = self._config.value('general', 'axis')
        self.axis = [float(x) for x in self.axis.split(' ')] if self.axis else None

        self.tau = 0.3
        self.tilt = self._config.value('lamino', 'tilt')
        self.width = self._config.value('lamino', 'width')
        self.height = self._config.value('lamino', 'height')
        self.downsample = self._config.value('lamino', 'downsample', 1)

        self.bbox = self._config.value('lamino', 'bbox')
        self.bbox = [int(x) for x in self.bbox.split(' ')] if self.bbox else None

        self.pad = self._config.value('lamino', 'pad')
        self.pad = [int(x) for x in self.pad.split(' ')] if self.pad else None


def write(axis=0.0, angle=0.0, disable='#', input='path/to/input',
          region='y_step', output='path/to/output', from_projections=True):
    disable_fp = '#' if not from_projections else ''
    out = TEMPLATE.format(axis=axis, angle=angle, input=input, region=region,
                          output=output, from_projections=from_projections,
                          disable=disable, disable_fp=disable_fp)

    with open(NAME, 'w') as f:
        f.write(out)
