import argparse
import logging
import time
from threading import Thread
from gi.repository import Ufo
from .preprocess import create_flat_correct_pipeline, create_projection_filtering_pipeline
from .tasks import get_task, get_writer
from .util import determine_shape, fbp_filtering_in_phase_retrieval

LOG = logging.getLogger(__name__)

def create_ffc_flt_pipeline(
        args: argparse.Namespace,
        graph: Ufo.TaskGraph,
        processing_node: int) -> Ufo.TaskNode:
    """
    Configures computational graph for flat-field correction and filtering.
    
    :param args: parameters for nodes.
    :type args: argparse.Namespace
    :param graph: Ufo task graph
    :type graph: Ufo.TaskGraph
    :param gpu_index: index of the gpu node
    :type processing_node: int
    :return: final task node after connecting flat-field to filtering
    :rtype: Ufo.TaskNode
    """
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
    """
    Configures full computational graph for reconstruction.
    
    :param args: parameters for nodes.
    :type args: argparse.Namespace
    :param graph: Ufo task graph.
    :type graph: Ufo.TaskGraph
    :param gpu_index: index of the gpu node
    :type gpu_index: int
    """
    determine_shape(args=args, store=True)
    sink: Ufo.TaskNode = get_writer(params=args)
    source: Ufo.TaskNode = create_ffc_flt_pipeline(args=args, graph=graph, processing_node=gpu_index)
    backproject: Ufo.TaskNode = get_task('rgba-backproject', processing_node=gpu_index)
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
    graph.connect_nodes(source, backproject)
    graph.connect_nodes(backproject, sink)

def run_rgba_bp(args: argparse.Namespace) -> None:
    """
    Implements optimized backprojection leveraging RGBA color channels in texture memory.
    
    Required parameters in args:
    For testing it is easier to focus on absorption reconstruction. Hence, we focus on the minimum
    required parameters for flat-field correction with absorptivity, filtering and back-projection.

    - projections: location of the projections.
    - flats: location of the flat fields.
    - darks: location of the dark fields.
    - output: location to write the final output slices.
    - burst: number of projections to be processed per kernel invocation.
    - number: number of projections to be processed.
    - overall-angle: angles of rotation.
    - center_position_x: axis of rotation
    - center_position_z: z-position of the 0th slice.
    - region: z-region for reconstruction (from, to, step)
    - absorptivity: indicates to compute absorption (Beer-Lambert) from transmission.
    - projection-crop-after: indicates to crop the projection (we use filter for efficiency,
    default backproject)

    Example Command:
    tofu rgbabp --projections radios --flats flats --darks darks/ --output slices.tiff --burst 24 \
        --number 3001 --overall-angle -180 --center-position-x 588.2 --center-position-z 606 \
            --region=-400,400,10 --absorptivity --projection-crop-after filter --verbose
    """
    try:
        assert args.darks
        assert args.flats
        assert args.projections
        assert args.output
    except AssertionError:
        raise RuntimeError('test version: darks, flats, projections, output are needed')
    print(f"###################################################Called#####")
    st = time.time()
    scheduler = Ufo.FixedScheduler()
    graph = Ufo.TaskGraph()
    _ = setup_single_gpu_graph(args=args, graph=graph)
    thread = Thread(target=scheduler.run, args=(graph,), daemon=True)    
    thread.start()
    thread.join()
    duration = time.time() - st
    LOG.debug('Duration: %.2f s', duration)
