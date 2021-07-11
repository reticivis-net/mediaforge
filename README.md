# ![MediaForge](media/banner.png)

[![MediaForge Discord](https://discordapp.com/api/guilds/803788965215338546/widget.png)](https://discord.gg/xwWjgyVqBz)
[![Discord Bots](https://top.gg/api/widget/status/780570413767983122.svg)](https://top.gg/bot/780570413767983122)
[![Discord Bots](https://top.gg/api/widget/servers/780570413767983122.svg)](https://top.gg/bot/780570413767983122)
[![Discord Bots](https://top.gg/api/widget/upvotes/780570413767983122.svg)](https://top.gg/bot/780570413767983122/vote)
![uptime](https://app.statuscake.com/button/index.php?Track=6022597&Design=6)

![Total Lines](https://img.shields.io/tokei/lines/github/HexCodeFFF/captionbot)
![discord.py](https://img.shields.io/github/pipenv/locked/dependency-version/hexcodefff/captionbot/discord.py)
![python](https://img.shields.io/github/pipenv/locked/python-version/hexcodefff/captionbot)
[![stars](https://img.shields.io/github/stars/HexCodeFFF/captionbot?style=social)](https://github.com/HexCodeFFF/captionbot/stargazers)
[![built with immense swag](https://img.shields.io/static/v1?label=built+with&message=immense+swag&color=D262BA)](https://knowyourmeme.com/memes/trollface)

<a href="https://www.buymeacoffee.com/reticivis" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-violet.png" alt="Buy Me A Coffee" height=60px></a>

### A Discord bot for editing and creating videos, images, GIFs, and more!

## general technical info about the bot

- inspired by [esmBot](https://github.com/esmBot/esmBot)
- uses discord.py (python discord lib)
- uses FFmpeg for most media functions
- uses selenium and ChromeDriver to render captions in html with Chrome
    - although not the fastest approach, it is very readable, flexible, and easy to work with/expand.

## to self-host

verified working on windows 10 and ubuntu 18.04. will _probably_ work on macos and other linux distros if the below
libraries are available but theyre untested and unsupported.

### external libraries

the bot uses many CLI programs for media processing.

- FFmpeg - not included but [easily installable on windows and linux](https://ffmpeg.org/download.html)
    - **If installing on ubuntu, ensure that ffmpeg version >= 4**
- gifski - windows executable is included. linux version [downloadable from the website](https://gif.ski/)
- pngquant - windows executable is included. installable on linux with `sudo apt-get install pngquant`
- ChromeDriver - ChromeDriver 87.0.4280.88 for both windows and linux are included. They have functioned as intended in
  my testing, but [here's the website anyways.](https://chromedriver.chromium.org/)
    - ChromeDriver requires there to be an installation of chrome on your system accessible via path or similair. Your
      chrome version doesn't have to be the exact same as your chromedriver version, but it should be similar
    - you may need to run `sudo chmod +x ./chromedriver87` on linux to make it a working executable.
- ImageMagick - not included but [downloadable here](https://imagemagick.org/script/download.php)
- ExifTool - windows executable is included. installable on linux
  with `sudo apt-get install exiftool` https://exiftool.org/
- apngasm - windows executable is included. installable on linux with `sudo apt-get install apngasm`
- cairo - install on linux with `sudo apt-get install libcairo2-dev`. installable on windows by downloading
  GTK+. https://www.cairographics.org/download/
    - this library is not yet used. it is needed to render lottie stickers but the library for rendering them is bugged
      so it isnt used yet.

### pip libraries

- This project uses [`pipenv`](https://github.com/pypa/pipenv), run `pipenv install` to install required dependencies.
- check [pipenv's repo](https://github.com/pypa/pipenv) for more info on pipenv usage.
- for now, a [`requirements.txt`](requirements.txt) file is also maintained, this may change.

### config

- create a copy of [`config.example.py`](config.example.py) and name it `config.py`.
- insert/change the appropriate config settings such as your discord api token. be sure not to add or remove quotes.
- the 2 required config settings to change for proper functionality are the discord and tenor tokens.

### python

- developed and tested on python 3.8. use that or a later compatible version

### to run

- once you've set up all of the libraries, just run the program with `python main.py` (or `python3.8 main.py` or
  whatever your python is named). make sure it can read and write to the directory it lives in and also access/execute
  all the aforementioned libraries
    - if using pipenv, run `pipenv run python main.py` or open the venv shell with `pipenv shell` and then
      run `python main.py`
- terminate the bot by running the `shutdown` command, this will _probably_ close better than a termination

## !!experimental!! heroku-based hosting

1. [install heroku cli and log in](https://devcenter.heroku.com/articles/getting-started-with-python#set-up)
2. run `heroku create` in the mediaforge directory to create a heroku app
3. add buildpacks
    ```shell
    heroku buildpacks:add https://github.com/jonathanong/heroku-buildpack-ffmpeg-latest.git
    heroku buildpacks:add https://github.com/heroku/heroku-buildpack-google-chrome.git
    heroku buildpacks:add https://github.com/heroku/heroku-buildpack-chromedriver.git
    heroku buildpacks:add heroku-community/apt
    heroku buildpacks:add heroku/python
    ```
4. add [Heroku Postgres addon](https://elements.heroku.com/addons/heroku-postgresql)
5. set up bot config
    - [create a local config file](#config)
        - don't worry about `chrome_driver_linux`, this option is ignored in heroku production.
    - encode the file as base64
        - on linux:
            - `base64 config.py` prints the output to terminal
            - `base64 config.py > config.txt` writes the output to config.txt
        - with python:
            ```python
            import base64
            with open("config.py", "rb") as f:
                out = base64.b64encode(f.read())
            print(out)  # write to terminal
            # write to file
            with open("config.txt", "wb+") as f:
                f.write(out)
            ```
    - save file as config option (replace `<BASE64OUTPUT>` with the output from earlier.)
        ```shell
        heroku config:set PRIVATEFILE_config.py=<BASE64OUTPUT>
        ```
        - note: if you want other private files deployed to heroku, do the same steps but replace `config.py`
          in `PRIVATEFILE_config.py` with the filename.
6. start app
    ```shell
    heroku ps:scale worker=1
    ```

**NOTE:** currently, guild-specific prefixes wont persist after a re-deployment. heroku files are temporary and i
haven't YET written the code to interface with their databases.
