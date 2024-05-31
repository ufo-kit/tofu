import argparse
import sys
import logging
import configparser as configparser
from collections import OrderedDict
from tofu.util import convert_filesize, restrict_value, tupleize, range_list


LOG = logging.getLogger(__name__)
NAME = "reco.conf"
SECTIONS = OrderedDict()

SECTIONS['general'] = {
    'config': {
        'default': NAME,
        'type': str,
        'help': "File name of configuration",
        'metavar': 'FILE'},
    'verbose': {
        'default': False,
        'ezdefault': False,
        'help': 'Verbose output',
        'action': 'store_true'},
    'output': {
        'default': 'result-%05i.tif',
        'type': str,
        'help': "Path to location or format-specified file path "
                "for storing reconstructed slices",
        'metavar': 'PATH'},
    'output-bitdepth': {
        'default': 32,
        'ezdefault': 8,
        'type': restrict_value((0, None), dtype=int),
        'help': "Bit depth of output, either 8, 16 or 32",
        'metavar': 'BITDEPTH'},
    'output-minimum': {
        'default': None,
        'ezdefault': 0.0,
        'type': float,
        'help': "Minimum value that maps to zero (turns on --output-rescale)",
        'metavar': 'MIN'},
    'output-maximum': {
        'default': None,
        'ezdefault': 0.0,
        'type': float,
        'help': "Maximum input value that maps to largest output value (turns on --output-rescale)",
        'metavar': 'MAX'},
    'output-rescale': {
        'default': False,
        'action': 'store_true',
        'help': "If true rescale grey values either automatically or according to set "
                "--output-minimum and --output-maximum"},
    'output-bytes-per-file': {
        'default': '128g',
        'type': convert_filesize,
        'help': "Maximum bytes per file (0=single-image output, otherwise multi-image output)\
                , 'k', 'm', 'g', 't' suffixes can be used",
        'metavar': 'BYTESPERFILE'},
    'output-append': {
        'default': False,
        'action': 'store_true',
        'help': 'Append images instead of overwriting existing files'},
    'log': {
        'default': None,
        'type': str,
        'help': "File name of optional log",
        'metavar': 'FILE'},
    'width': {
        'default': None,
        'type': restrict_value((0, None), dtype=int),
        'help': "Input width"}}

SECTIONS['reading'] = {
    'y': {
        'default': 0,
        'ezdefault': 100,
        'type': restrict_value((0, None), dtype=int),
        'help': 'Vertical coordinate from where to start reading the input image'},
    'height': {
        'default': None,
        'ezdefault': 200,
        'type': restrict_value((0, None), dtype=int),
        'help': "Number of rows which will be read"},
    'bitdepth': {
        'default': 32,
        'type': restrict_value((0, None), dtype=int),
        'help': "Bit depth of raw files"},
    'y-step': {
        'default': 1,
        'ezdefault': 20,
        'type': restrict_value((0, None), dtype=int),
        'help': "Read every \"step\" row from the input"},
    'start': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'help': 'Offset to the first read file'},
    'number': {
        'default': None,
        'type': restrict_value((0, None), dtype=int),
        'help': 'Number of files to read'},
    'step': {
        'default': 1,
        'ezdefault': 1,
        'type': restrict_value((0, None), dtype=int),
        'help': 'Read every \"step\" file'},
    'resize': {
        'default': None,
        'type': restrict_value((0, None), dtype=int),
        'help': 'Bin pixels before processing'},
    'retries': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'metavar': 'NUMBER',
        'help': 'How many times to wait for new files'},
    'retry-timeout': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'metavar': 'TIME',
        'help': 'How long to wait for new files per trial'}}

SECTIONS['flat-correction'] = {
    'projections': {
        'default': None,
        'type': str,
        'help': "Location with projections",
        'metavar': 'PATH'},
    'darks': {
        'default': None,
        'type': str,
        'help': "Location with darks",
        'metavar': 'PATH'},
    'dark-scale': {
        'default': 1,
        'type': float,
        'help': "Scaling dark"},
    'reduction-mode': {
        'default': "Average",
        'type': str,
        'help': "Flat-field correction options: Average (darks) or median (flats)"},
    'fix-nan-and-inf': {
        'default': False,
        'help': "Fix nan and inf",
        'action': 'store_true'},
    'flats': {
        'default': None,
        'type': str,
        'help': "Location with flats",
        'metavar': 'PATH'},
    'flats2': {
        'default': None,
        'type': str,
        'help': "Location with flats 2 for interpolation correction",
        'metavar': 'PATH'},
    'flat-scale': {
        'default': 1,
        'type': float,
        'help': "Scaling flat"},
    'absorptivity': {
        'default': False,
        'action': 'store_true',
        'help': 'Do absorption correction'}}

SECTIONS['retrieve-phase'] = {
    'retrieval-method': {
        'choices': ['tie', 'ctf', 'qp', 'qp2'],
        'default': 'tie',
        'help': "Phase retrieval method"},
    'energy': {
        'default': None,
        'ezdefault': 20,
        'type': float,
        'help': "X-ray energy [keV]"},
    'propagation-distance': {
        'default': None,
        'ezdefault': "0.1",
        'type': tupleize(),
        'help': ("Sample <-> detector distance (if one value, then use the same for x and y "
                 "direction, otherwise first specifies x and second y direction) [m]")},
    'pixel-size': {
        'default': 1e-6,
        'ezdefault': 3.6e-6,
        'type': float,
        'help': "Pixel size [m]"},
    'regularization-rate': {
        'default': 2,
        'ezdefault': 2.3,
        'type': float,
        'help': "Regularization rate (typical values between [2, 3])"},
    'delta': {
        'default': None,
        'type': float,
        'help': "Real part of the complex refractive index of the material. "
                "If specified, phase retrieval returns projected thickness, "
                "if not, it returns phase"},
    'tie-approximate-logarithm': {
        'default': False,
        'help': ("Approximate the logarithm of the tie method by the first order Taylor series "
                 "expansion [ln(x) ~ ln(a) + (x - a) / a at a, a specified with "
                 "--tie-approximate-point].  This way we may do the filtering for FBP already "
                 "by the phase retrieval and save one forward and one backward 1D FFT needed "
                 "if the filtering occurse separately. This is mostly useful for online reconstruction "
                 "when one reconstruct only a few slices."),
        'action': 'store_true'},
    'tie-approximate-point': {
        'default': 0.75,
        'type': float,
        'help': ("Taylor series point of expansion used by --tie-approximate-logarithm. "
                 "The error of the approximation will be smallest around this point, "
                 "so you can tune this for the desired grey level of interest "
                 "(given by the sample based on e^(-mju * projected_thickness)).")},
    'retrieval-padded-width': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'help': "Padded width used for phase retrieval"},
    'retrieval-padded-height': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'help': "Padded height used for phase retrieval"},
    'retrieval-padding-mode': {
        'choices': ['none', 'clamp', 'clamp_to_edge', 'repeat', 'mirrored_repeat'],
        'default': 'clamp_to_edge',
        'help': "Padded values assignment"},
    'thresholding-rate': {
        'default': 0.01,
        'type': float,
        'help': "Thresholding rate (typical values between [0.01, 0.1])"},
    'frequency-cutoff': {
        'default': 1e30,
        'type': float,
        'help': "Phase retrieval frequency cutoff [rad]"}}

SECTIONS['sinos'] = {
    'pass-size': {
        'type': restrict_value((0, None), dtype=int),
        'default': 0,
        'help': 'Number of sinograms to process per pass'}}

SECTIONS['reconstruction'] = {
    'sinograms': {
        'default': None,
        'type': str,
        'help': "Location with sinograms",
        'metavar': 'PATH'},
    'angle': {
        'default': None,
        'type': float,
        'help': "Angle step between projections in radians"},
    'enable-tracing': {
        'default': False,
        'help': "Enable tracing and store result in .PID.json",
        'action': 'store_true'},
    'remotes': {
        'default': None,
        'type': str,
        'help': "Addresses to remote ufo-nodes",
        'nargs': '+'},
    'projection-filter': {
        'default': 'ramp-fromreal',
        'type': str,
        'help': "Projection filter",
        'choices': ['none', 'ramp', 'ramp-fromreal', 'butterworth', 'faris-byer', 'bh3', 'hamming']},
    'projection-filter-cutoff': {
        'default': 0.5,
        'type': float,
        'help': "Relative cutoff frequency"},
    'projection-padding-mode': {
        'choices': ['none', 'clamp', 'clamp_to_edge', 'repeat', 'mirrored_repeat'],
        'default': 'clamp_to_edge',
        'help': "Padded values assignment"}}

SECTIONS['tomographic-reconstruction'] = {
    'axis': {
        'default': None,
        'type': float,
        'help': "Axis position"},
    'dry-run': {
        'default': False,
        'help': "Reconstruct without writing data",
        'action': 'store_true'},
    'offset': {
        'default': 0.0,
        'type': float,
        'help': "Angle offset of first projection in radians"},
    'method': {
        'default': 'fbp',
        'type': str,
        'help': "Reconstruction method",
        'choices': ['fbp', 'dfi', 'sart', 'sirt', 'sbtv', 'asdpocs']}}

SECTIONS['laminographic-reconstruction'] = {
    'angle': {
        'default': None,
        'type': float,
        'help': "Angle step between projections in radians"},
    'dry-run': {
        'default': False,
        'help': "Reconstruct without writing data",
        'action': 'store_true'},
    'axis': {
        'default': None,
        'required': True,
        'type': tupleize(num_items=2),
        'help': "Axis position"},
    'x-region': {
        'default': "0,-1,1",
        'type': tupleize(num_items=3, conv=int),
        'help': "X region as from,to,step"},
    'y-region': {
        'default': "0,-1,1",
        'type': tupleize(num_items=3, conv=int),
        'help': "Y region as from,to,step"},
    'z': {
        'default': 0,
        'type': int,
        'help': "Z coordinate of the reconstructed slice"},
    'z-parameter': {
        'default': 'z',
        'type': str,
        'choices': ['z', 'x-center', 'lamino-angle', 'roll-angle'],
        'help': "Parameter to vary along the reconstructed z-axis"},
    'region': {
        'default': "0,-1,1",
        'type': tupleize(num_items=3),
        'help': "Z-axis parameter region as from,to,step"},
    'overall-angle': {
        'default': None,
        'type': float,
        'help': "The total angle over which projections were taken in degrees"},
    'lamino-angle': {
        'default': None,
        'required': True,
        'type': float,
        'help': "The laminographic angle in degrees"},
    'roll-angle': {
        'default': 0.0,
        'type': float,
        'help': "Sample angular misalignment to the side (roll) in degrees, positive angles mean\
        clockwise misalignment"},
    'slices-per-device': {
        'default': None,
        'type': restrict_value((0, None), dtype=int),
        'help': "Number of slices computed by one computing device"},
    'only-bp': {
        'default': False,
        'action': 'store_true',
        'help': "Do only backprojection with no other processing steps"},
    'lamino-padding-mode': {
        'choices': ['none', 'clamp', 'clamp_to_edge', 'repeat', 'mirrored_repeat'],
        'default': 'clamp',
        'help': "Padded values assignment for the filtered projection"}}

SECTIONS['fbp'] = {
    'crop-width': {
        'default': None,
        'type': restrict_value((0, None), dtype=int),
        'help': "Width of final slice"},
    'projection-crop-after': {
        'choices': ['filter', 'backprojection'],
        'default': 'backprojection',
        'help': "Whether to crop projections after filtering (can cause truncation "
                "artifacts) or after backprojection"}}

SECTIONS['dfi'] = {
    'oversampling': {
        'default': None,
        'type': restrict_value((0, None), dtype=int),
        'help': "Oversample factor"}}

SECTIONS['ir'] = {
    'num-iterations': {
        'default': 10,
        'type': restrict_value((0, None), dtype=int),
        'help': "Maximum number of iterations"}}

SECTIONS['sart'] = {
    'relaxation-factor': {
        'default': 0.25,
        'type': float,
        'help': "Relaxation factor"}}

SECTIONS['sbtv'] = {
    'lambda': {
        'default': 0.1,
        'type': float,
        'help': "Lambda"},
    'mu': {
        'default': 0.5,
        'type': float,
        'help': "mu"}}

SECTIONS['gui'] = {
    'enable-cropping': {
        'default': False,
        'help': "Enable cropping width",
        'action': 'store_true'},
    'show-2d': {
        'default': False,
        'help': "Show 2D slices with pyqtgraph",
        'action': 'store_true'},
    'show-3d': {
        'default': False,
        'help': "Show 3D slices with pyqtgraph",
        'action': 'store_true'},
    'last-dir': {
        'default': '.',
        'type': str,
        'help': "Path of the last used directory",
        'metavar': 'PATH'},
    'deg0': {
        'default': '.',
        'type': str,
        'help': "Location with 0 deg projection",
        'metavar': 'PATH'},
    'deg180': {
        'default': '.',
        'type': str,
        'help': "Location with 180 deg projection",
        'metavar': 'PATH'},
    'ffc-correction': {
        'default': False,
        'help': "Enable darks or flats correction",
        'action': 'store_true'},
    'num-flats': {
        'default': 0,
        'type': int,
        'help': "Number of flats for ffc correction."}}

SECTIONS['estimate'] = {
    'estimate-method': {
        'type': str,
        'default': 'correlation',
        'help': 'Rotation axis estimation algorithm',
        'choices': ['reconstruction', 'correlation']}}

SECTIONS['perf'] = {
    'num-runs': {
        'default': 3,
        'type': restrict_value((0, None), dtype=int),
        'help': "Number of runs"},
    'width-range': {
        'default': '1024',
        'type': range_list,
        'help': "Width or range of widths of generated projections"},
    'height-range': {
        'default': '1024',
        'type': range_list,
        'help': "Height or range of heights of generated projections"},
    'num-projection-range': {
        'default': '512',
        'type': range_list,
        'help': "Number or range of number of projections"}}

SECTIONS['preprocess'] = {
    'transpose-input': {
        'default': False,
        'action': 'store_true',
        'help': "Transpose projections before they are backprojected (after phase retrieval)"},
    'projection-filter': {
        'default': 'ramp-fromreal',
        'type': str,
        'help': "Projection filter",
        'choices': ['none', 'ramp', 'ramp-fromreal', 'butterworth', 'faris-byer', 'bh3', 'hamming']},
    'projection-filter-cutoff': {
        'default': 0.5,
        'type': float,
        'help': "Relative cutoff frequency"},
    'projection-filter-scale': {
        'default': 1.,
        'type': float,
        'help': "Multiplicative factor of the projection filter"},
    'projection-padding-mode': {
        'choices': ['none', 'clamp', 'clamp_to_edge', 'repeat', 'mirrored_repeat'],
        'default': 'clamp_to_edge',
        'help': "Padded values assignment"},
    'projection-crop-after': {
        'choices': ['filter', 'backprojection'],
        'default': 'backprojection',
        'help': "Whether to crop projections after filtering (can cause truncation "
                "artifacts) or after backprojection"}}

SECTIONS['cone-beam-weight'] = {
    'source-position-y': {
        'default': "-Inf",
        'type': tupleize(dtype=list),
        'help': "Y source position (along beam direction) in global coordinates [pixels] "
                "(multiple of detector pixel size)"},
    'detector-position-y': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Y detector position (along beam direction) in global coordinates [pixels] "
                "(multiple of detector pixel size)"},
    'center-position-x': {
        'default': None,
        'type': tupleize(),
        'help': "X rotation axis position on a projection [pixels]"},
    'center-position-z': {
        'default': None,
        'ezdefault': "0",
        'type': tupleize(),
        'help': "Z rotation axis position on a projection [pixels]"},
    'axis-angle-x': {
        'default': "0",
        'ezdefault': "30",
        'type': tupleize(dtype=list),
        'help': "Rotation axis rotation around the x axis"
                "(laminographic angle, 0 = tomography) [deg]"}}

SECTIONS['general-reconstruction'] = {
    'enable-tracing': {
        'default': False,
        'help': "Enable tracing and store result in .PID.json",
        'action': 'store_true'},
    'disable-cone-beam-weight': {
        'default': False,
        'action': 'store_true',
        'help': "Disable cone beam weighting"},
    'slice-memory-coeff': {
        'default': 0.8,
        'ezdefault': 0.7,
        'type': restrict_value((0.01, 0.95)),
        'help': "Portion of the GPU memory used for slices (from 0.01 to 0.9) [fraction]. "
                "The total amount of consumed memory will be larger depending on the "
                "complexity of the graph. In case of OpenCL memory allocation errors, "
                "try reducing this value."},
    'num-gpu-threads': {
        'default': 1,
        'ezdefault': None,
        'type': restrict_value((1, None), dtype=int),
        'help': "Number of parallel reconstruction threads on one GPU"},
    'disable-projection-crop': {
        'default': False,
        'action': 'store_true',
        'help': "Disable automatic cropping of projections computed from volume region"},
    'dry-run': {
        'default': False,
        'help': "Reconstruct without reading or writing data",
        'action': 'store_true'},
    'data-splitting-policy': {
        'default': 'one',
        'ezdefault': 'one',
        'type': str,
        'help': "'one': one GPU should process as many slices as possible, "
                "'many': slices should be spread across as many GPUs as possible",
        'choices': ['one', 'many']},
    'projection-margin': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'help': "By optimization of the read projection region, the read region will be "
                "[y - margin, y + height + margin]"},
    'slices-per-device': {
        'default': None,
        'ezdefault': None,
        'type': restrict_value((0, None), dtype=int),
        'help': "Number of slices computed by one computing device"},
    'gpus': {
        'default': None,
        'nargs': '+',
        'type': int,
        'help': "GPUs with these indices will be used (0-based)"},
    'burst': {
        'default': None,
        'type': restrict_value((0, None), dtype=int),
        'help': "Number of projections processed per kernel invocation"},
    'x-region': {
        'default': "0,-1,1",
        'type': tupleize(num_items=3),
        'help': "x region as from,to,step"},
    'y-region': {
        'default': "0,-1,1",
        'type': tupleize(num_items=3),
        'help': "y region as from,to,step"},
    'z': {
        'default': 0,
        'type': int,
        'help': "z coordinate of the reconstructed slice"},
    'z-parameter': {
        'default': 'z',
        'type': str,
        'choices': ['axis-angle-x', 'axis-angle-y', 'axis-angle-z',
                    'volume-angle-x', 'volume-angle-y', 'volume-angle-z',
                    'detector-angle-x', 'detector-angle-y', 'detector-angle-z',
                    'detector-position-x', 'detector-position-y', 'detector-position-z',
                    'source-position-x', 'source-position-y', 'source-position-z',
                    'center-position-x', 'center-position-z', 'z'],
        'help': "Parameter to vary along the reconstructed z-axis"},
    'region': {
        'default': "0,1,1",
        'type': tupleize(num_items=3),
        'help': "z axis parameter region as from,to,step"},
    'source-position-x': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "X source position (horizontal) in global coordinates [pixels]"},
    'source-position-z': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Z source position (vertical) in global coordinates [pixels]"},
    'detector-position-x': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "X detector position (horizontal) in global coordinates [pixels]"},
    'detector-position-z': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Z detector position (vertical) in global coordinates [pixels]"},
    'detector-angle-x': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Detector rotation around the x axis (horizontal) [deg]"},
    'detector-angle-y': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Detector rotation around the y axis (along beam direction) [deg]"},
    'detector-angle-z': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Detector rotation around the z axis (vertical) [deg]"},
    'axis-angle-y': {
        'default': "0",
        'ezdefault': "0",
        'type': tupleize(dtype=list),
        'help': "Rotation axis rotation around the y axis (along beam direction) [deg]"},
    'axis-angle-z': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Rotation axis rotation around the z axis (vertical) [deg]"},
    'volume-angle-x': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Volume rotation around the x axis (horizontal) [deg]"},
    'volume-angle-y': {
        'default': "0",
        'type': tupleize(dtype=list),
        'help': "Volume rotation around the y axis (along beam direction) [deg]"},
    'volume-angle-z': {
        'default': "0",
        'ezdefault': "0.0",
        'type': tupleize(dtype=list),
        'help': "Volume rotation around the z axis (vertical) [deg]"},
    'compute-type': {
        'default': 'float',
        'type': str,
        'help': "Data type for performing kernel math operations",
        'choices': ['half', 'float', 'double']},
    'result-type': {
        'default': 'float',
        'type': str,
        'help': "Data type for storing the intermediate gray value for a voxel "
                "from various rotation angles",
        'choices': ['half', 'float', 'double']},
    'store-type': {
        'default': 'float',
        'type': str,
        'help': "Data type of the output volume",
        'choices': ['half', 'float', 'double', 'uchar', 'ushort', 'uint']},
    'overall-angle': {
        'default': None,
        'ezdefault': 360,
        'type': float,
        'help': "The total angle over which projections were taken in degrees"},
    'genreco-padding-mode': {
        'choices': ['none', 'clamp', 'clamp_to_edge', 'repeat', 'mirrored_repeat'],
        'default': 'clamp',
        'help': "Padded values assignment for the filtered projection"},
    'slice-gray-map': {
        'default': "0,0",
        'type': tupleize(num_items=2, conv=float),
        'help': "Minimum and maximum gray value mapping if store-type is integer-based"}
    }

SECTIONS['find-large-spots'] = {
    'method': {
        'default': 'grow',
        'type': str,
        'help': "Data type of the output volume",
        'choices': ['grow', 'median']},
    # median arguments
    'median-width': {
        'default': 10,
        'type': int,
        'help': "Width of the median filter (operates only horizontally)"},
    'median-direction': {
        'default': 'horizontal',
        'choices': ['both', 'horizontal', 'vertical'],
        'help': "Median filtering direction (in case of 'both', it will be a disk with radius "
                "'median-width' / 2"},
    'dilation-disk-radius': {
        'default': 2,
        'type': int,
        'help': "Dilation disk radius used for enlarging the found mask"},
    # grow arguments
    'images': {
        'default': None,
        'type': str,
        'help': "Location with input images",
        'metavar': 'PATH'},
    'transpose-input': {
        'default': False,
        'action': 'store_true',
        'help': "Transpose image when *vertical_sigma* is True, i.e. filter horizontal stripes "
                "instead of vertical"},
    'gauss-sigma': {
        'default': 0.0,
        'ezdefault': 2.0,
        'type': float,
        'help': "Gaussian sigma for removing low frequencies (filter will be 1 - gauss window)"},
    'vertical-sigma': {
        'default': False,
        'action': 'store_true',
        'help': "*gauss-sigma* will be used for removing low frequencies in a horizontal stripe "
                "(vertical Gaussian profile applied around frequency ky=0 for all kx in a 1 - "
                "gauss window fashion)"},
    'blurred-output': {
        'default': None,
        'type': str,
        'help': "Path where to store the blurred input"},
    'averaging-mode': {
        'default': 'first',
        'type': str,
        'help': "How to average input images (first = take a single image, "
                "only available with --method median)",
        'choices': ['first', 'mean', 'median']},
    'spot-threshold': {
        'default': 0.0,
        'ezdefault': 1000,
        'type': float,
        'help': "Pixels with grey value larger than this are considered as spots. In case of "
                "'median' method and if 'spot-threshold' is not set, it is automatically "
                "set to 99-th percentile of the histogram."},
    'spot-threshold-mode': {
        'default': 'absolute',
        'type': str,
        'help': "Pixels must be either \"below\", \"above\" the spot threshold, or \
                their \"absolute\" value can be compared",
        'choices': ['below', 'above', 'absolute']},
    'grow-threshold': {
        'default': 0.0,
        'type': float,
        'help': "Spot growing threshold, if 0 it will be set to FWTM times noise standard deviation "
                "in case of 'grow' method, all pixels connected to the ones previously found by "
                "'spot-threshold' which are above 'grow-threshold' are marked as spots. In case "
                "'median' method, the median blurred image is subtracted from the original and "
                "pixels which are above 'grow-threshold' in the absolute value of this "
                "difference are marked."
                },
    'find-large-spots-padding-mode': {
        'choices': ['none', 'clamp', 'clamp_to_edge', 'repeat', 'mirrored_repeat'],
        'default': 'repeat',
        'help': "Padded values assignment for the filtered input image"},
    }

SECTIONS['inpaint'] = {
    'projections': {
        'default': None,
        'type': str,
        'help': "Location with projections",
        'metavar': 'PATH'},
    'guidance-image': {
        'default': None,
        'type': str,
        'help': "Guidance image, structure which will be inpainted into input images"},
    'mask-image': {
        'default': None,
        'type': str,
        'help': "Mask image, pixels with ones will use the guidance image, pixels with zeros \
                the original image"},
    'inpaint-padded-width': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'help': "Padded width used for inpainting"},
    'inpaint-padded-height': {
        'default': 0,
        'type': restrict_value((0, None), dtype=int),
        'help': "Padded height used for inpainting"},
    'inpaint-padding-mode': {
        'choices': ['none', 'clamp', 'clamp_to_edge', 'repeat', 'mirrored_repeat'],
        'default': 'clamp_to_edge',
        'help': "Padded values assignment for inpainting"},
    'preserve-mean': {
        'default': False,
        'action': 'store_true',
        'help': "Mean value of the inpainted result will be the same as the one of the input"},
    'harmonize-borders': {
        'default': False,
        'action': 'store_true',
        'help': "Harmonize transitions between image borders useful for the removal of the "
                "cross in the power spectrum"},
}

TOMO_PARAMS = ('flat-correction', 'reconstruction', 'tomographic-reconstruction', 'fbp', 'dfi', 'ir', 'sart', 'sbtv')

PREPROC_PARAMS = ('preprocess', 'cone-beam-weight', 'flat-correction', 'retrieve-phase')
LAMINO_PARAMS = PREPROC_PARAMS + ('laminographic-reconstruction',)
GEN_RECO_PARAMS = PREPROC_PARAMS + ('general-reconstruction',)

NICE_NAMES = ('General', 'Input', 'Flat field correction', 'Phase retrieval',
              'Sinogram generation', 'General reconstruction', 'Tomographic reconstruction',
              'Laminographic reconstruction', 'Filtered backprojection',
              'Direct Fourier Inversion', 'Iterative reconstruction',
              'SART', 'SBTV', 'GUI settings', 'Estimation', 'Performance',
              'Preprocess', 'Cone beam weight', 'General reconstruction', 'Find large spots',
              'Inpaint')

def get_config_name():
    """Get the command line --config option."""
    name = ''
    for i, arg in enumerate(sys.argv):
        if arg.startswith('--config'):
            if arg == '--config':
                return sys.argv[i + 1]
            else:
                name = sys.argv[i].split('--config')[1]
                if name[0] == '=':
                    name = name[1:]
                return name

    return name


def parse_known_args(parser, subparser=False):
    """
    Parse arguments from file and then override by the ones specified on the
    command line. Use *parser* for parsing and is *subparser* is True take into
    account that there is a value on the command line specifying the subparser.
    """
    if len(sys.argv) > 1:
        subparser_value = [sys.argv[1]] if subparser else []
        config_values = config_to_list(config_name=get_config_name())
        values = subparser_value + config_values + sys.argv[1:]
        args = None
        if config_values:
            args = parser.parse_known_args(args=subparser_value + config_values)[0]
        parser.parse_args(args=sys.argv[1:], namespace=args)
    else:
        values = ""

    return parser.parse_known_args(values)[0]


def config_to_list(config_name=''):
    """
    Read arguments from config file and convert them to a list of keys and
    values as sys.argv does when they are specified on the command line.
    *config_name* is the file name of the config file.
    """
    result = []
    config = configparser.ConfigParser()

    if not config.read([config_name]):
        return []

    for section in SECTIONS:
        for name, opts in ((n, o) for n, o in list(SECTIONS[section].items()) if config.has_option(section, n)):
            value = config.get(section, name)

            if value != '' and value != 'None':
                action = opts.get('action', None)

                if action == 'store_true' and value == 'True':
                    # Only the key is on the command line for this action
                    result.append('--{}'.format(name))

                if not action == 'store_true':
                    if opts.get('nargs', None) == '+':
                        result.append('--{}'.format(name))
                        result.extend((v.strip() for v in value.split(',')))
                    else:
                        result.append('--{}={}'.format(name, value))

    return result


def without_keys(d, keys):
    return {k: v for k, v in d.items() if k not in keys}


class Params(object):
    def __init__(self, sections=()):
        self.sections = sections + ('general', 'reading')
    
    def add_parser_args(self, parser):
        for section in self.sections:
            for name in sorted(SECTIONS[section]):
                opts = without_keys(SECTIONS[section][name], {'ezdefault'})
                parser.add_argument('--{}'.format(name), **opts)
                
    def add_arguments(self, parser):
        self.add_parser_args(parser)
        return parser

    def get_defaults(self):
        parser = argparse.ArgumentParser()
        self.add_arguments(parser)

        return parser.parse_args('')


def write(config_file, args=None, sections=None):
    """
    Write *config_file* with values from *args* if they are specified,
    otherwise use the defaults. If *sections* are specified, write values from
    *args* only to those sections, use the defaults on the remaining ones.
    """
    config = configparser.ConfigParser()

    for section in SECTIONS:
        config.add_section(section)
        for name, opts in list(SECTIONS[section].items()):
            if args and sections and section in sections and hasattr(args, name.replace('-', '_')):
                value = getattr(args, name.replace('-', '_'))

                if isinstance(value, list):
                    value = ', '.join(value)
            else:
                value = opts['default'] if opts['default'] != None else ''

            prefix = '# ' if value == '' else ''

            if name != 'config':
                config.set(section, prefix + name, value)

    with open(config_file, 'wb') as f:
        config.write(f)


def log_values(args):
    """Log all values set in the args namespace.

    Arguments are grouped according to their section and logged alphabetically
    using the DEBUG log level thus --verbose is required.
    """
    args = args.__dict__

    for section, name in zip(SECTIONS, NICE_NAMES):
        entries = sorted((k for k in list(args.keys()) if k.replace('_', '-') in SECTIONS[section]))

        if entries:
            LOG.debug(name)

            for entry in entries:
                value = args[entry] if args[entry] is not None else "-"
                LOG.debug("  {:<16} {}".format(entry, value))
