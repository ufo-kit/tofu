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

__all__ = ["ArctanCompander", "Compander", "TanhCompander", "compress", "decompress"]


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

    @abstractmethod
    def compress(self, image):
        """Compress the dynamic range of *image*."""

    @abstractmethod
    def expand(self, image):
        """Expand a previously compressed *image*."""

    @abstractmethod
    def get_scale(self):
        """Get compander scale factor that maps input to quantized dynamic range."""

    def quantize(self, image):
        return image.astype(get_uint_dtype(self.dynamic_range))

    @abstractmethod
    def get_linearity_deviation(self, value):
        """Get deviation from linearity based on the compressing function in output dynamic range."""    


class TanhCompander(Compander):
    """Compress and expand values using a hyperbolic tangent curve."""

    def get_linearity_deviation(self, value):
        scaled = (value - self.center) * self.get_scale()
        return np.abs(scaled / 2 - np.tanh(scaled) / 2) * self.dynamic_range
    
    def get_scale(self):
        return 2 / (self.delta * self.dynamic_range)
    
    def compress(self, image):
        compressed = (1 + np.tanh((image - self.center) * self.get_scale())) * self.dynamic_range / 2

        return self.quantize(compressed)

    def expand(self, image):
        limit = np.nextafter(1.0, 0.0)
        scaled = np.clip(2 * image.astype(float) / self.dynamic_range - 1, -limit, limit)

        return np.arctanh(scaled) / self.get_scale() + self.center


class ArctanCompander(Compander):
    """Compress and expand values using an arctangent curve."""

    def get_linearity_deviation(self, value):
        scaled = (value - self.center) * self.get_scale()
        return np.abs(scaled / 2 - 2 / np.pi * np.arctan(scaled) / 2) * self.dynamic_range
    
    def get_scale(self):
        return 2 / (self.delta * self.dynamic_range)
    
    def compress(self, image):
        compressed = (1 + 2 / np.pi * np.arctan((image - self.center) * self.get_scale())) * self.dynamic_range / 2

        return self.quantize(compressed)

    def expand(self, image):
        limit = np.nextafter(np.pi / 2, 0.0)
        scaled = np.clip(
            (2 * image.astype(float) / self.dynamic_range - 1) * np.pi / 2,
            -limit,
            limit
        )

        return np.tan(scaled) / self.get_scale() + self.center


def optimize_delta_to_sigma(args, sigma, images):
    dynamic_range = 2 ** args.compress_bits - 1

    def obj_func(delta_to_sigma):
        delta = delta_to_sigma * sigma
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
            
        return np.mean(rmses) / sigma
    
    res = minimize_scalar(
        obj_func, bounds=(0.05, 10), method="bounded", options={"xatol": 0.05}
    )
    LOG.debug("Optimized delta to sigma: %.2f", res.x)
    LOG.debug("Optimized mean RMSE / sigma after quantization: %.2f", res.fun)
    
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
    j2k_psnr = get_psnr(dynamic_range, args.compress_j2k_rmse)
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
        # rmse_decoder.append(get_rmse(expanded, expanded_full))
        rmse_decoder.append(get_rmse(compressed, decoded))
        rmse_full.append(get_rmse(image, expanded_full))
        tifffile.imwrite("/mnt/fast3/compression/original.tif", image.astype(np.float32))
        tifffile.imwrite("/mnt/fast3/compression/expanded.tif", expanded.astype(np.float32))
        tifffile.imwrite("/mnt/fast3/compression/compressed.tif", expanded_full.astype(np.float32))

    LOG.debug("Center: %g", args.compress_center)
    LOG.debug("Delta grey level: %g (native data range)", args.compress_delta)
    LOG.debug("Noise sigma: %g (native data range)", sigma)
    LOG.debug("Quantized noise sigma: %g (grey levels)", sigma / args.compress_delta)
    LOG.debug("JPEG2000 PSNR: %.2f", j2k_psnr)
    LOG.debug(
        "Required dynamic range for given delta: %d",
        int(np.ceil(input_span / args.compress_delta)),
    )
    LOG.debug("Data sigma / compress delta: %.2f (should be > 1)", sigma / args.compress_delta)
    LOG.debug("Quantized span / soft data span: %.2f (should be > 1)", delta_span / input_span)
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
    LOG.debug("Mean RMSE / sigma after quantization: %.2f", np.mean(rmse_compander) / sigma)
    LOG.debug("JPEG2000 RMSE: %.2f / %.2f (target/measured)", args.compress_j2k_rmse, np.mean(rmse_decoder))
    LOG.debug("Final mean RMSE / sigma after all steps: %.2f", np.mean(rmse_full) / sigma)


def compress(args):
    dynamic_range = 2 ** args.compress_bits - 1
    images = read_image(
        args.images, image_start=args.image_start, image_step=args.image_step, allow_multi=True
    )
    sigma = None
    side = np.minimum(images.shape[-1], images.shape[-2])
    inner_side = int(side / np.sqrt(2))
    margin = side - inner_side
    images = images[
        :,
        (images.shape[1] - inner_side) // 2:-(images.shape[1] - inner_side) // 2,
        (images.shape[2] - inner_side) // 2:-(images.shape[2] - inner_side) // 2
    ]
    if args.compress_softmin is None or args.compress_softmax is None or args.compress_center is None:
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
        args.compress_delta = max(0.25, optimize_delta_to_sigma(args, sigma, images)) * sigma
        
    if not args.compress_j2k_rmse:
        sigma = np.median([get_sigma(image) for image in images])
        # j2k compression error max 1/2 of the quantized noise sigma
        args.compress_j2k_rmse = sigma / args.compress_delta / 2

    analyze(args, images)
    

def decompress(args):
    pass
