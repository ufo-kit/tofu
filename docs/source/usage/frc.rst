Fourier ring correlation
========================

``tofu frc`` measures similarity between projection images, **not spatial
resolution**. Different angles do not contain exactly the same signal; structural
variation and shared calibration artifacts can affect the diagnostic.

Inputs and pair selection
-------------------------

Choose one input mode::

    # Acquisition sweep: equidistant disjoint consecutive pairs
    tofu frc --projections radios/ --number 3001 --num-corr 50 --output frc

    # Explicit zero-based pair within a projection dataset
    tofu frc --projections projections.tif --pair 10 42 --output pair-frc

    # Two distinct single-frame grayscale TIFFs
    tofu frc --img1 first.tif --img2 second.tif --output image-frc

``--projections`` accepts a TIFF file, directory or glob, including multipage
TIFFs. Files are sorted lexicographically, then pages are read in order.
All indices, coordinates and region identifiers are **zero-based**.

For sweeps, pairs are (0,1), (2,3), etc., including across file boundaries.
An odd final frame is ignored. ``--num-corr`` defaults to all ``number // 2``
pairs; an explicit count selects approximately equidistant pairs, including both
ends. One requested pair selects the middle pair (the later middle for an even
pair count). Requests outside 1..number//2 are rejected.

``--number`` (alias ``--num-projections``) limits the initial dataset sequence;
its default is all frames. Explicit ``--pair I J`` indices must be distinct and
within that sequence. There is no projection-step option.
``--pair`` and ``--num-corr`` are mutually exclusive.
``--img1`` and ``--img2`` must be supplied together and cannot be combined
with ``--projections``, ``--pair``, ``--number`` or ``--num-corr``.

Regions
-------

``--x`` and ``--y`` default to zero; ``--width`` and ``--height``
default to the remaining detector extent. These specify the outer ROI.

By default the entire ROI is correlated. Alternatively::

    # Top/bottom halves; use 2 2 for quadrants
    tofu frc --projections radios/ --num-corr 20 --region-grid 2 1

    # Quadrants for one pair
    tofu frc --projections radios/ --pair 0 1 --region-grid 2 2

    # 256x256 windows with 128-pixel steps: 50% overlap along each axis
    tofu frc --img1 first.tif --img2 second.tif \
        --x 100 --y 200 --width 1024 --height 1024 \
        --window-size 256 256 --window-stride 128 128

``--region-grid ROWS COLS`` requires positive integers dividing the ROI height
and width exactly. Regions follow row-major order, starting at the top left.
Grids work for both acquisition sweeps and explicit pairs.

``--window-size HEIGHT WIDTH`` requires an explicit pair; it is not available
for acquisition sweeps, even with ``--num-corr 1``.
``--window-stride Y X`` defaults to the window size. Smaller strides overlap;
larger strides leave gaps. Only fully contained windows are evaluated, starting
at the outer ROI origin; a trailing border may therefore remain unused.
Window size must fit within the ROI and all sizes/strides must be positive.
Grid and window modes are mutually exclusive; stride requires window size.

Each region uses identical detector coordinates in the two images. All regions
within a run have equal dimensions and share frequency bins and ring counts.
Their original detector rectangles are recorded as ``(x,y,width,height)``.

Preprocessing and execution
---------------------------

All images and calibrations must share the detector shape. Provide both
``--flats`` and ``--darks`` or neither, in every input mode. Calibration
uses ``--reduction-mode average`` (default) or ``median``, with actual TIFF
page counts. ``--dark-scale``, ``--flat-scale``, ``--absorptivity`` and
``--fix-nan-and-inf`` retain their usual meanings. Without calibration,
absorptivity applies negative logarithm directly. ``flats2`` is unsupported.

Regions run sequentially on ``--gpu`` (default visible GPU 0), with automatic
graph expansion disabled. Each region gets a separate graph and corresponding
calibration crops; calibration reduction repeats per region. No padding,
resizing, filtering or phase retrieval is performed. Live acquisition,
multi-GPU scheduling and frame export are not part of this command.

Corrected images and spectra stay on the GPU; only compact ring statistics are
downloaded. Python reads selected raw ROIs and recycles one host input buffer.
Input and calibration files must remain unchanged throughout the run.

Frequency geometry and criteria
-------------------------------

``--pixel-size-x/y`` default to 1, giving cycles/detector-pixel frequencies.
Other positive spacings use one common physical unit. Automatic ``--ring-width 0``
selects max(1/(Nx*dx), 1/(Ny*dy)); automatic ``--max-frequency 0`` selects
min(1/(2*dx), 1/(2*dy)). The core uses rounded radial bins with centres b*width
and floor(max-frequency/width) bins. The retained-bin rule, not an additional
radial clipping operation, determines membership.

``--threshold-criterion`` accepts ``one-bit`` (default) and ``half-bit``.
These information curves use full-spectrum ring counts, without
effective-independent-sample corrections. Crossings are interpolated between
adjacent finite bins where FRC minus the criterion changes from positive to
non-positive. An absent crossing is null, not the maximum frequency.
The geometric lower bound is diagnostic, never a resolution criterion.

Plots and artifacts
-------------------

``--output`` defaults to ``frc``. Three artifacts are produced:

* ``frc.png``: an acquisition sweep shows crossing frequency versus pair
  midpoint, with grid subplots when requested. Even a one-pair sweep uses this
  plot. An explicit pair shows FRC, the selected criterion and geometric bound,
  optionally in spatially arranged grid subplots.
* For sliding windows, ``frc.png`` instead shows discrete markers at window
  centres in detector coordinates. Color represents the crossing frequency of
  the **whole window**, not an individual pixel. Cross markers identify absent
  crossings. There is no interpolation; unsampled gaps are not measurements.
* ``frc.npz`` retains all FRC and geometric curves as ``(pairs,regions,bins)``,
  raw statistics as ``(pairs,regions,7,bins)``, and shared frequency, count and
  threshold vectors. Pair indices, regions, plotting modes, geometry and archive
  version are included. Loading needs no pickle.
* ``frc.json`` records configuration (omitting unspecified null defaults),
  shared geometry, region definitions, pair indices, a pair-by-region crossing
  matrix, device information and total command execution time.

Curves are never pooled. No acquisition-frequency heatmap is produced.
Missing crossings are marked separately, not plotted as measured zero or maximum
frequencies. Numeric artifacts are saved before plotting.

Replot without UFO or rerunning the computation::

    from tofu.frc import FRCResult, plot_frc
    result = FRCResult.from_npz("frc/frc.npz")
    plot_frc(result, "frc/replot.png")

Plot controls are grouped near the top of ``tofu/frc.py``.
The loader also accepts old, unversioned NPZ files: one-based pair indices are
converted to zero-based and a singleton region axis is added. These archives
represent acquisition sweeps; missing historical ROI coordinates are not invented.

Configuration files
-------------------

``--config`` uses the usual INI format; two-value options use whitespace::

    [frc]
    projections = radios/
    pair = 0 1
    region-grid = 2 2
    threshold-criterion = one-bit
    gpu = 0
    output = frc

CLI options override configuration values. An explicit CLI source, pair selector
or spatial selector also replaces its conflicting configuration alternative.
Conflicting options specified together on the CLI are rejected.

Shared general, reading and flat-correction sections supply only options advertised
by FRC; unsupported options in ``[frc]`` are rejected.
Use ``tofu frc --help`` for the complete option list.
