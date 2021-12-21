General 3D Reconstruction
=========================


You can use command ``tofu reco`` to reconstruct paralell/cone beam
tomography/laminography data. The algorithm is filtered back projection for
parallel beam data and `Feldkamp <https://doi.org/10.1364/JOSAA.1.000612>`_
approach for cone beam data. It always reconstructs 2D slices in the plane
parallel to the beam direction. The third dimensions may be the vertical slice
position (the default) but can also be one of the geometrical parameters in order to find
their best values for the final reconstruction (see ``tofu reco --help`` and
check the ``--z-parameter`` entry for possible values). Angular input values are
in degrees.

To reconstruct slices -100, 100 with the step size 0.5 around the center which
is defined as 1008.5 from 1500 projections acquired over 180 degrees stored in
``projs.tif``, with rotation axis in pixel 951 one would do::

    tofu reco --projections projs.tif --number 1500 --center-position-x 951
    --overall-angle 180 --center-position-z 1008.5 --region=-100,100,0.5
    --output slices.tif


To scan the roll angle around -2, 2 degrees with step 0.1 degree, one can use
the following command::
    tofu reco --projections projs.tif --number 1500 --overall-angle 180
    --center-position-x 951 --center-position-z 1008.5 --z-parameter
    detector-angle-y --region=-2,2,0.1 --output detector-angle-y-scan.tif
    --disable-projection-crop


To scan the rotation axis region from pixel 940 to pixel 960 with step 0.5
pixels, (the ``center-position-x`` parameter), one can use::
    tofu reco --projections projs.tif --number 1500 --overall-angle 180
    --center-position-z 1008.5 --z-parameter center-position-x
    --region=940,960,0.5 --output center-position-x-scan.tif
