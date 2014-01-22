import ConfigParser as configparser


NAME = 'reco.conf'
TEMPLATE = """[general]
{disable}axis = {axis}
{disable}angle = {angle}
{disable}input = {input}
{disable}output = {output}

## Reconstruct from projections instead of sinograms
{disable_fp}from_projections = {from_projections}
## Flat-field correction will not be performed if these are missing
#darks = path/to/darks
#flats = path/to/flats

[fbp]
# crop_width = 128

[dfi]
# oversampling = 2
"""

class DefaultConfigParser(configparser.ConfigParser):
    def value(self, section, option, default=None, target=None):
        try:
            v = self.get(section, option)
            if target:
                return target(v)
            return v

        except (configparser.NoOptionError, configparser.NoSectionError):
            return default


class RecoParams(object):
    def __init__(self):
        self._config = DefaultConfigParser()
        self._config.read([NAME])

        self.include = self._config.value('general', 'include')
        self.input = self._config.value('general', 'input', '.')
        self.output = self._config.value('general', 'output', '.')
        self.darks = self._config.value('general', 'darks')
        self.flats = self._config.value('general', 'flats')
        self.angle = self._config.value('general', 'angle', target=float)
        self.offset = self._config.value('general', 'angle_offset', 0)
        self.dry_run = False
        self.enable_tracing = False

    def add_arguments(self, parser):
        parser.add_argument('-i', '--input', type=str,
                            default=self.input, metavar='PATH',
                            help="Location with sinograms or projections")
        parser.add_argument('-o', '--output', type=str,
                            default=self.output, metavar='PATH',
                            help="Path to location or format-specified file path "
                            "for storing reconstructed slices")
        parser.add_argument('--include', type=str, nargs='*', default=None, metavar='PATH',
                            help="Paths to search for plugins and kernel files")
        parser.add_argument('--flats', type=str,
                            default=self.flats, metavar='PATH',
                            help="Location with flats")
        parser.add_argument('--darks', type=str,
                            default=self.darks, metavar='PATH',
                            help="Location with darks")
        parser.add_argument('--angle', type=float,
                            default=self.angle,
                            help="Angle step between projections in radians")
        parser.add_argument('--offset', type=float,
                            default=self.offset,
                            help="Angle offset of first projection in radians")
        parser.add_argument('--enable-tracing', action='store_true', default=False,
                            help="Enable tracing and store result in .PID.json")
        parser.add_argument('--dry-run', action='store_true', default=False,
                            help="Reconstruct without writing data")
        return parser

    def update(self, args):
        for k, v in args.__dict__.items():
            if hasattr(self, k):
                setattr(self, k, v)


class TomoParams(RecoParams):
    def __init__(self):
        super(TomoParams, self).__init__()
        self.method = self._config.value('general', 'method', 'fbp')
        self.from_projections = self._config.value('fbp', 'from_projections', False)
        self.crop_width = self._config.value('fbp', 'crop_width', target=int)
        self.oversampling = self._config.value('dfi', 'oversampling', target=int)
        self.axis = self._config.value('general', 'axis', target=float)

    def add_arguments(self, parser):
        parser = super(TomoParams, self).add_arguments(parser)

        parser.add_argument('--method', choices=['fbp', 'sart', 'dfi'],
                            default=self.method,
                            help="Reconstruction method")
        parser.add_argument('--axis', type=float,
                            default=self.axis,
                            help="Axis position")
        parser.add_argument('--crop-width', type=int,
                            default=self.crop_width,
                            help="Width of final slice")
        parser.add_argument('--oversampling', type=int,
                            default=self.oversampling,
                            help="Oversample factor")
        parser.add_argument('--server', type=str, nargs='*', default=[], metavar='ADDR',
                            help="ZeroMQ addresses of machines on which `ufod' is running")
        parser.add_argument('--from-projections', action='store_true',
                            default=self.from_projections,
                            help="Reconstruct from projections instead of sinograms")
        return parser


class LaminoParams(RecoParams):
    def __init__(self):
        super(LaminoParams, self).__init__()
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

        parser.add_argument('--tilt', type=float,
                            default=self._config.value('lamino', 'tilt'),
                            help="Tilt angle of sample in radians")
        parser.add_argument('--axis', nargs='+', action='append',
                            default=self.axis,
                            help="Axis")
        parser.add_argument('--bbox', nargs='+', action='append',
                            default=self.bbox,
                            help="Bounding box of reconstructed volume")
        parser.add_argument('--pad', nargs='+', action='append',
                            default=self.pad,
                            help="Final padded size of input")
        parser.add_argument('--width', type=int,
                            default=self.width,
                            help="Width of the input projection")
        parser.add_argument('--height', type=int,
                            default=self.height,
                            help="Height of the input projection")
        parser.add_argument('--downsample', type=int,
                            default=self.downsample,
                            help="Downsampling factor")

        return parser


def write(axis=0.0, angle=0.0, disable='#',
          input='path/to/input', output='path/to/output',
          from_projections=True):
    disable_fp = '#' if not from_projections else ''
    out = TEMPLATE.format(axis=axis, angle=angle, input=input,
                          output=output, from_projections=from_projections,
                          disable=disable, disable_fp=disable_fp)

    with open(NAME, 'w') as f:
        f.write(out)
