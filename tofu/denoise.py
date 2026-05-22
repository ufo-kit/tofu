"""Non-local means denoising."""
import logging

from gi.repository import Ufo

from tofu.tasks import get_task, get_writer
from tofu.util import run_scheduler, set_node_props, setup_read_task


LOG = logging.getLogger(__name__)


def set_denoise_props(denoise_task, args):
    """Set UFO denoising properties from prefixed tofu arguments."""
    props = {
        'search_radius': args.denoise_search_radius,
        'patch_radius': args.denoise_patch_radius,
        'h': args.denoise_h,
        'sigma': args.denoise_sigma,
        'window': args.denoise_window,
        'fast': args.denoise_fast,
        'estimate_sigma': args.denoise_estimate_sigma,
        'addressing_mode': args.denoise_addressing_mode,
    }

    denoise_task.set_properties(**props)


def create_denoising_pipeline(args, processing_node=None):
    """Create the UFO denoising task."""
    denoise_task = get_task('non-local-means', processing_node=processing_node)
    set_denoise_props(denoise_task, args)

    return denoise_task


def denoise(args):
    """Run non-local means denoising."""
    graph = Ufo.TaskGraph()
    sched = Ufo.Scheduler()

    reader = get_task('read')
    set_node_props(reader, args)
    if not args.images:
        raise RuntimeError('--images not set')
    setup_read_task(reader, args.images, args)

    out_task = get_writer(args)
    current = create_denoising_pipeline(args)
    graph.connect_nodes(reader, current)
    graph.connect_nodes(current, out_task)

    run_scheduler(sched, graph)
