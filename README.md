# ![MediaForge](media/external/banner.png)

[![MediaForge Discord](https://discordapp.com/api/guilds/803788965215338546/widget.png)](https://discord.gg/xwWjgyVqBz)
[![uptime](https://app.statuscake.com/button/index.php?Track=6022597&Design=6)](https://uptime.statuscake.com/?TestID=JyWrfGfIjT)

[//]: # ([![Discord Bots]&#40;https://top.gg/api/widget/status/780570413767983122.svg&#41;]&#40;https://top.gg/bot/780570413767983122&#41;)

[//]: # ([![Discord Bots]&#40;https://top.gg/api/widget/servers/780570413767983122.svg&#41;]&#40;https://top.gg/bot/780570413767983122&#41;)

[//]: # ([![Discord Bots]&#40;https://top.gg/api/widget/upvotes/780570413767983122.svg&#41;]&#40;https://top.gg/bot/780570413767983122/vote&#41;)

![Total Lines](https://img.shields.io/tokei/lines/github/reticivis-net/mediaforge)
[![wakatime](https://wakatime.com/badge/github/reticivis-net/mediaforge.svg)](https://wakatime.com/badge/github/reticivis-net/mediaforge)
[![stars](https://img.shields.io/github/stars/reticivis-net/mediaforge?style=social)](https://github.com/reticivis-net/mediaforge/stargazers)
[![built with immense swag](https://img.shields.io/static/v1?label=built+with&message=immense+swag&color=D262BA)](https://knowyourmeme.com/memes/trollface)

[//]: # (![discord.py]&#40;https://img.shields.io/github/pipenv/locked/dependency-version/reticivis-net/mediaforge/nextcord&#41;)

[//]: # (![python]&#40;https://img.shields.io/github/pipenv/locked/python-version/reticivis-net/mediaforge&#41;)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Q5Q75US4A)

### A Discord bot for editing and creating videos, images, GIFs, and more!

## general technical info about the bot

- inspired by [esmBot](https://github.com/esmBot/esmBot)
- uses discord.py 2
- uses libvips for captioning
- uses FFmpeg for media processing

## self-host with docker

### to install

All you need to install yourself is [Docker Desktop](https://docs.docker.com/get-docker/)

as of writing, a working docker copy of MediaForge takes up ~3.46GB. if this is a concern and you are using some of the
apt libraries MediaForge does, see [to self-host natively](#to-self-host-natively)

once that's installed, run these commands in your terminal of choice.

```shell
docker build -t melodyflorum/mediaforge https://github.com/reticivis-net/mediaforge.git
docker run -it --cap-add SYS_NICE --shm-size 8G --name mediaforge melodyflorum/mediaforge
```

on linux, you may need to run docker with `sudo`

replace `8G` with how much free RAM your system has that you would like to give MediaForge (in gigabytes). At least `1G`
is suggested. Making this too small can make commands fail due to not enough space, as the `/dev/shm` in-memory
filesystem is, by default, MediaForge's sole temporary directory. Override the `override_temp_dir` option in `config.py`
if you can't allocate enough memory.

if the installation succeeded, you should be prompted with some options. you'll need to select "Edit Config". this will
open a text editor within your terminal. the 2 required config settings to change for proper functionality are the
discord and tenor tokens. be sure not to add or remove quotes. press `CTRL+S` to save and `CTRL+X` to exit.

if you don't want to use the built-in text editor, you can [get the example config from GitHub](config.example.py), hold
down `CTRL+K` to clear the file and then use `CTRL+V` to paste in your config.

### to run

run in your favorite terminal:

```shell
docker start -ia mediaforge
```

by default, MediaForge will await user input for 10 seconds before attempting to run the bot automatically.

### to stop

killing the terminal window/`CTRL+C` won't kill the bot, because docker runs in the background.

to kill the bot, run

```shell
docker stop mediaforge
```

### to limit resource consumption

since docker is very containerized, you can easily limit the amount of resources it's allowed to consume.

the main command to do this is [`docker update`](https://docs.docker.com/engine/reference/commandline/update/#usage),
though most of these arguments can be passed verbatim to `docker run` during setup.

the most useful options are `--memory` and `--cpus`.

for example, this is (as of writing) what the official MediaForge bot uses:

```shell
docker update --memory 9000M --memory-swap -1 --cpus "3.9" mediaforge
```

- `--memory 9000M`: this limits it to 9gb (9000mb) of physical memory
- `--memory-swap -1`: this allows it to use as much swap memory as it wants (swap memory is temporarily storing memory
  on disk)
- `--cpus "3.9"`: the host server has 4 cores, so this allows it to use "3.9"/4 (97.5%) of the PC's CPU time.

### Automode

this is designed to work with hosting providers where terminal control is not possible. There are 3 arguments to this
mode that can be set as
docker [build arguments](https://docs.docker.com/engine/reference/commandline/build/#build-arg)
or [environment variables](https://docs.docker.com/engine/reference/commandline/run/#env)
.
`AUTOMODE`: set to "ON" to enable automode
`AUTOUPDATE`: set to "ON" to update code and packages every run
`CONFIG`: base64 encoded version of your config file.

#### to encode base 64

##### on linux:

- `base64 config.py` prints the output to terminal
- `base64 config.py > config.txt` writes the output to `config.txt`

##### with python:

```python
import base64

with open("config.py", "rb") as f:
    out = base64.b64encode(f.read())
print(out)  # write to terminal
# write to file
with open("config.txt", "wb+") as f:
    f.write(out)
```

## to self-host natively

MediaForge is a complex application and manually installing all dependencies is a headache. for almost all use
cases, [the docker distribution](#self-host-with-docker) is much better.

### summary

ensure your OS is one of the [supported OSes](#supported-oses), then install the [python libraries](#python-libraries)
and the [non-python libraries](#non-python-libraries), set up the [config](#config), and [run](#to-run)

### supported OSes

built and tested on windows 10/11 and debian 10/buster (inside docker). these 2 OSes (and their successors) will
continue to be officially supported.

will _probably_ work on macos and other linux/unix distros if the below libraries are available but theyre untested and
unsupported. just replace `apt-get` with your system's preferred package manager ([`brew`](https://brew.sh/) for macos)

on Windows, color emojis won't work. no idea why, just is a windows pango bug.

### python libraries

- This project uses [`poetry`](https://python-poetry.org/), run `poetry install` to install the required dependencies.
    - install poetry with `pip install poetry`
    - part of [`pyvips`](https://pypi.org/project/pyvips/) is built from source on installation.
        - on Windows this will require the MSVC compiler, which is an optional component
          of [Visual Studio](https://visualstudio.microsoft.com/downloads/)
        - on Linux this will require [`gcc`](https://packages.ubuntu.com/bionic/gcc), installable
          by `sudo apt-get install gcc`

### non-python libraries

the bot uses many external CLI programs for media processing.

- FFmpeg - not included but [easily installable on windows and linux](https://ffmpeg.org/download.html)
    - **If installing on linux, ensure that ffmpeg version >= 5**
- libvips - installable on linux with `sudo apt-get install libvips-dev`
  . [windows instructions here](https://www.libvips.org/install.html#installing-the-windows-binary)
- ImageMagick - **not included** but [downloadable here](https://imagemagick.org/script/download.php)
- TTS
    - on linux, this uses [`mimic`](https://github.com/MycroftAI/mimic1). a pre-compiled binary is included.
        - the male and female voices are downloaded from mimic's repo on bot start if they are not detected. if you want
          to re-download for some reason, delete the 2 files ending in `.flitefox` in `tts/`
    - on windows, [`powershell`](https://aka.ms/powershell) is used to
      access [Windows's native TTS](https://docs.microsoft.com/en-us/uwp/api/windows.media.speechsynthesis.speechsynthesizer)
      . Both are included in modern versions of Windows, but ensure powershell is in the system path.
  - the "retro" voice uses [sam-cli](https://github.com/reticivis-net/sam-cli). it is included, but it
      requires [node.js](https://nodejs.org/) to be installed and added to the system path
        - pretty sure both the windows & linux installers add it to path on installation but cant hurt to check

### config

- create a copy of [`config.example.py`](config.example.py) and name it `config.py`.
- insert/change the appropriate config settings such as your discord api token. be sure not to add or remove quotes.
- the 2 required config settings to change for proper functionality are the discord and tenor tokens.

### python

- developed and tested on python 3.11. use that or a later compatible version

### to run

- once you've set up all of the libraries, just run the program with `poetry run python src/main.py` (
  or `poetry run python3.11 src/main.py` or whatever your python is named). make sure it can read and write to the
  directory
  it lives in and also access/execute all the aforementioned libraries
    - if poetry isn't installing on the right python version, run `<yourpython> -m pip` instead of pip
      and `<yourpython> -m poetry` instead of `poetry`
- terminate the bot by running the `shutdown` command, this will _probably_ close better than a termination

## legal stuff

[terms of service](media/external/terms_of_service.md)

[privacy policy](media/external/privacy_policy.md)