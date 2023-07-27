FROM python:3.11.4 AS builder

# automode
ARG AUTOMODE="OFF"
ARG CONFIG=""
ARG AUTOUPDATE="OFF"
ENV AUTOMODE=$AUTOMODE CONFIG=$CONFIG AUTOUPDATE=$AUTOUPDATE

# copy mediaforge code to container
COPY . mediaforge
RUN chmod +x /mediaforge/docker/*

# we need non-free
RUN printf "\ndeb https://deb.debian.org/debian bookworm contrib non-free" >> "/etc/apt/sources.list.d/debian-extended.list"

# apt
RUN apt-get -y update
RUN apt-get -y upgrade
# most packages
RUN apt-get --no-install-recommends install -y nano imagemagick nodejs libgif-dev lsb-release software-properties-common

# ffmpeg
# https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu#FFmpeg
RUN apt-get --no-install-recommends install -y  \
    # build deps
  autoconf automake build-essential cmake git-core libass-dev libfreetype6-dev libgnutls28-dev libmp3lame-dev libsdl2-dev libtool libva-dev libvdpau-dev libvorbis-dev libxcb1-dev libxcb-shm0-dev libxcb-xfixes0-dev meson ninja-build pkg-config texinfo wget yasm zlib1g-dev \
    # build deps "for ubuntu 20.04"
  libunistring-dev libaom-dev libdav1d-dev \
    # deps not listed in the build guide grrr \
  libsvtav1enc-dev \
    # optional deps
  libdav1d-dev libopus-dev libfdk-aac-dev libvpx-dev libx265-dev libnuma-dev libx264-dev nasm
RUN bash -c /mediaforge/docker/buildffmpeg.sh

# libvips
# https://www.libvips.org/install.html#building-libvips-from-source
RUN apt-get --no-install-recommends install -y \
    # build deps
    ninja-build build-essential pkg-config bc \
    # other deps
    libcgif-dev libfftw3-dev libopenexr-dev libgsf-1-dev libglib2.0-dev liborc-dev libopenslide-dev libmatio-dev libwebp-dev libjpeg-dev libexpat1-dev libexif-dev libtiff5-dev libcfitsio-dev libpoppler-glib-dev librsvg2-dev libpango1.0-dev libopenjp2-7-dev libimagequant-dev
RUN pip install --upgrade --user pip --no-warn-script-location --root-user-action=ignore
RUN pip install meson --no-warn-script-location --root-user-action=ignore
RUN bash -c /mediaforge/docker/buildvips.sh

RUN apt-get -y autoremove

# python packages
RUN pip install --user poetry --no-warn-script-location --root-user-action=ignore

WORKDIR mediaforge
RUN python -m poetry install

RUN cp config.example.py config.py
# so mediaforge knows to prompt with nano
ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["/bin/bash", "/mediaforge/docker/dockerentry.sh"]
#CMD ["/bin/bash", "./dockerentry.sh"]



