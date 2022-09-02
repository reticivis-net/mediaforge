"""
Miscellaneous helper functions for commands
"""
# TODO: reddit moment caption
import asyncio
import datetime
import glob
import inspect
import json
import typing

import aiofiles
import aiohttp
import humanize
import discord
import regex as re
import requests
import yt_dlp as youtube_dl
from discord.ext import commands

import config
import database
import renderpool
from clogs import logger
from tempfiles import TempFileSession, get_random_string, temp_file


async def fetch(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        async with session.get(url) as response:
            if response.status != 200:
                response.raise_for_status()
            return await response.text()


def get_full_class_name(obj):
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + '.' + obj.__class__.__name__


def download_sync(url, filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb+') as f:
            for chunk in r.iter_content(chunk_size=8192):
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                # if chunk:
                f.write(chunk)


class MyLogger(object):
    def debug(self, msg: ""):
        logger.debug(msg.replace("\r", ""))

    def warning(self, msg: ""):
        logger.warning(msg.replace("\r", ""))

    def error(self, msg: ""):
        logger.error(msg.replace("\r", ""))


def ytdownload(vid, form):
    while True:
        name = f"temp/{get_random_string(12)}"
        if len(glob.glob(name + ".*")) == 0:
            break
    opts = {
        # "max_filesize": config.file_upload_limit,
        "quiet": True,
        "outtmpl": f"{name}.%(ext)s",
        "default_search": "auto",
        "logger": MyLogger(),
        "merge_output_format": "mp4",
        "format": f'(bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best)'
                  f'[filesize<?{config.file_upload_limit}]',
        "max_filesize": config.file_upload_limit
        # "format": "/".join(f"({i})[filesize<{config.file_upload_limit}]" for i in [
        #     "bestvideo[ext=mp4]+bestaudio", "best[ext=mp4]", "bestvideo+bestaudio", "best"
        # ]),
    }
    if form == "audio":
        opts['format'] = f"bestaudio[filesize<{config.file_upload_limit}]"
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }]
    with youtube_dl.YoutubeDL(opts) as ydl:
        # manually exclude livestreams, cant find a better way to do this ¯\_(ツ)_/¯
        nfo = ydl.extract_info(vid, download=False)
        logger.debug(nfo)
        if "is_live" in nfo and nfo["is_live"]:
            raise youtube_dl.DownloadError("Livestreams cannot be downloaded.")
        # TODO: YOU IDIOT THIS IS SYNC!!!
        ydl.download([vid])
    filename = glob.glob(name + ".*")
    if len(filename) > 0:
        return filename[0]
    else:
        return None


tenor_url_regex = re.compile(r"https?://tenor\.com/view/([\w\d]+-)*(\d+)/?")


async def handlemessagesave(m: discord.Message):
    """
    handles saving of media from discord messages
    :param m: a discord message
    :return: list of file URLs detected in the message
    """
    # weird half-message thing that starts threads, get the actual parent message
    if m.type == discord.MessageType.thread_starter_message:
        m = m.reference.resolved
    detectedfiles = []
    if len(m.embeds):
        for embed in m.embeds:
            if embed.type == "gifv":
                # https://github.com/esmBot/esmBot/blob/master/utils/imagedetect.js#L34
                if (match := tenor_url_regex.fullmatch(embed.url)) is not None:
                    gif_id = match.group(2)
                    tenor = await fetch(f"https://api.tenor.com/v1/gifs?ids={gif_id}&key={config.tenor_key}")
                    tenor = json.loads(tenor)
                    if 'error' in tenor:
                        # await ctx.reply(f"{config.emojis['2exclamation']} Tenor Error! `{tenor['error']}`")
                        logger.error(f"Tenor Error! `{tenor['error']}`")
                    else:
                        detectedfiles.append(tenor['results'][0]['media'][0]['mp4']['url'])
            elif embed.type in ["image", "video", "audio"]:
                if await contentlength(embed.url):  # prevent adding youtube videos and such
                    detectedfiles.append(embed.url)
    if len(m.attachments):
        for att in m.attachments:
            if not att.filename.endswith("txt"):  # it was reading traceback attachments >:(
                detectedfiles.append(att.url)
    if len(m.stickers):
        for sticker in m.stickers:
            if sticker.format != discord.StickerFormatType.lottie:
                detectedfiles.append(str(sticker.url))
            else:
                logger.warning("lottie sticker ignored.")
            # this is commented out due to the lottie render code being buggy
            # if sticker.format == discord.StickerType.lottie:
            #     detectedfiles.append("LOTTIE|" + lottiestickers.stickerurl(sticker))
    return detectedfiles


async def imagesearch(ctx, nargs=1):
    """
    searches the channel for nargs media
    :param ctx: command context
    :param nargs: amount of media to return
    :return: False if none or not enough media found, list of file paths if found
    """
    messageschecked = []
    outfiles = []

    m = ctx.message
    if m not in messageschecked:
        messageschecked.append(m)
        hm = await handlemessagesave(m)
        outfiles += hm
        if len(outfiles) >= nargs:
            return outfiles[:nargs]
    if ctx.message.reference:
        m = ctx.message.reference.resolved
        messageschecked.append(m)
        hm = await handlemessagesave(m)
        outfiles += hm
        if len(outfiles) >= nargs:
            return outfiles[:nargs]
    async for m in ctx.channel.history(limit=50, before=ctx.message):
        logger.debug(m.type)
        if m not in messageschecked:
            messageschecked.append(m)
            hm = await handlemessagesave(m)
            outfiles += hm
            if len(outfiles) >= nargs:
                return outfiles[:nargs]
    return False


async def saveurl(url, extension=None):
    """
    save a url to /temp
    :param url: web url of a file
    :param extension: force a file extension
    :return: local path of saved file
    """
    tenorgif = url.startswith("https://media.tenor.com") and url.endswith("/mp4")  # tenor >:(
    if tenorgif:
        extension = "mp4"
    lottie = url.startswith("LOTTIE|")
    if lottie:
        url = url.lstrip('LOTTIE|')
    if extension is None:
        after_slash = url.split("/")[-1].split("?")[0]
        if "." in after_slash:
            extension = after_slash.split(".")[-1]
        # extension will stay None if no extension detected.
    name = temp_file(extension)
    # https://github.com/aio-libs/aiohttp/issues/3904#issuecomment-632661245
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        # i used to make a head request to check size first, but for some reason head requests can be super slow
        async with session.get(url) as resp:
            if resp.status == 200:
                if not lottie:  # discord why
                    if "Content-Length" not in resp.headers:  # size of file to download
                        raise Exception("Cannot determine filesize!")
                    size = int(resp.headers["Content-Length"])
                    logger.info(f"Url is {humanize.naturalsize(size)}")
                    if config.max_file_size < size:  # file size to download must be under max configured size.
                        raise improcessing.NonBugError(f"Your file is too big ({humanize.naturalsize(size)}). "
                                                       f"I'm configured to only download files up to "
                                                       f"{humanize.naturalsize(config.max_file_size)}.")
                logger.info(f"Saving url {url} as {name}")
                f = await aiofiles.open(name, mode='wb')
                await f.write(await resp.read())
                await f.close()
            else:

                logger.error(f"aiohttp status {resp.status}")
                logger.error(f"aiohttp status {await resp.read()}")
                resp.raise_for_status()
    if tenorgif:
        name = await improcessing.mp4togif(name)
    # if lottie:
    #     name = await renderpool.submit(lottiestickers.lottiestickertogif, name)
    return name


async def saveurls(urls: list):
    """
    saves list of URLs and returns it
    :param urls: list of urls
    :return: list of filepaths
    """
    if not urls:
        return False
    files = []
    for url in urls:
        files.append(await saveurl(url))
    return files


async def handletenor(m, ctx, gif=False):
    """
    like handlemessagesave() but only for tenor
    :param m: discord message
    :param ctx: command context
    :param gif: return GIF url if true, mp4 url if false
    :return: raw tenor media url
    """
    if len(m.embeds):
        if m.embeds[0].type == "gifv":
            # https://github.com/esmBot/esmBot/blob/master/utils/imagedetect.js#L34
            tenor = await fetch(
                f"https://api.tenor.com/v1/gifs?ids={m.embeds[0].url.split('-').pop()}&key={config.tenor_key}")
            tenor = json.loads(tenor)
            if 'error' in tenor:
                logger.error(tenor['error'])
                await ctx.send(f"{config.emojis['2exclamation']} Tenor Error! `{tenor['error']}`")
                return False
            else:
                if gif:
                    return tenor['results'][0]['media'][0]['gif']['url']
                else:
                    return tenor['results'][0]['media'][0]['mp4']['url']
    return None


async def tenorsearch(ctx, gif=False):
    # currently only used for 1 command, might have future uses?
    """
    like imagesearch() but for tenor
    :param ctx: discord context
    :param gif: return GIF url if true, mp4 url if false
    :return:
    """
    if ctx.message.reference:
        m = ctx.message.reference.resolved
        hm = await handletenor(m, ctx, gif)
        if hm is None:
            return False
        else:
            return hm
    else:
        async for m in ctx.channel.history(limit=50):
            hm = await handletenor(m, ctx, gif)
            if hm is not None:
                return hm
    return False


async def improcess(ctx: discord.ext.commands.Context, func: callable, allowedtypes: list, *args,
                    resize=True, expectresult=True,
                    filename=None, spoiler=False):
    """
    The core function of the bot. Gathers media and sends it to the proper function.

    :param ctx: discord context. media is gathered using imagesearch() with this.
    :param func: function to process input media with
    :param allowedtypes: list of lists of strings. each inner list is an argument, the strings it contains are the
    types that arg must be. or just False/[] if no media needed
    :param args: any non-media arguments, passed into func()
    :param handleanimated: if func() only works on still images, set to True to process each frame individually.
    :param expectresult: is func() supposed to return a result? if true, it expects an image. if false, can use a
    string.
    :param filename: filename of the uploaded file. if None, not passed.
    :param spoiler: wether to spoil the uploaded file or not.
    :return: nothing, all processing and uploading is done in this function
    """
    if allowedtypes:
        # nothing to download sometimes
        msg = await ctx.reply(f"{config.emojis['working']} Downloading...", mention_author=False)

    async def updatestatus(st):
        nonlocal msg
        try:
            msg = await msg.edit(content=f"{config.emojis['working']} {st}",
                                 allowed_mentions=discord.AllowedMentions.none())
        except discord.NotFound:
            msg = await ctx.reply(f"{config.emojis['working']} {st}", mention_author=False)

    with TempFileSession() as tempfilesession:
        try:
            if allowedtypes:
                urls = await imagesearch(ctx, len(allowedtypes))
                files = await saveurls(urls)
            else:
                files = []
            if files or not allowedtypes:
                for i, file in enumerate(files):
                    if (imtype := await improcessing.mediatype(file)) not in allowedtypes[i]:
                        await ctx.reply(
                            f"{config.emojis['warning']} Media #{i + 1} is {imtype}, it must be: "
                            f"{', '.join(allowedtypes[i])}")
                        logger.warning(f"Media {i} type {imtype} is not in {allowedtypes[i]}")
                        # for f in files:
                        #     os.remove(f)
                        break
                    else:
                        if await improcessing.is_apng(file):
                            asyncio.create_task(ctx.reply(f"{config.emojis['warning']} Media #{i + 1} is an apng, w"
                                                          f"hich FFmpeg and MediaForge have limited support for. Ex"
                                                          f"pect errors.", delete_after=10))
                        if resize:
                            files[i] = await improcessing.ensuresize(ctx, file, config.min_size, config.max_size)
                else:
                    pt = "Processing... (this may take a while or, if a severe error occurs, may not finish)"
                    logger.info("Processing...")
                    if allowedtypes:
                        await updatestatus(pt)
                    else:
                        # Downloading message doesnt exist, create it
                        msg = await ctx.reply(f"{config.emojis['working']} {pt}", mention_author=False)
                    if allowedtypes and not forcerenderpool:
                        if len(files) == 1:
                            filesforcommand = files[0]
                        else:
                            filesforcommand = files.copy()
                        if handleanimated:
                            result = await improcessing.handleanimated(filesforcommand, func, ctx, *args)
                        else:
                            if inspect.iscoroutinefunction(func):
                                result = await func(filesforcommand, *args)
                            else:
                                logger.warning(f"{func} is not coroutine!")
                                result = func(filesforcommand, *args)
                    else:
                        if inspect.iscoroutinefunction(func):
                            result = await func(*args)
                        else:
                            result = await renderpool.renderpool.submit(func, *args)
                    if expectresult:
                        if not result:
                            raise improcessing.ReturnedNothing(f"Expected image, {func} returned nothing.")
                        result = await improcessing.assurefilesize(result, ctx)
                        await improcessing.watermark(result)
                    else:
                        if not result:
                            raise improcessing.ReturnedNothing(f"Expected string, {func} returned nothing.")
                        else:
                            asyncio.create_task(ctx.reply(result))
                    if result and expectresult:
                        logger.info("Uploading...")
                        await updatestatus("Uploading...")
                        if filename is not None:
                            uploadtask = asyncio.create_task(ctx.reply(file=discord.File(result, spoiler=spoiler,
                                                                                         filename=filename)))
                        else:
                            uploadtask = asyncio.create_task(ctx.reply(file=discord.File(result, spoiler=spoiler)))
                        await uploadtask
            else:
                logger.warning("No media found.")
                await ctx.reply(f"{config.emojis['x']} No file found.")
        except Exception as e:
            await msg.delete()
            raise e
        else:
            try:
                await msg.delete()
            except NameError:
                pass


number = typing.Union[float, int]


def number_range(lower_bound: typing.Optional[number] = None, upper_bound: typing.Optional[number] = None,
                 lower_incl: bool = True, upper_incl: bool = True,
                 num_type: typing.Literal['float', 'int'] = 'float') -> object:
    """
    type hint a discord.py parameter to be within a specific number range.
    :param lower_bound: lower bound of arg
    :param upper_bound: upper bound of arg
    :param lower_incl: should the lower bound be included
    :param upper_incl: should the upper bound be included
    :param num_type: float or int
    :return: callable that converts string to num within range or raises commands.BadArgument if not
    """
    numfunc = float if num_type == "float" else int

    def inner(argument):
        try:
            argument = numfunc(argument)
        except ValueError:
            raise commands.BadArgument(
                f"`{argument}` is not a valid number."
                f"{' This argument only accepts whole numbers. ' if numfunc == int else ''}"
            )

        def error():
            raise commands.BadArgument(f"`{argument}` is not between `{lower_bound}` "
                                       f"({'included' if lower_incl else 'excluded'}) "
                                       f"and `{upper_bound}` "
                                       f"({'included' if upper_incl else 'excluded'}).")

        if lower_bound is not None:
            if lower_incl:
                if not lower_bound <= argument:
                    error()
            else:
                if not lower_bound < argument:
                    error()
        if upper_bound is not None:
            if upper_incl:
                if not argument <= upper_bound:
                    error()
            else:
                if not argument < upper_bound:
                    error()
        return argument

    return inner


async def contentlength(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        # i used to make a head request to check size first, but for some reason head requests can be super slow
        async with session.get(url) as resp:
            if resp.status == 200:
                if "Content-Length" not in resp.headers:  # size of file to download
                    return False
                else:
                    return int(resp.headers["Content-Length"])


async def prefix_function(dbot: typing.Union[commands.Bot, commands.AutoShardedBot], message: discord.Message,
                          no_mnts=False):
    mentions = [f'<@{dbot.user.id}> ', f'<@!{dbot.user.id}> ', f'<@{dbot.user.id}>', f'<@!{dbot.user.id}>']
    if not message.guild:
        if no_mnts:
            return config.default_command_prefix
        else:
            # mentions or default or nothing for DMs only
            return mentions + [config.default_command_prefix, ""]
    async with database.db.execute("SELECT prefix from guild_prefixes WHERE guild=?", (message.guild.id,)) as cur:
        pfx = await cur.fetchone()
        if pfx:
            pfx = pfx[0]
        else:
            pfx = config.default_command_prefix
        if no_mnts:
            return pfx
        else:
            return mentions + [pfx]


def quote(string: str) -> str:
    """
    (tries to) discord quote a string
    :param string: string to quote
    :return: quoted string
    """
    return re.sub("([\n\r]|^) *>* *", "\n> ", string)


def now():
    return datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
