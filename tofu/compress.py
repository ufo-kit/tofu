from abc import ABC, abstractmethod
import logging

import numpy as np
from tofu.util import read_image
from tofu.metrics import get_sigma, get_psnr, get_rmse

LOG = logging.getLogger(__name__)

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

    def __init__(self, center, input_span, quantized_span, output_percentile, dynamic_range):
        self.center = center
        self.input_span = input_span
        self.quantized_span = quantized_span
        self.output_percentile = output_percentile
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


class TanhCompander(Compander):
    """Compress and expand values using a hyperbolic tangent curve."""

    def get_scale(self):
        return 2 * np.arctanh(self.output_percentile) / self.quantized_span
    
    def compress(self, image):
        return 0.5 * (1 + np.tanh((image - self.center) * self.get_scale())) * self.dynamic_range

    def expand(self, image):
        limit = np.nextafter(1.0, 0.0)
        scaled = np.clip(2 * image.astype(float) / self.dynamic_range - 1, -limit, limit)

        return np.arctanh(scaled) / self.get_scale() + self.center


class ArctanCompander(Compander):
    """Compress and expand values using an arctangent curve."""

    def compress(self, image):
        normalized = self._normalize(image)
        compressed = np.arctan(self.strength * normalized) / np.arctan(self.strength)

        return self._denormalize(compressed)

    def expand(self, image):
        normalized = self._normalize(image)
        expanded = np.tan(normalized * np.arctan(self.strength)) / self.strength

        return self._denormalize(expanded)


def analyze(args, minimum, maximum):
    input_span = maximum - minimum
    dynamic_range = 2 ** args.compress_bits - 1
    delta_span = dynamic_range * args.compress_delta

    LOG.debug("Compression info")
    LOG.debug("Center: %g", args.compress_center)
    LOG.debug("Noise sigma: %g", args.compress_sigma)
    LOG.debug("Compress delta: %g", args.compress_delta)
    LOG.debug(
        "Required dynamic range for given delta: %d",
        int(np.ceil(input_span / args.compress_delta)),
    )
    LOG.debug("Data span for percentile %g: %g", args.compress_input_percentile, input_span)
    LOG.debug(
        "Possible span for dynamic range %d and compress delta %g: %g",
        dynamic_range,
        args.compress_delta,
        delta_span
    )
    LOG.debug("Data sigma / compress delta: %.2f (should be > 1)", args.compress_sigma / args.compress_delta)
    LOG.debug("Possible span / data span: %.2f (should be > 1)", delta_span / input_span)


def compress(args):
    dynamic_range = 2 ** args.compress_bits - 1
    images = read_image(
        args.images, image_start=args.image_start, image_step=args.image_step, allow_multi=True
    )
    side = np.minimum(images.shape[-1], images.shape[-2])
    inner_side = int(side / np.sqrt(2))
    margin = side - inner_side
    images = images[
        :,
        (images.shape[1] - inner_side) // 2:-(images.shape[1] - inner_side) // 2,
        (images.shape[2] - inner_side) // 2:-(images.shape[2] - inner_side) // 2
    ]
    minimum, center, maximum = np.percentile(
        images,
        (args.compress_input_percentile, 50, 100 - args.compress_input_percentile)
    )
    if not args.compress_sigma:
        args.compress_sigma = np.median([get_sigma(image) for image in images])

    if args.compress_center is None:
        args.compress_center = center

    if not args.compress_delta:
        args.compress_delta = args.compress_sigma / 4

    analyze(args, minimum, maximum)

    compander = TanhCompander(
        args.compress_center,
        maximum - minimum,
        args.compress_delta * dynamic_range,
        args.compress_output_percentile / 100,
        dynamic_range
    )
    im = images[0]
    #compressed = compander.compress(im)
    #expanded = compander.expand(compressed)
    #print(get_rmse(im, expanded) / args.compress_sigma)
    linear_range = np.arange(dynamic_range + 1)
    input_range = (linear_range - (dynamic_range + 1) / 2.0) * args.compress_delta
    compressed_range = compander.compress(input_range)

    print(np.tanh(args.compress_delta * dynamic_range * compander.get_scale() / 2))
    print(compander.compress(args.compress_delta * dynamic_range / 2))
    print(compander.compress(input_range))
    import matplotlib.pyplot as plt
    plt.plot(compressed_range)
    plt.show()


def decompress(args):
    pass
