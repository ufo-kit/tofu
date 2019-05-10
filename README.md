## About

This repository contains Python data processing scripts to be used with the UFO
framework. At the moment they are targeted at high-performance reconstruction of
tomographic data sets.


## Installation

Run

    python setup.py install

in a prepared virtualenv or as root for system-wide installation. Note, that if
you do plan to use the graphical user interface you need PyQt4, pyqtgraph and
PyOpenGL. You are strongly advised to install PyQt through your system package
manager, you can install pyqtgraph and PyOpenGL using the pip package manager
though:

    pip install pyqtgraph PyOpenGL


## Usage

### Reconstruction

To do a tomographic reconstruction you simply call

    $ tofu tomo --sinograms $PATH_TO_SINOGRAMS

from the command line. To get get correct results, you may need to append
options such as `--axis-pos/-a` and `--angle-step/-a` (which are given in
radians!). Input paths are either directories or glob patterns. Output paths are
either directories or a format that contains one `%i`
[specifier](http://www.pixelbeat.org/programming/gcc/format_specs.html):

    $ tofu tomo --axis-pos=123.4 --angle-step=0.000123 \
         --sinograms="/foo/bar/*.tif" --output="/output/slices-%05i.tif"

You can get a help for all options by running

    $ tofu tomo --help

and more verbose output by running with the `-v/--verbose` flag.

You can also load reconstruction parameters from a configuration file called
`reco.conf`. You may create a template with

    $ tofu init

Note, that options passed via the command line always override configuration
parameters!

Besides scripted reconstructions, one can also run a standalone GUI for both
reconstruction and quick assessment of the reconstructed data via

    $ tofu gui

![GUI](https://cloud.githubusercontent.com/assets/115270/6442540/db0b55fe-c0f0-11e4-9577-0048fddae8b7.png)


### Performance measurement

If you are running at least ufo-core/filters 0.6, you can evaluate the performance
of the filtered backprojection (without sinogram transposition!), with

    $ tofu perf

You can customize parameter scans, pretty easily via

    $ tofu perf --width 256:8192:256 --height 512

which will reconstruct all combinations of width between 256 and 8192 with a
step of 256 and a fixed height of 512 pixels.


### Estimating the center of rotation

If you do not know the correct center of rotation from your experimental setup,
you can estimate it with:

    $ tofu estimate -i $PATH_TO_SINOGRAMS

Currently, a modified algorithm based on the work of [Donath et
al.](http://dx.doi.org/10.1364/JOSAA.23.001048) is used to determine the center.


## Citation

If you use this software for publishing your data, we kindly ask to cite the article below.

Vogelgesang, Matthias, et al. "Real-time image-content-based beamline control for smart 4D X-ray imaging." Journal of synchrotron radiation 23.5 (2016): 1254-1263.
