Interactive reconstruction tuning
=================================

The ``tune`` tool is intended for interactive tuning of phase retrieval,
frequency-domain sharpening and single-slice reconstruction. It shows the 1D
filter curves, can display processed projections, and can reconstruct a single
slice from a flat-corrected projection stack. This makes it useful for choosing
processing and reconstruction parameters before spending time on a full
reconstruction.

Start the window with:

.. code-block:: bash

   tofu tune --energy 20 --propagation-distance 0.1 --pixel-size 1e-6

The command accepts the phase retrieval and sharpening parameters described on
the pre-processing page. Values supplied on the command line are used as the
initial values in the GUI. If not specified, the GUI starts with a
``1024 x 1024`` filter grid, ``15 keV`` energy, ``0.1 m`` propagation distance,
maximum ICT alpha threshold and frequency cutoff, and the ``lorentz``
sharpening method.

Main controls
-------------

The left side contains the parameters. The most important groups are:

- **Phase retrieval**: choose the retrieval method and tune parameters such as
  energy, propagation distance, pixel size, ``log10(delta / beta)`` and
  frequency cutoff. The ``log10(delta / beta)`` field is the
  ``regularization-rate`` parameter used by UFO filters; the physical ratio is
  :math:`\delta / \beta = 10^\mathrm{value}`.
- **Sharpening**: enable sharpening and tune the method, strength, Lorentz FWHM
  and maximum boost.
- **Reconstruction**: select flat-corrected projections in a single TIFF file,
  choose the detector row to reconstruct, set the rotation center and small
  axis-angle corrections, and optionally restrict the output slice with
  ``X region`` and ``Y region`` triples.

Text fields update only when Enter is pressed. This keeps reconstruction from
being triggered while a number is still being typed.

If no phase retrieval method is selected, the Projection and Reconstruction
tabs switch to absorption mode. In that mode the phase retrieval pipeline is
omitted and the displayed data are converted to absorptivity,
:math:`-\log(I)`, by the normal preprocessing pipeline.

Views
-----

The right side contains three tabs:

- **Filters**: plots the current phase retrieval and sharpening filter curves.
- **Projection**: shows processed projections from the selected TIFF file.
- **Reconstruction**: shows the reconstructed slice.

Projection and reconstruction views share the same interaction model. Greyscale
limits and zoom are synchronized automatically between method tabs. The
``Reset greyscale`` button resets the current image limits and applies the same
limits to the other tabs. ``Sync all`` synchronizes profile and region overlays.
Views can also be popped out into separate windows.

Line profiles and regions
-------------------------

Each image view has a yellow profile line. Drag the line to inspect grey values
along the profile; the plot below the image updates with the current data. Hold
Shift while dragging a line endpoint to constrain it horizontally or vertically.
The profile line is synchronized between tabs.

In the Projection tab, hold Ctrl and left-click on a detector row to copy that
row into the reconstruction ``Slice`` field. This is often the fastest way to
choose a slice: inspect a projection, Ctrl-click the feature of interest, and
then run or update the reconstruction.

In the reconstruction view, hold Ctrl and drag with the left mouse button to
draw a rectangle. The rectangle updates ``X region`` and ``Y region`` using the
coordinate system of the current reconstructed slice, where ``0,0`` is the
rotation axis. These region fields are written as ``from,to,step`` triples and
may contain negative values. Press ``Reset region`` to return both fields to
``0,-1,1``, the default full-region value.

Single-slice reconstruction
---------------------------

The reconstruction panel expects flat-corrected projections in one TIFF file.
When projections are selected, the number of images and detector height are
detected automatically. The slice field is initialized to the middle detector
row. An out-of-range slice number is rejected.

The ``Axis angle X`` and ``Axis angle Y`` fields are entered in degrees in the
GUI. Internally they are passed to the general reconstruction code in radians,
as expected by the UFO backprojection task. These fields are useful for
correcting small setup misalignments while interactively checking one slice.

For each reconstruction the GUI computes the projection rows that must be read
before building the graph. First it asks the same ``CTGeometry`` code used by
``tofu reco`` for the detector region required by the current reconstruction
geometry, including ``Axis angle X`` and ``Axis angle Y``. If phase retrieval is
active, this geometry region is expanded by the vertical Fresnel margin needed
by the retrieval filter. The final reader ``y`` and ``height`` are the union of
the geometry requirement and the phase retrieval margin. If the requested slice
is close to the detector edge and the full margin cannot be read, the read
window is clamped and a warning is logged. The phase retrieval padded width and
height are rounded up to powers of two.

In absorption mode, the Fresnel margin is not needed. Only the geometry-derived
reader region is used, and the input projection is converted with
:math:`-\log(I)` before backprojection.

Example workflow
----------------

One practical tuning workflow is:

1. Start without sharpening enabled.
2. Select the phase retrieval method and tune the phase retrieval parameters
   while watching the filter curve.
3. Select a flat-corrected projection TIFF and inspect the Projection tab.
4. Ctrl-click a detector row in the Projection tab to choose the slice to
   reconstruct.
5. Reconstruct a representative slice and adjust phase retrieval until the
   slice looks physically reasonable. If needed, tune ``Axis angle X`` and
   ``Axis angle Y`` to correct small alignment errors.
6. Temporarily disable all phase retrieval methods to compare the result with
   a pure absorption reconstruction.
7. Enable sharpening and tune the sharpening parameters while comparing the
   phase and sharpened tabs.
8. Use the profile line to compare grey-value changes across edges or features.
9. Use Ctrl-drag in the Reconstruction tab to crop to a smaller region if you
   want faster iteration on a local feature.

After the parameters are chosen, use the same values with ``tofu preprocess`` or
``tofu reco`` for batch processing.
