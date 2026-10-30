from __future__ import annotations

import argparse
import gc
import ctypes as ct
import ctypes.util
from dataclasses import asdict, dataclass
from concurrent.futures import ThreadPoolExecutor
import json
import logging
import math
import os
from pathlib import Path
import tempfile
from queue import Empty, Queue
from threading import Event, Lock, Thread
import time
from typing import Any, Callable, Sequence

import numpy as np

LOG = logging.getLogger("tofu.fsc")
GEOMETRIC_MIN_SAMPLES = 10
PLOT_STYLE = "darkgrid"
PLOT_PALETTE = "muted"
PLOT_CONTEXT = "notebook"
PLOT_FIGSIZE = (7.2, 4.5)
PLOT_DPI = 180
PLOT_ALPHA = 0.82


@dataclass(frozen=True)
class ShellGeometry:
    """Frequency geometry, in reciprocal configured voxel-size units."""

    delta_k_xyz: tuple[float, float, float]
    shell_width: float
    max_frequency: float
    number_of_bins: int


@dataclass(frozen=True)
class FSCShellStatistics:
    """Seven compact rows from fsc-core, with integral counts."""

    cross_sum: np.ndarray
    power_1_sum: np.ndarray
    power_2_sum: np.ndarray
    n_shell: np.ndarray
    k_bin: np.ndarray
    minimum_magnitude: np.ndarray
    maximum_magnitude: np.ndarray

    @classmethod
    def from_ufo(cls, values: np.ndarray) -> FSCShellStatistics:
        rows = np.asarray(values, dtype=np.float32)
        if rows.ndim != 2 or rows.shape[0] != 7 or rows.shape[1] == 0:
            raise ValueError("fsc-core must emit a nonempty (7, B) array")
        if not np.isfinite(rows[:5]).all():
            raise ValueError("Non-finite FSC sums, counts or frequencies")
        if np.any(rows[3] < 0) or np.any(rows[3] != np.floor(rows[3])):
            raise ValueError("Invalid FSC shell counts")
        # Counts above 2**24 cannot be certified exact in the float32 contract.
        if np.any(rows[3] > 2**24):
            raise ValueError("FSC shell count exceeds exact float32 integer range")
        counts = rows[3].astype(np.int64)
        occupied = counts > 0
        minimum, maximum = rows[5:7]
        if (
            not np.isfinite(rows[5:7, occupied]).all()
            or np.any(minimum[occupied] < 0)
            or np.any(maximum[occupied] < minimum[occupied])
            or not np.isnan(rows[5:7, ~occupied]).all()
        ):
            raise ValueError("Invalid FSC magnitude extrema")
        return cls(
            rows[0].copy(),
            rows[1].copy(),
            rows[2].copy(),
            counts,
            rows[4].copy(),
            minimum.copy(),
            maximum.copy(),
        )


def half_bit_threshold(counts: np.ndarray) -> np.ndarray:
    counts = np.asarray(counts, dtype=np.float64)
    result = np.full(counts.shape, np.nan)
    valid = np.isfinite(counts) & (counts > 0)
    root = np.sqrt(counts[valid])
    s = (np.sqrt(2.0) - 1.0) / 2.0
    h = 2.0 * np.sqrt(s)
    result[valid] = (s * root + h + 1.0) / ((s + 1.0) * root + h)
    return result


def geometric_bound(statistics: FSCShellStatistics) -> np.ndarray:
    minimum = statistics.minimum_magnitude.astype(np.float64)
    maximum = statistics.maximum_magnitude.astype(np.float64)
    result = np.full(minimum.shape, np.nan)
    valid = (
        (statistics.n_shell > GEOMETRIC_MIN_SAMPLES)
        & np.isfinite(minimum)
        & np.isfinite(maximum)
        & (minimum >= 0)
        & (maximum > 0)
        & (minimum <= maximum)
    )
    ratio = minimum[valid] / maximum[valid]
    result[valid] = 2.0 * np.sqrt(ratio) / (1.0 + ratio)
    return result


def first_curve_crossing(
    frequency: np.ndarray, fsc: np.ndarray, threshold: np.ndarray
) -> float | None:
    """First downward crossing between adjacent finite samples; no extrapolation."""
    frequency, fsc, threshold = np.broadcast_arrays(frequency, fsc, threshold)
    difference = fsc - threshold
    for i in range(1, len(frequency)):
        if (
            np.isfinite(frequency[i - 1 : i + 1]).all()
            and np.isfinite(difference[i - 1 : i + 1]).all()
            and difference[i - 1] > 0 >= difference[i]
        ):
            fraction = difference[i - 1] / (difference[i - 1] - difference[i])
            return float(
                frequency[i - 1] + fraction * (frequency[i] - frequency[i - 1])
            )
    return None


@dataclass(frozen=True)
class FSCResult:
    """FSC and diagnostic curves. Load an artifact with :meth:`from_npz`."""

    fsc: np.ndarray
    k_bin: np.ndarray
    n_shell: np.ndarray
    half_bit_threshold: np.ndarray
    geometric_bound: np.ndarray
    geometry: ShellGeometry
    statistics: FSCShellStatistics

    @classmethod
    def from_statistics(
        cls, statistics: FSCShellStatistics, geometry: ShellGeometry
    ) -> FSCResult:
        if len(statistics.k_bin) != geometry.number_of_bins:
            raise ValueError("Output bin count differs from resolved geometry")
        expected = np.arange(geometry.number_of_bins, dtype=np.float32) * np.float32(
            geometry.shell_width
        )
        if not np.array_equal(statistics.k_bin, expected):
            raise ValueError("Output bin centres differ from resolved geometry")
        first = statistics.power_1_sum.astype(np.float64)
        second = statistics.power_2_sum.astype(np.float64)
        denominator = np.sqrt(first * second)
        valid = (statistics.n_shell > 0) & (first > 0) & (second > 0)
        fsc = np.full(first.shape, np.nan)
        np.divide(
            statistics.cross_sum.astype(np.float64), denominator, out=fsc, where=valid
        )
        return cls(
            fsc,
            statistics.k_bin.copy(),
            statistics.n_shell.copy(),
            half_bit_threshold(statistics.n_shell),
            geometric_bound(statistics),
            geometry,
            statistics,
        )

    @property
    def crossing_frequency(self) -> float | None:
        return first_curve_crossing(self.k_bin, self.fsc, self.half_bit_threshold)

    def to_npz(self, path: str | Path) -> None:
        """Save numeric arrays only; no pickled Python objects."""
        arrays = {
            name: getattr(self.statistics, name)
            for name in self.statistics.__dataclass_fields__
        }
        arrays.update(
            fsc=self.fsc,
            half_bit_threshold=self.half_bit_threshold,
            geometric_bound=self.geometric_bound,
            delta_k_xyz=np.asarray(self.geometry.delta_k_xyz),
            shell_width=self.geometry.shell_width,
            max_frequency=self.geometry.max_frequency,
            number_of_bins=self.geometry.number_of_bins,
        )
        np.savez_compressed(path, **arrays)

    @classmethod
    def from_npz(cls, path: str | Path) -> FSCResult:
        """Rebuild the typed result and criteria from saved sufficient statistics."""
        with np.load(path, allow_pickle=False) as data:
            names = tuple(FSCShellStatistics.__dataclass_fields__)
            rows = np.stack([data[name] for name in names])
            statistics = FSCShellStatistics.from_ufo(rows)
            geometry = ShellGeometry(
                tuple(float(v) for v in data["delta_k_xyz"]),
                float(data["shell_width"]),
                float(data["max_frequency"]),
                int(data["number_of_bins"]),
            )
        return cls.from_statistics(statistics, geometry)


def plot_fsc(
    result: FSCResult,
    path: str | Path,
    frequency_label: str,
    title: str = "Fourier shell correlation",
) -> None:
    """All visual choices live here; the geometric curve is not a threshold."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    with sns.axes_style(PLOT_STYLE), sns.plotting_context(PLOT_CONTEXT):
        figure, axis = plt.subplots(figsize=PLOT_FIGSIZE, constrained_layout=True)
        colors = sns.color_palette(PLOT_PALETTE)
        for index, (curve, label, style, width) in enumerate(
            [
                (result.fsc, "FSC", "-", 1.5),
                (result.half_bit_threshold, "Half-bit threshold", "-.", 1.1),
                (result.geometric_bound, "Geometric lower bound", ":", 1.3),
            ]
        ):
            # Matplotlib preserves NaN gaps (Seaborn's dataframe path drops them).
            axis.plot(
                result.k_bin,
                curve,
                label=label,
                linestyle=style,
                linewidth=width,
                color=colors[index],
                alpha=PLOT_ALPHA if index == 0 else 1.0,
            )
        axis.axhline(0.0, color="black", linewidth=0.6)
        axis.set(
            xlim=(0.0, result.geometry.max_frequency),
            xlabel=frequency_label,
            ylabel="FSC",
            title=title,
        )
        axis.legend()
        figure.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
        plt.close(figure)


def resolve_geometry(shape: Sequence[int], args: argparse.Namespace) -> ShellGeometry:
    sizes = (args.voxel_size_x, args.voxel_size_y, args.voxel_size_z)
    if not all(math.isfinite(v) and v > 0 for v in sizes):
        raise ValueError("Voxel sizes must be finite and positive")
    if not all(
        math.isfinite(v) and v >= 0 for v in (args.shell_width, args.max_frequency)
    ):
        raise ValueError(
            "Shell width and maximum frequency must be finite and nonnegative"
        )
    delta = tuple(1.0 / (n * d) for n, d in zip(reversed(shape), sizes))
    with np.errstate(over="ignore", under="ignore"):
        width = float(np.float32(args.shell_width or max(delta)))
    maximum = args.max_frequency or min(1.0 / (2.0 * d) for d in sizes)
    if not math.isfinite(width) or width <= 0 or not math.isfinite(maximum):
        raise ValueError("Shell geometry is outside the supported numerical range")
    ratio = maximum / width
    if not math.isfinite(ratio):
        raise ValueError("Shell geometry is outside the supported numerical range")
    bins = math.floor(ratio + 16 * np.finfo(np.float64).eps * max(1.0, abs(ratio)))
    if not 1 <= bins <= 2**32 - 1:
        raise ValueError("Shell configuration produces an unsupported number of bins")
    return ShellGeometry(delta, width, maximum, bins)


@dataclass(frozen=True)
class InputInfo:
    width: int
    height: int
    frames: int
    raw: bool


def _inspect_input(
    path: str, args: argparse.Namespace, projections: bool = False
) -> InputInfo:
    """Inspect metadata, never read a TIFF stack to discover its dimensions."""
    from tofu.util import get_filenames
    from tifffile import TiffFile

    files = [
        p
        for p in get_filenames(path)
        if Path(p).is_file()
        and Path(p).suffix.lower() in (".tif", ".tiff", ".edf", ".raw")
    ]
    if projections:
        if Path(path).is_file():
            if args.start != 0 or args.step != 1:
                raise ValueError(
                    "--start/--step select files, not TIFF pages; omit them for a single file"
                )
        else:
            files = files[args.start :: args.step]
    if not files:
        raise ValueError(f"No supported input files selected at {path}")
    shape = None
    raw_kind = None
    frames = 0
    for filename in files:
        suffix = Path(filename).suffix.lower()
        raw = suffix == ".raw"
        if raw_kind is not None and raw != raw_kind:
            raise ValueError(
                "Mixing RAW and header-based input in one stream is unsupported"
            )
        raw_kind = raw
        if raw:
            if not args.width or not args.height or args.bitdepth not in (8, 16, 32):
                raise ValueError(
                    "RAW input requires --width, --height and --bitdepth 8, 16 or 32"
                )
            current = (args.height, args.width)
            frame_bytes = math.prod(current) * (args.bitdepth // 8)
            count, remainder = divmod(Path(filename).stat().st_size, frame_bytes)
            if remainder or count == 0:
                raise ValueError(
                    f"RAW file size is not a positive whole number of frames: {filename}"
                )
        elif suffix in (".tif", ".tiff"):
            with TiffFile(filename) as tif:
                current = tuple(tif.pages[0].shape)
                count = len(tif.pages)
                if len(current) != 2 or any(
                    tuple(page.shape) != current for page in tif.pages
                ):
                    raise ValueError(
                        f"Expected equal-shaped grayscale TIFF pages: {filename}"
                    )
        else:
            import fabio

            with fabio.open(filename) as edf:
                current = tuple(edf.shape)
                count = edf.nframes
                if len(current) != 2:
                    raise ValueError(f"Expected a 2D EDF image: {filename}")
        if shape is not None and current != shape:
            raise ValueError(f"Input dimensions change within {path}")
        shape = current
        frames += count
        if projections and frames >= args.number:
            break
    return InputInfo(shape[1], shape[0], frames, bool(raw_kind))


def resolve_inputs(args: argparse.Namespace) -> dict[str, Any]:
    if not 2 <= args.number <= 32768:
        raise ValueError("--number must be between 2 and 32768")
    if not 1 <= args.burst <= 128:
        raise ValueError("Burst must be in 1..128")
    if args.step < 1 or min(args.start, args.y, args.retries, args.retry_timeout) < 0:
        raise ValueError("Invalid reading selection or retry settings")
    if any(v is not None and v <= 0 for v in (args.width, args.height)):
        raise ValueError("Input width and height must be positive")
    for name in (
        "overall_angle",
        "center_position_x",
        "dark_scale",
        "flat_scale",
        "projection_filter_scale",
        "projection_filter_cutoff",
    ):
        value = getattr(args, name)
        if value is not None and not math.isfinite(value):
            raise ValueError(f"{name.replace('_', '-')} must be finite")
    if args.overall_angle == 0:
        raise ValueError("Angular coverage must be nonzero")
    if bool(args.flats) != bool(args.darks) or (args.flats2 and not args.flats):
        raise ValueError(
            "Supply --flats and --darks together; --flats2 additionally requires both"
        )
    # Reader has no retry properties: retries apply to preflight input readiness.
    for attempt in range(args.retries + 1):
        try:
            inputs = {"projections": _inspect_input(args.projections, args, True)}
            for name in ("darks", "flats", "flats2"):
                if getattr(args, name):
                    inputs[name] = _inspect_input(getattr(args, name), args)
            if inputs["projections"].frames < args.number:
                raise ValueError(
                    f"Only {inputs['projections'].frames} projections available; {args.number} requested"
                )
            break
        except (ValueError, OSError):
            if attempt == args.retries:
                raise
            time.sleep(args.retry_timeout)
    detector = inputs["projections"]
    for info in inputs.values():
        if (info.width, info.height) != (detector.width, detector.height):
            raise ValueError(
                "Projection and calibration detector dimensions must match"
            )
    if args.width is not None and args.width != detector.width:
        raise ValueError(
            "--width must match detector width; use x-region for reconstruction cropping"
        )
    height = (
        detector.height - args.y if detector.raw or args.height is None else args.height
    )
    if height <= 0 or args.y + height > detector.height:
        raise ValueError("Selected detector rows lie outside the input image")
    cx = (
        detector.width / 2.0
        if args.center_position_x is None
        else args.center_position_x
    )
    # Individual centres are resolved separately, after detector cropping is known.
    cz = detector.height / 2.0
    x_region = args.x_region or (-detector.width / 2.0, detector.width / 2.0, 1.0)
    y_region = args.y_region or (-detector.width / 2.0, detector.width / 2.0, 1.0)
    shape = tuple(math.ceil(r[1] - r[0]) for r in (args.region, y_region, x_region))
    if any(n <= 0 or n > 2**31 - 1 for n in shape):
        raise ValueError("Unsupported reconstruction dimensions")
    from tofu.util import get_filtering_padding

    padding = (
        get_filtering_padding(detector.width) if args.projection_filter != "none" else 0
    )
    retain_padding = args.projection_crop_after == "backprojection"
    return {
        "inputs": inputs,
        "detector_width": detector.width,
        "detector_height": detector.height,
        "height": height,
        "width": detector.width,
        "backprojection_width": detector.width + (padding if retain_padding else 0),
        "padded_width": detector.width + padding,
        "center_position_x": cx,
        "center_position_z": cz,
        "backprojection_center_x": cx + (padding // 2 if retain_padding else 0),
        "backprojection_center_z": cz - args.y,
        "overall_angle_radians": math.radians(args.overall_angle),
        "x_region": x_region,
        "y_region": y_region,
        "volume_shape_zyx": shape,
    }


def _device_limits(gpu: Any) -> dict[str, int]:
    """Query the device behind this exact queue, not a second device enumeration."""
    library = ctypes.util.find_library("OpenCL")
    if not library:
        raise RuntimeError("Cannot find the OpenCL loader for the memory preflight")
    cl = ct.CDLL(library)
    signature = [ct.c_void_p, ct.c_uint, ct.c_size_t, ct.c_void_p, ct.c_void_p]
    cl.clGetCommandQueueInfo.argtypes = signature
    cl.clGetCommandQueueInfo.restype = ct.c_int
    cl.clGetDeviceInfo.argtypes = signature
    cl.clGetDeviceInfo.restype = ct.c_int
    device = ct.c_void_p()
    status = cl.clGetCommandQueueInfo(
        gpu.get_cmd_queue(), 0x1091, ct.sizeof(device), ct.byref(device), None
    )
    if status:
        raise RuntimeError(f"Cannot query selected OpenCL queue (error {status})")
    limits = {}
    for name, parameter, value_type in (
        ("compute_units", 0x1002, ct.c_uint),
        ("max_allocation", 0x1010, ct.c_ulonglong),
        ("image_width", 0x1011, ct.c_size_t),
        ("image_height", 0x1012, ct.c_size_t),
        ("image_layers", 0x1041, ct.c_size_t),
        ("global_memory", 0x101F, ct.c_ulonglong),
        ("local_memory", 0x1023, ct.c_ulonglong),
    ):
        value = value_type()
        status = cl.clGetDeviceInfo(
            device, parameter, ct.sizeof(value), ct.byref(value), None
        )
        if status:
            raise RuntimeError(f"Cannot query OpenCL {name} (error {status})")
        limits[name] = value.value
    return limits


def estimate_memory(
    args: argparse.Namespace,
    resolved: dict[str, Any],
    geometry: ShellGeometry,
    limits: dict[str, int],
) -> dict[str, Any]:
    """Check known task-local allocations, without a combined pipeline budget.

    Each entry includes one current input/output and the task's known private
    storage. Scheduler recycling pools and unknown FFT backend scratch storage
    are not guessed. A passing check is not a promise of free memory at runtime.
    """
    nz, ny, nx = resolved["volume_shape_zyx"]
    zp = 4 * math.ceil(nz / 4)
    width, height = resolved["backprojection_width"], resolved["height"]
    batch = 2 * args.burst
    real = 4 * nx * ny * nz
    spectrum = 2 * real
    plane = 4 * resolved["width"] * height
    bins = geometry.number_of_bins
    groups = max(1, min(4 * limits["compute_units"], nx * ny * nz))
    tasks: dict[str, dict[str, int]] = {}
    host_allocations: dict[str, int] = {}
    problems: list[str] = []

    def check(name: str, allocations: dict[str, int], rgba: bool = False) -> None:
        tasks[name] = allocations
        limit = (
            min(limits["max_allocation"], 2**32) if rgba else limits["max_allocation"]
        )
        for label, size in allocations.items():
            if size > limit:
                problems.append(
                    f"{name}: {label} needs {size / 2**20:.1f} MiB; "
                    f"allocation limit {limit / 2**20:.1f} MiB"
                )
        working_set = sum(allocations.values())
        if working_set > limits["global_memory"]:
            problems.append(
                f"{name}: known working set {working_set / 2**30:.2f} GiB "
                f"exceeds total device memory {limits['global_memory'] / 2**30:.2f} GiB"
            )
        LOG.info("%s: known task-local working set %.3f GiB", name, working_set / 2**30)

    # Volume mode has two coalesced accumulators; it does not allocate the
    # slice-mode planar buffer. Packing the first output overlaps both accumulators.
    check(
        "rgba-backproject",
        {
            "input projection": 4 * width * height,
            "projection staging": 4 * width * height * batch,
            "projection texture": 2 * width * zp * batch,
            "even accumulator": 4 * nx * ny * zp,
            "odd accumulator": 4 * nx * ny * zp,
            "angle table": 8 * batch,
            "output volume": real,
        },
        rgba=True,
    )

    work_shape = tuple(
        n if n & (n - 1) == 0 else 1 << (2 * n - 2).bit_length() for n in (nx, ny, nz)
    )
    fft_allocations = {"input volume": real, "output spectrum": spectrum}
    if work_shape != (nx, ny, nz):
        work_bytes = 8 * math.prod(work_shape)
        fft_allocations.update(
            {
                "chirp-Z temporary": work_bytes,
                "chirp-Z coefficients": work_bytes,
                "chirp-Z transformed coefficients": work_bytes,
            }
        )
    check("fft (3D)", fft_allocations)
    check(
        "fsc-core",
        {
            "input spectrum": spectrum,
            "retained first spectrum": spectrum,
            "partial reductions (group-count upper bound)": 32 * groups * bins,
            "shell output": 28 * bins,
        },
    )
    if 24 * bins > limits["local_memory"]:
        problems.append(
            f"fsc-core: local shell table needs {24 * bins} bytes; "
            f"local-memory limit {limits['local_memory']}"
        )
    for name, needed in (
        ("image_width", width),
        ("image_height", zp // 4),
        ("image_layers", batch),
    ):
        if needed > limits[name]:
            problems.append(
                f"rgba-backproject: {name} needs {needed}; limit {limits[name]}"
            )

    for name, info in resolved["inputs"].items():
        if name == "projections":
            continue
        if args.reduction_mode == "median":
            # stack and flatten are CPU tasks: never charge their stacks to VRAM.
            host_allocations[f"{name} stack"] = plane * info.frames
            LOG.info(
                "%s median stack: %.1f MiB host memory (not GPU)",
                name,
                plane * info.frames / 2**20,
            )
        else:
            check(
                f"average ({name})", {"input frame": plane, "accumulator/output": plane}
            )
    if args.flats:
        check(
            "flat-field-correct",
            {
                "projection": plane,
                "dark": plane,
                "flat": plane,
                "output": plane,
            },
        )
    elif args.absorptivity or args.fix_nan_and_inf:
        check("calculate", {"input": plane, "output": plane})
    if args.flats2:
        check(
            "interpolate",
            {
                "first input": plane,
                "second input": plane,
                "retained first": plane,
                "retained second": plane,
                "output": plane,
            },
        )
    if args.projection_filter != "none":
        padded = 4 * resolved["padded_width"] * height
        check("pad", {"input": plane, "output": padded})
        check("fft (projection)", {"input": padded, "output": 2 * padded})
        check(
            "filter",
            {
                "input": 2 * padded,
                "output": 2 * padded,
                "coefficients": 8 * resolved["padded_width"],
            },
        )
        check("ifft (projection)", {"input": 2 * padded, "output": padded})
        if args.projection_crop_after == "filter":
            check("crop", {"input": padded, "output": plane})
    if problems:
        raise RuntimeError(
            f"FSC shape (Z,Y,X)={nz, ny, nx} fails plugin-local memory checks:\n"
            + "\n".join(problems)
            + "\nReduce the relevant region/burst, use coarser shells, or select a larger GPU."
        )
    LOG.info(
        "Plugin-local checks passed; no combined pipeline budget or percentage reserve applied. "
        "Overlapping allocations, FFT backend workspace and other GPU users can still cause runtime allocation failure."
    )
    return {
        "plugins": {
            name: {
                "allocations": allocations,
                "working_set_bytes": sum(allocations.values()),
            }
            for name, allocations in tasks.items()
        },
        "host_allocations": host_allocations,
        "device_memory_bytes": limits["global_memory"],
        "fft_work_shape_xyz": work_shape,
    }


def construct_reconstruction_graph(
    args: argparse.Namespace, resolved: dict[str, Any], gpu: Any
) -> tuple[Any, Any]:
    from gi.repository import Ufo
    from tofu.tasks import get_task
    from tofu.preprocess import create_projection_filtering_pipeline

    graph = Ufo.TaskGraph()

    def task(name: str, **properties: Any) -> Any:
        return get_task(name, processing_node=gpu, **properties)

    def read(name: str) -> Any:
        info = resolved["inputs"][name]
        properties = dict(
            path=getattr(args, name), y=args.y, height=resolved["height"], y_step=1
        )
        if name == "projections":
            properties.update(start=args.start, step=args.step, number=args.number)
        if info.raw:
            properties.update(
                raw_width=info.width, raw_height=info.height, raw_bitdepth=args.bitdepth
            )
        return task("read", **properties)

    def calibration(name: str) -> Any:
        reader = read(name)
        if args.reduction_mode == "average":
            reduced = task("average")
            graph.connect_nodes(reader, reduced)
        else:
            stack = task("stack", number=resolved["inputs"][name].frames)
            reduced = task("flatten", mode="median")
            graph.connect_nodes(reader, stack)
            graph.connect_nodes(stack, reduced)
        return reduced

    current = read("projections")
    if args.flats:
        correction = task(
            "flat-field-correct",
            dark_scale=args.dark_scale,
            flat_scale=args.flat_scale,
            absorption_correct=args.absorptivity,
            fix_nan_and_inf=args.fix_nan_and_inf,
        )
        graph.connect_nodes_full(current, correction, 0)
        graph.connect_nodes_full(calibration("darks"), correction, 1)
        flats = calibration("flats")
        if args.flats2:
            interpolation = task("interpolate", number=args.number)
            graph.connect_nodes_full(flats, interpolation, 0)
            graph.connect_nodes_full(calibration("flats2"), interpolation, 1)
            flats = interpolation
        graph.connect_nodes_full(flats, correction, 2)
        current = correction
    elif args.absorptivity:
        expression = "-log(v)"
        if args.fix_nan_and_inf:
            expression = "isfinite(-log(v)) ? -log(v) : 0.0f"
        absorption = task("calculate", expression=expression)
        graph.connect_nodes(current, absorption)
        current = absorption
    elif args.fix_nan_and_inf:
        cleaned = task("calculate", expression="isfinite(v) ? v : 0.0f")
        graph.connect_nodes(current, cleaned)
        current = cleaned
    if args.projection_filter != "none":
        filtering_args = argparse.Namespace(**vars(args))
        filtering_args.width = resolved["width"]
        filtering_args.height = resolved["height"]
        first, last = create_projection_filtering_pipeline(
            filtering_args, graph, processing_node=gpu
        )
        graph.connect_nodes(current, first)
        current = last
    backproject = task(
        "rgba-backproject",
        burst=args.burst,
        num_projections=args.number,
        overall_angle=resolved["overall_angle_radians"],
        center_position_x=[resolved["backprojection_center_x"]],
        center_position_z=[resolved["backprojection_center_z"]],
        region=list(args.region),
        x_region=list(resolved["x_region"]),
        y_region=list(resolved["y_region"]),
        addressing_mode=args.addressing_mode,
        operation_mode="even_odd",
        output_mode="volume",
    )
    graph.connect_nodes(current, backproject)
    return graph, backproject


def construct_graph(
    args: argparse.Namespace, resolved: dict[str, Any], gpu: Any
) -> tuple[Any, Any]:
    from gi.repository import Ufo
    from tofu.tasks import get_task

    graph, backproject = construct_reconstruction_graph(args, resolved, gpu)

    def task(name: str, **properties: Any) -> Any:
        return get_task(name, processing_node=gpu, **properties)

    fft = task("fft", dimensions=3, auto_zeropadding=False)
    core = task(
        "fsc-core",
        voxel_size_x=args.voxel_size_x,
        voxel_size_y=args.voxel_size_y,
        voxel_size_z=args.voxel_size_z,
        shell_width=args.shell_width,
        max_frequency=args.max_frequency,
    )
    output = Ufo.OutputTask()
    output.set_property("num-dims", 2)
    for source, target in (
        (backproject, fft),
        (fft, core),
        (core, output),
    ):
        graph.connect_nodes(source, target)
    return graph, output


@dataclass(frozen=True)
class FSCRegion:
    """One independently reconstructed region, in original detector coordinates."""

    index: int
    center: float
    detector_region: tuple[float, float, float]

    def resolve(self, shared: dict[str, Any], row_offset: int) -> dict[str, Any]:
        return {
            **shared,
            "center_position_z": self.center,
            "backprojection_center_z": self.center - row_offset,
        }


def resolve_regions(
    args: argparse.Namespace, shared: dict[str, Any]
) -> list[FSCRegion]:
    if args.center_position_z is not None and args.num_regions is not None:
        raise ValueError("--num-regions and --center-position-z are mutually exclusive")
    if args.center_position_z is not None:
        centers = tuple(args.center_position_z)
    elif args.num_regions is not None:
        number = args.num_regions
        if number < 1 or number > shared["height"]:
            raise ValueError(
                "--num-regions must be between 1 and the selected detector height"
            )
        # Integer band boundaries and midpoints avoid introducing fractional row shifts.
        edges = [args.y + i * shared["height"] // number for i in range(number + 1)]
        centers = tuple(float((a + b) // 2) for a, b in zip(edges, edges[1:]))
    else:
        # Preserve the original single-region default, including with detector cropping.
        centers = (shared["detector_height"] / 2.0,)
    if not centers or any(not math.isfinite(center) for center in centers):
        raise ValueError("Specify at least one finite Z centre")
    if len(set(centers)) != len(centers):
        raise ValueError("Z centres must be distinct")
    regions = []
    for index, center in enumerate(centers, 1):
        start, stop = center + args.region[0], center + args.region[1]
        if start < args.y or stop > args.y + shared["height"]:
            raise ValueError(
                f"Region {index}: detector interval [{start:g}, {stop:g}) lies outside "
                f"selected rows [{args.y}, {args.y + shared['height']}); "
                "reduce --region or choose another centre"
            )
        regions.append(FSCRegion(index, center, (start, stop, 1.0)))
    return regions


class PipelineControl:
    """Cancel active schedulers and unblock their output consumers on interruption."""

    def __init__(self) -> None:
        self.stopped = Event()
        self._lock = Lock()
        self._active: dict[int, tuple[Any, Any]] = {}

    def register(self, scheduler: Any, output: Any = None) -> None:
        with self._lock:
            if self.stopped.is_set():
                raise RuntimeError("FSC execution cancelled")
            self._active[id(scheduler)] = (scheduler, output)

    def unregister(self, scheduler: Any) -> None:
        with self._lock:
            self._active.pop(id(scheduler), None)

    def cancel(self) -> None:
        with self._lock:
            self.stopped.set()
            active = list(self._active.values())
        for scheduler, output in active:
            scheduler.abort()
            if output is not None:
                output.emit("inputs-stopped")


def run_region_jobs(
    regions: Sequence[FSCRegion],
    workers: Sequence[tuple[int, Any, Any]],
    operation: Callable[[FSCRegion, Any, Any, PipelineControl], Any],
    continue_on_error: bool = False,
) -> tuple[dict[int, Any], dict[int, str]]:
    """A dynamic queue, with one persistent worker and resource owner per GPU."""
    pending: Queue[FSCRegion] = Queue()
    for region in regions:
        pending.put(region)
    control = PipelineControl()
    successes: dict[int, Any] = {}
    failures: dict[int, str] = {}
    lock = Lock()

    def work(worker: tuple[int, Any, Any]) -> None:
        device_index, resources, gpu = worker
        while not control.stopped.is_set():
            try:
                region = pending.get_nowait()
            except Empty:
                return
            LOG.info(
                "Region %d on GPU %d: detector rows %s",
                region.index,
                device_index,
                region.detector_region,
            )
            try:
                value = operation(region, resources, gpu, control)
                with lock:
                    successes[region.index] = value
            except Exception as exc:
                with lock:
                    failures[region.index] = str(exc)
                LOG.error("Region %d failed: %s", region.index, exc)
                if not continue_on_error:
                    # Let other in-flight graphs finish, but do not start more work.
                    control.stopped.set()
            finally:
                pending.task_done()

    pool = ThreadPoolExecutor(max_workers=len(workers), thread_name_prefix="fsc-gpu")
    try:
        futures = [pool.submit(work, worker) for worker in workers]
        for future in futures:
            future.result()
    except BaseException:
        control.cancel()
        raise
    finally:
        pool.shutdown(wait=True)
    return successes, failures


def execute_graph(
    graph: Any, output: Any, resources: Any, control: PipelineControl | None = None
) -> np.ndarray:
    from gi.repository import Ufo
    import ufo.numpy

    # FixedScheduler respects the explicit per-node GPU bindings and never expands.
    scheduler = Ufo.FixedScheduler()
    scheduler.set_resources(resources)
    scheduler.set_property("expand", False)
    failures: list[BaseException] = []

    def execute() -> None:
        try:
            scheduler.run(graph)
        except BaseException as exc:
            failures.append(exc)
            # Setup can fail before UFO sends the normal output EOF notification.
            output.emit("inputs-stopped")

    worker = Thread(target=execute, name="tofu-fsc-scheduler", daemon=True)
    arrays = []
    if control is not None:
        control.register(scheduler, output)
    try:
        worker.start()
        while True:
            buffer = output.get_output_buffer()
            if buffer is None:
                break
            try:
                arrays.append(ufo.numpy.asarray(buffer).copy())
            finally:
                output.release_output_buffer(buffer)
        worker.join()
    except BaseException:
        scheduler.abort()
        if worker.ident is not None:
            worker.join()
        raise
    finally:
        if control is not None:
            control.unregister(scheduler)
    if failures:
        raise RuntimeError(f"FSC pipeline failed: {failures[0]}") from failures[0]
    if len(arrays) != 1:
        raise RuntimeError(
            f"Expected one complete FSC pair, received {len(arrays)} results; check projection count"
        )
    return arrays[0]


def write_volumes(
    args: argparse.Namespace,
    resolved: dict[str, Any],
    gpu: Any,
    resources: Any,
    destination: Path,
    control: PipelineControl | None = None,
) -> Path:
    """Optional diagnostic rerun; keep all export-only behavior in this function.

    The caller has already saved FSC and released its graph. This second graph
    intentionally downloads reconstructed volumes; the main graph never does.
    """
    from gi.repository import Ufo
    from tifffile import TiffFile
    from tofu.tasks import get_task

    directory = destination.parent
    LOG.info(
        "Exporting even/odd volumes with a second reconstruction; inputs must remain unchanged"
    )

    def reconstruct(path: Path) -> None:
        graph, backproject = construct_reconstruction_graph(args, resolved, gpu)
        # Always split to 2D, including Z=3 (write otherwise interprets it as RGB).
        slices = get_task("slice", processing_node=gpu)
        writer = get_task(
            "write",
            processing_node=gpu,
            filename=str(path),
            bits=32,
            rescale=False,
            append=False,
            tiff_bigtiff=True,
        )
        graph.connect_nodes(backproject, slices)
        graph.connect_nodes(slices, writer)
        scheduler = Ufo.FixedScheduler()
        scheduler.set_resources(resources)
        scheduler.set_property("expand", False)
        if control is not None:
            control.register(scheduler)
        try:
            scheduler.run(graph)
        finally:
            if control is not None:
                control.unregister(scheduler)
            # Dropping the writer closes/flushes the TIFF before metadata validation.
            del scheduler, graph, writer, slices, backproject
            gc.collect()

    try:
        with tempfile.TemporaryDirectory(
            prefix=".fsc-volumes-", dir=directory
        ) as temporary:
            staging = Path(temporary)
            volume_path = staging / destination.name
            reconstruct(volume_path)
            nz, ny, nx = resolved["volume_shape_zyx"]
            with TiffFile(volume_path) as tif:
                if not tif.is_bigtiff or len(tif.pages) != 2 * nz:
                    raise ValueError(
                        "Export must be a BigTIFF containing exactly 2*Z pages"
                    )
                for page in tif.pages:
                    if (
                        page.shape != (ny, nx)
                        or page.dtype != np.dtype("float32")
                        or page.samplesperpixel != 1
                    ):
                        raise ValueError(
                            "Export must contain float32 grayscale (Y,X) planes"
                        )
            # Workers never edit the shared JSON; the coordinator owns metadata.
            os.replace(volume_path, destination)
    except Exception as exc:
        raise RuntimeError(
            f"FSC results were saved, but the requested volume export failed: {exc}"
        ) from exc
    LOG.info("Saved float32 even-then-odd volumes to %s", destination)
    return destination


def artifact_names(region: FSCRegion, number: int) -> dict[str, str]:
    prefix = f"region-{region.index:03d}-" if number > 1 else ""
    return {
        "plot": prefix + "fsc.png",
        "npz": prefix + "fsc-result.npz",
        "volumes": prefix + "even-odd-volumes.tif",
    }


def crossing_summary(results: Sequence[FSCResult]) -> dict[str, Any]:
    """Descriptive statistics of detected crossings, not an aggregate resolution."""
    crossings = [
        r.crossing_frequency for r in results if r.crossing_frequency is not None
    ]
    return {
        "regions_with_crossing": len(crossings),
        "regions_without_crossing": len(results) - len(crossings),
        "minimum_crossing_frequency": min(crossings) if crossings else None,
        "median_crossing_frequency": float(np.median(crossings)) if crossings else None,
        "maximum_crossing_frequency": max(crossings) if crossings else None,
    }


def save_metadata(document: dict[str, Any], directory: Path, started: float) -> None:
    # One wall-clock duration, never a sum of worker durations. The final metadata
    # write/replacement itself is necessarily outside the recorded interval.
    document["runtime"] = {
        "total_execution_time_seconds": time.perf_counter() - started
    }
    with tempfile.TemporaryDirectory(prefix=".fsc-json-", dir=directory) as temporary:
        path = Path(temporary) / "fsc.json"
        path.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
        os.replace(path, directory / path.name)


def save_outputs(
    args: argparse.Namespace,
    resolved: dict[str, Any],
    regions: Sequence[FSCRegion],
    results: Sequence[FSCResult],
    started: float,
    gpu_indices: Sequence[int],
) -> dict[str, Any]:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    normalized = all(getattr(args, "voxel_size_" + axis) == 1.0 for axis in "xyz")
    unit = (
        "cycles/reconstructed voxel" if normalized else "cycles/configured length unit"
    )
    configuration = {
        key: value
        for key, value in vars(args).items()
        if not key.startswith("_")
        and key not in ("commands", "center_position_z", "threshold_criterion")
        and value is not None
    }
    configuration.update(
        gpus=list(gpu_indices),
        num_regions=len(regions),
        x_region=resolved["x_region"],
        y_region=resolved["y_region"],
        center_position_x=resolved["center_position_x"],
        overall_angle_radians=resolved["overall_angle_radians"],
        backprojection_center_x=resolved["backprojection_center_x"],
        detector_shape_yx=[resolved["detector_height"], resolved["detector_width"]],
        selected_detector_height=resolved["height"],
        backprojection_width=resolved["backprojection_width"],
        operation_mode="even_odd",
        output_mode="volume",
    )
    document = {
        "configuration": configuration,
        "volume_shape_zyx": resolved["volume_shape_zyx"],
        "shell_geometry": {**asdict(results[0].geometry), "frequency_unit": unit},
        "result": {"threshold_criterion": "half-bit", "regions": []},
    }
    if len(regions) > 1:
        document["result"]["crossing_summary"] = crossing_summary(results)
    with tempfile.TemporaryDirectory(prefix=".fsc-", dir=output) as temporary:
        staging = Path(temporary)
        filenames = []
        for region, result in zip(regions, results):
            names = artifact_names(region, len(regions))
            start, stop, _ = region.detector_region
            title = f"FSC — region {region.index}, detector rows [{start:g}, {stop:g})"
            plot_fsc(
                result,
                staging / names["plot"],
                f"Spatial frequency ({unit})",
                title=title,
            )
            result.to_npz(staging / names["npz"])
            filenames.extend((names["plot"], names["npz"]))
            crossing = result.crossing_frequency
            document["result"]["regions"].append(
                {
                    "region": region.index,
                    "center_position_z": region.center,
                    "detector_region": region.detector_region,
                    "crossing_frequency": crossing,
                    "status": (
                        "crossing_found"
                        if crossing is not None
                        else "no_crossing_in_sampled_band"
                    ),
                    "outputs": {
                        key: str(output / names[key]) for key in ("plot", "npz")
                    },
                }
            )
            LOG.info("Region %d half-bit crossing: %s %s", region.index, crossing, unit)
        # Prepare every plot/archive before replacing any existing artifact.
        for name in filenames:
            os.replace(staging / name, output / name)
    save_metadata(document, output, started)
    return document


def run(args: argparse.Namespace) -> FSCResult | tuple[FSCResult, ...]:
    """Run independent regions; preserve the scalar return for a single region."""
    from gi.repository import Ufo

    started = time.perf_counter()
    try:
        resolved = resolve_inputs(args)
        regions = resolve_regions(args, resolved)
        geometry = resolve_geometry(resolved["volume_shape_zyx"], args)
        first_resources = Ufo.Resources.new()
        devices = first_resources.get_gpu_nodes()
        indices = list(range(len(devices))) if args.gpus is None else list(args.gpus)
        if not indices or any(i < 0 or i >= len(devices) for i in indices):
            raise ValueError(
                f"--gpus must select available indices; {len(devices)} visible GPU(s)"
            )
        if len(set(indices)) != len(indices):
            raise ValueError("--gpus must not contain duplicate indices")
        # Every worker GPU must accommodate the unchanged region shape. No silent
        # size changes or device omissions: users can narrow --gpus when necessary.
        for index in indices[: len(regions)]:
            try:
                estimate_memory(
                    args, resolved, geometry, _device_limits(devices[index])
                )
            except (ValueError, RuntimeError) as exc:
                raise ValueError(f"GPU {index}: {exc}") from exc
        workers = []
        for position, index in enumerate(indices[: len(regions)]):
            resources = first_resources if position == 0 else Ufo.Resources.new()
            gpu = resources.get_gpu_nodes()[index]
            workers.append((index, resources, gpu))
            LOG.info("GPU worker %d: %s", index, gpu.get_info(Ufo.GpuNodeInfo.NAME))

        def compute(
            region: FSCRegion, resources: Any, gpu: Any, control: PipelineControl
        ) -> FSCResult:
            local = region.resolve(resolved, args.y)
            graph, output = construct_graph(args, local, gpu)
            try:
                statistics = FSCShellStatistics.from_ufo(
                    execute_graph(graph, output, resources, control)
                )
            finally:
                # Release spectra, accumulators and FFT workspaces before the next job.
                del graph, output
                gc.collect()
            return FSCResult.from_statistics(statistics, geometry)

        computed, failures = run_region_jobs(regions, workers, compute)
        if failures:
            raise RuntimeError(
                "FSC failed; no new result artifacts saved: "
                + "; ".join(
                    f"region {index}: {message}"
                    for index, message in sorted(failures.items())
                )
            )
        results = tuple(computed[region.index] for region in regions)
        for result in results[1:]:
            if not np.array_equal(result.k_bin, results[0].k_bin) or not np.array_equal(
                result.n_shell, results[0].n_shell
            ):
                raise RuntimeError(
                    "Regions produced incompatible frequency bins or shell counts"
                )
        document = save_outputs(args, resolved, regions, results, started, indices)
        if args.write_volumes:

            def export(
                region: FSCRegion, resources: Any, gpu: Any, control: PipelineControl
            ) -> Path:
                destination = (
                    Path(args.output) / artifact_names(region, len(regions))["volumes"]
                )
                return write_volumes(
                    args,
                    region.resolve(resolved, args.y),
                    gpu,
                    resources,
                    destination,
                    control,
                )

            exported, failures = run_region_jobs(
                regions, workers, export, continue_on_error=True
            )
            for entry in document["result"]["regions"]:
                index = entry["region"]
                if index in exported:
                    entry["outputs"]["volumes"] = str(exported[index])
                elif index in failures:
                    entry["volume_export_error"] = failures[index]
            save_metadata(document, Path(args.output), started)
            if failures:
                raise RuntimeError(
                    "FSC results were saved, but volume export failed for region(s): "
                    + ", ".join(map(str, sorted(failures)))
                )
        LOG.info("Saved %d regional FSC result(s) to %s", len(regions), args.output)
        return results[0] if len(results) == 1 else results
    except (ValueError, OSError, ImportError, OverflowError) as exc:
        raise RuntimeError(str(exc)) from exc
