import gi
import logging
import numpy as np
gi.require_version('Ufo', '0.0')
from gi.repository import Ufo
from tofu.tasks import get_memory_in, get_task, get_writer
from tofu.util import (
    determine_shape,
    make_subargs,
    run_scheduler,
    set_node_props,
    setup_read_task,
    setup_padding,
)


LOG = logging.getLogger(__name__)


SELECT_SRC = """
kernel void
select_simple (global float *image,
               global float *mask,
               global float *output)
{
    const size_t idx = get_global_id (1) * get_global_size (0) + get_global_id (0);
    output[idx] = mask[idx] > 0.0f ? 0.0f : image[idx];
}

kernel void
select_guidance (global float *image,
                 global float *mask,
                 global float *guidance,
                 global float *output)
{
    const size_t idx = get_global_id (1) * get_global_size (0) + get_global_id (0);
    output[idx] = mask[idx] > 0.0f ? guidance[idx] : image[idx];
}
"""

ADD_CONSTANT_SRC = """
kernel void
add_constant (global float *image,
              global float *value,
              global float *output)
{
    const size_t idx = get_global_id (1) * get_global_size (0) + get_global_id (0);

    output[idx] = image[idx] + value[0];
}
"""


def _make_discrete_inverse_laplace(width, height):
    """Make discrete Laplace deconvolution kernel special for this use case, where we do not care
    about the (0, 0) frequency becuase the kernel is going to be applied on Laplace-filtered data,
    which has zero mean.
    """
    f = np.fft.fftfreq(width)
    g = np.fft.fftfreq(height)
    f, g = np.meshgrid(f, g)
    # From discrete Laplace and time shift: F[f''(x, y)] = -4 F[f(x, y)]
    # + F[f(x + 1, y)] + F[f(x - 1, y)] + F[f(x, y + 1)] + F[f(x, y - 1)] = the result below when we
    # use the time shift property of the Fourier transform.
    kernel = 2 * (np.cos(2 * np.pi * f) + np.cos(2 * np.pi * g) - 2)
    # Make this invertible by simply setting the (0, 0) frequency to 1 instead of making sure that
    # after the inversion it is 0. We can afford this becuase we know the input to filtering will be
    # Laplace-filtered -> zero mean -> (0, 0) frequency = 0.
    kernel[0, 0] = 1

    return (1 / kernel).astype(np.float32)


def prepare_border_smoothing(padded_width, padded_height):
    """
    The use case here is mainly the removal of the cross at (0, 0) in the power spectrum by masking
    out the borders of the image, i.e. the gradients are forced to go to zeros at the borders and
    thus removing the sharp transitions when we consider the periodicity assumed by the DFT.
    *padded_width* and *padded_height* are the width and height of the FFT-padding, not the original
    image shape. One should use `mirrored_repeat' padding mode on the input images to get the
    FFT-padded image, compute the mask here and use it for inpainting.
    """
    mask = np.ones((padded_width, padded_height), dtype=np.float32)
    mask[1:-1, 1:-1] = 0
    mem_in_task = get_memory_in(mask)

    return mem_in_task


def _get_gradient_task(finite_difference_type, direction):
    return get_task(
        "gradient",
        finite_difference_type=finite_difference_type,
        direction=direction,
        addressing_mode="repeat",
    )


def create_inpaint_pipeline(
    args,
    graph,
    processing_node=None
):
    """
    Create tasks needed for inpainting and connect them. The pipeline has three inputs and one
    output, which is the inpainted image. Based on :cite:`MOREL2012342`.
    """
    determine_shape(args, path=args.projections, store=True, do_raise=True)

    if not args.inpaint_padded_width:
        args.inpaint_padded_width = args.width
    if not args.inpaint_padded_height:
        args.inpaint_padded_height = args.height

    do_pad = args.inpaint_padded_width != args.width and args.inpaint_padded_height != args.height
    use_guidance = not args.harmonize_borders and args.guidance_image
    LOG.debug("inpaint padding on: %s", do_pad)
    LOG.debug("inpaint using guidance image: %s", use_guidance)

    copy_projections = Ufo.CopyTask()
    copy_mask = Ufo.CopyTask()
    copy_guidance = Ufo.CopyTask() if use_guidance else None

    if do_pad:
        # Padding
        pad_projections = get_task("pad")
        pad_mask = get_task("pad")
        pad_guidance = get_task("pad")
        for pad_task in (pad_projections, pad_mask, pad_guidance):
            setup_padding(
                pad_task,
                args.width,
                args.height,
                args.inpaint_padding_mode,
                pad_width=args.inpaint_padded_width - args.width,
                pad_height=args.inpaint_padded_height - args.height,
                centered=False
            )
        graph.connect_nodes(pad_projections, copy_projections)
        graph.connect_nodes(pad_mask, copy_mask)
        if use_guidance:
            graph.connect_nodes(pad_guidance, copy_guidance)
        else:
            pad_guidance = None
        inputs = (pad_projections, pad_mask, pad_guidance)
    else:
        inputs = (copy_projections, copy_mask, copy_guidance)
    # First gradient is forward and the second backward -> we get exactly the discrete Laplace after
    # the two passes.
    gx = _get_gradient_task("forward", "horizontal")
    gy = _get_gradient_task("forward", "vertical")
    ggx = _get_gradient_task("backward", "horizontal")
    ggy = _get_gradient_task("backward", "vertical")
    fft_task = get_task("fft", dimensions=2)
    ifft_task = get_task("ifft", dimensions=2)
    add_ggx_ggy = get_task("opencl", kernel="add", dimensions=2)
    mul_task = get_task("opencl", kernel="multiply", halve_width=False, dimensions=2)
    select_kernel = "select_guidance" if use_guidance else "select_simple"
    select_gx = get_task("opencl", source=SELECT_SRC, kernel=select_kernel, dimensions=2)
    select_gy = get_task("opencl", source=SELECT_SRC, kernel=select_kernel, dimensions=2)
    # We are computing discrete gradients -> Laplace must also be discrete
    lap_kernel = _make_discrete_inverse_laplace(
        args.inpaint_padded_width,
        args.inpaint_padded_height
    )
    # Multiply interleaved complex array -> a * z = a * Re[z] + j * a * Im[z]
    mem_in_task = get_memory_in(lap_kernel + 1j * lap_kernel)
    if args.preserve_mean:
        mean_task = get_task("measure", axis=-1, metric="mean")
        add_constant = get_task(
            "opencl", source=ADD_CONSTANT_SRC, kernel="add_constant", dimensions=2
        )

    # First derivative
    graph.connect_nodes(copy_projections, gx)
    graph.connect_nodes(copy_projections, gy)

    # Select guidance or zeros where mask >= 0
    graph.connect_nodes_full(gx, select_gx, 0)
    graph.connect_nodes_full(gy, select_gy, 0)
    graph.connect_nodes_full(copy_mask, select_gx, 1)
    graph.connect_nodes_full(copy_mask, select_gy, 1)
    if use_guidance:
        guidance_gx = _get_gradient_task("forward", "horizontal")
        guidance_gy = _get_gradient_task("forward", "vertical")

        graph.connect_nodes(copy_guidance, guidance_gx)
        graph.connect_nodes(copy_guidance, guidance_gy)
        graph.connect_nodes_full(guidance_gx, select_gx, 2)
        graph.connect_nodes_full(guidance_gy, select_gy, 2)

    # Second derivative
    graph.connect_nodes(select_gx, ggx)
    graph.connect_nodes(select_gy, ggy)

    # Sum -> Laplacian
    graph.connect_nodes_full(ggx, add_ggx_ggy, 0)
    graph.connect_nodes_full(ggy, add_ggx_ggy, 1)

    # Deconvolve with Laplacian
    graph.connect_nodes(add_ggx_ggy, fft_task)
    graph.connect_nodes_full(fft_task, mul_task, 0)
    graph.connect_nodes_full(mem_in_task, mul_task, 1)
    graph.connect_nodes(mul_task, ifft_task)

    if args.preserve_mean:
        # Get the mean back to the one of the input image
        graph.connect_nodes(copy_projections, mean_task)
        graph.connect_nodes_full(ifft_task, add_constant, 0)
        graph.connect_nodes_full(mean_task, add_constant, 1)
        last = add_constant
    else:
        last = ifft_task

    outputs = (last,)

    return (inputs, outputs)


def run(args):
    """Usage with tofu: create readers, the pipeline and run it."""
    if args.harmonize_borders:
        if args.mask_image:
            LOG.warning(
                "--mask-image has no effect when --harmonize-borders is specified"
            )
        if args.guidance_image:
            LOG.warning(
                "--guidance-image has no effect when --harmonize-borders is specified"
            )
        if args.inpaint_padding_mode != "mirrored_repeat":
            LOG.warning(
                "Padding mode should be `mirrored_repeat' for smooth transitions between "
                "true image borders and padded borders"
            )
    elif not args.mask_image:
        raise ValueError("One of --mask-image or --harmonize-borders must be specified")

    # Reading
    reader = get_task("read")
    roi_args = make_subargs(args, ['y', 'height', 'y_step'])
    set_node_props(reader, args)
    setup_read_task(reader, args.projections, args)

    out_task = get_writer(args)
    graph = Ufo.TaskGraph()

    ((input_projections, input_mask, input_guidance), (last,)) = create_inpaint_pipeline(
        args,
        graph,
    )

    if args.harmonize_borders:
        mask_reader = prepare_border_smoothing(
            args.inpaint_padded_width,
            args.inpaint_padded_height
        )
    else:
        mask_reader = get_task("read")
        set_node_props(mask_reader, roi_args)
        setup_read_task(mask_reader, args.mask_image, args)

    graph.connect_nodes(reader, input_projections)
    graph.connect_nodes(mask_reader, input_mask)
    if not args.harmonize_borders and args.guidance_image:
        guidance_reader = get_task("read")
        set_node_props(guidance_reader, roi_args)
        setup_read_task(guidance_reader, args.guidance_image, args)
        graph.connect_nodes(guidance_reader, input_guidance)

    graph.connect_nodes(last, out_task)

    # CopyTask works only with FixedScheduler
    sched = Ufo.FixedScheduler()
    run_scheduler(sched, graph)
