## About

This repository contains data processing scripts to be used with the UFO
framework. At the moment they are targeted at high-performance reconstruction of
tomographic data sets.


## Installation

Run

    python setup.py install

in a prepared virtualenv or as root for system-wide installation.


## Usage

### Reconstruction

To do a reconstruction you simply call

    $ ufo-reconstruct run -i $PATH_TO_SINOGRAMS

from the command line. To get get correct results, you may need to append
options such as `--axis-pos/-a` and `--angle-step/-a` (which are given in
radians!). Input paths are either directories or glob patterns. Output paths are
either directories or a format that contains one `%i`
[specifier](http://www.pixelbeat.org/programming/gcc/format_specs.html):

    $ ufo-reconstruct run --axis-pos=123.4 --angle-step=0.000123 \
         --input="/foo/bar/*.tif" --output="/output/slices-%05i.tif"

You can get a help for all options by running

    $ ufo-reconstruct run --help

and more verbose output by running with the `-v/--verbose` flag.

You can also load reconstruction parameters from a configuration file called
`reco.conf`. You may create a template with

    $ ufo-reconstruct init

Note, that options passed via the command line always override configuration
parameters!


### Estimating the center of rotation

If you do not know the correct center of rotation from your experimental setup,
you can estimate it with:

    $ ufo-reconstruct estimate -i $PATH_TO_SINOGRAMS

Currently, a modified algorithm based on the work of [Donath et
al.](http://dx.doi.org/10.1364/JOSAA.23.001048) is used to determine the center.
