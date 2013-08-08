# -*- coding: utf-8 -*-

"""
pkgconfig is a Python module to interface with the pkg-config command line
tool.

It can be used to 

- check if a package exists

    >>> pkgconfig.exists('glib-2.0')
    True

- check if a package meets certain version requirements

    >>> pkgconfig.installed('glib-2.0', '< 2.26')
    False

- query CFLAGS and LDFLAGS

    >>> pkgconfig.cflags('glib-2.0')
    '-I/usr/include/glib-2.0 -I/usr/lib/glib-2.0/include'

    >>> pkgconfig.libs('glib-2.0')
    '-lglib-2.0'
"""

import subprocess
import re


def _compare_versions(v1, v2):
    """
    Compare two version strings.

    The implementation is taken from the top answer at
    http://stackoverflow.com/a/1714190/997768.
    """
    def normalize(v):
        return [int(x) for x in re.sub(r'(\.0+)*$', '', v).split(".")]

    return cmp(normalize(v1), normalize(v2))


def _split_version_specifier(spec):
    """Splits version specifiers in the form ">= 0.1.2" into ('0.1.2', '>=')"""
    m = re.search(r'([<>=]?=?)?\s*((\d*\.)*\d*)', spec)
    return m.group(2), m.group(1)


def _query(package, option):
    cmd = 'pkg-config {0} {1}'.format(option, package).split()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, err = proc.communicate()
    return out.rstrip()


def exists(package):
    """Return True if package information is available."""
    try:
        cmd = 'pkg-config --exists {0}'.format(package).split()
        return subprocess.call(cmd) == 0
    except OSError:
        raise EnvironmentError("pkg-config not installed")


def cflags(package):
    """Return the CFLAGS string returned by pkg-config."""
    return _query(package, '--cflags')


def libs(package):
    """Return the LDFLAGS string returned by pkg-config."""
    return _query(package, '--libs')


def installed(package, version):
    """
    Check if the package meets the required version.

    The version specifier consists of an optional comparator (one of =, ==, >,
    <, >=, <=) and an arbitrarily long version number separated by dots. The
    should be as you would expect, e.g. for an installed version '0.1.2' of
    package 'foo':

    >>> installed('foo', '==0.1.2')
    True
    >>> installed('foo', '<0.1')
    False
    >>> installed('foo', '>= 0.0.4')
    True
    """
    if not exists(package):
        return False

    number, comparator = _split_version_specifier(version)
    modversion = _query(package, '--modversion')

    try:
        result = _compare_versions(modversion, number)
    except ValueError:
        msg = "{0} is not a correct version specifier".format(version)
        raise ValueError(msg)

    comparison_table = {
        '>': result > 0,
        '>=': result >= 0,
        '': result == 0,
        '=': result == 0,
        '==': result == 0,
        '<=': result <= 0,
        '<': result < 0
    }

    return comparison_table[comparator]
