Input/Output
============


Image Reading
-------------

Tofu uses UFO's `Reader
<https://ufo-filters.readthedocs.io/en/master/generators.html#read-read>`_ which
can handle multiple file types, including single- and multi-page tif files. If
you specify a file, only that file will be read, if you specify a directory, all
files in the directory will be read. If you specify a pattern, all files
matching that pattern will be read. The following arguments for reading are
available for all of the ``tofu`` commands unless stated otherwise:

- ``--y``: Vertical coordinate from where to start reading the input image (default: ``0``);
- ``--height``: Number of rows which will be read (default: ``None``, meaning: all);
- ``--bitdepth``: Bit depth of raw files (bits per pixel, default: ``32``);
- ``--y-step``: Read every "step" row from the input (default: ``1``);
- ``--start``: Offset to the first read file (default: ``0``);
- ``--number``: Number of files to read (default: ``None``, meaning: all);
- ``--step``: Read every "step" file (default: ``1``).


Image Writing
-------------

Tofu writes tif files by UFO's `Writer
<https://ufo-filters.readthedocs.io/en/master/sinks.html?highlight=write#write-write>`_
and they can be either single- or multi-page, which is controlled by
``--output-bytes-per-file`` and ``--outuput`` arguments. If you set
``--output-bytes-per-file`` to ``0`` or any number smaller than the size of two
images in bytes, the output will be singe-page. If you specify a larger value,
there will be multiple images in one tif file. On the top of that, if the file
size is larger than 4 GB the tif file will be in the bigtiff format (this may
make it harder to open but ImageJ can handle it).  In the case you specify a
file name to be a single file, like ``output.tif``, you need to make sure that
``--output-bytes-per-file`` is large enough to facilitate all images which are
about to be written. Alternatively, you can specify the output as a *format
string* e.g. ``output-%04d.tif``, which will create files ``output-0000.tif``,
``output-0001.tif`` and so on. A new file will be created every time the amount
of bytes written in the current file would exceed the value specified by
``--output-bytes-per-file``.

.. note::
   You may use ``k``, ``m``, ``g``, ``t`` suffixes with
   ``--output-bytes-per-file`` to indicate respectively kibibytes
   (:math:`2^{10}` bytes), mebibytes (:math:`2^{20}` bytes) gibibytes
   (:math:`2^{30}` bytes) and tebibytes (:math:`2^{40}` bytes). When you want to
   make sure all fits into one file, just use e.g. "1t", which stands for "one
   tebibyte" and equals 1.099.511.627.776 bytes.
