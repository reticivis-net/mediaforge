FROM python:3.8 AS builder

# automode
ARG AUTOMODE="OFF"
ARG CONFIG=""
ARG AUTOUPDATE="OFF"
ENV AUTOMODE=$AUTOMODE CONFIG=$CONFIG AUTOUPDATE=$AUTOUPDATE

COPY . mediaforge
# like cd but for docker
WORKDIR mediaforge
# add repos for weird packages
# the static deb here makes me nervous but the alternative is Really Weird so no
RUN dpkg -i $(curl -w "%{filename_effective}" -LO "https://www.deb-multimedia.org/pool/main/d/deb-multimedia-keyring/deb-multimedia-keyring_2016.8.1_all.deb")
# experimental/testing/unstable for ffmpeg and non-free/contrib for mbrola
RUN printf "\ndeb https://deb.debian.org/debian bullseye contrib non-free\ndeb https://deb.debian.org/debian experimental main\ndeb https://deb.debian.org/debian unstable main\n" >> "/etc/apt/sources.list.d/debian-extended.list"
# apt
RUN apt-get -y update && apt-get -t experimental install -y ffmpeg
    # imagemagick, conflicts with ffmpeg so i have to do it after grrrrrrr
RUN echo "deb https://www.deb-multimedia.org bullseye main" >> "/etc/apt/sources.list.d/imagemagick.list"
    # most packages
RUN apt-get -y update && apt-get -t stable install -y pngquant exiftool apngasm nano imagemagick-7 nodejs

    # chrome is weird
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt install ./google-chrome-stable_current_amd64.deb

# gifski isnt on an actual repo, use this shit i found on github to install the latest deb off github
RUN dpkg -i $(curl -w "%{filename_effective}" -LO $(curl -s https://api.github.com/repos/ImageOptim/gifski/releases | grep browser_download_url | grep '64[.]deb' | head -n 1 | cut -d '"' -f 4))

# python packages
RUN pip install --user poetry --no-warn-script-location
RUN python -m poetry install

RUN cp config.example.py config.py
# so mediaforge knows to prompt with nano
ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["/bin/bash", "./dockerentry.sh"]
#CMD ["/bin/bash", "./dockerentry.sh"]



