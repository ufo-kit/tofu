## About

This directory contains canonical data processing scripts to be used together
with the UFO framework. At the moment they are targeted at high-performance
reconstruction of tomographic data sets:

* `ufo-sinos`: Create sinograms from a set of projections and correct them if
  flat and dark field images are provided.
* `ufo-reconstruct`: Reconstruct tomographic volumes from sinograms or
  projections using different reconstruction algorithms.
* `ufo-estimate-center`: Estimate the center of rotation from the input data.


## Installation

Just run

    python setup.py install

in a prepared virtualenv or as root for system-wide installation.
