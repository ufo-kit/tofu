Diagnostic Fourier ring correlation
==================================

``tofu frc`` compares consecutive projection images. Unlike FSC, this command is
a diagnostic of acquisition-dependent similarity, **not a spatial-resolution
estimator**: neighboring angles do not contain exactly the same projected signal.
Structural variation and shared calibration artifacts can also affect the curves.

Usage::

    tofu frc --projections radios/ --flats flats/ --darks darks/ \
        --absorptivity --fix-nan-and-inf --number 3001 --num-corr 50 --output frc

    tofu frc --projections projections.tif --x 100 --y 200 \
        --width 1024 --height 512 --gpu 0 --threshold-criterion half-bit

Inputs and selection
--------------------

Inputs are existing grayscale TIFF files, directories or globs, including
multipage TIFFs. Files are sorted lexicographically, then pages are read in order.
``--number`` (alias ``--num-projections``) limits the initial frame sequence;
its default is all available frames. There is no projection-step option.

Pairs are disjoint: (1,2), (3,4), etc., including across file boundaries. An odd
final frame is ignored. ``--num-corr`` defaults to all ``number // 2`` pairs;
otherwise it selects approximately equidistant pairs, including the first and
last. One requested pair selects the middle pair (the later middle for an even
pair count). Requests outside 1..number//2 are rejected.

``--x`` and ``--y`` default to zero; ``--width`` and ``--height`` default to the
remaining detector extent. Rectangular ROIs are supported; all images and
calibrations must share the detector shape. No padding, resizing, filtering or
phase retrieval is performed. ``--gpu`` selects one visible GPU (default 0);
automatic graph expansion is disabled. Live acquisition and multi-GPU scheduling
are not part of this command.

Provide both ``--flats`` and ``--darks`` or neither. Calibration is reduced once
with ``--reduction-mode average`` (default) or ``median``, using actual TIFF page
counts. ``--dark-scale``, ``--flat-scale``, ``--absorptivity`` and
``--fix-nan-and-inf`` have the usual flat-correction meanings. Without calibration,
absorptivity applies negative logarithm directly. ``flats2`` is not supported.

Frequency geometry and criteria
------------------------------

``--pixel-size-x/y`` default to 1, giving cycles/detector-pixel frequencies.
Other positive spacings use one common physical unit. Automatic ``--ring-width 0``
selects max(1/(Nx*dx), 1/(Ny*dy)); automatic ``--max-frequency 0`` selects
min(1/(2*dx), 1/(2*dy)). The core uses rounded radial bins with centres b*width
and floor(max-frequency/width) bins. The retained-bin rule, not an additional
radial clipping operation, determines membership.

``--threshold-criterion`` accepts ``one-bit`` (default) and ``half-bit``. These
information curves use the full-spectrum ring counts, following the same
convention as tofu FSC, without effective-independent-sample corrections.
Crossings are diagnostic frequencies only. They are interpolated between adjacent
finite bins where FRC minus the criterion changes from positive to non-positive.
No crossing is recorded as null, not as the maximum frequency. The geometric
lower bound is also retained as a diagnostic, never a resolution criterion.

Outputs and plotting
--------------------

``--output`` defaults to ``frc``. Three artifacts are produced:

* ``frc.npz`` contains every curve, seven raw statistics per pair, pair indices,
  shared frequency/count vectors, selected threshold and geometric bounds.
* ``frc.json`` contains configuration (omitting unspecified null defaults), resolved
  ROI/geometry, pair indices and crossings, device and total execution time.
* ``frc.png`` shows an FRC heatmap and crossing-frequency trace. Heatmap columns
  are spatial frequencies, rows are original projection-pair midpoints, and color
  is correlation on a fixed [-1,1] scale. Gray cells indicate invalid values;
  unrepresented frequencies beyond the last bin are not measurements. Gaps in the
  crossing trace indicate absent crossings. A single pair instead produces a line
  plot of FRC, the selected criterion and geometric bound.

Curves are not averaged or pooled. A low-correlation band flags a pair worth
inspecting, but does not identify an acquisition fault by itself. Numeric results
are saved before plotting. Replot without UFO or rerunning the acquisition::

    from tofu.frc import FRCResult, plot_frc
    result = FRCResult.from_npz("frc/frc.npz")
    plot_frc(result, "frc/replot.png")

Plot constants are grouped near the top of ``tofu/frc.py``. Corrected images and
spectra stay on the GPU; only compact ring statistics are downloaded. Python reads
selected raw ROIs and recycles one host input buffer after UFO copies it; the
graph's bounded queues supply the scheduler's lookahead without retaining the
whole input dataset.
The input files must remain unchanged throughout the run.

Configuration files
-------------------

``--config`` uses the usual INI format and CLI precedence::

    [frc]
    projections = radios/
    num-corr = 50
    threshold-criterion = one-bit
    gpu = 0
    output = frc

Use ``tofu frc --help`` for the complete supported option list. Shared general,
reading and flat-correction sections supply only options advertised by FRC;
unsupported options in the dedicated ``[frc]`` section are rejected.
