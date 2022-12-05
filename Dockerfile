FROM python:3.11 AS builder

# automode
ARG AUTOMODE="OFF"
ARG CONFIG=""
ARG AUTOUPDATE="OFF"
ENV AUTOMODE=$AUTOMODE CONFIG=$CONFIG AUTOUPDATE=$AUTOUPDATE

COPY . mediaforge
# like cd but for docker
WORKDIR mediaforge
# the static deb here makes me nervous but the alternative is Really Weird so no
RUN dpkg -i $(curl -w "%{filename_effective}" -LO "https://www.deb-multimedia.org/pool/main/d/deb-multimedia-keyring/deb-multimedia-keyring_2016.8.1_all.deb")
# experimental/testing/unstable for ffmpeg and non-free/contrib for mbrola
RUN printf "\ndeb https://deb.debian.org/debian bullseye contrib non-free\ndeb https://deb.debian.org/debian bookworm main\ndeb https://www.deb-multimedia.org bookworm main\n" >> "/etc/apt/sources.list.d/debian-extended.list"

# apt
RUN apt-get -y update

# ffmpeg 5 isnt on stable for some reason so it has to be installed separately
# libgif-dev is here because apt is weird see #128
# libvips is here cause stable is old
RUN apt-get -t testing --no-install-recommends install -y ffmpeg libgif-dev libvips-dev
# most packages
RUN apt-get -t stable --no-install-recommends install -y nano imagemagick nodejs

# weird bugs here
RUN apt-mark hold usrmerge usr-is-merged
# if i dont do this there are weird errors trying to build pip packages
RUN apt-get -y upgrade

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



