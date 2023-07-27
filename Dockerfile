FROM python:3.11.4 AS builder

# automode
ARG AUTOMODE="OFF"
ARG CONFIG=""
ARG AUTOUPDATE="OFF"
ENV AUTOMODE=$AUTOMODE CONFIG=$CONFIG AUTOUPDATE=$AUTOUPDATE

COPY . mediaforge
# like cd but for docker
WORKDIR mediaforge

# Install required dependencies for building
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    imagemagick \
    libexpat1-dev \
    libgirepository1.0-dev \
    libglib2.0-dev \
    libgif-dev \
    nodejs \
    pkg-config \
    unzip \
    yasm \
    nano
	
# Install latest supported libvips-dev
RUN apt-get install -y libvips42 gir1.2-vips-8.0 libfftw3-dev libpango1.0-dev gettext liborc-0.4-dev libmatio-dev libcfitsio-dev libopenslide-dev libgsf-1-dev libcgif-dev libpoppler-glib-dev libjxl-dev libimagequant-dev libheif-dev
RUN dpkg -i $(curl -w "%{filename_effective}" -LO "http://http.us.debian.org/debian/pool/main/v/vips/gir1.2-vips-8.0_8.14.2-1_amd64.deb")
RUN dpkg -i $(curl -w "%{filename_effective}" -LO "http://http.us.debian.org/debian/pool/main/v/vips/libvips42_8.14.2-1_amd64.deb")
RUN dpkg -i $(curl -w "%{filename_effective}" -LO "http://http.us.debian.org/debian/pool/main/v/vips/libvips-dev_8.14.2-1_amd64.deb")
RUN apt --fix-broken install
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y libvips-dev

# Install ffmpeg from source
RUN apt install -y libx264-dev
RUN curl -LO "https://github.com/FFmpeg/FFmpeg/archive/refs/tags/n6.0.zip" \
 && unzip n6.0.zip \
 && cd FFmpeg-n6.0 \
 && ./configure --enable-gpl --enable-libx264 \
 && make -j$(nproc) \
 && make -j$(nproc) install \
 && cd /mediaforge \
 && rm -rf FFmpeg-n6.0 n6.0.zip

# weird bugs here
RUN apt-mark hold usrmerge usr-is-merged

RUN apt-get -y autoremove

# python packages
RUN pip install --upgrade pip --no-warn-script-location --root-user-action=ignore
RUN pip install --user poetry --no-warn-script-location --root-user-action=ignore
RUN python -m poetry install

RUN cp config.example.py config.py
# so mediaforge knows to prompt with nano
ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["/bin/bash", "./dockerentry.sh"]
#CMD ["/bin/bash", "./dockerentry.sh"]