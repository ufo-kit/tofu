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
                node.set_property(name, getattr(args, name))


def positive_int(value):
    """Convert *value* to an integer and make sure it is positive."""
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError('Only positive integers are allowed')

    return result


def tupleize(num_items, conv=None):
    """Convert comma-separated string values to a *num-items*-tuple of values converted with
    *conv*.
    """
    def split_values(value):
        """Convert comma-separated string *value* to a tuple of numbers."""
        try:
            result = tuple([conv(x) for x in value.split(',')])
        except:
            raise argparse.ArgumentTypeError('Expect comma-separated tuple')

        if len(result) != num_items:
            raise argparse.ArgumentTypeError('Expected {} items'.format(num_items))

        return result

    return split_values


def get_filenames(path):
    """Get all filenams from *path*, which could be a directory or a pattern
    for matching files in a directory.
    """
    if os.path.isdir(path):
        path = os.path.join(path, '*')

    return sorted(glob.glob(path))


def next_power_of_two(number):
    """Compute the next power of two of the *number*."""
    return 2 ** int(math.ceil(math.log(number, 2)))


def read_image(filename):
    """Read image from file *filename*."""
    if filename.lower().endswith('.tif'):
        from tofu.tifffile import TiffFile
        import numpy as np
        with TiffFile(filename) as tif:
            image = np.copy(tif.asarray())
    elif '.edf' in filename.lower():
        import fabio
        edf = fabio.edfimage.edfimage()
        edf.read(filename)
        image = edf.data
    else:
        raise ValueError('Unsupported image format')

    return image


def determine_shape(args):
    """Determine input shape from *args* which means either width and height are specified in
    args or try to read the input and determine the shape from it. Return a tuple (width, height).
    """
    width = args.width
    height = args.height

    if not (width and height):
        filename = get_filenames(args.input)[0]
        try:
            image = read_image(filename)
            # Now set the width and height but only if they were not specified
            if not width:
                width = image.shape[1]
            if not height:
                height = image.shape[0]
        except:
            LOG.info("Couldn't determine image dimensions from '{}'".format(filename))

    return (width, height)
