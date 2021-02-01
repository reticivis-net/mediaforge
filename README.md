# ![MediaForge](banner.png)
[![MediaForge Discord](https://discordapp.com/api/guilds/803788965215338546/embed.png)](https://discord.gg/xwWjgyVqBz)
![Total Lines](https://img.shields.io/tokei/lines/github/HexCodeFFF/captionbot)
![Downloads](https://img.shields.io/github/downloads/HexCodeFFF/captionbot/total)
![discord.py](https://img.shields.io/github/pipenv/locked/dependency-version/hexcodefff/captionbot/discord.py)
![python](https://img.shields.io/github/pipenv/locked/python-version/hexcodefff/captionbot)
### A Discord bot for editing and creating videos, images, GIFs, and more!

## general info about the bot

- inspired by [esmBot](https://github.com/esmBot/esmBot)
- written in python and uses discord.py
- uses FFmpeg for most media functions
- uses selenium and ChromeDriver to render captions in html with Chrome
    - look i know it sounds stupid but HTML is easy and flexible
    - it's still very fast, 20 are running at once thanks to python's `multiprocessing.Pool`

## to self-host

- verified working on windows 10 and ubuntu 18.04

### external libraries

the bot uses many CLI programs for media processing.

- FFmpeg - not included but [easily installable on windows and linux](https://ffmpeg.org/download.html)
  - **If installing on ubuntu, ensure that ffmpeg version >= 4**
- gifski - windows executable is included. linux version [downloadable from the website](https://gif.ski/)
- pngquant - windows executable is included. installable on linux with `sudo apt-get install pngquant`
- ChromeDriver - ChromeDriver 87.0.4280.88 for both windows and linux are included. linux isn't verified to work but it
  probably does. [here's the website anyways.](https://chromedriver.chromium.org/)
  - also chromedriver requires there to be some form of chrome on your system that it can find. i only use it
    headless, so it should work on headless machines probably. tested with chrome 87 & 88
- I'll also probably implement ImageMagick in the
  future [downloadable here](https://imagemagick.org/script/download.php)

### pip libraries

- This project uses [`pipenv`](https://github.com/pypa/pipenv), run `pipenv install` to install required dependencies.
- check [pipenv's repo](https://github.com/pypa/pipenv) for more info on pipenv usage.

### config

- create a copy of [`config.example.py`](config.example.py) and name it `config.py`.
- insert/change the appropriate config settings such as your discord api token. be sure not to add or remove quotes.
- for now, a [`requirements.txt`](requirements.txt) file is also maintained.

### python

- developed and tested on python 3.8, so use that or some compatible version

### to run

- once you've set up all of the libraries, just run the program with `python main.py`. make sure it can read and write
  to the directory it lives in.
- terminate the bot by running the `shutdown` command, this will _probably_ close better than a termination
