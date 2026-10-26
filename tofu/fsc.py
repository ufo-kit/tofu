from __future__ import annotations

import argparse
import configparser
import ctypes as ct
import ctypes.util
from dataclasses import asdict, dataclass
import json
import logging
import math
import os
from pathlib import Path
import tempfile
from threading import Thread
import time
from typing import Any, Sequence

import numpy as np

LOG = logging.getLogger("tofu.fsc")
MEMORY_FRACTION = 0.8
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


def plot_fsc(result: FSCResult, path: str | Path, frequency_label: str) -> None:
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
            title="Fourier shell correlation",
        )
        axis.legend()
        figure.savefig(path, dpi=PLOT_DPI, bbox_inches="tight")
        plt.close(figure)


def _region(value: str) -> tuple[float, float, float]:
    try:
        parts = tuple(float(v) for v in value.split(","))
        if len(parts) != 3 or not all(math.isfinite(v) for v in parts):
            raise ValueError
        if parts[1] <= parts[0] or parts[2] != 1.0:
            raise ValueError
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected finite START,STOP,1 with STOP > START"
        ) from exc
    return parts


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register only supported options; do not inherit Params' writer flags."""
    from tofu import config

    selections = {
        "general": ("config", "verbose", "log", "width"),
        "reading": (
            "y",
            "height",
            "bitdepth",
            "start",
            "step",
            "retries",
            "retry-timeout",
        ),
        "flat-correction": (
            "projections",
            "flats",
            "darks",
            "flats2",
            "dark-scale",
            "flat-scale",
            "absorptivity",
            "fix-nan-and-inf",
        ),
        "preprocess": (
            "projection-filter",
            "projection-filter-cutoff",
            "projection-filter-scale",
            "projection-padding-mode",
            "projection-crop-after",
        ),
    }
    for section, names in selections.items():
        for name in names:
            options = {
                k: v
                for k, v in config.SECTIONS[section][name].items()
                if k not in ("unit", "ezdefault")
            }
            if name == "config":
                options["default"] = None
            if name == "projections":
                options["required"] = True
            parser.add_argument("--" + name, **options)
    parser.add_argument(
        "--number",
        "--num-projections",
        type=int,
        required=True,
        help="Number of selected projection frames (2..32768)",
    )
    parser.add_argument(
        "--output", default="fsc", help="Directory for PNG, JSON and NPZ results"
    )
    parser.add_argument("--gpu", type=int, default=0, help="One visible UFO GPU index")
    parser.add_argument("--burst", type=int, default=16)
    parser.add_argument(
        "--overall-angle", type=float, default=180.0, help="Angular coverage in degrees"
    )
    for axis in ("x", "z"):
        parser.add_argument(
            "--center-position-" + axis,
            type=float,
            help="Centre in original detector pixels (default: detector midpoint)",
        )
    parser.add_argument(
        "--region", type=_region, required=True, help="Z region: START,STOP,1"
    )
    for axis in ("x", "y"):
        parser.add_argument(
            "--" + axis + "-region",
            type=_region,
            help="START,STOP,1; default covers the unpadded detector width",
        )
    parser.add_argument(
        "--addressing-mode", choices=("none", "clamp", "clamp_to_edge"), default="clamp"
    )
    parser.add_argument(
        "--reduction-mode",
        type=str.lower,
        choices=("average", "median"),
        default="average",
    )
    for axis in ("x", "y", "z"):
        parser.add_argument(
            "--voxel-size-" + axis,
            type=float,
            default=1.0,
            help="Reconstructed voxel spacing in a common length unit",
        )
    parser.add_argument(
        "--shell-width",
        type=float,
        default=0.0,
        help="Radial bin width; 0 selects automatic",
    )
    parser.add_argument(
        "--max-frequency",
        type=float,
        default=0.0,
        help="Frequency limit; 0 selects automatic",
    )
    parser.add_argument(
        "--threshold-criterion", choices=("half-bit",), default="half-bit"
    )


def parse_args(
    parser: argparse.ArgumentParser, argv: Sequence[str]
) -> argparse.Namespace:
    """Read compatible INI sections, then [fsc], then explicit CLI overrides."""
    probe = argparse.ArgumentParser(add_help=False)
    probe.add_argument("--config")
    config_path = probe.parse_known_args(argv)[0].config
    tokens: list[str] = []
    if config_path:
        settings = configparser.ConfigParser(interpolation=None)
        if not settings.read(config_path):
            parser.error(f"Cannot read configuration file: {config_path}")
        option_parser = argparse.ArgumentParser(add_help=False)
        add_arguments(option_parser)
        actions = option_parser._option_string_actions
        for section in ("general", "reading", "flat-correction", "preprocess", "fsc"):
            if not settings.has_section(section):
                continue
            for name, value in settings.items(section):
                option = "--" + name.replace("_", "-")
                if option not in actions:
                    if section == "fsc":
                        parser.error(f"Unsupported FSC configuration option: {name}")
                    continue
                if value in ("", "None"):
                    continue
                action = actions[option]
                if isinstance(action, argparse._StoreTrueAction):
                    try:
                        enabled = settings.getboolean(section, name)
                    except ValueError as exc:
                        parser.error(str(exc))
                    # A false value in [fsc] can override an earlier true value.
                    tokens = [token for token in tokens if token != option]
                    if enabled:
                        tokens.append(option)
                else:
                    tokens.append(f"{option}={value}")
    return parser.parse_args(["fsc", *tokens, *argv])


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
    if not 1 <= args.burst <= 128 or args.gpu < 0:
        raise ValueError("Burst must be in 1..128 and GPU index must be nonnegative")
    if args.step < 1 or min(args.start, args.y, args.retries, args.retry_timeout) < 0:
        raise ValueError("Invalid reading selection or retry settings")
    if any(v is not None and v <= 0 for v in (args.width, args.height)):
        raise ValueError("Input width and height must be positive")
    for name in (
        "overall_angle",
        "center_position_x",
        "center_position_z",
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
    cz = (
        detector.height / 2.0
        if args.center_position_z is None
        else args.center_position_z
    )
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
    """Conservative allocation ledger, not a measurement of currently free VRAM."""
    nz, ny, nx = resolved["volume_shape_zyx"]
    zp = 4 * math.ceil(nz / 4)
    width, height = resolved["backprojection_width"], resolved["height"]
    batch = 2 * args.burst
    voxels = nx * ny * nz
    real = 4 * voxels
    complex_bytes = 8 * voxels
    bins = geometry.number_of_bins
    # G <= 4 * compute units, independently of the kernel's local-size choice.
    groups = max(1, 4 * limits["compute_units"])
    allocations: list[tuple[str, int, int, bool]] = []

    def add(name: str, size: int, copies: int = 1, rgba: bool = False) -> None:
        allocations.append((name, size, copies, rgba))

    add("RGBA projection staging", 4 * width * height * batch, rgba=True)
    add("RGBA texture", 2 * width * zp * batch, rgba=True)
    add("RGBA accumulators/coalescing", 4 * nx * ny * zp, 3, rgba=True)
    add("RGBA angle table", 8 * batch, rgba=True)
    add("RGBA output pool", real, 2)
    add("FFT output pool and retained FSC spectrum", complex_bytes, 3)
    work_shape = tuple(
        n if n & (n - 1) == 0 else 1 << (2 * n - 2).bit_length() for n in (nx, ny, nz)
    )
    work_bytes = 8 * math.prod(work_shape)
    if work_shape != (nx, ny, nz):
        add("FFT chirp-Z temporary and coefficient arrays", work_bytes, 3)
    add("3D FFT backend workspace allowance", work_bytes)
    add("FSC partial reductions", 32 * groups * bins)
    add("FSC output pool/copy", 28 * bins, 3)

    plane = 4 * resolved["width"] * height
    add("Projection reader output pool", plane, 2)
    for name, info in resolved["inputs"].items():
        if name == "projections":
            continue
        add(f"{name} reader and reduction pools", plane, 5)
        if args.reduction_mode == "median":
            # stack output is a reductor buffer; allow recycling plus sort workspace.
            add(f"{name} median stack/workspace", plane * info.frames, 3)
    if args.flats:
        add("Flat correction output pool", plane, 2)
    elif args.absorptivity:
        add("Absorption conversion output pool", plane, 2)
    if args.flats2:
        add("Flat interpolation output pool", plane, 2)
    if args.projection_filter != "none":
        padded_plane = 4 * resolved["padded_width"] * height
        add("Filtering real buffer pools", padded_plane, 4)
        add("Filtering complex buffer pools/backend allowances", 2 * padded_plane, 6)
        add("Filter coefficients", 4 * resolved["padded_width"])
        if args.projection_crop_after == "filter":
            add("Filtering crop output pool", plane, 2)

    total = sum(size * count for _, size, count, _ in allocations)
    budget = int(limits["global_memory"] * MEMORY_FRACTION)
    problems = []
    for name, size, _, rgba in allocations:
        limit = (
            min(limits["max_allocation"], 2**32) if rgba else limits["max_allocation"]
        )
        if size > limit:
            problems.append(
                f"{name}: one allocation needs {size / 2**20:.1f} MiB; limit {limit / 2**20:.1f} MiB"
            )
    if 24 * bins > limits["local_memory"]:
        problems.append(
            f"FSC local shell table needs {24 * bins} bytes; limit {limits['local_memory']}"
        )
    for name, needed in (
        ("image_width", width),
        ("image_height", zp // 4),
        ("image_layers", batch),
    ):
        if needed > limits[name]:
            problems.append(f"RGBA {name}: needs {needed}; limit {limits[name]}")
    if total > budget:
        problems.append("Total estimated pipeline memory exceeds the 80% budget")
    explanation = (
        f"FSC shape (Z,Y,X)={nz, ny, nx}: estimated {total / 2**30:.2f} GiB, "
        f"budget {budget / 2**30:.2f} GiB (80% of total device memory)."
    )
    if problems:
        raise RuntimeError(
            explanation
            + "\n"
            + "\n".join(problems)
            + "\nReduce the reconstruction region/burst, use coarser shells, or select a larger GPU. "
            "Non-power-of-two shapes can require substantially larger FFT work arrays."
        )
    LOG.info(explanation)
    LOG.info(
        "Preflight uses total, not currently free, GPU memory; concurrent users can still cause allocation failure."
    )
    return {
        "estimated_bytes": total,
        "budget_bytes": budget,
        "fft_work_shape_xyz": work_shape,
        "allocations": {name: size * count for name, size, count, _ in allocations},
    }


def construct_graph(
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
        (current, backproject),
        (backproject, fft),
        (fft, core),
        (core, output),
    ):
        graph.connect_nodes(source, target)
    return graph, output


def execute_graph(graph: Any, output: Any, resources: Any) -> np.ndarray:
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
    worker.start()
    try:
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
        worker.join(timeout=5.0)
        raise
    if failures:
        raise RuntimeError(f"FSC pipeline failed: {failures[0]}") from failures[0]
    if len(arrays) != 1:
        raise RuntimeError(
            f"Expected one complete FSC pair, received {len(arrays)} results; check projection count"
        )
    return arrays[0]


def save_outputs(
    args: argparse.Namespace,
    resolved: dict[str, Any],
    result: FSCResult,
    started: float,
) -> None:
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    normalized = all(getattr(args, "voxel_size_" + axis) == 1.0 for axis in "xyz")
    unit = (
        "cycles/reconstructed voxel" if normalized else "cycles/configured length unit"
    )
    names = ("fsc.png", "fsc-result.npz", "fsc.json")
    # Finish all serialization before replacing any previous result artifacts.
    with tempfile.TemporaryDirectory(prefix=".fsc-", dir=output) as temporary:
        staging = Path(temporary)
        plot_fsc(result, staging / names[0], f"Spatial frequency ({unit})")
        result.to_npz(staging / names[1])
        configuration = {
            key: value
            for key, value in vars(args).items()
            if not key.startswith("_") and key != "commands"
        }
        configuration.update(
            x_region=resolved["x_region"],
            y_region=resolved["y_region"],
            center_position_x=resolved["center_position_x"],
            center_position_z=resolved["center_position_z"],
            overall_angle_radians=resolved["overall_angle_radians"],
            backprojection_center_x=resolved["backprojection_center_x"],
            backprojection_center_z=resolved["backprojection_center_z"],
            detector_shape_yx=[resolved["detector_height"], resolved["detector_width"]],
            selected_detector_height=resolved["height"],
            backprojection_width=resolved["backprojection_width"],
            operation_mode="even_odd",
            output_mode="volume",
        )
        crossing = result.crossing_frequency
        document = {
            "configuration": configuration,
            "volume_shape_zyx": resolved["volume_shape_zyx"],
            "shell_geometry": {**asdict(result.geometry), "frequency_unit": unit},
            "runtime": {"total_execution_time_seconds": time.perf_counter() - started},
            "result": {
                "threshold_criterion": "half-bit",
                "crossing_frequency": crossing,
                "frequency_unit": unit,
                "status": (
                    "crossing_found"
                    if crossing is not None
                    else "no_crossing_in_sampled_band"
                ),
            },
            "outputs": {
                "plot": str(output / names[0]),
                "npz": str(output / names[1]),
                "json": str(output / names[2]),
            },
        }
        (staging / names[2]).write_text(
            json.dumps(document, indent=2, allow_nan=False) + "\n"
        )
        for name in names:
            os.replace(staging / name, output / name)
    if result.crossing_frequency is None:
        LOG.info("Half-bit FSC: no crossing in sampled band")
    else:
        LOG.info(
            "First half-bit FSC crossing: %.9g %s", result.crossing_frequency, unit
        )
    LOG.info("Saved FSC results to %s", output)


def run(args: argparse.Namespace) -> FSCResult:
    """Reconstruct a single region and return its device-reduced FSC result."""
    from gi.repository import Ufo

    started = time.perf_counter()
    try:
        resolved = resolve_inputs(args)
        geometry = resolve_geometry(resolved["volume_shape_zyx"], args)
        resources = Ufo.Resources.new()
        devices = resources.get_gpu_nodes()
        if args.gpu >= len(devices):
            raise ValueError(
                f"GPU index {args.gpu} unavailable; {len(devices)} visible device(s)"
            )
        gpu = devices[args.gpu]
        LOG.info("Selected GPU %d: %s", args.gpu, gpu.get_info(Ufo.GpuNodeInfo.NAME))
        # estimate_memory(args, resolved, geometry, _device_limits(gpu))
        graph, output = construct_graph(args, resolved, gpu)
        statistics = FSCShellStatistics.from_ufo(
            execute_graph(graph, output, resources)
        )
        result = FSCResult.from_statistics(statistics, geometry)
        save_outputs(args, resolved, result, started)
        return result
    except (ValueError, OSError, ImportError, OverflowError) as exc:
        raise RuntimeError(str(exc)) from exc
