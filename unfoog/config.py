import re
import ConfigParser as configparser
from collections import defaultdict
from unfoog.util import positive_int


NAME = "reco.conf"
TEMPLATE = """[general]
{disable}axis =
{disable}offset = 0.0
{disable}input = {input}
{disable}region = {region}
{disable}output = {output}

## Reconstruct from projections instead of sinograms
{disable_fp}from_projections = {from_projections}
## Flat-field correction will not be performed if these are missing
#darks = path/to/darks
#flats = path/to/flats

[tomo]
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
        'config': {
            'default': NAME,
            'type': str,
            'help': "File name of configuration",
            'metavar': 'FILE'
            },
        'darks': {
            'default': '.',
            'type': str,
            'help': "Location with darks",
            'metavar': 'PATH'
            },
        'dark_scale': {
            'default': 1,
            'type': float,
            'help': "Scaling dark",
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
        'dry_run': {
            'default': False,
            'help': "Reconstruct without writing data",
            'action': 'store_true'
            },
        'enable_tracing': {
            'default': False,
            'help': "Enable tracing and store result in .PID.json",
            'action': 'store_true'
            },
        'ffc_correction': {
            'default': False,
            'help': "Enable darks or flats correction",
            'action': 'store_true'
            },
        'ffc_options': {
            'default': "Average",
            'type': str,
            'help': "Flat-field correction options: Average (darks) or median (flats)"
            },
        'flats': {
            'default': '.',
            'type': str,
            'help': "Location with flats",
            'metavar': 'PATH'
            },
        'flats2': {
            'default': '.',
            'type': str,
            'help': "Location with flats 2 for interpolation correction",
            'metavar': 'PATH'
            },
        'include': {
            'default': '.',
            'type': str,
            'help': "Paths to search for plugins and kernel files",
            'nargs': '*',
            'metavar': 'PATH'
            },
        'input': {
            'default': '.',
            'type': str,
            'help': "Location with sinograms or projections",
            'metavar': 'PATH'
            },
        'ip_correction': {
            'default': False,
            'help': "Enable interpolation correction",
            'action': 'store_true'
            },
        'last_dir': {
            'default': '.',
            'type': str,
            'help': "Path of the last used directory",
            'metavar': 'PATH'
            },
        'method': {
            'default': 'fbp',
            'type': str,
            'help': "Reconstruction method",
            'choices': ['fbp', 'sart', 'dfi']
            },
        'num_flats': {
            'default': 0,
            'type': int,
            'help': "Number of flats for ffc correction."
            },
        'offset': {
            'default': 0.0,
            'type': float,
            'help': "Angle offset of first projection in radians"
            },
        'output': {
            'default': '.',
            'type': str,
            'help': "Path to location or format-specified file path "
                    "for storing reconstructed slices",
            'metavar': 'PATH'
            },
        'use_gpu': {
            'default': False,
            'help': "Use GPU device exclusively",
            'action': 'store_true'
            },
        'y_step': {
            'default': 1,
            'type': int,
            'help': "Read every \"step\" row",
            },
        },
    'fbp': {
        'crop_width': {
            'default': None,
            'type': positive_int,
            'help': "Width of final slice"
            },
        'enable_cropping': {
            'default': False,
            'help': "Enable cropping width",
            'action': 'store_true'
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
            'default': 0,
            'type': int,
            'help': "Maximum number of iterations"
            },
        'relaxation_factor': {
            'default': 0.0,
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
        'height': {
            'default': None,
            'type': positive_int,
            'help': "Height of the input projection"  
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
        'width': {
            'default': None,
            'type': positive_int,
            'help': "Width of the input projection"
            }
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


class RecoParams(object):
    def __init__(self, config_name=NAME):
        self._config = DefaultConfigParser()
        self._config.read([config_name])
        self._params = defaultdict(dict)

        self.read_sections(['general'])

        self.include = self._config.value('general', 'include')
        self.input = self._config.value('general', 'input', '.')
        self.output = self._config.value('general', 'output', '.')
        self.angle = self._config.value('general', 'angle', target=float)
        self.angle_offset = self._config.value('general', 'angle_offset', 0)
        self.absorptivity = self._config.value('general', 'absorptivity')
        self.dry_run = False
        self.enable_tracing = False

    def read_sections(self, sections):
        for section in sections:
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
        self.add_parser_args(parser, ['general'])
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


class TomoParams(RecoParams):
    def __init__(self, config_name=NAME):
        super(TomoParams, self).__init__(config_name)
        self.read_sections(['fbp', 'dfi', 'sart'])

        self.method = self._config.value('general', 'method', 'fbp')
        self.from_projections = self._config.value('fbp', 'from_projections', False)
        self.crop_width = self._config.value('fbp', 'crop_width', target=int)
        self.oversampling = self._config.value('dfi', 'oversampling', target=int)
        self.axis = self._config.value('general', 'axis', target=float)

    def add_arguments(self, parser):
        parser = super(TomoParams, self).add_arguments(parser)
        self.add_parser_args(parser, ['fbp', 'dfi'])
        return parser


class LaminoParams(RecoParams):
    def __init__(self):
        super(LaminoParams, self).__init__()
        self.read_sections(['lamino'])

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

    def add_arguments(self, parser):
        parser = super(LaminoParams, self).add_arguments(parser)
        self.add_parser_args(parser, ['lamino'])

        return parser


def write(axis=0.0, angle=0.0, disable='#', input='path/to/input',
          region='y_step', output='path/to/output', from_projections=True):
    disable_fp = '#' if not from_projections else ''
    out = TEMPLATE.format(axis=axis, angle=angle, input=input, region=region,
                          output=output, from_projections=from_projections,
                          disable=disable, disable_fp=disable_fp)

    with open(NAME, 'w') as f:
        f.write(out)
