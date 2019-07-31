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
        writer.props.tiff_bigtiff = params.output_bigtiff

    return writer
