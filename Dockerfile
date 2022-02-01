FROM debian:stable

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Berlin

RUN apt-get update && \
    apt-get install -y \
        bash \
        libufo-bin \
        ufo-filters \
        gir1.2-ufo-1.0 \
        python3-gi \
        python3-pip && \
    rm -rf /var/lib/apt/lists/* && \
    pip3 install cython

COPY . .

RUN python3 setup.py install
