"""Various utility functions."""
import glob


def range_from(s):
    """
    Split *s* separated by ':' into int triple, filling missing values with 1s.
    """
    lst = [int(x) for x in s.split(':')]

    if len(lst) == 1:
        frm = lst[0]
        return (frm, frm + 1, 1)

    if len(lst) == 2:
        return (lst[0], lst[1], 1)

    if len(lst) == 3:
        return (lst[0], lst[1], lst[2])

    raise ValueError("Cannot parse {}".format(s))


def set_reader(reader, input_prefix, region=None):
    """Set up a *reader* to read from *input_prefix* and use *region*."""
    reader.props.path = input_prefix
    if region:
        region = range_from(region)
        reader.props.start = region[0]
        reader.props.end = region[1]
        reader.props.step = region[2]


def check_input(input_prefix, region):
    """Check if there are enough file from *input_prefix* to satisfy *region*."""
    total = len(glob.glob(input_prefix))
    region = range_from(region)
    if total - region[0] < len(range(*region)):
        raise ValueError('Not enough files to satisfy region')
