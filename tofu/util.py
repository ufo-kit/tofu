"""Various utility functions."""
import argparse
import glob
import logging
import math
import os
from collections import OrderedDict


LOG = logging.getLogger(__name__)


def range_list(value):
    """
    Split *value* separated by ':' into int triple, filling missing values with 1s.
    """
    def check(region):
        if region[0] >= region[1]:
            raise argparse.ArgumentTypeError("{} must be less than {}".format(region[0], region[1]))

    lst = [int(x) for x in value.split(':')]

    if len(lst) == 1:
        frm = lst[0]
        return (frm, frm + 1, 1)

    if len(lst) == 2:
        check(lst)
        return (lst[0], lst[1], 1)

    if len(lst) == 3:
        check(lst)
        return (lst[0], lst[1], lst[2])

    raise argparse.ArgumentTypeError("Cannot parse {}".format(value))


def make_subargs(args, subargs):
    """Return an argparse.Namespace consisting of arguments from *args* which are listed in the
    *subargs* list."""
    namespace = argparse.Namespace()
    for subarg in subargs:
        setattr(namespace, subarg, getattr(args, subarg))

    return namespace


def set_node_props(node, args):
    """Set up *node*'s properties to *args* which is a dictionary of values."""
    for name in dir(node.props):
        if not name.startswith('_') and hasattr(args, name):
            value = getattr(args, name)
            if value is not None:
                LOG.debug("Setting {}:{} to {}".format(node.get_plugin_name(), name, value))
                node.set_property(name, getattr(args, name))


def get_filenames(path):
    """
    Get all filenams from *path*, which could be a directory or a pattern for
    matching files in a directory.
    """
    return sorted(glob.glob(os.path.join(path, '*') if os.path.isdir(path) else path))


def setup_read_task(task, path, args):
    """Set up *task* and take care of handling file types correctly."""
    task.props.path = path

    fnames = get_filenames(path)

    if fnames and fnames[0].endswith('.raw'):
        if not args.width or not args.height:
            raise RuntimeError("Raw files require --width, --height and --bitdepth arguments.")

        task.props.raw_width = args.width
        task.props.raw_height = args.height
        task.props.raw_bitdepth = args.bitdepth


def restrict_value(limits, dtype=float):
    """Convert value to *dtype* and make sure it is within *limits* (included) specified as tuple
    (min, max). If one of the tuple values is None it is ignored."""
    def check(value):
        result = dtype(value)
        if limits[0] is not None and result < limits[0]:
            raise argparse.ArgumentTypeError('Value cannot be less than {}'.format(limits[0]))
        if limits[1] is not None and result > limits[1]:
            raise argparse.ArgumentTypeError('Value cannot be greater than {}'.format(limits[1]))

        return result

    check.dtype = dtype
    check.limits = limits

    return check


def convert_filesize(value):
    multiplier = 1
    conv = OrderedDict((('k', 2 ** 10),
                        ('m', 2 ** 20),
                        ('g', 2 ** 30),
                        ('t', 2 ** 40)))

    if not value[-1].isdigit():
        if value[-1] not in list(conv.keys()):
            raise argparse.ArgumentTypeError('--output-bytes-per-file must either be a ' +
                                             'number or end with {} '.format(list(conv.keys())) +
                                             'to indicate kilo, mega, giga or terabytes')
        multiplier = conv[value[-1]]
        value = value[:-1]

    value = int(float(value) * multiplier)
    if value < 0:
        raise argparse.ArgumentTypeError('--output-bytes-per-file cannot be less than zero')

    return value


def tupleize(num_items=None, conv=float, dtype=tuple):
    """Convert comma-separated string values to a *num-items*-tuple of values converted with
    *conv*.
    """
    def split_values(value):
        """Convert comma-separated string *value* to a tuple of numbers."""
        try:
            result = dtype([conv(x) for x in value.split(',')])
        except:
            raise argparse.ArgumentTypeError('Expect comma-separated tuple')

        if num_items and len(result) != num_items:
            raise argparse.ArgumentTypeError('Expected {} items'.format(num_items))

        return result

    split_values.dtype = conv

    return split_values


def next_power_of_two(number):
    """Compute the next power of two of the *number*."""
    return 2 ** int(math.ceil(math.log(number, 2)))


def read_image(filename):
    """Read image from file *filename*."""
    if filename.lower().endswith('.tif') or filename.lower().endswith('.tiff'):
        from tifffile import TiffFile
        import numpy as np
        with TiffFile(filename) as tif:
            return tif.asarray(out='memmap')
    elif '.edf' in filename.lower():
        import fabio
        edf = fabio.edfimage.edfimage()
        edf.read(filename)
        return edf.data
    else:
        raise ValueError('Unsupported image format')


def get_image_shape(filename):
    """Determine image shape (numpy order) from file *filename*."""
    if filename.lower().endswith('.tif') or filename.lower().endswith('.tiff'):
        from tifffile import TiffFile
        with TiffFile(filename) as tif:
            page = tif.pages[0]
            shape = (page.imagelength, page.imagewidth)
            if len(tif.pages) > 1:
                shape = (len(tif.pages),) + shape
    else:
        # fabio doesn't seem to be able to read the shape without reading the data
        shape = read_image(filename).shape

    return shape


def get_first_filename(path):
    """Returns the first valid image filename in *path*."""
    if not path:
        raise RuntimeError("Path to sinograms or projections not set.")

    filenames = get_filenames(path)

    if not filenames:
        raise RuntimeError("No files found in `{}'".format(path))

    return filenames[0]


def determine_shape(args, path=None, store=False):
    """Determine input shape from *args* which means either width and height are specified in args
    or try to read the *path* and determine the shape from it. The default path is args.projections,
    which is the typical place to find the input. If *store* is True, assign the determined values
    if they aren't already present in *args*. Return a tuple (width, height).
    """
    width = args.width
    height = args.height

    if not (width and height):
        filename = get_first_filename(path or args.projections)

        try:
            shape = get_image_shape(filename)

            # Now set the width and height if not specified
            width = width or shape[-1]
            height = height or shape[-2]
        except:
            LOG.info("Couldn't determine image dimensions from '{}'".format(filename))

    if store:
        if not args.width:
            args.width = width
        if not args.height:
            args.height = height - args.y

    return (width, height)


def get_filtering_padding(width):
    """Get the number of horizontal padded pixels in order to avoid convolution artifacts."""
    return next_power_of_two(2 * width) - width


def setup_padding(pad, width, height, mode, crop=None, pad_width=0, pad_height=0):
    if not pad_width:
        # Default is horizontal padding only
        pad_width = get_filtering_padding(width)
    pad.props.width = width + pad_width
    pad.props.height = height + pad_height
    pad.props.x = pad_width // 2
    pad.props.y = pad_height // 2
    pad.props.addressing_mode = mode
    LOG.debug('Padded size: ({}, {})'.format(width + pad_width, height + pad_height))
    LOG.debug('Padding mode: {}'.format(mode))

    if crop:
        # crop to original width after filtering
        crop.props.width = width
        crop.props.height = height
        crop.props.x = pad_width // 2
        crop.props.y = pad_height // 2

    return (pad_width, pad_height)


def make_region(n, dtype=int):
    """Make region in such a way that in case of odd *n* it is centered around 0. Use *dtype* as
    data type.
    """
    return (-dtype(n / 2), dtype(n / 2 + n % 2), dtype(1))


def get_reconstructed_cube_shape(x_region, y_region, z_region):
    """Get the shape of the reconstructed cube as (slice width, slice height, num slices)."""
    import numpy as np
    z_start, z_stop, z_step = z_region
    y_start, y_stop, y_step = y_region
    x_start, x_stop, x_step = x_region

    num_slices = len(np.arange(z_start, z_stop, z_step))
    slice_height = len(np.arange(y_start, y_stop, y_step))
    slice_width = len(np.arange(x_start, x_stop, x_step))

    return slice_width, slice_height, num_slices


def get_reconstruction_regions(params, store=False, dtype=int):
    """Compute reconstruction regions along all three axes, use *dtype* for as data type for x and y
    regions, z region is always float.
    """
    width, height = determine_shape(params)
    if getattr(params, 'transpose_input', False):
        # In case down the pipeline there is a transpose task
        tmp = width
        width = height
        height = tmp

    if params.x_region[1] == -1:
        x_region = make_region(width, dtype=dtype)
    else:
        x_region = params.x_region
    if params.y_region[1] == -1:
        y_region = make_region(width, dtype=dtype)
    else:
        y_region = params.y_region
    if params.region[1] == -1:
        region = make_region(height, dtype=float)
    else:
        region = params.region
    LOG.info('X region: {}'.format(x_region))
    LOG.info('Y region: {}'.format(y_region))
    LOG.info('Parameter region: {}'.format(region))

    if store:
        params.x_region = x_region
        params.y_region = y_region
        params.region = region

    return x_region, y_region, region


def get_scarray_value(scarray, index):
    if len(scarray) == 1:
        return scarray[0]

    return scarray[index]


class Vector(object):

    """A vector based on axis-angle representation."""

    def __init__(self, x_angle=0, y_angle=0, z_angle=0, position=None):
        import numpy as np
        self.position = np.array(position, dtype=np.float) if position is not None else None
        self.x_angle = x_angle
        self.y_angle = y_angle
        self.z_angle = z_angle

    def __repr__(self):
        return 'Vector(position={}, angles=({}, {}, {}))'.format(self.position,
                                                                 self.x_angle,
                                                                 self.y_angle,
                                                                 self.z_angle)

    def __str__(self):
        return repr(self)
