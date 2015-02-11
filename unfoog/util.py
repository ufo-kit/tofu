"""Various utility functions."""
import argparse
import glob
import logging
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


def set_reader(reader, input_prefix, region=None):
    """Set up a *reader* to read from *input_prefix* and use *region*."""
    reader.props.path = input_prefix


def check_input(input_prefix, region):
    """Check if there are enough file from *input_prefix* to satisfy *region*."""
    total = len(get_filenames(input_prefix))
    region = range_from(region)
    if total - region[0] < len(range(*region)):
        raise ValueError('Not enough files to satisfy region')


def positive_int(value):
    """Convert *value* to an integer and make sure it is positive."""
    result = int(value)
    if result < 0:
        raise argparse.ArgumentTypeError('Only positive integers are allowed')

    return result


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
