Fourier shell correlation
=========================

``tofu fsc`` reconstructs the even and odd projections separately on one GPU,
transforms both volumes and reduces their Fourier coefficients into radial shell
statistics. Only seven compact vectors are downloaded, not the volumes or spectra.
The command requires installed ``rgba-backproject``, ``fft`` and seven-row
``fsc-core`` UFO plugins and their matching installed kernels.

Basic usage
-----------

For projections requiring flat-field and absorption correction::

    tofu fsc --projections projections/ --flats flats/ --darks darks/ \
        --number 3000 --region=-128,128,1 --absorptivity

Each input path may be a file, directory or glob. TIFF inputs may contain multiple
grayscale pages. Headerless RAW requires ``--width``, ``--height`` (the full RAW
frame height) and ``--bitdepth`` (8, 16 or 32). EDF metadata requires Fabio.
Input streams must have consistent detector dimensions. Do not mix input formats
or unrelated image datasets in one input directory.

``--number`` (alias ``--num-projections``) is required and counts projection
**frames**, not files. ``--start`` and ``--step`` select files from a sorted
directory/glob, not pages within TIFFs. Non-default file selection is rejected
for a single input file. The selected stream is the angular sequence passed to
backprojection: ``--overall-angle`` describes its coverage, and parity refers
to its consecutive frames. Selecting every second original projection changes
the meaning of even/odd; it does not preserve original acquisition parity.

``--retries`` and ``--retry-timeout`` retry input-readiness checks before
reconstruction. They do not turn the command into a live acquisition reader.
The requested frames must exist when preflight finishes.

For the already-filtered data used by the FSC benchmark::

    tofu fsc --projections filtered.tif --number 3000 \
        --region=-128,128,1 --center-position-x=996 \
        --projection-filter none

Do not enable absorption conversion or another filter for already-corrected,
filtered input. To compare against a benchmark, also match reconstruction regions,
centres, angle, addressing mode and shell settings. The benchmark uses radians;
this command accepts **degrees**, defaulting to 180. Negative angles are supported.

Correction and filtering
------------------------

``--flats`` and ``--darks`` must be supplied together, or both omitted. Calibration
frames are reduced using ``--reduction-mode average`` (default) or ``median``.
``--dark-scale`` and ``--flat-scale`` default to 1. ``--absorptivity`` enables
negative-log conversion; without it corrected intensities remain intensities.
``--fix-nan-and-inf`` replaces invalid correction values with zero.

``--flats2`` defaults to **None** and is unnecessary for ordinary use. If supplied,
it represents a second flat-field acquisition, typically after the scan. The
correction interpolates between the two reduced flat fields over the requested
projection count. Calibration stack sizes count actual frames, including TIFF pages.

Projection filtering defaults to ``ramp-fromreal``, with cutoff 0.5, scale 1,
``clamp_to_edge`` padding and ``--projection-crop-after backprojection``.
``--projection-filter none`` bypasses the entire filtering/padding stage.
Other available filter names and padding modes are listed in ``tofu fsc --help``.
There is no phase retrieval, phase/filter fusion or automatic filter-scale override.

Geometry and device
-------------------

``--gpu`` chooses one index among the devices visible to UFO, default 0. Every
GPU task is bound to it and graph expansion is disabled. Device-visibility
environment variables may change which physical GPU this index identifies.

``--region`` is the required half-open Z interval ``START,STOP,1``. Optional
``--x-region`` and ``--y-region`` default to ``-W/2,W/2,1``, where W is the original
detector width, **not its padded filtering width**. Each dimension is independently
``ceil(STOP - START)``. Cubic volumes are not required. All region steps must be
exactly 1; detector resampling, transpose and resizing are not offered.

``--center-position-x`` and ``--center-position-z`` are scalar coordinates in the
original detector, defaulting to its width/2 and height/2. ``--y`` and ``--height``
crop detector rows. Internally the command subtracts the row offset from the Z
centre and, when filtering padding is retained, adds the actual integer padding
offset to the X centre. It does not change the reconstruction regions or add a
half-pixel offset. For RAW, ``--height`` describes the full frame and the selected
rows extend from ``--y`` to its end.

``--burst`` defaults to 16. ``--addressing-mode`` accepts only ``none``, ``clamp``
(default) and ``clamp_to_edge``. Even/odd reconstruction and volume output are fixed,
not user options. A complete region must fit on one GPU; there is no slab splitting.

Before reconstruction, each GPU plugin is checked independently. Each known
allocation must fit the device allocation limit, and that plugin's known
simultaneous input/output/private working set must fit total device memory.
RGBA's additional allocation cap and image limits, and FSC's local-memory limit,
are also checked. There is no combined pipeline budget or percentage reserve.
RGBA volume mode excludes the slice-only planar buffer. Median calibration stacks
are host allocations because ``stack`` and ``flatten`` are CPU tasks; they are
reported separately, not charged against GPU memory.
Exact-size non-power-of-two FFTs use expanded chirp-Z arrays and may require much
more memory than similarly sized power-of-two volumes.

These are plugin-local feasibility checks, not a measurement of free VRAM or a
guarantee for the combined runtime peak. Overlapping task allocations, unknown FFT
backend workspace, driver overhead and concurrent GPU users can cause allocation
failure. Speculative workspace reserves and scheduler pools are not grounds for
preflight rejection. Rejection identifies the plugin, allocation and limit before creating
result artifacts. Reduce the region or burst, or choose a larger GPU, as appropriate.

FSC configuration and interpretation
------------------------------------

``--voxel-size-x/y/z`` are positive reconstructed-sample spacings, all default 1.
Use one common length unit for physical spacings. They describe the sampling grid;
they do not resize the reconstruction. With shape ``(Nz, Ny, Nx)``, the axial
frequency increments are ``1/(Nx*dx)``, ``1/(Ny*dy)`` and ``1/(Nz*dz)``.

``--shell-width 0`` selects the largest axial increment. ``--max-frequency 0``
selects the smallest axial Nyquist frequency ``min(1/(2*di))``. Positive values
override these choices. The core uses float32 shell geometry, with
``B = floor(max_frequency / shell_width)`` (including its numerical tolerance),
rounded shell indices ``floor(radius / shell_width + 0.5)``, and centres
``k_bin[b] = b * shell_width``. It retains indices less than B, without a separate
radial clipping rule. No FFT shift or automatic volume zero-padding is performed.

With unit spacings the plot covers 0 to 0.5 cycles/reconstructed voxel. Otherwise
frequencies are cycles per configured length unit. If a physical voxel size is
exactly one unit on every axis, the default normalized label is numerically
equivalent; interpret its units according to your supplied sampling convention.

``--threshold-criterion half-bit`` is the default and the only supported criterion.
The full-spectrum shell count n determines the half-bit threshold, with
``s = (sqrt(2)-1)/2``, ``h = 2*sqrt(s)`` and
``T = (s*sqrt(n)+h+1)/((s+1)*sqrt(n)+h)``. Empty shells remain NaN.
The first adjacent finite pair where FSC minus threshold goes from positive to
non-positive yields a linearly interpolated crossing frequency. Invalid gaps are
not bridged; an initially sub-threshold sample is not an interpolated crossing.
No crossing is reported as such, without extrapolating a resolution.

The geometric lower bound is always plotted, using the minimum m and maximum M
magnitudes across both spectra: ``2*sqrt(M*m)/(M+m)``. Shells with at most 10
coefficients, empty shells and all-zero shells are masked. A populated shell with
``m=0<M`` has bound zero. This curve is a **diagnostic bound**, not a resolution
threshold. The fixed 0.143 criterion is not part of this command.

Noise independence is an experimental assumption, not something the command can
verify. Even/odd separation does not eliminate shared artifacts or correlated
calibration errors. A threshold crossing must be interpreted with those caveats.

Results and Python access
-------------------------

``--output`` names a directory, default **fsc**. A successful run writes:

* ``fsc.png``: FSC, half-bit and geometric curves with a legend.
* ``fsc.json``: resolved configuration, shape, shell geometry, total elapsed time,
  output paths and the half-bit crossing frequency/status. A missing crossing is
  JSON ``null``. Runtime contains no detailed profiling or device dump.
* ``fsc-result.npz``: the curves, counts, bin centres, raw cross/power sums,
  magnitude extrema and resolved shell geometry.

These filenames are replaced on successful reruns. Computation failure leaves
previous artifacts untouched. Plot and serialization finish in temporary files
before replacement; replacement of all three files is not a filesystem transaction.
Total execution time includes preflight, GPU computation, plotting and NPZ writing,
but excludes the final JSON write and artifact replacement.

Optional reconstructed volumes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``--write-volumes`` defaults to false. When omitted, only the three FSC artifacts
are written; an older volume export is not deleted or updated.

When enabled, the command releases the main graph and then runs a second
reconstruction on the same GPU. Both runs share exactly the same reconstruction
builder, including correction, filtering, detector selection, regions and centres.
The second graph is ``rgba-backproject(output-mode=volume) -> slice -> write``.
The slice stage avoids the writer's special RGB handling of three-plane inputs.

``even-odd-volumes.tif`` is one unscaled float32 BigTIFF shaped ``(2Z,Y,X)``:
the complete even volume first, then the complete odd volume. Its dimensions,
page count and dtype are validated before replacing a previous export. The export
path is added to ``fsc.json`` and total execution time includes the second run.
If requested export fails, the completed FSC PNG/JSON/NPZ are retained, an error
is reported and the command exits nonzero. File replacement is not a multi-file
filesystem transaction.

Export does not branch or download volumes from the main FSC graph and does not
change its computed results. It adds reconstruction time, host memory and disk I/O.
Inputs must remain unchanged between passes. A second reconstruction may differ
slightly through floating-point arithmetic; compare numerically rather than bitwise.

For an already-filtered benchmark dataset::

    tofu fsc --projections filtered.tif --number 3000 \
        --region=-16,16,1 --center-position-x=996 \
        --projection-filter none --write-volumes

Match the benchmark's burst, addressing mode, regions, centres and projection
selection; tofu's angle is in degrees, whereas the benchmark JSON uses radians.
Use the NumPy benchmark on the exported volumes, with the same voxel spacings,
shell width and maximum frequency::

    python /path/to/analytical_methods/benchmarks/fsc/run_numpy_fsc.py \
        fsc/even-odd-volumes.tif --voxel-size-x 1 --voxel-size-y 1 \
        --voxel-size-z 1 --shell-width 0 --max-frequency 0.5

Compare bin centres and counts first, then FSC, half-bit and geometric curves.
The benchmark's additional fixed-threshold curve is not produced by tofu. Use
the established ``rtol=2e-3, atol=2e-4`` for floating reductions; unexpected count
differences or larger discrepancies need investigation rather than plot adjustments.

Structured result access
~~~~~~~~~~~~~~~~~~~~~~~~

Load a structured result without UFO resource creation or pickle::

    from tofu.fsc import FSCResult

    result = FSCResult.from_npz("fsc/fsc-result.npz")
    print(result.crossing_frequency)
    frequency = result.k_bin
    correlation = result.fsc
    counts = result.n_shell
    powers = result.statistics.power_1_sum

Or access named arrays directly::

    import numpy as np

    with np.load("fsc/fsc-result.npz", allow_pickle=False) as data:
        print(data.files)
        frequency = data["k_bin"]
        correlation = data["fsc"]

Raw statistics and bin centres retain float32 storage; counts are int64 and FSC
normalization/criteria use float64. Invalid bins retain NaN; FSC is not clamped.
NPZ reload recomputes criteria from the saved sufficient statistics.

Configuration files
-------------------

Use ``tofu fsc --config fsc.conf`` with an INI file, for example::

    [fsc]
    projections = filtered.tif
    number = 3000
    region = -128,128,1
    projection-filter = none
    overall-angle = 180
    output = fsc
    write-volumes = false

Supported settings in ``[general]``, ``[reading]``, ``[flat-correction]`` and
``[preprocess]`` are also accepted. ``[fsc]`` takes precedence, followed by explicit
CLI options. Unsupported keys in ``[fsc]`` and unsupported CLI options are errors;
unrelated legacy sections/settings are ignored. No legacy rgbabp settings are used.
