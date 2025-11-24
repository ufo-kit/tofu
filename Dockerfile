ARG PYTHON_VERSION=3.11

FROM debian:12-slim AS ufo-builder
ARG UFO=master
ARG UFO_FILTERS=master
ARG DEBIAN_FRONTEND=noninteractive

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

RUN git clone --depth 1 https://github.com/ufo-kit/ufo-core.git --branch ${UFO} && \
    git clone --depth 1 https://github.com/ufo-kit/ufo-filters.git --branch ${UFO_FILTERS}

RUN cd /ufo-core && meson build --libdir=lib -Dbashcompletiondir=$HOME/.local/share/bash-completion/completions && cd build && ninja install
RUN cd /ufo-filters && \
    meson build --libdir=lib -Dcontrib_filters=True && \
    cd build && ninja install

FROM python:${PYTHON_VERSION} AS developer
COPY --from=ufo-builder /usr/local/ /usr/local/
COPY --from=ufo-builder /ufo-core/python /ufo-core/python

# Add any system dependencies for the developer/build environment here
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgirepository1.0-dev \
    python-gi-dev \
    libjson-glib-dev \
    ocl-icd-opencl-dev \
    # runtime
    libclfft2 \
    libhdf5-103-1 \
    libzmq5 \
    # ocl-icd-libopencl1 \ # runtime
    # libjson-glib-1.0-0 \ # runtime
    # qt5
    libqt5gui5 \
    dbus \
    && rm -rf /var/lib/apt/lists/*

# OpenCL nvidia
RUN mkdir -p /etc/OpenCL/vendors && \
    echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,utility

# Things to remove
COPY requirements-ufo.txt /

# Required for ufo-core/python meson build to find ufo
ENV LD_LIBRARY_PATH=/usr/local/lib/:$LD_LIBRARY_PATH
ENV GI_TYPELIB_PATH=/usr/local/lib/girepository-1.0:$GI_TYPELIB_PATH
ENV PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH

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
    pip install --no-cache-dir /ufo-core/python

RUN rm -rf /ufo-core

# The build stage installs the context into the venv
FROM developer AS build
COPY . /context
WORKDIR /context
RUN touch dev-requirements.txt && pip install -c dev-requirements.txt .

# The runtime stage copies the built venv into a slim runtime container
FROM python:${PYTHON_VERSION}-slim AS runtime

COPY --from=ufo-builder /usr/local/ /usr/local/
COPY --from=build /opt/venv /opt/venv/
# Add apt-get system dependecies for runtime here
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjson-glib-dev \
    libgirepository-1.0-1 \
    libclfft2 \
    ocl-icd-libopencl1 \
    libhdf5-103-1 \
    libzmq5 \
    # qt5
    libqt5gui5 \
    dbus \
    && rm -rf /var/lib/apt/lists/*

# OpenCL nvidia
RUN mkdir -p /etc/OpenCL/vendors && \
    echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd
ENV NVIDIA_VISIBLE_DEVICES all
ENV NVIDIA_DRIVER_CAPABILITIES compute,utility
ENV GI_TYPELIB_PATH=/usr/local/lib/girepository-1.0:$GI_TYPELIB_PATH
ENV PATH=/opt/venv/bin:$PATH