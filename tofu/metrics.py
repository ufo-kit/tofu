import numpy as np
from skimage.restoration import estimate_sigma


def _as_float_array(image):
    """Return *image* as a floating-point NumPy array."""
    return np.asarray(image, dtype=np.float64)


def _check_matching_shapes(reference, image):
    """Raise an error if *reference* and *image* do not have the same shape."""
    if reference.shape != image.shape:
        raise ValueError(
            "Images must have the same shape, got {} and {}".format(
                reference.shape, image.shape
            )
        )


def get_mse(reference, image):
    """Return the mean squared error between a reference image and an image."""
    reference = _as_float_array(reference)
    image = _as_float_array(image)
    _check_matching_shapes(reference, image)

    return np.mean((reference - image) ** 2)


def get_rmse(reference, image):
    """Return the root mean squared error between a reference image and an image."""
    return np.sqrt(get_mse(reference, image))


def get_psnr(data_range, rmse):
    """Compute the peak signal-to-noise ratio from *data_range* and *rmse*."""
    return 20 * np.log10(data_range / rmse)


def get_sigma(image):
    """Return the standard deviation of image noise."""
    return estimate_sigma(image)
