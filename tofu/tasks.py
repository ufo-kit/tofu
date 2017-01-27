import logging


LOG = logging.getLogger(__name__)


def get_task(pm, name, **kwargs):
    task = pm.get_task(name)
    task.set_properties(**kwargs)
    return task


def get_writer(pm, params):
    if params.dry_run:
        LOG.debug("Discarding data output")
        return get_task(pm, 'null', download=True)
    else:
        outname = params.output
        LOG.debug("Writing output to {}".format(outname))
        return get_task(pm, 'write', filename=outname)
