import os
import glob
import math
import tifffile
import multiprocessing
import json
import appdirs
from flask import Flask, render_template, request, send_from_directory


app = Flask('tofu')

HOME = os.path.expanduser('~')
DEST = os.path.join(HOME, '.cache', 'tofu')


def get_dataset_paths():
    return sorted(glob.glob(os.path.join(DEST, '*')))


def get_datasets():
    return [os.path.basename(d) for d in get_dataset_paths()]


class Process(multiprocessing.Process):
    def __init__(self, name, slice_path):
        self.slice_path = slice_path
        self.dataset = name or 'foo'
        super(Process, self).__init__()

    def run(self):
        from ufo import Read, Write, Rescale, MapSlice

        app.logger.debug("Downscaling and mapping")
        root = os.path.join(HOME, self.slice_path)
        dataset_dir = os.path.join(DEST, self.dataset)

        filenames = sorted(glob.glob(root))
        is_multi_tiff = len(first.shape) > 2
        first = tifffile.imread(filenames[0])
        slice_size = first.shape[1] if is_multi_tiff else first.shape[0]
        num_slices = first.shape[0] if is_multi_tiff else len(filenames)

        # Optimize the input to 4 slice maps at 4Kx4K pixels
        tiles_per_map = num_slices / 4.0
        tile_length = int(math.ceil(math.sqrt(tiles_per_map)))
        tile_size = 4096. / tile_length
        factor = tile_size / slice_size

        read = Read(path=root)
        dataset_maps = os.path.join(dataset_dir, 'maps', 'sm-%02i.jpg')
        write = Write(filename=dataset_maps)
        rescale = Rescale(factor=factor)
        map_slice = MapSlice(number=int(tile_length * tile_length))

        write(map_slice(rescale(read()))).run().join()

        with open(os.path.join(dataset_dir, 'meta.json'), 'w') as f:
            json.dump({'tilelength': tile_length,
                       'numslices': num_slices }, f)

        app.logger.debug("Finished conversion")


@app.route('/')
def index():
    datasets = get_datasets()
    return render_template('index.html', datasets=datasets)


@app.route('/import', methods=['GET', 'POST'])
def import_existing():
    if request.method == 'POST':
        pass

    return render_template('import.html', home=HOME)


@app.route('/create', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        proc = Process(request.form['name'], request.form['slices'])
        proc.start()
        return render_template('index.html', home=HOME)

    return render_template('create.html', home=HOME)


@app.route('/render/<int:dataset_id>', methods=['GET'])
def render(dataset_id):
    # FIXME: invalid accesses
    path = get_dataset_paths()[dataset_id]

    meta = json.load(open(os.path.join(path, 'meta.json')))
    slicemaps = range(len(glob.glob(os.path.join(path, 'maps', 'sm*.jpg'))))
    return render_template('render.html', dataset_id=dataset_id, slicemaps=slicemaps, **meta)


@app.route('/data/<int:dataset_id>/<int:number>')
def data(dataset_id, number):
    path = get_dataset_paths()[dataset_id]
    slicemap = glob.glob(os.path.join(path, 'maps', 'sm*.jpg'))[number]
    basename, filename = os.path.split(slicemap)
    
    # sanitize here
    return send_from_directory(basename, filename)
