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
RUN printf "\ndeb https://deb.debian.org/debian bullseye contrib non-free\ndeb https://deb.debian.org/debian testing main\ndeb https://www.deb-multimedia.org bullseye main\n" >> "/etc/apt/sources.list.d/debian-extended.list"

# apt
RUN apt-get -y update

# ffmpeg 5 isnt on stable for some reason so it has to be installed separately
RUN apt-get -t testing --no-install-recommends install -y ffmpeg
# most packages
RUN apt-get -t stable --no-install-recommends install -y apngasm nano imagemagick-7 nodejs libvips-dev

# weird bugs here
RUN apt-mark hold usrmerge usr-is-merged
# if i dont do this there are weird errors trying to build pip packages
RUN apt-get -y upgrade

# gifski isnt on an actual repo, use this shit i found on github to install the latest deb off github
RUN dpkg -i $(curl -w "%{filename_effective}" -LO $(curl -s https://api.github.com/repos/ImageOptim/gifski/releases | grep browser_download_url | grep '64[.]deb' | head -n 1 | cut -d '"' -f 4))

# python packages
RUN pip install --upgrade pip --no-warn-script-location --root-user-action=ignore
RUN pip install --user poetry --no-warn-script-location --root-user-action=ignore
RUN python -m poetry install

RUN cp config.example.py config.py
# so mediaforge knows to prompt with nano
ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["/bin/bash", "./dockerentry.sh"]
#CMD ["/bin/bash", "./dockerentry.sh"]



