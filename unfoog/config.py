import re
import ConfigParser as configparser


NAME = 'reco.conf'
TEMPLATE = """[general]
{disable}axis =
{disable}offset = 0.0
{disable}input = {input}
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
# width = 2048          # Width of input
# height = 2048         # Height of input
# downsample = 2        # Downsampling factor
# bbox = 256 256 256    # Reconstruction box
# pad = 0 0             # Padding added around input
"""


class DefaultConfigParser(configparser.ConfigParser):
    def value(self, section, option):
        try:
            return self.get(section, option)
        except (configparser.NoOptionError, configparser.NoSectionError):
            return None


class RecoParams(object):
    def __init__(self):
        self.types = {}

    def add_arguments(self, parser):
        self._add_argument(parser, '--config', type=str,
                           default=NAME, metavar='FILE',
                           help="File name of configuration")
        self._add_argument(parser, '-i', '--input', type=str,
                           default='.', metavar='PATH',
                           help="Location with sinograms or projections")
        self._add_argument(parser, '-o', '--output', type=str,
                           default='.', metavar='PATH',
                           help="Path to location or format-specified file path "
                           "for storing reconstructed slices")
        self._add_argument(parser, '--include', type=str, nargs='*', default=None, metavar='PATH',
                           help="Paths to search for plugins and kernel files")
        self._add_argument(parser, '--flats', type=str,
                           default=None, metavar='PATH',
                           help="Location with flats")
        self._add_argument(parser, '--darks', type=str,
                           default=None, metavar='PATH',
                           help="Location with darks")
        self._add_argument(parser, '--angle', type=float,
                           default=None,
                           help="Angle step between projections in radians")
        self._add_argument(parser, '--offset', type=float,
                           default=0,
                           help="Angle offset of first projection in radians")
        self._add_argument(parser, '--enable-tracing', action='store_true', default=False,
                           help="Enable tracing and store result in .PID.json")
        self._add_argument(parser, '--dry-run', action='store_true', default=False,
                           help="Reconstruct without writing data")
        self._add_argument(parser, '--from-projections', action='store_true',
                           default=False,
                           help="Reconstruct from projections instead of sinograms")
        return parser

    def update(self, args):
        config = DefaultConfigParser()
        config.read(args.config)

        for k, v in args.__dict__.items():
            setattr(self, k, v)

        self._override(args, config, 'general')

        return config

    def _add_argument(self, parser, *args, **kwargs):
        arg = parser.add_argument(*args, **kwargs)
        self.types[arg.dest] = arg.type

    def _override(self, args, config, section):
        for k, v in args.__dict__.items():
            override = config.value(section, k)

            if override:
                vtype = self.types.get(k, None)

                if vtype:
                    setattr(self, k, vtype(override))
                else:
                    setattr(self, k, override)


class TomoParams(RecoParams):
    def __init__(self):
        super(TomoParams, self).__init__()

    def add_arguments(self, parser):
        parser = super(TomoParams, self).add_arguments(parser)

        self._add_argument(parser, '--method', choices=['fbp', 'sart', 'dfi'],
                           default='fbp',
                           help="Reconstruction method")
        self._add_argument(parser, '--axis', type=float,
                           default=None,
                           help="Axis position")
        self._add_argument(parser, '--crop-width', type=int,
                           default=None,
                           help="Width of final slice")
        self._add_argument(parser, '--oversampling', type=int, default=None,
                           help="Oversample factor")
        return parser

    def update(self, args):
        config = super(TomoParams, self).update(args)
        self._override(args, config, 'tomo')


class LaminoParams(RecoParams):
    def __init__(self):
        super(LaminoParams, self).__init__()

    def add_arguments(self, parser):
        parser = super(LaminoParams, self).add_arguments(parser)

        parser.add_argument('--tilt', type=float,
                            default=None,
                            help="Tilt angle of sample in radians")
        parser.add_argument('--axis', nargs='+', action='append',
                            default=None,
                            help="Axis")
        parser.add_argument('--bbox', nargs='+', action='append',
                            default=None,
                            help="Bounding box of reconstructed volume")
        parser.add_argument('--pad', nargs='+', action='append',
                            default=None,
                            help="Final padded size of input")
        parser.add_argument('--width', type=int,
                            default=None,
                            help="Width of the input projection")
        parser.add_argument('--height', type=int,
                            default=None,
                            help="Height of the input projection")
        parser.add_argument('--downsample', type=int,
                            default=1,
                            help="Downsampling factor")

        return parser

    def update(self, args):
        config = super(LaminoParams, self).update(args)
        self._override(args, config, 'lamino')


def write(axis=0.0, angle=0.0, disable='#',
          input='path/to/input', output='path/to/output',
          from_projections=True):
    disable_fp = '#' if not from_projections else ''
    out = TEMPLATE.format(axis=axis, angle=angle, input=input,
                          output=output, from_projections=from_projections,
                          disable=disable, disable_fp=disable_fp)

    with open(NAME, 'w') as f:
        f.write(out)
