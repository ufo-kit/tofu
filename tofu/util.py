"""Various utility functions."""
import argparse
import glob
import logging
import math
import os


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

    return check


def tupleize(num_items=None, conv=float):
    """Convert comma-separated string values to a *num-items*-tuple of values converted with
    *conv*.
    """
    def split_values(value):
        """Convert comma-separated string *value* to a tuple of numbers."""
        try:
            result = tuple([conv(x) for x in value.split(',')])
        except:
            raise argparse.ArgumentTypeError('Expect comma-separated tuple')

        if num_items and len(result) != num_items:
            raise argparse.ArgumentTypeError('Expected {} items'.format(num_items))

        return result

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
            return tif.asarray()
    elif '.edf' in filename.lower():
        import fabio
        edf = fabio.edfimage.edfimage()
        edf.read(filename)
        return edf.data
    else:
        raise ValueError('Unsupported image format')


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
            image = read_image(filename)

            # Now set the width and height if not specified
            width = width or image.shape[-1]
            height = height or image.shape[-2]
        except:
            LOG.info("Couldn't determine image dimensions from '{}'".format(filename))

    if store:
        if not args.width:
            args.width = width
        if not args.height:
            args.height = height - args.y

    return (width, height)


def setup_padding(pad, crop, width, height, mode):
    padding = next_power_of_two(width + 32) - width
    pad.props.width = width + padding
    pad.props.height = height
    pad.props.x = padding / 2
    pad.props.y = 0
    pad.props.addressing_mode = mode
    LOG.debug('Padded width: {}'.format(width + padding))
    LOG.debug('Padding mode: {}'.format(mode))

    # crop to original width after filtering
    crop.props.width = width
    crop.props.height = height
    crop.props.x = padding / 2
    crop.props.y = 0


def make_region(n):
    """Make region in such a way that in case of odd *n* it is centered around 0."""
    return (-(n / 2), n / 2 + n % 2, 1)


def get_reconstructed_cube_shape(x_region, y_region, z_region):
    """Get the shape of the reconstructed cube as (slice width, slice height, num slices)."""
    import numpy as np
    z_start, z_stop, z_step = z_region
    y_start, y_stop, y_step = y_region
    x_start, x_stop, x_step = x_region

    num_slices = len(np.arange(z_start, z_stop, z_step))
    slice_height = len(range(y_start, y_stop, y_step))
    slice_width = len(range(x_start, x_stop, x_step))

    return slice_width, slice_height, num_slices


def get_reconstruction_regions(params):
    """Compute reconstruction regions along all three axes.."""
    width, height = determine_shape(params)
    if getattr(params, 'transpose_input', False):
        # In case down the pipeline there is a transpose task
        tmp = width
        width = height
        height = tmp

    if params.x_region[1] == -1:
        x_region = make_region(width)
    else:
        x_region = params.x_region
    if params.y_region[1] == -1:
        y_region = make_region(width)
    else:
        y_region = params.y_region
    if params.region[1] == -1:
        region = make_region(height)
    else:
        region = params.region
    LOG.info('X region: {}'.format(x_region))
    LOG.info('Y region: {}'.format(y_region))
    LOG.info('Parameter region: {}'.format(region))

    return x_region, y_region, region
