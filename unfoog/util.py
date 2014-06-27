"""Various utility functions."""


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
