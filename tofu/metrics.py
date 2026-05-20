import numpy as np
from skimage.restoration import estimate_sigma
from scipy.ndimage import correlate, convolve
from numpy.fft import fft2, ifft2, fftshift


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


def get_pearson_correlation(image, kernel, fast=True):
    """Get Pearson correlation coefficient between *image* and *kernel*. It is normalized to (-1,
    1).
    """
    image = image.astype(float)
    kernel = kernel - kernel.mean()
    box_kernel = np.ones(kernel.shape, dtype=float) / kernel.size

    if fast:
        hk, wk = kernel.shape
        hkh, wkh = hk // 2, wk // 2
        addition = (hk % 2, wk % 2)
        padded = np.pad(image, ((hk // 2, hk // 2), (wk // 2, wk // 2)), mode="reflect")
        h, w = padded.shape
        kernel_padding = ((h - hk) // 2, (w - wk) // 2)
        padded_kernel = fftshift(
            np.pad(
                kernel,
                (
                    (kernel_padding[0] + addition[0], kernel_padding[0]),
                    (kernel_padding[1] + addition[1], kernel_padding[1]),
                ),
                mode="constant"
            )
        )

        padded_box_kernel = fftshift(
            np.pad(
                box_kernel,
                (
                    (kernel_padding[0] + addition[0], kernel_padding[0]),
                    (kernel_padding[1] + addition[1], kernel_padding[1]),
                ),
                mode="constant"
            )
        )

        # Normalizations by local image means and standard deviations can be realized by additional
        # convolutions with a box function.
        corr = ifft2(fft2(padded) * np.conj(fft2(padded_kernel))).real[hkh:-hkh, wkh:-wkh]
        im_means = ifft2(fft2(padded) * fft2(padded_box_kernel)).real[hkh:-hkh, wkh:-wkh]
        im_squares = ifft2(fft2(padded ** 2) * fft2(padded_box_kernel)).real[hkh:-hkh, wkh:-wkh]
    else:
        # Mainly for debugging
        corr = correlate(image, kernel, mode="reflect")
        im_means = convolve(image.astype(float), box_kernel)
        im_squares = convolve(image.astype(float) ** 2, box_kernel)

    im_std = np.sqrt(im_squares - im_means ** 2)

    return corr / (im_std * np.std(kernel) * kernel.size)
