FROM python:3.8 AS builder

# for release
#RUN git clone --depth 1 https://github.com/HexCodeFFF/mediaforge.git
# for development
COPY . mediaforge
# like cd but for docker
WORKDIR mediaforge
# add repos for weird packages
# google's key TODO: "apt-key is deprecated"
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add -
RUN echo "deb https://dl.google.com/linux/chrome/deb/ stable main" >> "/etc/apt/sources.list.d/google-chrome.list"
# the static deb here makes me nervous but the alternative is Really Weird so no
RUN dpkg -i $(curl -w "%{filename_effective}" -LO "https://www.deb-multimedia.org/pool/main/d/deb-multimedia-keyring/deb-multimedia-keyring_2016.8.1_all.deb")
# experimental/testing/unstable for ffmpeg and non-free/contrib for mbrola
RUN echo "deb http://deb.debian.org/debian bullseye contrib non-free\ndeb http://deb.debian.org/debian experimental main\ndeb http://deb.debian.org/debian unstable main" >> "/etc/apt/sources.list.d/debian-extended.list"

# apt
RUN apt-get -y update && apt-get -t experimental install -y ffmpeg
    # imagemagick, conflicts with ffmpeg so i have to do it after grrrrrrr
RUN echo "deb http://www.deb-multimedia.org bullseye main" >> "/etc/apt/sources.list.d/imagemagick.list"
    # most packages
RUN apt-get -y update && apt-get -t stable install -y pngquant exiftool apngasm espeak nano mbrola-us1 mbrola-us2 google-chrome-stable imagemagick-7

# gifski isnt on an actual repo, use this shit i found on github to install the latest deb off github
RUN dpkg -i $(curl -w "%{filename_effective}" -LO $(curl -s https://api.github.com/repos/ImageOptim/gifski/releases | grep browser_download_url | grep '64[.]deb' | head -n 1 | cut -d '"' -f 4))

# python packages
RUN pip install --user poetry --no-warn-script-location
RUN python -m poetry install

RUN cp config.example.py config.py
# so mediaforge knows to prompt with nano
ENV AM_I_IN_A_DOCKER_CONTAINER Yes

ENTRYPOINT ["python","-m","poetry","run","python","main.py"]
CMD ["python","-m","poetry","run","python","main.py"]



