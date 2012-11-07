import os
import sys
import argparse
import numpy as np
from gi.repository import Ufo

def number_of_tiff_files(path):
    return len([name for name in os.listdir(path) if name.endswith('.tif')])

if __name__ == '__main__':
    n_sinograms = number_of_tiff_files('./sinograms')

    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--axis', type=float, default=1000.0,
                        required=True,
                        help="Axis position")
    parser.add_argument('-s', '--angle-step', type=float, default=None,
                        help="Angle step between projections")
    parser.add_argument('-f', '--first', type=int, default=0,
                        help="First slice")
    parser.add_argument('-l', '--last', type=int, default=n_sinograms,
                        help="Last slice")
    parser.add_argument('-o', '--output-directory', type=str, default='.',
                        help="Location to store reconstructed slices")
    parser.add_argument('-i', '--input-directory', type=str, default='.',
                        help="Location with sinograms")

    args = parser.parse_args()

    # create nodes
    pm = Ufo.PluginManager()
    sino_reader = pm.get_filter('reader')
    writer = pm.get_filter('writer')
    fft = pm.get_filter('fft')
    ifft = pm.get_filter('ifft')
    fltr = pm.get_filter('filter')
    bp = pm.get_filter('backproject')

    # configure nodes
    sino_reader.set_properties(path=args.input_directory, nth=args.first, count=(args.last - args.first))
    writer.set_properties(prefix='slice-', path=args.output_directory)
    fft.set_properties(dimensions=1)
    ifft.set_properties(dimensions=1)
    bp.set_properties(axis_pos=args.axis)

    if args.angle_step:
        bp.set_properties(angle_step=args.angle_step)

    g = Ufo.Graph()
    dist = Ufo.TransferMode.DISTRIBUTE

    # backproject filtered sinograms
    g.connect_filters(sino_reader, fft)
    g.connect_filters(fft, fltr)
    g.connect_filters(fltr, ifft)
    g.connect_filters(ifft, bp)
    g.connect_filters(bp, writer)

    s = Ufo.Scheduler()
    s.run(g)

