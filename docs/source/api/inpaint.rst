Inpainting
==========


Module for inpainting images, mainly used for the following:

    * interpolation of holes in the images
    * seamless cloning
    * removal of harsh transitions between image borders for cross removal in
      the power spectrum


Power Spectrum Cross Removal
----------------------------

The helper function for the removal of the cross in the power spectrum is
:func:`.prepare_border_smoothing`. For details see :cite:`moisan2011periodic`.
Our implementation, which uses the 2-step forward/backward gradient to get the
Laplacian in :func:`.create_inpaint_pipeline` makes the "v" field slightly
different than in the paper (defined in :cite:`moisan2011periodic` below eq.
11). The right/bottom border is equal to "v" from the paper but the left/top
border are True Laplacian values.  Nevertheless, the other side does get inside,
so the filtering result is very similar. How is it similar and different::

    g_forw( 0) = f(1) - f( 0)
    g_forw(-1) = f(0) - f(-1)
    # This is different from the paper
    g_back( 0) = g_forw( 0) - g_forw(-1) = -2f(0) + f(1) + f(-1)
    # After the forward pass, the gradient field is set to zeros everywhere except the borders.
    # This is equivalent to the paper
    g_back(-1) = g_forw(-1) - g_forw(-2) = g_forw(-1) - 0 = f(0) - f(-1)


On the top of that, we use the fact that:

.. math::
    :nowrap:

    \begin{align}
        g(x, y)
        & = f(x, y) - \mathcal{F}^{-1} \left\{
            \frac{\mathcal{F}
                \left[
                    \frac{\partial}{\partial x}
                        \left(
                            \left( \frac{\partial}{\partial x} f(x, y) \right) m(x, y)
                        \right)
                    + \frac{\partial}{\partial y}
                        \left(
                            \left( \frac{\partial}{\partial y} f(x, y) \right) m(x, y)
                        \right)
                \right]}
            {L(u, v)} \right\} \\
        & = \mathcal{F}^{-1}
            \left\{
                \frac{\mathcal{F}
                \left[
                    \frac{\partial}{\partial x}
                        \left(
                            \left(
                                \frac{\partial}{\partial x} f(x, y)
                            \right) \left( 1 - m(x, y) \right)
                        \right)
                    + \frac{\partial}{\partial y}
                        \left(
                            \left(
                                \frac{\partial}{\partial y} f(x, y)
                            \right) \left( 1 - m(x, y) \right)
                        \right)
                \right]}
                {L(u, v)}
            \right\} \\
        & = \mathcal{F}^{-1}
            \left\{
                \frac{\mathcal{F}
                \left[
                    \frac{\partial}{\partial x}
                            \left( \frac{\partial}{\partial x} f(x, y) \right)
                    + \frac{\partial}{\partial y}
                            \left( \frac{\partial}{\partial y} f(x, y) \right)
                \right]} {L(u, v)}
                - \frac{\mathcal{F}
                    \left[
                        \frac{\partial}{\partial x}
                            \left(
                                \left( \frac{\partial}{\partial x} f(x, y) \right) m(x, y)
                            \right)
                        + \frac{\partial}{\partial y}
                            \left(
                                \left( \frac{\partial}{\partial y} f(x, y) \right) m(x, y)
                            \right)
                    \right]} {L(u, v)}
            \right\} \\
        & = \mathcal{F}^{-1}
            \left\{
                \mathcal{F} \left[ f(x, y) \right]
                - \frac{\mathcal{F}
                    \left[
                        \frac{\partial}{\partial x}
                            \left(
                                \left( \frac{\partial}{\partial x} f(x, y) \right) m(x, y)
                            \right)
                        + \frac{\partial}{\partial y}
                            \left(
                                \left( \frac{\partial}{\partial y} f(x, y) \right) m(x, y)
                            \right)
                    \right]} {L(u, v)}
            \right\}
    \end{align}

to remove the need of the subtraction from the original image, thus, we implement Eq. (2)
instead of Eq. (1). :math:`\mathcal{F}` is the Fourier transform, :math:`m(x, y)` is the binary
mask which specifies which pixels in the gradient will be zeroed, :math:`L(u, v)` is the Laplace
operator in Fourier space.


Inpaint Module
--------------

.. automodule:: tofu.inpaint
    :members:
