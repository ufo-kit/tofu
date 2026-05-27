import imagecodecs
import logging
import multiprocessing
import numpy as np
from abc import ABC, abstractmethod
from gi.repository import Ufo
from tofu.denoise import create_denoising_pipeline
from tofu.tasks import get_task, get_writer
from tofu.util import read_image, run_scheduler, set_node_props, setup_read_task
from tofu.metrics import get_sigma, get_psnr, get_rmse
from scipy.optimize import minimize_scalar

LOG = logging.getLogger(__name__)
CPU_COUNT = multiprocessing.cpu_count()

__all__ = [
    "ArctanCompander",
    "ClipCompander",
    "Compander",
    "RecipSqRootCompander",
    "TanhCompander",
    "compress",
    "decompress",
    "get_companders",
    "get_uint_dtype",
    "show_compander_results_pyqtgraph",
    "show_compander_results",
    "show_compander_tone_curves_pyqtgraph",
    "show_compander_tone_curves",
]


def get_uint_dtype(dynamic_range):
    """Return the smallest unsigned integer dtype that can store *dynamic_range*."""
    if dynamic_range <= np.iinfo(np.uint8).max:
        return np.uint8
    if dynamic_range <= np.iinfo(np.uint16).max:
        return np.uint16

    raise ValueError("data range does not fit into uint16")


def run_qt_app(app):
    """Run a Qt application across PyQt versions."""
    if hasattr(app, 'exec'):
        return app.exec()

    return app.exec_()


class Compander(ABC):
    """Base class for reversible dynamic range companders."""

    def __init__(self, center, delta, dynamic_range):
        self.center = center
        self.delta = delta
        self.dynamic_range = dynamic_range

    @property
    def scale_factor(self):
        """Compander scale factor that maps input to quantized dynamic range."""
        return 2 / (self.delta * self.dynamic_range)

    def normalize(self, image):
        """Normalize input values around the compander center."""
        return (image - self.center) * self.scale_factor

    def denormalize(self, scaled):
        """Denormalize scaled values back to input data units."""
        return scaled / self.scale_factor + self.center

    def scale(self, image):
        """Scale the dynamic range of *image* for the compressing function."""
        return self.forward(self.normalize(image))

    def compress(self, image, quantize=True):
        """Compress the dynamic range of *image*."""
        compressed = (1 + self.scale(image)) / 2 * self.dynamic_range
        if quantize:
            compressed = self.quantize(compressed)

        return compressed

    def expand(self, image):
        """Expand a previously compressed *image*."""
        scaled = 2 * image.astype(float) / self.dynamic_range - 1

        return self.denormalize(self.inverse(scaled))

    def get_linearity_deviation(self, value):
        """Get deviation from linearity in output dynamic range."""
        scaled = self.normalize(value)
        deviation = scaled / 2 - self.forward(scaled) / 2

        return np.abs(deviation) * self.dynamic_range

    @abstractmethod
    def forward(self, scaled):
        """Apply the compander curve to normalized values."""

    @abstractmethod
    def inverse(self, scaled):
        """Apply the inverse compander curve to scaled output values."""

    def quantize(self, image):
        """Quantize *image* to the compander output dtype."""
        return np.rint(image).astype(get_uint_dtype(self.dynamic_range))

    def create_ufo_task(self, direction='forward', processing_node=None):
        """Create a UFO compand task from this compander."""
        task = get_task('compand', processing_node=processing_node)
        task.props.center = self.center
        task.props.delta = self.delta
        task.props.bits = int(np.log2(self.dynamic_range + 1))
        task.props.direction = direction
        task.props.type = self.ufo_type

        return task


class TanhCompander(Compander):
    """Compress and expand values using a hyperbolic tangent curve."""

    ufo_type = 'tanh'

    def forward(self, scaled):
        return np.tanh(scaled)

    def inverse(self, scaled):
        limit = np.nextafter(1.0, 0.0)

        return np.arctanh(np.clip(scaled, -limit, limit))


class ArctanCompander(Compander):
    """Compress and expand values using an arctangent curve."""

    ufo_type = 'arctan'

    @property
    def scale_factor(self):
        """Get compander scale factor that maps input to quantized dynamic range."""
        return np.pi / (self.delta * self.dynamic_range)

    def forward(self, scaled):
        return 2 / np.pi * np.arctan(scaled)

    def inverse(self, scaled):
        limit = np.nextafter(np.pi / 2, 0.0)
        scaled = np.clip(scaled * np.pi / 2, -limit, limit)

        return np.tan(scaled)


class RecipSqRootCompander(Compander):
    """Compress and expand values using the x / sqrt(1 + x^2) function."""

    ufo_type = 'recip_sqrt'

    def forward(self, scaled):
        return scaled / np.sqrt(1 + scaled ** 2)

    def inverse(self, scaled):
        limit = np.nextafter(1.0, 0.0)
        scaled = np.clip(scaled, -limit, limit)

        return scaled / np.sqrt(1 - scaled ** 2)


class ClipCompander(Compander):
    """Compress and expand values using clipping."""

    ufo_type = 'clip'

    def forward(self, scaled):
        return np.clip(scaled, -1, 1)

    def inverse(self, scaled):
        limit = np.nextafter(1.0, 0.0)

        return np.clip(scaled, -limit, limit)


COMPANDER_TYPES = {
    "tanh": TanhCompander,
    "arctan": ArctanCompander,
    "recip_sqrt": RecipSqRootCompander,
    "clip": ClipCompander,
}


def get_companders(args):
    """Return all available companders initialized from compression arguments."""
    dynamic_range = 2 ** args.compress_bits - 1

    return [
        ("tanh", TanhCompander(args.compress_center, args.compress_delta, dynamic_range)),
        ("arctan", ArctanCompander(args.compress_center, args.compress_delta, dynamic_range)),
        (
            "reciprocal square root",
            RecipSqRootCompander(args.compress_center, args.compress_delta, dynamic_range)
        ),
        ("clip", ClipCompander(args.compress_center, args.compress_delta, dynamic_range)),
    ]


def show_compander_results(args, image, hardmin=None, hardmax=None, colormap="gray", show=True):
    """Show compressed *image* result for the selected compander."""
    import matplotlib.pyplot as plt
    from matplotlib.widgets import RangeSlider

    compander_name = getattr(args, 'compress_compander', 'tanh')
    dynamic_range = 2 ** args.compress_bits - 1
    compander = COMPANDER_TYPES[compander_name](
        args.compress_center,
        args.compress_delta,
        dynamic_range
    )
    compressed = compander.compress(image)
    compressed_min = np.min(compressed)
    compressed_max = np.max(compressed)
    compressed_softmin, compressed_softmax = np.percentile(compressed, (0.01, 99.99))
    if compressed_min == compressed_max:
        compressed_max = compressed_min + 1
    if compressed_softmin == compressed_softmax:
        compressed_softmax = compressed_max

    fig = plt.figure(figsize=(9, 8))
    image_rect = [0.01, 0.07, 0.9, 0.89]
    fig_width, fig_height = fig.get_size_inches()
    image_aspect = compressed.shape[1] / compressed.shape[0]
    rect_aspect = image_rect[2] * fig_width / (image_rect[3] * fig_height)
    if image_aspect > rect_aspect:
        ax_width = image_rect[2]
        ax_height = ax_width * fig_width / (image_aspect * fig_height)
        ax_left = image_rect[0]
        ax_bottom = image_rect[1] + (image_rect[3] - ax_height) / 2
    else:
        ax_height = image_rect[3]
        ax_width = ax_height * fig_height * image_aspect / fig_width
        ax_left = image_rect[0] + (image_rect[2] - ax_width) / 2
        ax_bottom = image_rect[1]
    ax = fig.add_axes([ax_left, ax_bottom, ax_width, ax_height])
    colorbar_ax = fig.add_axes([0.93, 0.07, 0.015, 0.89])
    color_image = ax.imshow(
        compressed,
        cmap=colormap,
        vmin=compressed_softmin,
        vmax=compressed_softmax
    )
    ax.set_title(compander_name, pad=2)
    ax.axis("off")

    colorbar = fig.colorbar(color_image, cax=colorbar_ax)
    slider_ax = fig.add_axes([0.18, 0.025, 0.64, 0.012])
    slider = RangeSlider(
        slider_ax,
        "vmin/vmax",
        compressed_min,
        compressed_max,
        valinit=(compressed_softmin, compressed_softmax),
        valfmt="%g"
    )

    def update_limits(limits):
        vmin, vmax = limits
        color_image.set_clim(vmin, vmax)
        colorbar.update_normal(color_image)
        fig.canvas.draw_idle()

    slider.on_changed(update_limits)
    fig._tofu_colorbar = colorbar
    fig._tofu_vrange_slider = slider

    if show:
        plt.show()

    return fig


def show_compander_results_pyqtgraph(args, image, hardmin=None, hardmax=None, colormap="gray", show=True):
    """Show compressed *image* result for the selected compander using pyqtgraph."""
    import pyqtgraph
    from PyQt5 import QtCore, QtWidgets

    pyqtgraph.setConfigOptions(antialias=True, imageAxisOrder='row-major')

    compander_name = getattr(args, 'compress_compander', 'tanh')
    dynamic_range = 2 ** args.compress_bits - 1
    compander = COMPANDER_TYPES[compander_name](
        args.compress_center,
        args.compress_delta,
        dynamic_range
    )
    compressed = compander.compress(image)
    compressed_softmin, compressed_softmax = np.percentile(compressed, (0.01, 99.99))

    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QtWidgets.QApplication([])

    view = pyqtgraph.ImageView(view=pyqtgraph.PlotItem())
    view.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    view.setWindowTitle("{} compander".format(compander_name))
    view.getView().setAspectLocked(True)
    view.setImage(
        compressed,
        autoRange=True,
        autoLevels=False,
        levels=(compressed_softmin, compressed_softmax)
    )

    if hasattr(view.ui, 'roiBtn'):
        view.ui.roiBtn.hide()
    if hasattr(view.ui, 'menuBtn'):
        view.ui.menuBtn.hide()

    image_item = view.getImageItem()
    plot_item = view.getView()
    default_title = "{} compander".format(compander_name)
    plot_item.setTitle(default_title)

    def update_mouse_position(event):
        if not image_item.sceneBoundingRect().contains(event):
            plot_item.setTitle(default_title)
            return

        pos = image_item.mapFromScene(event)
        x = int(pos.x() + 0.5)
        y = int(pos.y() + 0.5)
        if 0 <= y < compressed.shape[0] and 0 <= x < compressed.shape[1]:
            plot_item.setTitle("x={}, y={}, I={:g}".format(x, y, compressed[y, x]))
        else:
            plot_item.setTitle(default_title)

    mouse_proxy = pyqtgraph.SignalProxy(
        image_item.scene().sigMouseMoved,
        rateLimit=60,
        slot=lambda event: update_mouse_position(event[0])
    )

    view._tofu_qapp = app
    view._tofu_mouse_proxy = mouse_proxy
    if show:
        view.show()
        if owns_app:
            run_qt_app(app)

    return view


def show_compander_tone_curves_pyqtgraph(
        args, softmin, softmax, hardmin, hardmax, num_points=1024, show=True):
    """Show tone curves for every compander using pyqtgraph."""
    import pyqtgraph
    from PyQt5 import QtCore, QtWidgets

    pyqtgraph.setConfigOptions(antialias=True, background='w', foreground='k')

    app = QtWidgets.QApplication.instance()
    owns_app = app is None
    if owns_app:
        app = QtWidgets.QApplication([])

    companders = get_companders(args)
    values = np.linspace(hardmin, hardmax, num=num_points)
    soft_mask = (softmin <= values) & (values <= softmax)
    curves = [(name, compander.compress(values, quantize=False)) for name, compander in companders]
    y_min = min(np.min(curve) for _, curve in curves)
    y_max = max(np.max(curve) for _, curve in curves)
    if y_min == y_max:
        y_max = y_min + 1

    plot = pyqtgraph.PlotWidget(title="Compander tone curves")
    plot.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    plot.setWindowTitle("Compander tone curves")
    plot.setLabel("bottom", "Input value")
    plot.setLabel("left", "Quantized value")
    plot.showGrid(x=False, y=False)
    plot.addLegend()

    for index, (name, curve) in enumerate(curves):
        color = pyqtgraph.intColor(index, hues=len(curves), minValue=80, maxValue=200)
        plot.plot(values, curve, pen=pyqtgraph.mkPen(color, width=1))
        if np.any(soft_mask):
            plot.plot(
                values[soft_mask],
                curve[soft_mask],
                pen=pyqtgraph.mkPen(color, width=3),
                name=name
            )

    center_pen = pyqtgraph.mkPen((0, 0, 0), width=3, style=QtCore.Qt.DashLine)
    soft_pen = pyqtgraph.mkPen((40, 110, 220), width=2, style=QtCore.Qt.DotLine)
    hard_pen = pyqtgraph.mkPen((180, 60, 40), width=2, style=QtCore.Qt.DashLine)
    plot.plot([args.compress_center, args.compress_center], [y_min, y_max], pen=center_pen, name="center")
    plot.plot([softmin, softmin], [y_min, y_max], pen=soft_pen, name="softmin/softmax")
    plot.plot([softmax, softmax], [y_min, y_max], pen=soft_pen)
    plot.plot([hardmin, hardmin], [y_min, y_max], pen=hard_pen, name="hardmin/hardmax")
    plot.plot([hardmax, hardmax], [y_min, y_max], pen=hard_pen)

    plot.setXRange(hardmin, hardmax, padding=0.02)
    plot.setYRange(y_min, y_max, padding=0.05)

    def update_mouse_position(event):
        plot_item = plot.getPlotItem()
        if not plot_item.sceneBoundingRect().contains(event):
            plot_item.setTitle("Compander tone curves")
            return

        pos = plot_item.vb.mapSceneToView(event)
        x = pos.x()
        y = pos.y()
        if hardmin <= x <= hardmax and y_min <= y <= y_max:
            plot_item.setTitle("x={:g}, y={:g}".format(x, y))
        else:
            plot_item.setTitle("Compander tone curves")

    mouse_proxy = pyqtgraph.SignalProxy(
        plot.scene().sigMouseMoved,
        rateLimit=60,
        slot=lambda event: update_mouse_position(event[0])
    )

    plot._tofu_qapp = app
    plot._tofu_mouse_proxy = mouse_proxy

    if show:
        plot.show()
        if owns_app:
            run_qt_app(app)

    return plot


def show_compander_tone_curves(args, softmin, softmax, hardmin, hardmax, num_points=1024, show=True):
    """Show tone curves for every compander."""
    import matplotlib.pyplot as plt

    companders = get_companders(args)

    values = np.linspace(hardmin, hardmax, num=num_points)
    soft_mask = (softmin <= values) & (values <= softmax)
    fig, ax = plt.subplots(figsize=(8, 6), constrained_layout=True)

    for name, compander in companders:
        line, = ax.plot(values, compander.compress(values, quantize=False), alpha=0.5)
        color = line.get_color()
        if np.any(soft_mask):
            ax.plot(
                values[soft_mask],
                compander.compress(values[soft_mask], quantize=False),
                color=color,
                label=name,
                linewidth=2
            )

    ax.axvline(
        args.compress_center,
        color="black",
        linestyle="-.",
        linewidth=1,
        label="center"
    )
    ax.axvline(
        softmin,
        color="0.4",
        linestyle=":",
        linewidth=1
    )
    ax.axvline(
        softmax,
        color="0.4",
        linestyle=":",
        linewidth=1,
        label="softmin/softmax"
    )
    ax.axvline(
        hardmin,
        color="0.2",
        linestyle="--",
        linewidth=1,
    )
    ax.axvline(
        hardmax,
        color="0.2",
        linestyle="--",
        linewidth=1,
        label="hardmin/hardmax"
    )
    ax.set_xlabel("Input value")
    ax.set_ylabel("Quantized value")
    ax.grid(True)
    ax.legend()

    if show:
        plt.show()

    return fig


def optimize_delta_to_sigma(args, sigma, images):
    """Find a compression delta that keeps quantization RMSE near *sigma*."""
    dynamic_range = 2 ** args.compress_bits - 1

    def obj_func(delta):
        compander = TanhCompander(
            args.compress_center,
            delta,
            dynamic_range
        )

        rmses = []
        for image in images:
            compressed = compander.compress(image).astype(get_uint_dtype(dynamic_range))
            reco = compander.expand(compressed)
            rmses.append(get_rmse(image, reco))

        return np.mean(rmses)

    res = minimize_scalar(
        obj_func,
        bounds=(sigma / 20, 10 * sigma),
        method="bounded",
        options={"xatol": sigma / 20}
    )
    LOG.debug("Optimized delta / sigma: %.2f", res.x / sigma)
    LOG.debug("Optimized RMSE / sigma after quantization: %.2f", res.fun / sigma)

    return res.x


def analyze(args, images):
    """Log compression quality estimates for *images*."""
    LOG.debug("Compression info")
    sigma = np.median([get_sigma(image) for image in images])
    dynamic_range = 2 ** args.compress_bits - 1
    delta_span = dynamic_range * args.compress_delta
    hardmin, softmin, softmax, hardmax = np.percentile(
        images,
        (0, args.compress_input_percentile, 100 - args.compress_input_percentile, 100)
    )
    input_span = hardmax - hardmin

    compander = TanhCompander(
        args.compress_center,
        args.compress_delta,
        dynamic_range
    )
    # Dynamic range rescaled to physical range
    j2k_psnr = get_psnr(args.compress_delta * dynamic_range, args.compress_j2k_rmse)
    rmse_compander = []
    rmse_decoder = []
    rmse_full = []
    for image in images:
        compressed = compander.compress(image)
        encoded = imagecodecs.jpeg2k_encode(compressed, numthreads=CPU_COUNT, level=j2k_psnr)
        decoded = imagecodecs.jpeg2k_decode(encoded, numthreads=CPU_COUNT)
        expanded = compander.expand(compressed)
        expanded_full = compander.expand(decoded)

        rmse_compander.append(get_rmse(image, expanded))
        rmse_decoder.append(get_rmse(expanded, expanded_full))
        rmse_full.append(get_rmse(image, expanded_full))

    LOG.debug("Center: %g", args.compress_center)
    LOG.debug("hardmin: %g", hardmin)
    LOG.debug("hardmax: %g", hardmax)
    LOG.debug("softmin: %g", softmin)
    LOG.debug("softmax: %g", softmax)
    LOG.debug("Delta grey level: %g", args.compress_delta)
    LOG.debug("JPEG2000 RMSE: %g", args.compress_j2k_rmse)
    LOG.debug(
        "Required dynamic range for given delta: %d",
        int(np.ceil(input_span / args.compress_delta)),
    )
    LOG.debug(
        "Data sigma / compress delta: %.2f (should be > 1)",
        sigma / args.compress_delta
    )
    LOG.debug(
        "Dynamic range / soft data dynamic range: %.2f (should be > 1)",
        delta_span / input_span
    )
    max_soft_deviation = max(
        compander.get_linearity_deviation(softmin),
        compander.get_linearity_deviation(softmax),
    )
    hardmin, hardmax = np.percentile(images, (0, 100))
    max_hard_deviation = max(
        compander.get_linearity_deviation(hardmin),
        compander.get_linearity_deviation(hardmax),
    )
    LOG.debug(
        "Max linearity deviation within soft limits: %.2f (%.3f %% of output dynamic range)",
        max_soft_deviation,
        max_soft_deviation / dynamic_range * 100
    )
    LOG.debug(
        "Max linearity deviation within image range: %.2f (%.3f %% of output dynamic range)",
        max_hard_deviation,
        max_hard_deviation / dynamic_range * 100
    )
    LOG.debug("RMSE / sigma of quantization: %.2f", np.mean(rmse_compander) / sigma)
    LOG.debug(
        "RMSE / sigma of JPEG2000: %.2f / %.2f (measured / target)",
        np.mean(rmse_decoder) / sigma,
        args.compress_j2k_rmse / sigma
    )
    LOG.debug("RMSE / sigma of all steps: %.2f", np.mean(rmse_full) / sigma)

    if args.compress_visualize:
        from PyQt5 import QtWidgets

        app = QtWidgets.QApplication.instance()
        owns_app = app is None
        if owns_app:
            app = QtWidgets.QApplication([])

        image_view = show_compander_results_pyqtgraph(
            args,
            images[images.shape[0] // 2],
            hardmin,
            hardmax,
            show=False
        )
        tone_curves = show_compander_tone_curves_pyqtgraph(
            args,
            softmin,
            softmax,
            hardmin,
            hardmax,
            show=False
        )
        image_view.show()
        tone_curves.show()
        if owns_app:
            run_qt_app(app)


def determine_compression_parameters(args):
    """Determine missing compression parameters from *args.images*."""
    images = None
    sigma = None

    if (
        not args.compress_delta
        or not args.compress_j2k_rmse
        or not args.compress_center
        or getattr(args, 'compress_analyze', False)
    ):
        images = read_image(args.images, args=args, allow_multi=True)
        args.compress_center = np.percentile(images, 50)
        LOG.debug("--compress-center calculated: %g", args.compress_center)

    if not args.compress_delta:
        sigma = np.median([get_sigma(image) for image in images])
        # delta is max 1/4 of the noise sigma
        args.compress_delta = max(sigma / 4, optimize_delta_to_sigma(args, sigma, images))
        LOG.debug("--compress-delta calculated: %g", args.compress_delta)
    if not args.compress_j2k_rmse:
        sigma = np.median([get_sigma(image) for image in images])
        # j2k RMSE wrt original noise sigma is 1/4
        args.compress_j2k_rmse = sigma / 4
        LOG.debug("--compress-j2k-rmse calculated using 1 / 4 of noise sigma: %g", args.compress_j2k_rmse)

    if sigma:
        LOG.debug("Noise sigma: %g", sigma)

    args._compression_images = images


def create_compression_pipeline(args, direction='forward', processing_node=None):
    """Create and configure a UFO companding task."""
    if direction == 'forward':
        determine_compression_parameters(args)
    elif args.compress_center is None or args.compress_delta is None:
        raise RuntimeError('--compress-center and --compress-delta must be specified')

    # Dynamic range rescaled to physical range
    j2k_psnr = get_psnr(args.compress_delta * (2 ** args.compress_bits - 1), args.compress_j2k_rmse)
    LOG.info("JPEG2000 PSNR: %.2f", j2k_psnr)

    dynamic_range = 2 ** args.compress_bits - 1
    compander_cls = COMPANDER_TYPES[getattr(args, 'compress_compander', 'tanh')]

    return compander_cls(
        args.compress_center,
        args.compress_delta,
        dynamic_range
    ).create_ufo_task(direction=direction, processing_node=processing_node)


def compress(args):
    """Run image compression using a UFO companding pipeline."""
    compand = create_compression_pipeline(args)

    if args.compress_analyze:
        analyze(args, args._compression_images)
        return

    graph = Ufo.TaskGraph()
    sched = Ufo.Scheduler()

    reader = get_task('read')
    set_node_props(reader, args)
    if not args.images:
        raise RuntimeError('--images not set')
    setup_read_task(reader, args.images, args)

    out_task = get_writer(args)
    if hasattr(out_task.props, 'bits'):
        out_task.props.bits = args.compress_bits
    if hasattr(out_task.props, 'tiff_jpeg2000'):
        out_task.props.tiff_jpeg2000 = True
    if hasattr(out_task.props, 'level'):
        out_task.props.level = int(round(
            get_psnr(
                args.compress_delta * (2 ** args.compress_bits - 1),
                args.compress_j2k_rmse
            )
        ))

    current = reader
    if getattr(args, 'denoise', False):
        denoise = create_denoising_pipeline(args)
        graph.connect_nodes(current, denoise)
        current = denoise

    graph.connect_nodes(current, compand)
    graph.connect_nodes(compand, out_task)

    run_scheduler(sched, graph)


def decompress(args):
    """Run image decompression using a UFO companding pipeline."""
    if args.compress_center is None:
        raise RuntimeError('--compress-center must be specified')
    if args.compress_delta is None:
        raise RuntimeError('--compress-delta must be specified')

    graph = Ufo.TaskGraph()
    sched = Ufo.Scheduler()

    reader = get_task('read')
    set_node_props(reader, args)
    if not args.images:
        raise RuntimeError('--images not set')
    setup_read_task(reader, args.images, args)

    out_task = get_writer(args)
    current = create_compression_pipeline(args, direction='backward')
    graph.connect_nodes(reader, current)
    graph.connect_nodes(current, out_task)

    run_scheduler(sched, graph)
