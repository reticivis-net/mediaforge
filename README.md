# Untitled Caption Bot

_i can't decide on a name lol!_

discord bot inspired by [esmBot](https://github.com/esmBot/esmBot) mainly for media processing.

## general info about the bot

- written in python and uses discord.py
- uses FFmpeg for most media functions
- uses selenium and ChromeDriver to render captions in html with Chrome
    - look i know it sounds stupid but HTML is easy and flexible
    - it's still very fast, 20 are running at once thanks to python's `multiprocessing.Pool`

## to self-host

- my goal is to support windows (where i develop) and ubuntu linux (where i will host the bot)
- currently, windows is the only verified working version

### external libraries

the bot uses many CLI programs for media processing.

- FFmpeg - not included but [easily installable on windows and linux](https://ffmpeg.org/download.html)
- gifski - windows executable is included. linux version [downloadable from the website](https://gif.ski/)
- pngquant - windows executable is included. installable on linux with `sudo apt-get install pngquant`
- ChromeDriver - ChromeDriver 87.0.4280.88 for both windows and linux are included. linux isn't verified to work but it
  probably does. [here's the website anyways.](https://chromedriver.chromium.org/)
    - also chromedriver requires there to be some form of chrome on your system that it can find. i only use it
      headless, so it should work on headless machines probably
- I'll also probably implement ImageMagick in the
  future [downloadable here](https://imagemagick.org/script/download.php)

### pip libraries

- The bot has a [requirements.txt](requirements.txt) file that can be installed
  with `python -m pip install -r requirements.txt`

### tokens

there need to be 2 txt files with tokens for the bot to function properly

- `token.txt` must contain a [discord bot token](https://discord.com/developers/applications)
- `tenorkey.txt` must contain a [tenor API key](https://tenor.com/developer/keyregistration)

### python

- developed and tested on python 3.8, so use that or some compatible version

### to run

- once you've set up all of the libraries, just run the program with `python main.py`. make sure it can read and write
  to the directory it lives in.
- terminate the bot by running the `shutdown` command, not by terminating it in the console.
