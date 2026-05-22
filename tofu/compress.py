import imagecodecs
import logging
import multiprocessing
import numpy as np
from abc import ABC, abstractmethod
from tofu.util import read_image
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
    "show_compander_results",
    "show_compander_tone_curves",
]


def get_uint_dtype(dynamic_range):
    """Return the smallest unsigned integer dtype that can store *dynamic_range*."""
    if dynamic_range <= np.iinfo(np.uint8).max:
        return np.uint8
    if dynamic_range <= np.iinfo(np.uint16).max:
        return np.uint16

    raise ValueError("data range does not fit into uint16")


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
        return np.rint(image).astype(get_uint_dtype(self.dynamic_range))

    def create_ufo_task(self):
        from gi.repository import Ufo
        pass


class TanhCompander(Compander):
    """Compress and expand values using a hyperbolic tangent curve."""

    def forward(self, scaled):
        return np.tanh(scaled)

    def inverse(self, scaled):
        limit = np.nextafter(1.0, 0.0)

        return np.arctanh(np.clip(scaled, -limit, limit))


class ArctanCompander(Compander):
    """Compress and expand values using an arctangent curve."""

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

    def forward(self, scaled):
        return scaled / np.sqrt(1 + scaled ** 2)

    def inverse(self, scaled):
        limit = np.nextafter(1.0, 0.0)
        scaled = np.clip(scaled, -limit, limit)

        return scaled / np.sqrt(1 - scaled ** 2)


class ClipCompander(Compander):
    """Compress and expand values using clipping."""

    def forward(self, scaled):
        return np.clip(scaled, -1, 1)

    def inverse(self, scaled):
        limit = np.nextafter(1.0, 0.0)

        return np.clip(scaled, -limit, limit)


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


def show_compander_results(args, image, colormap="gray", show=True):
    """Show compressed *image* results for every compander."""
    import matplotlib.pyplot as plt

    companders = get_companders(args)
    fig, axes = plt.subplots(
        2,
        2,
        figsize=(8, 8),
        constrained_layout=True,
        squeeze=False
    )
    axes = axes.ravel()
    color_image = None

    for ax, (name, compander) in zip(axes, companders):
        compressed = compander.compress(image)
        color_image = ax.imshow(
            compressed,
            cmap=colormap,
            vmin=0,
            vmax=compander.dynamic_range
        )
        ax.set_title(name)
        ax.axis("off")

    fig.colorbar(color_image, ax=axes.tolist())

    if show:
        plt.show()

    return fig


def show_compander_tone_curves(args, hardmin, hardmax, num_points=1024, show=True):
    """Show tone curves for every compander."""
    import matplotlib.pyplot as plt

    companders = get_companders(args)

    values = np.linspace(hardmin, hardmax, num=num_points)
    soft_mask = (args.compress_softmin <= values) & (values <= args.compress_softmax)
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
    ax.axvline(args.compress_softmin, color="0.4", linestyle=":", linewidth=1)
    ax.axvline(
        args.compress_softmax,
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
    LOG.debug("Compression info")
    sigma = np.median([get_sigma(image) for image in images])
    input_span = args.compress_softmax - args.compress_softmin
    dynamic_range = 2 ** args.compress_bits - 1
    delta_span = dynamic_range * args.compress_delta

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
    import tifffile
    for image in images:
        compressed = compander.compress(image)
        encoded = imagecodecs.jpeg2k_encode(compressed, numthreads=CPU_COUNT, level=j2k_psnr)
        decoded = imagecodecs.jpeg2k_decode(encoded, numthreads=CPU_COUNT)
        expanded = compander.expand(compressed)
        expanded_full = compander.expand(decoded)

        rmse_compander.append(get_rmse(image, expanded))
        rmse_decoder.append(get_rmse(expanded, expanded_full))
        # rmse_decoder.append(get_rmse(compressed, decoded))
        rmse_full.append(get_rmse(image, expanded_full))
        tifffile.imwrite("/mnt/fast3/compression/original.tif", image.astype(np.float32))
        tifffile.imwrite("/mnt/fast3/compression/expanded.tif", expanded.astype(np.float32))
        tifffile.imwrite(
            "/mnt/fast3/compression/compressed-orig.tif",
            expanded_full.astype(np.float32)
        )
        # tifffile.imwrite(
        #     "/mnt/fast3/compression/compressed.tif",
        #     compressed.astype(get_uint_dtype(dynamic_range)),
        #     compression="jpeg2000",
        #     compressionargs={"level": j2k_psnr}
        # )

    LOG.debug("Center: %g", args.compress_center)
    LOG.debug("Delta grey level: %g (native data range)", args.compress_delta)
    LOG.debug("Noise sigma: %g (native data range)", sigma)
    LOG.debug("JPEG2000 RMSE: %g", args.compress_j2k_rmse)
    LOG.debug("JPEG2000 PSNR: %.2f", j2k_psnr)
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
        compander.get_linearity_deviation(args.compress_softmin),
        compander.get_linearity_deviation(args.compress_softmax),
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


def compress(args):
    images = read_image(
        args.images, args=args, allow_multi=True
    )
    sigma = None
    if (
        args.compress_softmin is None
        or args.compress_softmax is None
        or args.compress_center is None
    ):
        softmin, center, softmax = np.percentile(
            images,
            (args.compress_input_percentile, 50, 100 - args.compress_input_percentile)
        )
        if args.compress_center is None:
            args.compress_center = center
        if args.compress_softmin is None:
            args.compress_softmin = softmin
        if args.compress_softmax is None:
            args.compress_softmax = softmax

    if not args.compress_delta:
        LOG.debug("delta / sigma not specified, optimizing...")
        sigma = np.median([get_sigma(image) for image in images])
        # delta is max 1/4 of the noise sigma
        args.compress_delta = max(sigma / 4, optimize_delta_to_sigma(args, sigma, images))
    if not args.compress_j2k_rmse:
        sigma = np.median([get_sigma(image) for image in images])
        # j2k RMSE wrt original noise sigma is 1/4
        args.compress_j2k_rmse = sigma / 4

    analyze(args, images)
    # show_compander_results(args, images[0], show=False)
    # hardmin, hardmax = np.percentile(images, (0, 100))
    # show_compander_tone_curves(args, hardmin, hardmax, show=True)


def decompress(args):
    pass
