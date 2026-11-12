"""Fourier Ring Correlation"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import glob
import json
import logging
import math
from pathlib import Path
from threading import Thread
import time
from typing import Any

import numpy as np

from tofu.correlation import (
    first_curve_crossing,
    geometric_bound,
    information_threshold,
    normalize,
)
from tofu.fsc import FSCShellStatistics

LOG = logging.getLogger(__name__)
PLOT_STYLE = "darkgrid"
PLOT_CONTEXT = "notebook"
PLOT_FIGSIZE = (7.2, 4.5)  # Per subplot
PLOT_DPI = 180
PLOT_CMAP = "viridis"
PLOT_INVALID_COLOR = "dimgray"
PLOT_LIMITS = (-1, 1)
PLOT_LINE_COLOR = "tab:blue"
PLOT_THRESHOLD_COLOR = "tab:orange"
PLOT_BOUND_COLOR = "tab:green"
PLOT_WINDOW_MARKER_SIZE = 60
ARCHIVE_VERSION = 2


@dataclass(frozen=True)
class RingGeometry:
    delta_k_xy: tuple[float, float]
    ring_width: float
    max_frequency: float
    number_of_bins: int


def resolve_geometry(shape: tuple[int, int], args: argparse.Namespace) -> RingGeometry:
    sizes = (args.pixel_size_x, args.pixel_size_y)
    if not all(math.isfinite(v) and v > 0 for v in sizes):
        raise ValueError("Pixel sizes must be finite and positive")
    if not all(
        math.isfinite(v) and v >= 0 for v in (args.ring_width, args.max_frequency)
    ):
        raise ValueError(
            "Ring width and maximum frequency must be finite and nonnegative"
        )
    delta = tuple(1.0 / (n * d) for n, d in zip(reversed(shape), sizes))
    with np.errstate(over="ignore", under="ignore"):
        width = float(np.float32(args.ring_width or max(delta)))
    maximum = args.max_frequency or min(1 / (2 * d) for d in sizes)
    if not math.isfinite(width) or width <= 0 or not math.isfinite(maximum):
        raise ValueError("Ring geometry exceeds the supported numerical range")
    ratio = maximum / width
    if not math.isfinite(ratio):
        raise ValueError("Ring geometry exceeds the supported numerical range")
    bins = math.floor(ratio + 16 * np.finfo(float).eps * max(1, abs(ratio)))
    if not 1 <= bins <= 2**32 - 1:
        raise ValueError("Ring geometry must produce at least one supported bin")
    return RingGeometry(delta, width, maximum, bins)


def select_pairs(number: int, num_corr: int | None) -> np.ndarray:
    """Return zero-based original frame indices; ties round upwards."""
    available = number // 2
    count = available if num_corr is None else num_corr
    if not 1 <= count <= available:
        raise ValueError(f"--num-corr must be in 1..{available}")
    if count == 1:
        selected = np.array([available // 2], dtype=np.int64)
    else:
        # Exact integer rounding, without float linspace duplicates.
        selected = np.array(
            [
                (2 * j * (available - 1) + count - 1) // (2 * (count - 1))
                for j in range(count)
            ],
            dtype=np.int64,
        )
    return np.column_stack((2 * selected, 2 * selected + 1))


def resolve_inputs(args: argparse.Namespace) -> tuple[TiffInput, np.ndarray, str, int]:
    """Inspect the selected source, preserving explicit image and pair order."""
    if args.img1 or args.img2:
        if not (args.img1 and args.img2) or args.projections:
            raise ValueError("Provide both --img1 and --img2, without --projections")
        if any(v is not None for v in (args.pair, args.num_corr, args.number)):
            raise ValueError("Image inputs cannot use --pair, --num-corr or --number")
        images = []
        for path in (args.img1, args.img2):
            if not Path(path).is_file():
                raise ValueError("--img1 and --img2 must each name one TIFF file")
            image = TiffInput.inspect(path)
            if image.frames != 1:
                raise ValueError("--img1 and --img2 require single-frame TIFFs")
            images.append(image)
        if images[0].shape != images[1].shape:
            raise ValueError("The two images must have equal dimensions")
        if Path(args.img1).samefile(args.img2):
            raise ValueError("--img1 and --img2 must be distinct files")
        source = TiffInput(
            (images[0].files[0], images[1].files[0]), (1, 1), images[0].shape
        )
        return source, np.array([[0, 1]], dtype=np.int64), "images", 2
    if not args.projections:
        raise ValueError("Provide --projections or both --img1 and --img2")
    source = TiffInput.inspect(args.projections)
    number = source.frames if args.number is None else args.number
    if not 2 <= number <= source.frames:
        raise ValueError(f"--number must be in 2..{source.frames}")
    if args.pair is not None:
        if args.num_corr is not None:
            raise ValueError("--pair and --num-corr are mutually exclusive")
        i, j = args.pair
        if i == j or not (0 <= i < number and 0 <= j < number):
            raise ValueError(f"--pair requires distinct indices in 0..{number - 1}")
        return source, np.array([[i, j]], dtype=np.int64), "pair", number
    return source, select_pairs(number, args.num_corr), "sweep", number


def resolve_regions(
    shape: tuple[int, int], args: argparse.Namespace, input_mode: str
) -> tuple[tuple[int, int, int, int], np.ndarray, str, tuple[int, int]]:
    """Return outer ROI, row-major detector rectangles, mode and grid shape."""
    h, w = shape
    x, y = args.x, args.y
    width = w - x if args.width is None else args.width
    height = h - y if args.height is None else args.height
    if min(x, y) < 0 or min(width, height) < 1 or x + width > w or y + height > h:
        raise ValueError("ROI must be a positive rectangle inside every detector frame")
    roi = (x, y, width, height)
    if args.region_grid is not None and args.window_size is not None:
        raise ValueError("--region-grid and --window-size are mutually exclusive")
    if args.window_stride is not None and args.window_size is None:
        raise ValueError("--window-stride requires --window-size")
    if args.region_grid is not None:
        rows, cols = args.region_grid
        if min(rows, cols) <= 0 or height % rows or width % cols:
            raise ValueError("Positive grid dimensions must divide the ROI exactly")
        wh, ww = height // rows, width // cols
        mode, sy, sx = "grid", wh, ww
    elif args.window_size is not None:
        if input_mode == "sweep":
            raise ValueError("Sliding windows require --pair or --img1/--img2")
        wh, ww = args.window_size
        sy, sx = args.window_stride or args.window_size
        if min(wh, ww, sy, sx) <= 0 or wh > height or ww > width:
            raise ValueError(
                "Positive window dimensions must fit inside the ROI; strides must be positive"
            )
        rows, cols = (height - wh) // sy + 1, (width - ww) // sx + 1
        mode = "windows"
    else:
        return roi, np.array([roi], dtype=np.int64), "whole", (1, 1)
    regions = np.array(
        [
            (x + col * sx, y + row * sy, ww, wh)
            for row in range(rows)
            for col in range(cols)
        ],
        dtype=np.int64,
    )
    return roi, regions, mode, (rows, cols)


@dataclass(frozen=True)
class TiffInput:
    files: tuple[str, ...]
    lengths: tuple[int, ...]
    shape: tuple[int, int]

    @property
    def frames(self) -> int:
        return sum(self.lengths)

    @classmethod
    def inspect(cls, path: str) -> TiffInput:
        from tifffile import TiffFile

        pattern = str(Path(path) / "*") if Path(path).is_dir() else path
        files = tuple(
            sorted(
                str(Path(p).resolve())
                for p in glob.glob(pattern)
                if Path(p).is_file() and Path(p).suffix.lower() in (".tif", ".tiff")
            )
        )
        if not files:
            raise ValueError(f"No TIFF files found: {path}")
        shape = None
        lengths = []
        for filename in files:
            with TiffFile(filename) as tif:
                if not len(tif.pages):
                    raise ValueError(f"Empty TIFF: {filename}")
                lengths.append(len(tif.pages))
                for page in tif.pages:
                    if len(page.shape) != 2 or page.dtype.kind not in "uif":
                        raise ValueError(
                            f"Expected real grayscale TIFF pages: {filename}"
                        )
                    if shape is not None and tuple(page.shape) != shape:
                        raise ValueError(f"TIFF frame dimensions differ: {filename}")
                    shape = tuple(page.shape)
        return cls(files, tuple(lengths), shape)

    def selected_frames(self, indices: np.ndarray, roi: tuple[int, int, int, int]):
        from tifffile import TiffFile

        ends = np.cumsum(self.lengths)
        current, opened = -1, None
        x, y, width, height = roi
        try:
            for index in indices:
                file_index = int(np.searchsorted(ends, index, side="right"))
                if file_index != current:
                    if opened is not None:
                        opened.close()
                    opened = TiffFile(self.files[file_index])
                    current = file_index
                page = int(index - (ends[file_index - 1] if file_index else 0))
                image = opened.pages[page].asarray()
                yield np.ascontiguousarray(
                    image[y : y + height, x : x + width], dtype=np.float32
                )
        finally:
            if opened is not None:
                opened.close()


@dataclass(frozen=True)
class FRCResult:
    pair_indices: np.ndarray  # zero-based original frames, shape (M, 2)
    frc: np.ndarray  # (M, R, B), float64 from compact float32 statistics
    k_bin: np.ndarray
    n_ring: np.ndarray
    threshold: np.ndarray
    geometric_bound: np.ndarray
    statistics: np.ndarray  # (M, R, 7, B)
    geometry: RingGeometry
    threshold_criterion: str
    pixel_size_xy: tuple[float, float]
    input_mode: str
    regions_xywh: np.ndarray
    spatial_mode: str
    grid_shape: tuple[int, int]
    outer_roi_xywh: tuple[int, int, int, int] | None

    @classmethod
    def from_statistics(
        cls,
        pairs,
        rows,
        geometry,
        criterion,
        pixel_size_xy=(1.0, 1.0),
        *,
        input_mode="sweep",
        regions_xywh=None,
        spatial_mode="whole",
        grid_shape=(1, 1),
        outer_roi_xywh=None,
    ):
        rows = np.asarray(rows, dtype=np.float32)
        pairs = np.asarray(pairs, dtype=np.int64)
        if pairs.ndim != 2 or pairs.shape[1] != 2 or len(pairs) == 0:
            raise ValueError("Expected a nonempty array of projection pairs")
        if (
            rows.ndim != 4
            or rows.shape != (len(pairs), rows.shape[1], 7, geometry.number_of_bins)
            or rows.shape[1] == 0
        ):
            raise ValueError("Unexpected FRC output shape")
        regions = (
            np.asarray(regions_xywh, dtype=np.int64)
            if regions_xywh is not None
            else np.empty((0, 4), dtype=np.int64)
        )
        # Legacy archives lack ROI coordinates. Do not invent detector positions.
        if regions.shape != (rows.shape[1], 4) and not (
            regions.shape == (0, 4) and rows.shape[1] == 1 and spatial_mode == "whole"
        ):
            raise ValueError("Region coordinates do not match the statistics")
        if input_mode not in ("sweep", "pair", "images") or spatial_mode not in (
            "whole",
            "grid",
            "windows",
        ):
            raise ValueError("Unknown input or spatial mode")
        if math.prod(grid_shape) != rows.shape[1]:
            raise ValueError("Grid shape does not match region count")
        if input_mode != "sweep" and len(pairs) != 1:
            raise ValueError(
                "An explicit pair must contain exactly one correlation pair"
            )
        if spatial_mode == "whole" and rows.shape[1] != 1:
            raise ValueError("Whole-ROI mode must contain exactly one region")
        if spatial_mode == "windows" and (
            input_mode == "sweep" or outer_roi_xywh is None
        ):
            raise ValueError("Window results require an explicit pair and outer ROI")
        statistics = [
            FSCShellStatistics.from_ufo(row)
            for row in rows.reshape(-1, 7, geometry.number_of_bins)
        ]
        first = statistics[0]
        expected = np.arange(geometry.number_of_bins, dtype=np.float32) * np.float32(
            geometry.ring_width
        )
        if not np.array_equal(first.k_bin, expected):
            raise ValueError("Output ring centres differ from resolved geometry")
        for item in statistics[1:]:
            if not (
                np.array_equal(item.k_bin, first.k_bin)
                and np.array_equal(item.n_shell, first.n_shell)
            ):
                raise ValueError("Ring geometry changed between pairs or regions")
        return cls(
            np.asarray(pairs, dtype=np.int64),
            np.stack(
                [
                    normalize(s.cross_sum, s.power_1_sum, s.power_2_sum, s.n_shell)
                    for s in statistics
                ]
            ).reshape(rows.shape[:2] + (geometry.number_of_bins,)),
            first.k_bin,
            first.n_shell,
            information_threshold(first.n_shell, criterion),
            np.stack([geometric_bound(s) for s in statistics]).reshape(
                rows.shape[:2] + (geometry.number_of_bins,)
            ),
            rows,
            geometry,
            criterion,
            tuple(pixel_size_xy),
            input_mode,
            regions,
            spatial_mode,
            tuple(grid_shape),
            tuple(outer_roi_xywh) if outer_roi_xywh is not None else None,
        )

    @property
    def crossing_frequencies(self) -> list[list[float | None]]:
        return [
            [first_curve_crossing(self.k_bin, curve, self.threshold) for curve in pair]
            for pair in self.frc
        ]

    def to_npz(self, path: str | Path) -> None:
        np.savez_compressed(
            path,
            archive_version=ARCHIVE_VERSION,
            index_base=0,
            input_mode=self.input_mode,
            spatial_mode=self.spatial_mode,
            grid_shape=self.grid_shape,
            regions_xywh=self.regions_xywh,
            outer_roi_xywh=np.asarray(self.outer_roi_xywh or (), dtype=np.int64),
            pair_indices=self.pair_indices,
            frc=self.frc,
            k_bin=self.k_bin,
            n_ring=self.n_ring,
            threshold=self.threshold,
            geometric_bound=self.geometric_bound,
            statistics=self.statistics,
            geometry=json.dumps(asdict(self.geometry)),
            threshold_criterion=self.threshold_criterion,
            pixel_size_xy=self.pixel_size_xy,
        )

    @classmethod
    def from_npz(cls, path: str | Path) -> FRCResult:
        with np.load(path, allow_pickle=False) as data:
            geometry = json.loads(str(data["geometry"]))
            geometry["delta_k_xy"] = tuple(geometry["delta_k_xy"])
            legacy = "archive_version" not in data
            if not legacy and (
                int(data["archive_version"]) != ARCHIVE_VERSION
                or int(data["index_base"]) != 0
            ):
                raise ValueError("Unsupported FRC archive version or index base")
            metadata = (
                {}
                if legacy
                else {
                    "input_mode": str(data["input_mode"]),
                    "spatial_mode": str(data["spatial_mode"]),
                    "grid_shape": tuple(data["grid_shape"].tolist()),
                    "regions_xywh": data["regions_xywh"],
                    "outer_roi_xywh": tuple(data["outer_roi_xywh"].tolist()) or None,
                }
            )
            return cls.from_statistics(
                data["pair_indices"] - 1 if legacy else data["pair_indices"],
                data["statistics"][:, None, :, :] if legacy else data["statistics"],
                RingGeometry(**geometry),
                str(data["threshold_criterion"]),
                data["pixel_size_xy"],
                **metadata,
            )


def plot_frc(result: FRCResult, path: str | Path) -> None:
    """Plot saved results without importing UFO or creating GPU resources."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import seaborn as sns

    label = (
        "Spatial frequency (cycles/detector pixel)"
        if result.pixel_size_xy == (1.0, 1.0)
        else "Spatial frequency (cycles/configured length unit)"
    )
    crossings = np.asarray(result.crossing_frequencies, dtype=float)
    with sns.axes_style(PLOT_STYLE), sns.plotting_context(PLOT_CONTEXT):
        if result.spatial_mode == "windows":
            figure, axis = plt.subplots(figsize=PLOT_FIGSIZE, constrained_layout=True)
            regions = result.regions_xywh
            centres = regions[:, :2] + regions[:, 2:] / 2
            values = crossings[0]
            valid = np.isfinite(values)
            points = axis.scatter(
                centres[valid, 0],
                centres[valid, 1],
                c=values[valid],
                cmap=PLOT_CMAP,
                vmin=0,
                vmax=result.geometry.max_frequency,
                marker="s",
                s=PLOT_WINDOW_MARKER_SIZE,
            )
            if np.any(~valid):
                axis.scatter(
                    centres[~valid, 0],
                    centres[~valid, 1],
                    marker="x",
                    color=PLOT_INVALID_COLOR,
                    s=PLOT_WINDOW_MARKER_SIZE,
                    label="No downward crossing",
                )
                axis.legend()
            x, y, width, height = result.outer_roi_xywh
            axis.set(
                xlim=(x, x + width),
                ylim=(y + height, y),
                xlabel="Detector X (zero-based)",
                ylabel="Detector Y (zero-based)",
                title="Window-centre crossing frequencies (diagnostic)",
                aspect="equal",
            )
            figure.colorbar(points, ax=axis, label=label)
        else:
            rows, cols = result.grid_shape
            figure, axes = plt.subplots(
                rows,
                cols,
                squeeze=False,
                sharex=True,
                sharey=True,
                figsize=(PLOT_FIGSIZE[0] * cols, PLOT_FIGSIZE[1] * rows),
                constrained_layout=True,
            )
            for region, axis in enumerate(axes.flat):
                if result.input_mode == "sweep":
                    positions = result.pair_indices.mean(axis=1)
                    values = crossings[:, region]
                    axis.plot(
                        positions,
                        values,
                        ".-",
                        color=PLOT_LINE_COLOR,
                        label=result.threshold_criterion.capitalize() + " crossing",
                    )
                    missing = ~np.isfinite(values)
                    if np.any(missing):
                        # Axes-coordinate height explicitly separates missing values
                        # from a measured zero-frequency crossing.
                        axis.scatter(
                            positions[missing],
                            np.full(missing.sum(), 0.04),
                            transform=axis.get_xaxis_transform(),
                            marker="x",
                            color=PLOT_INVALID_COLOR,
                            label="No downward crossing",
                        )
                    axis.set(
                        ylim=(0, result.geometry.max_frequency),
                        ylabel=label,
                        xlabel="Projection-pair midpoint (zero-based)",
                    )
                else:
                    axis.plot(
                        result.k_bin,
                        result.frc[0, region],
                        color=PLOT_LINE_COLOR,
                        label="FRC",
                    )
                    axis.plot(
                        result.k_bin,
                        result.threshold,
                        "-.",
                        color=PLOT_THRESHOLD_COLOR,
                        label=result.threshold_criterion.capitalize() + " reference",
                    )
                    axis.plot(
                        result.k_bin,
                        result.geometric_bound[0, region],
                        ":",
                        color=PLOT_BOUND_COLOR,
                        label="Geometric lower bound",
                    )
                    axis.axhline(0, color="gray", linewidth=0.6)
                    axis.set(
                        xlim=(0, result.geometry.max_frequency),
                        ylim=PLOT_LIMITS,
                        xlabel=label,
                        ylabel="Correlation",
                    )
                title = (
                    "First downward crossing (diagnostic)"
                    if result.input_mode == "sweep"
                    else f"Diagnostic FRC: pair {result.pair_indices[0].tolist()}"
                )
                if len(result.regions_xywh):
                    title += f"\nRegion {region}: x,y,w,h={tuple(result.regions_xywh[region])}"
                axis.set_title(title)
                axis.legend()
        figure.savefig(path, dpi=PLOT_DPI)
        plt.close(figure)


def construct_graph(args, roi, inputs, gpu):
    from gi.repository import Ufo
    from tofu.tasks import get_task

    graph, source, output = Ufo.TaskGraph(), Ufo.InputTask(), Ufo.OutputTask()
    output.set_property("num-dims", 2)
    x, y, width, height = roi

    def task(name, **props):
        return get_task(name, processing_node=gpu, **props)

    def calibration(name):
        # A temporary manifest directory supplied by run() contains only the
        # inspected files, in the same order, including mixed .tif/.tiff suffixes.
        reader = task("read", path=inputs[name][1], y=y, height=height, y_step=1)
        crop = task("crop", x=x, y=0, width=width, height=height)
        graph.connect_nodes(reader, crop)
        if args.reduction_mode == "median":
            stack = task("stack", number=inputs[name][0].frames)
            reduced = task("flatten", mode="median")
            graph.connect_nodes(crop, stack)
            graph.connect_nodes(stack, reduced)
        else:
            reduced = task("average")
            graph.connect_nodes(crop, reduced)
        return reduced

    current = source
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
        graph.connect_nodes_full(calibration("flats"), correction, 2)
        current = correction
    elif args.absorptivity or args.fix_nan_and_inf:
        expression = "-log(v)" if args.absorptivity else "v"
        if args.fix_nan_and_inf:
            expression = f"isfinite({expression}) ? ({expression}) : 0.0f"
        clean = task("calculate", expression=expression)
        graph.connect_nodes(current, clean)
        current = clean
    fft = task("fft", dimensions=2, auto_zeropadding=False)
    core = task(
        "frc-core",
        pixel_size_x=args.pixel_size_x,
        pixel_size_y=args.pixel_size_y,
        ring_width=args.ring_width,
        max_frequency=args.max_frequency,
    )
    for before, after in ((current, fft), (fft, core), (core, output)):
        graph.connect_nodes(before, after)
    return graph, source, output


def execute_pairs(graph, source, output, resources, frames, count):
    """Recycle one input buffer on generation; never wait for pair output to feed.

    UFO reductors fetch a lookahead before emitting. The input's generated signal
    runs after its host buffer has been copied and returned, so recycling here
    supplies lookahead without unbounded buffering or blocked producer threads.
    """
    from gi.repository import Ufo
    import ufo.numpy

    scheduler = Ufo.FixedScheduler()
    scheduler.set_resources(resources)
    scheduler.set_property("expand", False)
    failures = []

    def execute():
        try:
            scheduler.run(graph)
        except BaseException as exc:
            failures.append(exc)
            output.emit("inputs-stopped")

    worker = Thread(target=execute, name="tofu-frc-scheduler", daemon=True)
    rows = []
    stopped = False
    sent = 1

    def feed_next(task):
        nonlocal sent, stopped
        if stopped:
            return
        if sent == 2 * count:
            source.stop()
            stopped = True
            return
        try:
            buffer = task.get_input_buffer()  # Already returned by generate().
            ufo.numpy.fromarray_inplace(buffer, next(frames))
            task.release_input_buffer(buffer)
            sent += 1
        except BaseException as exc:
            failures.append(exc)
            source.stop()
            stopped = True

    handler = source.connect("generated", feed_next)
    owned_buffer = None
    try:
        owned_buffer = ufo.numpy.fromarray(next(frames))
        source.release_input_buffer(owned_buffer)
        worker.start()
        while True:
            buffer = output.get_output_buffer()
            if buffer is None:
                break
            try:
                rows.append(ufo.numpy.asarray(buffer).copy())
            finally:
                output.release_output_buffer(buffer)
        worker.join()
        if failures:
            raise RuntimeError(f"FRC pipeline failed: {failures[0]}") from failures[0]
        if len(rows) != count:
            raise RuntimeError(f"Expected {count} FRC results; received {len(rows)}")
    except BaseException:
        if not stopped:
            stopped = True
            source.stop()  # Wake the input generator before aborting.
        scheduler.abort()
        if worker.ident is not None:
            worker.join()
        raise
    finally:
        frames.close()
        source.disconnect(handler)
    return np.stack(rows)


def run(args: argparse.Namespace) -> FRCResult:
    from gi.repository import GLib, Ufo
    import tempfile

    started = time.perf_counter()
    try:
        projections, pairs, input_mode, number = resolve_inputs(args)
        roi, regions, spatial_mode, grid_shape = resolve_regions(
            projections.shape, args, input_mode
        )
        geometry = resolve_geometry((int(regions[0, 3]), int(regions[0, 2])), args)
        if bool(args.flats) != bool(args.darks):
            raise ValueError("Provide both --flats and --darks, or neither")
        calibrations = {}
        for name in ("flats", "darks"):
            if getattr(args, name):
                info = TiffInput.inspect(getattr(args, name))
                if info.shape != projections.shape:
                    raise ValueError(f"{name} dimensions must match projections")
                calibrations[name] = info
        resources = Ufo.Resources.new()
        devices = resources.get_gpu_nodes()
        if not 0 <= args.gpu < len(devices):
            raise ValueError(f"--gpu must select one of {len(devices)} visible GPUs")
        gpu = devices[args.gpu]
        directory = Path(args.output)
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tofu-frc-") as temporary:
            inputs = {}
            for name, info in calibrations.items():
                manifest = Path(temporary) / name
                manifest.mkdir()
                for index, filename in enumerate(info.files):
                    (manifest / f"{index:09d}.tif").symlink_to(filename)
                inputs[name] = (info, str(manifest / "*.tif"))
            region_rows = []
            for region in regions:
                rectangle = tuple(int(v) for v in region)
                graph, source, output = construct_graph(args, rectangle, inputs, gpu)
                try:
                    region_rows.append(
                        execute_pairs(
                            graph,
                            source,
                            output,
                            resources,
                            projections.selected_frames(pairs.ravel(), rectangle),
                            len(pairs),
                        )
                    )
                finally:
                    del graph, source, output
            rows = np.stack(region_rows, axis=1)
        result = FRCResult.from_statistics(
            pairs,
            rows,
            geometry,
            args.threshold_criterion,
            (args.pixel_size_x, args.pixel_size_y),
            input_mode=input_mode,
            regions_xywh=regions,
            spatial_mode=spatial_mode,
            grid_shape=grid_shape,
            outer_roi_xywh=roi,
        )
        result.to_npz(directory / "frc.npz")
        configuration = {
            k: v
            for k, v in vars(args).items()
            if not k.startswith("_") and k != "commands" and v is not None
        }
        document = {
            "archive_version": ARCHIVE_VERSION,
            "index_base": 0,
            "configuration": configuration,
            "resolved": {
                "number": number,
                "available_frames": projections.frames,
                "num_corr": len(pairs),
                "input_mode": input_mode,
                "spatial_mode": spatial_mode,
                "grid_shape": grid_shape,
                "regions_xywh": regions.tolist(),
                "roi_xywh": roi,
                "projection_files": projections.files,
                "geometry": asdict(geometry),
                "device": str(gpu.get_info(Ufo.GpuNodeInfo.NAME)),
            },
            "result": {
                "interpretation": "diagnostic, not spatial resolution",
                "threshold_criterion": args.threshold_criterion,
                "count_convention": "full-spectrum ring coefficients",
                "pair_indices": result.pair_indices.tolist(),
                "crossing_frequencies": result.crossing_frequencies,
            },
            "artifacts": {"npz": "frc.npz"},
            "runtime": {"total_seconds": time.perf_counter() - started},
        }
        if input_mode == "sweep" and number % 2:
            document["resolved"]["ignored_final_frame"] = number - 1
        metadata = directory / "frc.json"
        metadata.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
        plot_frc(result, directory / "frc.png")
        document["artifacts"]["plot"] = "frc.png"
        document["runtime"]["total_seconds"] = time.perf_counter() - started
        metadata.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
        LOG.info(
            "Saved %d diagnostic FRC curves to %s", len(pairs) * len(regions), directory
        )
        return result
    except (ValueError, OSError, ImportError, OverflowError, GLib.Error) as exc:
        raise RuntimeError(str(exc)) from exc
