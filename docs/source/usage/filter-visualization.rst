Interactive filter visualization
================================

The filter visualization tool is intended for interactive tuning of phase
retrieval and frequency-domain sharpening. It shows the 1D filter curves, can
display processed projections, and can reconstruct a single slice from a
flat-corrected projection stack. This makes it useful for choosing phase
retrieval parameters before spending time on a full reconstruction.

Start the window with:

.. code-block:: bash

   tofu filter-visualization --energy 20 --propagation-distance 0.1 --pixel-size 1e-6

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
  energy, propagation distance, pixel size, regularization and frequency
  cutoff.
- **Sharpening**: enable sharpening and tune the method, strength, Lorentz FWHM
  and maximum boost.
- **Reconstruction**: select flat-corrected projections in a single TIFF file,
  choose the detector row to reconstruct, and optionally restrict the output
  slice with ``X region`` and ``Y region`` triples.

Text fields update only when Enter is pressed. This keeps reconstruction from
being triggered while a number is still being typed.

Views
-----

The right side contains three tabs:

- **Filters**: plots the current phase retrieval and sharpening filter curves.
- **Projection**: shows processed projections from the selected TIFF file.
- **Reconstruction**: shows the reconstructed slice.

Projection and reconstruction views share the same interaction model. Greyscale
limits and zoom are synchronized automatically between method tabs. The
``Reset greyscale`` button resets the current image limits and applies the same
limits to the other tabs. ``Sync all`` additionally synchronizes profile and
region overlays. Views can also be popped out into separate windows.

Line profiles and regions
-------------------------

Each image view has a yellow profile line. Drag the line to inspect grey values
along the profile; the plot below the image updates with the current data. Hold
Shift while dragging a line endpoint to constrain it horizontally or vertically.
The profile line is synchronized between tabs.

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
row. The vertical input region needed for phase retrieval is computed from the
Fresnel scale and clipped to the detector only when necessary; an out-of-range
slice number is rejected.

Example workflow
----------------

One practical tuning workflow is:

1. Start without sharpening enabled.
2. Select the phase retrieval method and tune the phase retrieval parameters
   while watching the filter curve.
3. Select a flat-corrected projection TIFF and inspect the Projection tab.
4. Reconstruct a representative slice and adjust phase retrieval until the
   slice looks physically reasonable.
5. Enable sharpening and tune the sharpening parameters while comparing the
   phase and sharpened tabs.
6. Use the profile line to compare grey-value changes across edges or features.
7. Use Ctrl-drag in the Reconstruction tab to crop to a smaller region if you
   want faster iteration on a local feature.

After the parameters are chosen, use the same values with ``tofu preprocess`` or
``tofu reco`` for batch processing.
