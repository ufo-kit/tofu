"""Various utility functions."""
import argparse
import glob
import logging
import math
import os


def range_from(s):
    """
    Split *s* separated by ':' into int triple, filling missing values with 1s.
    """
    def check(region):
        if region[0] >= region[1]:
            raise ValueError("'From' must be less than 'to'")

    lst = [int(x) for x in s.split(':')]

    if len(lst) == 1:
        frm = lst[0]
        return (frm, frm + 1, 1)

    if len(lst) == 2:
        check(lst)
        return (lst[0], lst[1], 1)

    if len(lst) == 3:
        check(lst)
        return (lst[0], lst[1], lst[2])

    raise ValueError("Cannot parse {}".format(s))


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

    return glob.glob(path)


def config_log_handler(handler, log, msg_format=None):
    """Config logging *handler* to handle *log* and use *msg_format*.
    """
    if not msg_format:
        msg_format = '[%(asctime)s] - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(msg_format)
    handler.setFormatter(formatter)
    log.addHandler(handler)


def log_dictionary(dictionary, log, level=logging.INFO):
    """Log all key:value pairs in *dictionary* to *log*. *level* specifies logging level."""
    for k, v in dictionary.iteritems():
        log.log(level, '{}: {}'.format(k, v))


def next_power_of_two(number):
    """Compute the next power of two of the *number*."""
    return 2 ** int(math.ceil(math.log(number, 2)))
