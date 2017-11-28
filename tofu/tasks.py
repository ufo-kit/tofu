import logging


LOG = logging.getLogger(__name__)


def get_task(pm, name, **kwargs):
    task = pm.get_task(name)
    task.set_properties(**kwargs)
    return task


def get_writer(pm, params):
    if 'dry_run' in params and params.dry_run:
        LOG.debug("Discarding data output")
        return get_task(pm, 'null', download=True)

    outname = params.output
    LOG.debug("Writing output to {}".format(outname))
    writer = get_task(pm, 'write', filename=outname)

    if params.output_bitdepth != 32:
        writer.props.bits = params.output_bitdepth

    if params.output_minimum is not None and params.output_maximum is not None:
        writer.props.minimum = params.output_minimum
        writer.props.maximum = params.output_maximum

    return writer
