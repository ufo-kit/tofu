import os
import sys
import argparse
import numpy as np
from gi.repository import Ufo

def number_of_tiff_files(path):
    return len([name for name in os.listdir(path) if name.endswith('.tif')])

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-directory', metavar='PATH', type=str, default='.',
                        help="Location with raw projections in EDF or TIFF format")
    parser.add_argument('-o', '--output-directory', metavar='PATH', type=str, default='.',
                        help="Location to store reconstructed slices")
    parser.add_argument('-p', '--num-projections', metavar='N', type=int, required=True,
                        help="Number of projections")

    args = parser.parse_args()
    
    n_files = number_of_tiff_files(args.input_directory)

    if n_files == 0:
        print 'No input files found.'
        sys.exit(1)

    if not os.path.exists(args.output_directory):
        os.mkdir(args.output_directory)

    count = args.num_projections
    flat_start = n_files - count - 200
    proj_start = n_files - count

    pm = Ufo.PluginManager()
    flat_reader = pm.get_filter('reader')
    flat_averager = pm.get_filter('averager')
    proj_reader = pm.get_filter('reader')
    writer = pm.get_filter('writer')
    repeater = Ufo.FilterRepeater()

    sub = pm.get_filter('subtract')
    sinogenerator = pm.get_filter('sinogenerator')

    # configure nodes
    flat_reader.set_properties(path=args.input_directory, nth=flat_start, count=150)
    proj_reader.set_properties(path=args.input_directory, nth=proj_start, count=count)
    writer.set_properties(prefix='sinogram-', path=args.output_directory)
    repeater.set_properties(count=count)
    sinogenerator.set_properties(num_projections=count)

    g = Ufo.Graph()
    dist = Ufo.TransferMode.DISTRIBUTE

    # subtract averaged flats from projections
    g.connect_filters(flat_reader, flat_averager)
    g.connect_filters(flat_averager, repeater)
    g.connect_filters_full(proj_reader, 0, sub, 0, dist)
    g.connect_filters_full(repeater, 0, sub, 1, dist)

    # create sinograms from corrected projections
    g.connect_filters(sub, sinogenerator)

    # backproject filtered sinograms
    g.connect_filters(sinogenerator, writer)

    s = Ufo.Scheduler()
    s.run(g)

