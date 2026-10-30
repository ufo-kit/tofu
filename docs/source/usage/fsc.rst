Fourier shell correlation
=========================

``tofu fsc`` characterizes one or more equal-shaped reconstruction regions for estimating spatial
resolution limit in cycles/reconstructed-voxels. To compute FSC the specified region is reconstructed
independently from even and odd set of projections.

Usage and region selection
--------------------------

One region, centred at the original detector-height midpoint by default::

    tofu fsc --projections radios/ --flats flats/ --darks darks/ \
        --number 3001 --absorptivity --region=-64,64,1 --output fsc

Four automatically placed regions, executed by two GPU workers::

    tofu fsc --projections radios/ --flats flats/ --darks darks/ \
        --number 3001 --absorptivity --region=-64,64,1 \
        --x-region=-1024,1024,1 --y-region=-1024,1024,1 \
        --num-regions 4 --gpus 0 1 --output fsc

Or specify centres explicitly, in original detector-row coordinates::

    tofu fsc --projections filtered.tif --number 3001 --projection-filter none \
        --region=-64,64,1 --center-position-z 252,756,1260,1764 --gpus 0 1

``--num-regions N`` divides the selected detector rows into N portions with integer
boundaries and uses their integer midpoints. ``--center-position-z`` accepts one
centre or a comma-separated list and is mutually exclusive with ``--num-regions``.
Without either selector, one region is reconstructed at the original height/2,
preserving the single-region default. An explicit ``--num-regions 1`` instead
uses the selected rows' integer midpoint. Explicit centre order determines output
order, regardless of completion order. Duplicate/non-finite centres are rejected.

``--region START,STOP,1`` is required and specifies the same half-open Z offset
interval around every centre. Every interval must fit inside the selected detector
rows; no automatic shifting or clipping occurs. Bands determine placement, not slab
depth; overlapping regions are allowed and are not independent measurements.
``--x-region`` and ``--y-region`` default to ``-W/2,W/2,1``, where W is the original
detector width, not the filtering-padded width. Shape is independently
``ceil(STOP-START)`` along each axis; all steps must be 1. No resampling, transpose
or resizing is offered. Shape remains configurable; cubic volumes are unnecessary.

``--center-position-x`` defaults to original width/2. ``--y`` and ``--height`` select
detector rows. Internally Z centres are shifted by ``--y`` and the X centre by the
integer filtering-padding offset, where retained. No extra half-pixel shift is added.
``--overall-angle`` is in degrees (default 180; negative angles supported), converted
internally to radians. ``--burst`` defaults to 16; ``--addressing-mode`` accepts
``none``, ``clamp`` (default) and ``clamp_to_edge``. Even/odd and volume modes are fixed.

GPU execution and limits
------------------------

``--gpus 0 1`` selects visible UFO device indices, following ``tofu reco``.
``--gpu 0`` remains an alias. Without selection, all visible GPUs are eligible;
device-visibility environment variables may change their indices. At most one
worker per GPU runs, and surplus GPUs remain idle when regions are fewer.
Each worker has independent UFO resources and runs graphs with expansion disabled.
Workers take the next region as they finish, without a batch barrier: three regions
on two GPUs means the first free worker processes the third region.

Every region receives the complete selected projection stream with identical
preprocessing and parity. Readers and calibration/filtering work are repeated;
disk bandwidth and host memory can limit concurrent execution.

Input, correction and filtering
-------------------------------

``--projections``, ``--flats``, ``--darks`` and optional ``--flats2`` accept files,
directories or globs. TIFF may contain multiple grayscale pages; EDF requires Fabio.
RAW needs ``--width``, ``--height`` (full frame height) and ``--bitdepth`` (8/16/32).
For RAW, selected rows extend from ``--y`` to the full height. Input/calibration
dimensions must match; do not mix unrelated datasets or formats in one directory.

``--number`` (alias ``--num-projections``) counts selected projection frames.
``--start`` and ``--step`` select sorted files, not TIFF pages; non-default values
are rejected for a single file. Coverage and even/odd parity apply to this selected
sequence, not the original acquisition. ``--retries`` and ``--retry-timeout`` apply
only to input-readiness preflight, not live acquisition. Inputs must remain unchanged
throughout all regional jobs and optional export passes.

Supply ``--flats`` and ``--darks`` together or omit both. ``--flats2`` defaults to
None; if supplied, it provides a second flat acquisition interpolated over projections.
``--reduction-mode`` is ``average`` (default) or ``median``; ``--dark-scale`` and
``--flat-scale`` default to 1. ``--absorptivity`` enables negative-log conversion;
``--fix-nan-and-inf`` replaces invalid values with zero.

Filtering defaults to ``--projection-filter ramp-fromreal``,
``--projection-filter-cutoff 0.5``, ``--projection-filter-scale 1``,
``--projection-padding-mode clamp_to_edge`` and
``--projection-crop-after backprojection``. ``--projection-filter none`` bypasses
filtering/padding; use it for already-filtered input and omit correction flags if
already corrected. Other filter/padding choices appear in ``--help``. No phase
retrieval or automatic filter-scale override is performed.

FSC settings and interpretation
-------------------------------

``--voxel-size-x/y/z`` describe positive sample spacings in one common length unit,
default 1. They do not resize data. Axial FFT increments are ``1/(Ni*di)``.
``--shell-width 0`` uses their maximum; ``--max-frequency 0`` uses the smallest axial
Nyquist frequency ``min(1/(2*di))``. Positive settings override these defaults.
Float32 geometry uses ``B=floor(max_frequency/shell_width)`` with the core's numerical
tolerance, rounded bins ``floor(radius/shell_width+0.5)`` and centres
``k_bin[b]=b*shell_width``. Only ``b<B`` is retained, with no extra radial clipping.
No FFT shift or automatic volume padding is used. The plot extends to the resolved
maximum frequency, normally 0.5 cycles/voxel for unit spacing; otherwise frequencies
are per configured length unit.

``--threshold-criterion half-bit`` (van Heel & Schatz, 2005) is the only criterion supported for now.
With full-spectrum count n, ``s=(sqrt(2)-1)/2`` and ``h=2*sqrt(s)``, its value is
``(s*sqrt(n)+h+1)/((s+1)*sqrt(n)+h)``. Equal-shaped regions with shared settings have
identical counts and thresholds; returned counts and bin centres are checked for
equality. The first adjacent finite positive-to-nonpositive FSC-minus-threshold
transition is linearly interpolated. NaN gaps are not bridged, and an initially
sub-threshold bin is not a crossing. Missing crossings are not extrapolated.

Each plot also shows the geometric diagnostic ``2*sqrt(M*m)/(M+m)`` (Miqueles et al., 2025) from shell
magnitude extrema. Counts <=10, empty shells and all-zero shells are masked; ``m=0<M`` gives zero.
This is not a resolution threshold, rather projected as diagnostic lower bound for FSC.

Outputs and optional volumes
----------------------------

``--output`` is a directory (default ``fsc``). A single region retains ``fsc.png``
and ``fsc-result.npz``. Multiple regions write flat, indexed filenames:
``region-001-fsc.png``, ``region-001-fsc-result.npz``, etc. Each plot includes that
region's FSC, half-bit threshold and geometric bound, with its detector interval in
the title. There is no combined or aggregate plot.

One ``fsc.json`` stores shared configuration, shape and shell geometry once.
``result.threshold_criterion`` is shared; ``result.regions`` is an ordered array of
centres, detector intervals, crossing frequencies/status and artifact paths, including
for a single region. Unused None configuration values are omitted; missing crossings
remain JSON null. For multiple regions, ``result.crossing_summary`` reports min,
median and max of detected crossing frequencies, plus counts with/without crossings.
This descriptive summary excludes missing crossings and is neither pooled FSC nor
a global resolution estimate; if none cross, its three frequencies are null.

``--write-volumes`` defaults to false. When enabled, all FSC artifacts are saved
first; workers then run a second reconstruction per region using the same prefix
builder, followed by ``slice -> write``. Export is one unscaled float32 BigTIFF per region, shaped
``(2Z,Y,X)``, complete even volume then complete odd volume: ``even-odd-volumes.tif`` for one region or
``region-001-even-odd-volumes.tif`` etc.

Structured access and configuration
-----------------------------------

Every NPZ remains independently loadable without UFO resources or pickle::

    from tofu.fsc import FSCResult
    result = FSCResult.from_npz("fsc/region-001-fsc-result.npz")
    print(result.crossing_frequency)
    frequency, correlation = result.k_bin, result.fsc
    counts, powers = result.n_shell, result.statistics.power_1_sum

Archives contain raw statistics/extrema, curves and shell geometry. Raw floats are
float32, counts int64 and normalization/criteria float64; invalid bins remain NaN
without clamping. ``numpy.load(path, allow_pickle=False)`` also exposes named arrays.
Compare exported volumes with the NumPy benchmark using the same spacing, shell
settings and preprocessing: exact counts/bins, then ``rtol=2e-3, atol=2e-4`` for floats.

``--config fsc.conf`` accepts INI settings, for example::

    [fsc]
    projections = filtered.tif
    number = 3001
    region = -64,64,1
    num-regions = 4
    gpus = 0 1
    projection-filter = none
    write-volumes = false
    output = fsc

