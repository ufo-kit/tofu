import argparse
import logging
import time
from threading import Thread
from gi.repository import Ufo
from .preprocess import create_flat_correct_pipeline, create_projection_filtering_pipeline
from .tasks import get_task, get_writer
from .util import determine_shape, fbp_filtering_in_phase_retrieval

LOG = logging.getLogger(__name__)

def create_ffc_abs_flt_pipeline(
        args: argparse.Namespace,
        graph: Ufo.TaskGraph,
        processing_node: int) -> Ufo.TaskNode:
    assert args.darks is not None
    assert args.flats is not None
    assert args.projections is not None
    current: Ufo.TaskNode = create_flat_correct_pipeline(args, graph, processing_node=processing_node)
    if args.projection_filter != 'none' and not fbp_filtering_in_phase_retrieval(args):
        pf_first, pf_last = create_projection_filtering_pipeline(
            args, graph, processing_node=processing_node)
        if current:
            graph.connect_nodes(current, pf_first)
        current = pf_last
    return current


def setup_single_gpu_graph(
        args: argparse.Namespace,
        graph: Ufo.TaskGraph,
        gpu_index: int=0) -> None:
    determine_shape(args=args, store=True)
    assert args.output is not None
    sink = get_writer(params=args)
    flt_node = create_ffc_abs_flt_pipeline(args=args, graph=graph, processing_node=gpu_index)
    backproject = get_task('rgba-backproject', processing_node=gpu_index)
    backproject.props.burst = args.burst
    backproject.props.region = args.region
    # Following is required when we want to perform the cropping after back-projection. For our
    # testing we are enabling the parameter --projection-crop-after filter whereas default is
    # backproject. Hence, we can keep the adjustment of center_position_x disabled as use the value
    # provided in the command as is.
    # args.center_position_x = [pos + padding / 2 for pos in args.center_position_x]
    backproject.props.center_position_x = args.center_position_x
    backproject.props.center_position_z = args.center_position_z
    backproject.props.num_projections = args.number
    backproject.props.overall_angle = args.overall_angle
    backproject.props.addressing_mode = args.rgbabp_padding_mode
    graph.connect_nodes(flt_node, backproject)
    graph.connect_nodes(backproject, sink)

def run_rgba_bp(args: argparse.Namespace) -> None:
    """
    Simplified version of genreco for parallel beam tomographic reconstruction on a single GPU.
    
    Required parameters in args:
    - burst: Number of projections processed per kernel invocation
    - number: Total number of projections (num_projections)
    - center_position_x: Axis of rotation (list or single value)
    - center_position_z: Z position of the 0th slice (list or single value)
    - region: Z-region for reconstruction (from, to, step)
    - projections: Path to projection files
    - output: Output file path
    - width, height: Projection dimensions (determined automatically if not set)
    - Other defaults assumed: parallel beam, no rotations, etc.

    tofu rgbabp --projections radios --flats flats --darks darks/ --output slices.tiff --burst 24 \
        --number 3001 --overall-angle -180 --center-position-x 588.2 --center-position-z 606 \
            --region=-400,400,10 --absorptivity --projection-crop-after filter --verbose
    """
    st = time.time()
    scheduler = Ufo.FixedScheduler()
    graph = Ufo.TaskGraph()
    _ = setup_single_gpu_graph(args=args, graph=graph)
    thread = Thread(target=scheduler.run, args=(graph,), daemon=True)    
    thread.start()
    thread.join()
    duration = time.time() - st
    LOG.debug('Duration: %.2f s', duration)
