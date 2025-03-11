FROM debian:12-slim
ARG DEBIAN_FRONTEND=noninteractive

COPY requirements-ufo.txt /

RUN apt-get update && apt-get -y upgrade && apt-get install -y --no-install-recommends \
        # General build requirements
        apt-utils \
        build-essential \
        meson \
        ninja-build \
        git \
        # ufo-core
        asciidoc-base \
        bash-completion \
        cmake \
        gobject-introspection \
        # gtk-doc-tools \
        libgirepository1.0-dev \
        libglib2.0-dev \
        libjson-glib-dev \
        libzmq3-dev \
        ocl-icd-opencl-dev \
        # ufo-filters
        libclfft-dev \
        libgsl-dev \
        libhdf5-dev \
        libtiff-dev \
        # ufo-core python
        && apt-get install -y \
        python3-dev \
        python3-venv \
        libcairo2-dev \
        python-gi-dev \
        # qt5
        && apt-get install -y --no-install-recommends \
        libqt5gui5 \
        dbus \
        && rm -rf /var/lib/apt/lists/*

ENV LD_LIBRARY_PATH=/usr/local/lib/:$LD_LIBRARY_PATH
ENV GI_TYPELIB_PATH=/usr/local/lib/girepository-1.0:$GI_TYPELIB_PATH
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH

RUN mkdir -p /etc/OpenCL/vendors && \
    echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,utility

RUN git clone --depth 1 https://github.com/ufo-kit/ufo-core.git --branch master && \
    git clone --depth 1 https://github.com/ufo-kit/ufo-filters.git --branch master && \
    git clone --depth 1 https://github.com/ufo-kit/tofu --branch master

RUN cd /ufo-core && meson build --libdir=lib -Dbashcompletiondir=$HOME/.local/share/bash-completion/completions && cd build && ninja install
RUN cd /ufo-filters && \
    sed -i -E "s/find_program.'python/find_program('python3/" src/meson.build && sed -i -E "s/find_program.'python/find_program('python3/" tests/meson.build && \
    meson build --libdir=lib -Dcontrib_filters=True && cd build && ninja install

# Use a venv to avoid interfering with system Python.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
# This is equivalent to `source $VIRTUAL_ENV/bin/activate` but it
# persists into the runtime so we avoid the need to account for it
# in ENTRYPOINT or CMD.
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir -r /requirements-ufo.txt && \
    pip install --no-cache-dir /ufo-core/python && \
    pip install --no-cache-dir -r /tofu/requirements-flow.txt && \
    pip install --no-cache-dir /tofu

RUN rm -rf /ufo-core /ufo-filters /tofu
