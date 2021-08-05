import argparse
import glob
import multiprocessing
import os
import time
import numpy as np
from functools import partial
from tofu.util import read_image
from scipy.stats import skew, kurtosis


def sum_abs_gradient(data):
    """Sum of absolute gradients."""
    return np.sum(np.abs(np.gradient(data)))


def mad(data):
    """Median absolute deviation."""
    return np.median(np.abs(data - np.median(data)))


def abs_sum(data):
    """Sum of the absolute values."""
    return np.sum(np.abs(data))


def entropy(data, bins=256):
    """Image entropy."""
    hist, bins = np.histogram(data, bins=bins)
    hist = hist.astype(np.float)
    hist /= hist.sum()
    valid = np.where(hist > 0)

    return -np.sum(np.dot(hist[valid], np.log2(hist[valid])))


def inverted(func, *args, **kwargs):
    """Return -func(*args, **kwargs)."""
    return -func(*args, **kwargs)


def filter_data(data, fwhm=32.):
    """Filter low frequencies in 1D *data* (needed when the axis is far away by axis evaluation).
    *fwhm* is the FWHM of the gaussian used to filter out low frequencies in real space. The window
    is then computed as fft(1 - gauss).
    """
    mean = np.mean(data)
    sigma = fwhm / (2 * np.sqrt(2 * np.log(2)))
    # We compute the gaussian in Fourier space, so convert sigma first
    f_sigma = 1. / (2 * np.pi * sigma)
    x = np.fft.fftfreq(len(data))
    fltr = 1 - np.exp(- x ** 2 / (2 * f_sigma ** 2))

    return np.fft.ifft(np.fft.fft(data) * fltr).real + mean


METRICS_1D = {'mean': np.mean,
              'std': np.std,
              'skew': skew,
              'kurtosis': kurtosis,
              'mad': mad,
              'asum': abs_sum,
              'min': np.min,
              'max': np.max,
              'entropy': entropy}


METRICS_2D = {'sag': sum_abs_gradient}

for key in list(METRICS_1D):
    METRICS_1D['m' + key] = partial(inverted, METRICS_1D[key])

for key in list(METRICS_2D):
    METRICS_2D['m' + key] = partial(inverted, METRICS_2D[key])

#for key in METRICS_1D.keys():
#    METRICS_1D['m' + key] = partial(inverted, METRICS_1D[key])


#for key in METRICS_2D.keys():
#    METRICS_2D['m' + key] = partial(inverted, METRICS_2D[key])


def evaluate(image, metrics_1d=None, metrics_2d=None, global_min=None, global_max=None,
             metrics_1d_kwargs=None, blur_fwhm=None):
    """Evaluate *metrics_1d* which work on a flattened image and *metrics_2d* in an *image* which
    can either be a file path or an imageIf the metrics are None all the default ones are used.
    *global_min* and *global_max* are the mean extrema of the whole sequence used to cut off outlier
    values. Extrema are used only by 1d metrics. *metrics_1d_kwargs* are additional keyword
    arguments passed to the functions, they are specified in dictioinary {func_name: kwargs}.
    """
    if metrics_1d is None:
        metrics_1d = METRICS_1D
    if metrics_2d is None:
        metrics_2d = METRICS_2D
    results = {}

    if type(image) == str:
        image = read_image(image)
    if blur_fwhm:
        from scipy.ndimage import gaussian_filter
        image = gaussian_filter(image, blur_fwhm / (2 * np.sqrt(2 * np.log(2))))

    if global_min is None or global_max is None:
        flattened = image.flatten()
    else:
        # Use global cutoff
        flattened = image[np.where((image >= global_min) & (image <= global_max))]

    if metrics_1d is not None:
        for metric in metrics_1d:
            kwargs = {}
            if metrics_1d_kwargs and metric in metrics_1d_kwargs:
                kwargs = metrics_1d_kwargs[metric]
            results[metric] = metrics_1d[metric](flattened, **kwargs)
    if metrics_2d is not None:
        for metric in metrics_2d:
            results[metric] = metrics_2d[metric](image)

    return results


def evaluate_metrics(images, out_prefix, *args, **kwargs):
    """Evaluate many *images* which are either file paths or images. *out_prefix* is the metric
    results file prefix. Metric names and file extension are appended to it. *args* and *kwargs* are
    passed to :func:`evaluate`. Except for *fwhm* in *kwargs* which is used to filter low
    frequencies from the results.
    """
    fwhm = kwargs.pop('fwhm') if 'fwhm' in kwargs else None
    pool = multiprocessing.Pool(processes=multiprocessing.cpu_count())
    exec_func = partial(evaluate, *args, **kwargs)
    results = pool.map(exec_func, images)
    merged = {}

    for metric in results[0].keys():
        merged[metric] = np.array([result[metric] for result in results])
        if fwhm:
            # Filter out low frequencies
            merged[metric] = filter_data(merged[metric], fwhm=fwhm)
        if out_prefix is not None:
            path = out_prefix + '_' + metric + '.txt'
            np.savetxt(path, merged[metric], fmt='%g')

    return merged


def process(names, num_images_for_stats=0, metric_names=None, out_prefix=None, fwhm=None,
            metrcs_1d_kwargs=None, blur_fwhm=None):
    """Process many files given by *names*. *out_prefix* is the output file prefix where the metric
    results will be written to. *fwhm* is used to filter our low frequencies from the results.
    *metrics_1d_kwargs* are additional keyword arguments passed to the functions, they are specified
    in dictioinary {func_name: kwargs}.
    """
    if num_images_for_stats:
        if num_images_for_stats == -1:
            num_images_for_stats = len(names)
        extrema_metrics = {'min': np.min, 'max': np.max}
        extrema = evaluate_metrics(names[:num_images_for_stats], None,
                                   metrics_1d=extrema_metrics, fwhm=fwhm,
                                   blur_fwhm=blur_fwhm)
        global_min = np.mean(extrema['min'])
        global_max = np.mean(extrema['max'])
    else:
        global_min = global_max = None

    metrics_1d, metrics_2d = make_metrics(metric_names)

    return evaluate_metrics(names, out_prefix,
                            metrics_1d=metrics_1d, metrics_2d=metrics_2d,
                            global_min=global_min, global_max=global_max, fwhm=fwhm,
                            metrics_1d_kwargs=metrcs_1d_kwargs,
                            blur_fwhm=blur_fwhm)


def main():
    args = parse_args()
    names = sorted(glob.glob(args.input))
    if args.dims == 2:
        axis_length = int(np.sqrt(len(names)))
        size_str = '{} x {}'.format(axis_length, axis_length)
    else:
        axis_length = len(names)
        size_str = str(axis_length)
    print ('Data size: {}'.format(size_str))
    kwargs = {'entropy': {'bins': args.entropy_num_bins}}
    for key in kwargs.keys():
        kwargs['m' + key] = kwargs[key]

    st = time.time()
    results = process(names, num_images_for_stats=args.num_images_for_stats,
                      metric_names=args.metrics, fwhm=args.fwhm, metrcs_1d_kwargs=kwargs,
                      blur_fwhm=args.blur_fwhm)
    if args.verbose:
        print ('Duration: {} s'.format(time.time() - st))

    x_data = y_data = None
    for metric, data in results.iteritems():
        if x_data is None:
            x_data = construct_range(args.x_from, args.x_to, len(data), unit=args.x_unit)
            y_data = construct_range(args.y_from, args.y_to, len(data), unit=args.y_unit)
        write(args.output, metric, data, axis_length, x_data=x_data, y_data=y_data,
              save_raw=args.save_raw, save_txt=args.save_txt, save_plot=args.save_plot)
        argmax = np.argmax(data)
        if args.dims == 2:
            argmax = np.unravel_index(argmax, (axis_length, axis_length))
            y_argmax = y_data[argmax[0]].magnitude
            x_argmax = x_data[argmax[1]].magnitude
            retval = (x_argmax, y_argmax)
        else:
            x_argmax = x_data[argmax].magnitude
            retval = x_argmax

    print(retval)


def write(out_dir, metric, data, axis_length, x_data=None, y_data=None,
          save_raw=False, save_txt=False, save_plot=False):
    out_path = os.path.join(out_dir, metric)
    if not os.path.exists(out_dir):
        os.makedirs(out_dir, mode=0o755)

    if axis_length == len(data):
        # 1D
        if save_raw:
            np.save(out_path + '.npy', data)
        if save_plot:
            write_1d_plot(out_path, data, metric, x_data=x_data)
    else:
        reshaped = data.reshape(axis_length, axis_length)
        if save_raw:
            write_libtiff(out_path + '_raw' + '.tif', reshaped.astype(np.float32))
        if save_plot:
            write_2d_plot(out_path, reshaped, metric, x_data=x_data, y_data=y_data)

    if save_txt:
        data = np.array((x_data.magnitude, data))
        # Convenient to be read by pgfplots
        np.savetxt(out_path + '.txt', data.T, fmt='%g', delimiter='\t', comments='', header='x\ty')


def write_1d_plot(out_path, data, metric, x_data=None):
    from matplotlib import pyplot as plt
    plt.figure()
    if x_data is not None:
        plt.plot(x_data.magnitude, data)
        plt.xlabel(x_data.units)
    else:
        plt.plot(data)
    plt.title(metric)
    plt.grid()
    plt.savefig(out_path + '.tif')
    plt.close()


def write_2d_plot(out_path, data, metric, x_data=None, y_data=None):
    from matplotlib import pyplot as plt, cm
    plt.figure()
    plt.imshow(data, cmap=cm.gray)
    if x_data is not None:
        x_from = x_data[0].magnitude
        x_to = x_data[-1].magnitude
        num_x_ticks = min(data.shape[1], 9)
        x_locs = np.linspace(-0.5, data.shape[1] - 0.5, num_x_ticks)
        x_labels = np.linspace(x_from, x_to, num_x_ticks)
        plt.xticks(x_locs, x_labels)
        plt.xlabel(x_data.units)
    if y_data is not None:
        y_from = y_data[0].magnitude
        y_to = y_data[-1].magnitude
        num_y_ticks = min(data.shape[0], 9)
        y_locs = np.linspace(-0.5, data.shape[0] - 0.5, num_y_ticks)
        y_labels = np.linspace(y_from, y_to, num_y_ticks)
        plt.yticks(y_locs, y_labels)
        plt.ylabel(y_data.units)
    plt.title(metric)
    plt.savefig(out_path + '.tif')
    plt.close()


def construct_range(start, stop, num, unit=''):
    start = 0 if start is None else start
    stop = num if stop is None else stop
    region = np.linspace(start, stop, num=num, endpoint=False)

    return q.Quantity(region, unit)


def make_metrics(keys):
    """Buld 1d and 2d metrics dictionaries from *keys*."""
    if keys is None:
        metrics_1d = METRICS_1D
        metrics_2d = METRICS_2D
    else:
        metrics_1d = {key: METRICS_1D[key] for key in keys if key in METRICS_1D}
        metrics_2d = {key: METRICS_2D[key] for key in keys if key in METRICS_2D}

    return metrics_1d, metrics_2d


def parse_args():
    parser = argparse.ArgumentParser(description='Evaluate sharpness metrics based on parameter '
                                     'changes in 3D reconstruction')
    parser.add_argument('input', type=str, help='Input path pattern')
    parser.add_argument('dims', type=int, choices=(1, 2),
                        help='Number of scanned parameters in the data set')
    parser.add_argument('--output', type=str, default='.', help='Output directory')
    parser.add_argument('--metrics', type=str, nargs='*',
                        choices=METRICS_1D.keys() + METRICS_2D.keys(),
                        help='Metrics to determine (m prefix means -metric)')
    parser.add_argument('--x-from', type=float, help='X data from')
    parser.add_argument('--x-to', type=float, help='X data to')
    parser.add_argument('--x-unit', type=str, default='', help='X axis units')
    parser.add_argument('--y-from', type=float, help='Y data from')
    parser.add_argument('--y-to', type=float, help='Y data to')
    parser.add_argument('--y-unit', type=str, default='', help='Y axis units')
    parser.add_argument('--num-images-for-stats', type=int, default=0, help='If not zero, an '
                        'image sequence is first read and the mean min and max intensities are '
                        'used as a global range of values to work on (-1 means read all images)')
    parser.add_argument('--fwhm', type=float, help='FWHM of 1 - Gauss in real space used to '
                        'filter out low frequencies.')
    parser.add_argument('--entropy-num-bins', type=int, default=256,
                        help='Number of bins to use for histogram calculation by entropy')
    parser.add_argument('--blur-fwhm', type=float, help='FWHM of the Gaussian blur applied to images')
    parser.add_argument('--save-raw', action='store_true', help='Store raw data (1D npy, 2D tiff)?')
    parser.add_argument('--save-txt', action='store_true', help='Store raw data as text files')
    parser.add_argument('--save-plot', action='store_true', help='Store plot data')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()
    if (args.x_from is None) ^ (args.x_to is None):
        raise ValueError('Either both x-from and x-to are set or both are not')
    if (args.y_from is None) ^ (args.y_to is None):
        raise ValueError('Either both y-from and y-to are set or both are not')

    return args


if __name__ == '__main__':
    main()
