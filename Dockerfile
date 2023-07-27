FROM python:3.11.4 AS builder

# automode
ARG AUTOMODE="OFF"
ARG CONFIG=""
ARG AUTOUPDATE="OFF"
ENV AUTOMODE=$AUTOMODE CONFIG=$CONFIG AUTOUPDATE=$AUTOUPDATE

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
RUN wget -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2
RUN tar xjvf ffmpeg-snapshot.tar.bz2
WORKDIR ffmpeg
RUN PKG_CONFIG_PATH="$HOME/ffmpeg_build/lib/pkgconfig" ./configure \
  --prefix="$HOME/ffmpeg_build" \
  --pkg-config-flags="--static" \
  --extra-cflags="-I$HOME/ffmpeg_build/include" \
  --extra-ldflags="-L$HOME/ffmpeg_build/lib" \
  --extra-libs="-lpthread -lm" \
  --ld="g++" \
  --bindir="/usr/local/bin" \
  --enable-gpl \
  --enable-gnutls \
  --enable-libaom \
  --enable-libass \
  --enable-libfdk-aac \
  --enable-libfreetype \
  --enable-libmp3lame \
  --enable-libopus \
  --enable-libsvtav1 \
  --enable-libdav1d \
  --enable-libvorbis \
  --enable-libvpx \
  --enable-libx264 \
  --enable-libx265 \
  --enable-nonfree
RUN make -j$(nproc)
RUN make install -j$(nproc)
WORKDIR /

# libvips
# https://www.libvips.org/install.html#building-libvips-from-source
RUN apt-get --no-install-recommends install -y \
    # build deps
    ninja-build build-essential pkg-config bc \
    # other deps
    libcgif-dev libfftw3-dev libopenexr-dev libgsf-1-dev libglib2.0-dev liborc-dev libopenslide-dev libmatio-dev libwebp-dev libjpeg-dev libexpat1-dev libexif-dev libtiff5-dev libcfitsio-dev libpoppler-glib-dev librsvg2-dev libpango1.0-dev libopenjp2-7-dev libimagequant-dev
RUN pip install meson
RUN curl -s https://api.github.com/repos/libvips/libvips/releases/latest | grep -wo "\"https://github.com/libvips/libvips/releases/download/.*.tar.xz\"" | tr -d \'\" | wget -i -
RUN mkdir vips
RUN tar -xf vips*.tar.xz -C vips --strip-components 1
WORKDIR vips
RUN ls
RUN meson setup build  --libdir=lib --buildtype=release -Dintrospection=false
WORKDIR build
RUN meson compile
RUN meson test
RUN meson install
RUN ldconfig
WORKDIR /

RUN apt-get -y autoremove

# python packages
RUN pip install --upgrade pip --no-warn-script-location --root-user-action=ignore
RUN pip install --user poetry --no-warn-script-location --root-user-action=ignore
COPY . mediaforge
WORKDIR mediaforge
RUN python -m poetry install

RUN cp config.example.py config.py
# so mediaforge knows to prompt with nano
ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["/bin/bash", "./dockerentry.sh"]
#CMD ["/bin/bash", "./dockerentry.sh"]



