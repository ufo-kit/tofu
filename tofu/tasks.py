import logging
from gi.repository import Ufo


LOG = logging.getLogger(__name__)
PLUGIN_MANAGER = Ufo.PluginManager()


def get_task(name, processing_node=None, **kwargs):
    task = PLUGIN_MANAGER.get_task(name)
    task.set_properties(**kwargs)
    if processing_node and task.uses_gpu():
        LOG.debug("Assigning task '%s' to node %d", name, processing_node.get_index())
        task.set_proc_node(processing_node)

    return task


def get_writer(params):
    if 'dry_run' in params and params.dry_run:
        LOG.debug("Discarding data output")
        return get_task('null', download=True)

    outname = params.output
    LOG.debug("Writing output to {}".format(outname))
    writer = get_task('write', filename=outname)

    writer.props.append = params.output_append

    if params.output_bitdepth != 32:
        writer.props.bits = params.output_bitdepth

    if params.output_minimum is not None and params.output_maximum is not None:
        writer.props.minimum = params.output_minimum
        writer.props.maximum = params.output_maximum
    if hasattr (writer.props, 'bytes_per_file'):
        writer.props.bytes_per_file = params.output_bytes_per_file
    if hasattr(writer.props, 'tiff_bigtiff'):
        writer.props.tiff_bigtiff = params.output_bytes_per_file > 2 ** 32 - 2 ** 25

    return writer


def get_memory_in(array):
    import numpy as np

    if array.ndim != 2:
        raise ValueError("Only 2D images are supported")

    if array.dtype != np.float32 and array.dtype != np.complex64:
        raise ValueError("Only images with float32 or complex64 data type are supported")

    is_complex = array.dtype == np.complex64

    in_task = get_task('memory-in')
    in_task.props.complex_layout = is_complex
    in_task.props.pointer = array.__array_interface__['data'][0]
    in_task.props.width = 2 * array.shape[1] if is_complex else array.shape[1]
    in_task.props.height = array.shape[0]
    in_task.props.number = 1
    in_task.props.bitdepth = 32
    # We need to extend the survival of *array* beyond this function to the point when the graph is
    # executed, otherwise it will be destroyed and UFO will try to get data from freed memory. Thus,
    # attach it to the task which actually needs it, because when that one is garbage collected then
    # the array may be as well.
    in_task.np_array = array

    return in_task


def get_memory_out(width, height):
    import numpy as np

    array = np.empty((height, width), dtype=np.float32)
    out_task = get_task('memory-out')
    out_task.props.pointer = array.__array_interface__['data'][0]
    out_task.props.max_size = array.nbytes
    # We need to extend the survival of *array* beyond this function to the point when the graph is
    # executed, otherwise it will be destroyed and UFO will try to get data from freed memory. Thus,
    # attach it to the task which actually needs it, because when that one is garbage collected then
    # the array may be as well.
    out_task.np_array = array

    return out_task
