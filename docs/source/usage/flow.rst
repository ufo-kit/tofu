Flow: Visual Graph Creation
===========================


You can use command ``tofu flow`` to start a graphical user interface in which UFO
tasks are represented as nodes which you can connect together. Once you have
created your flow you can execute it.


Nodes
-----

An operation on data is represented by a node in a flow. A node has inputs and
outputs, which have data types. An input or output of a node is
represented by a `port`, which is a circle on the left of the node in case of an
input and on the right in case of output. Every port has a data type which is
represented by color. There are two data types:

- `UFO`: you can connect all UFO nodes together
- `Array`: a numpy array which comes out from UFO's ``memory_out`` node and may be
  used to visualize the processing result by ``image_viewer``

A node may have properties (almost all UFO nodes do, e.g. ``path`` in the
``read`` node) which are listed and can be set inside the node. If you hover the
mouse over a property field, a tooltip will be shown describing that property.
When you right click on a node which holds properties, a context menu pops up
and let's you choose which properties you want to be visible and which not. Some
nodes, like ``general_backproject`` have many properties, many of which may be
considered `expert` options which are not needed most of the times. By hiding
these properties, you can avoid clutter. There is a pre-defined set of
properties, which are shown by default. When you create a node in the scene,
this setting is applied and you can check which properties are hidden by default
by clicking on a node right after its creation. In case a node doesn't have
properties, right click either doesn't take effect or pops up a context menu
relevant for that node. E.g. ``image_viewer``'s context menu allows you to
configure the viewer's behavior.

.. double click

A node might implement an action on a double click, e.g. ``read`` node opens a
dialog allowing you to choose the data ``path``, ``image_viewer`` pops up an
external image window which can be enlarged and put on another display for
convenience. Current nodes which implement double clicks are:

- ``Composite``: opens a new window with a scene displaying internal composite
  nodes
- ``read``: opens a dialog which allows you to choose the input ``path``
- ``write``: opens a dialog which allows you to choose the output ``filename``
- ``image_viewer``: opens the image in a new window


.. auto fill

``read`` node currently supports an `auto fill` option, which may be invoked via
the main menu bar. The node sets its ``number`` property to the number of
detected images found in the specified ``path``.


UFO Nodes
~~~~~~~~~

An UFO node represents an `UFO task` and holds properties which are the
Properties of this `UFO task`. Please check the `UFO Filters Reference
<http://ufo-filters.readthedocs.io>`_ for the complete list of UFO tasks and
their properties. When you create an UFO node, its properties are the default
properties of the encapsulated UFO task.


Composite Nodes
~~~~~~~~~~~~~~~

In order to reduce clutter, you can combine several nodes in a composite node
(main menu's `Nodes->Create Composite`) and you can also nest composites, i.e.
have a composite node and create another composite node with the first one
inside. Internal nodes are listed as groups in the composite node in the scene
and similarly to property nodes, you can show and hide different internal nodes
from the listing. The input and output ports of a composite node are the ports
of its internal nodes which are not connected at the time of composite node's
creation.

A double click on a composite node opens its internal nodes in a separate
window, where you can edit their properties but you can't add new nodes or
change connections. You can open this window also by pressing `Nodes->Edit
Composite` in the main menu.

In order to store a composite node for later usage, you can export it into a
file via the main menu's `Nodes->Export Composite`. You can import composite
node definitions by `Nodes->Import Composites`, which are then available in the
flow scene's context menu in the `Composite` category.

There are several pre-defined composite nodes available via the scene's context
menu (category `Composite`), they are:

- ``CFlatFieldCorrect`` encapsulates readers and averagers and the
  ``flat_field_correct`` node itself
- ``CPhaseRetrieve`` encapsulates padding, fourier tranformation and the phase
  retrieval itself


General Backproject
~~~~~~~~~~~~~~~~~~~

This is a versatile back projection node which can reconstruct tomographic,
laminographic, parallel and cone beam data. It has one parameter which is not
part of the UFO task, ``slice-memory-coeff``. This parameter sets the fraction
(0 - 1) of a graphic card's memory which will be used to store the reconstructed
volume. If you are working with graphic cards which have other processes running
on them and these processes use a lot of memory, then you might need to reduce
this parameter.


Phase Retrieval
~~~~~~~~~~~~~~~

``retrieve_phase`` node may have varying number of inputs in order to support
multi-distance phase retrieval. You specify the number of inputs in a dialog
when you create the node. If you specify more than one input, the retrieval
method will be the multidistance contrast transfer function and the ``method``
field will be fixed to `ctf_multidistance`. In this case, fields ``distance-x``
and ``distance-y`` will be disabled. If you specify one input, you may choose
different methods via the ``method`` field. In this case, you can either specify
one value in the ``distance`` field, or specify separate distances for `x` and
`y` directions via ``distance-x`` and ``distance-y`` fields (they take
precedence over ``distance`` field in case they are both non-zero).


Image Viewer
~~~~~~~~~~~~

``image_viewer`` lets you display the results of your flow. It is composed of
the image itself and three text boxes with sliders, which allow you to specify
the image index shown, the black point and white point. In case only one image
is input the first slider is hidden. Right click on the node opens a context
menu which allows you to reset the black and white points (`Reset`), set them
automatically (`Auto Levels`) and specify whether they should be automatically
adjusted when new images are on input or left unchanged (`Auto Levels on New
Image`). Double click opens the image in a new window by using the PyQtGraph_
library. In case a separate window is open, image index, black and white point
settings can be set eigher in the flow node or in the window and they are
reflected in both the node and the window.


Flows
-----

On right click in the flow scene a context menu will pop up and you will be able
to add nodes. Then you can connect them by dragging a node's output port into
another node's input port if those ports have the same data type, which are
distinguished by port colors. By connecting node ports you create your flow
which you may later execute. Every node in the scene must have a unique
`caption`, so when you create a ``read`` node, the caption will be ``Read``,
when you create another ``read`` node, the caption will be ``Read 2`` and so on.
This is important for setting property links explained below.

The roots of the flow in the scene must be UFO nodes and leaves may have `UFO` or
`Array` type. It is not possible to go from `UFO` to `Array` and back to `UFO`,
i.e. the `UFO` portion of the flow in the scene must be one contiguous component
of the flow. There may be only one flow in the scene and it must be completely
connected (there can't be disconnected ports, e.g. ``flat_field_correct``'s
``darks`` port).

You can delete the current flow by pressing `Flow->New`, you can save a flow
into a flow file (.flow) by `Flow->Save` and open such files by `Flow->Open`.


Property Links
--------------

A property of a node might depend on another node's property, e.g. the number of
dimensions of an ``ifft`` node depends on the number of dimensions of the
predecessing ``fft`` task. In order to reduce the number of properties you need
to set, you can `link` properties together, i.e. when you set one node's
property, all the linked nodes' properties will be updated (e.g. when you change
the number of dimensions of an ``ifft`` node, the number of dimensions of the
linked ``fft`` node will be updated as well.

You can create property links in the `Property Links` window (open via main menu
bar's `View` field). At the top of the window, there is a tree view of the nodes
in the scene. Its items are the nodes in the flow scene, and in case there are
composites, they are listed recursively. The last level of the view are the
properties of the nodes in the flow. You can drag these properties into the list
in the second half of the window to start creating links. If you drag a property
to a new row or a row doesn't exist yet, it is automatically added. If you drag
a property into an existing row (over an existing cell), it is appended to this
row and a link is created. Links are allowed only for properties with compatible
data types, e.g. you cannot link ``read``'s ``path`` (a string) to ``fft``'s
``dimensions`` (a number). Also keep in mind that nodes which are able to
process batches have their fields which are responsible for receiving different
batches (e.g. ``number`` of the ``memory_out`` node) have string data type (so
that you can type `{region}` inside)


Execution
---------

Execution of the flow starts with executing the UFO part of the flow, and if
there is a ``memory_out`` and subsequent nodes, they get the result of the
UFO processing as the batches are finished (or just one batch if no
batch-capable nodes are in the flow). You start it by invoking main menu bar's
`Flow->run` action. You can abort the execution but invoking `Flow->abort`.


Batch Processing
~~~~~~~~~~~~~~~~

Some nodes require a lot of GPU memory and they can't process all the input data
at once (e.g. ``general_backproject``). Based on your system, they can split the
work on their own and tell the execution mechanism to run multiple batches. If
your system has multiple GPUs, ``tofu flow`` may create several batches and each
of these batches may be executed on one or more cards in your system.
Currently, only *one* batch processing task is allowed in the flow and only
``general_backproject`` supports batch processing.

In case your flow contains a node which is able to produce batches, then your
consumer nodes must be able to process batches and they must be notified of the
fact that they will get more batches on input. Currently, ``write`` and
``memory_out`` support batches and this is how you set them up for it:

- ``write``: ``filename`` must contain `{region}` somewhere in it, e.g.
  `slices-{region}.tif`
- ``memory_out``: ``number`` field must be set to `{region}`

The `{region}` template is then replaced by the current batch identifier provided by the
producer node which is capable of batch processing, e.g. `slices-0.tif`,
`slices-100.tif` and so on.

If there is no node capable of producing batches, this is how you set them up
for normal, non-batch processing:

- ``write``: ``filename`` field set to normal file name, e.g. `slices.tif`
- ``memory_out``: ``number`` field set to the number of input images


Python Console
--------------

Main menu's `View->Python Console` opens up a Python interpreter console with
attribute ``scene`` set to the flow scene, which allows you to interact with the
nodes programatically, see `qtpynodeeditor docs
<https://klauer.github.io/qtpynodeeditor/api.html?highlight=scene#qtpynodeeditor.FlowScenefor>`_
more details on flow scene functionality.


.. _PyQtGraph: http://www.pyqtgraph.org/
.. _qtpynodeeditor: 
