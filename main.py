# standard libs
import asyncio
import concurrent.futures
import datetime
import difflib
import glob
import inspect
import io
import json
import os
import sqlite3
import time
import traceback
import typing
import urllib.parse

import aiofiles
import aiohttp
import aiosqlite
import discordlists
import docstring_parser
import emojis
import humanize
import nextcord as discord
import pronouncing
import regex as re
import yt_dlp as youtube_dl
from nextcord.ext import commands, tasks

# project files
import captionfunctions
import chromiumrender
import config
import heartbeat
import improcessing
# import lottiestickers
import sus
import tempfiles
from clogs import logger
from improcessing import fetch
from tempfiles import TempFileSession, get_random_string, temp_file

# pip libs

"""
This file contains the discord.py functions, which call other files to do the actual processing.
"""


# TODO: reddit moment caption

def get_full_class_name(obj):
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + '.' + obj.__class__.__name__


# make copy of .reply() function
discord.Message.orig_reply = discord.Message.reply


async def safe_reply(self: discord.Message, *args, **kwargs) -> discord.Message:
    # replies to original message if it exists, just sends in channel if it doesnt
    try:
        # retrieve this message, will throw NotFound if its not found and go to the fallback option.
        # turns out trying to send a message will close any file objects which causes problems
        await self.channel.fetch_message(self.id)
        # reference copy of .reply() since this func will override .reply()
        return await self.orig_reply(*args, **kwargs)
    # for some reason doesnt throw specific error. if its unrelated httpexception itll just throw again and fall to the
    # error handler hopefully
    except (discord.errors.NotFound, discord.errors.HTTPException) as e:
        logger.debug(f"abandoning reply to {self.id} due to {get_full_class_name(e)}, "
                     f"sending message in {self.channel.id}.")
        return await self.channel.send(*args, **kwargs)


# override .reply()
discord.Message.reply = safe_reply

ready = False
db: aiosqlite.Connection
if __name__ == "__main__":  # prevents multiprocessing workers from running bot code
    logger.log(25, "Hello World!")
    logger.info(f"discord.py {discord.__version__}")
    chromiumrender.updatechromedriver()
    renderpool = improcessing.initializerenderpool()
    if not os.path.exists(config.temp_dir.rstrip("/")):
        os.mkdir(config.temp_dir.rstrip("/"))
    for f in glob.glob(f'{config.temp_dir}*'):
        os.remove(f)
    logger.debug("Initializing DB")
    # create table if it doesnt exist
    # this isnt done with aiosqlite because its easier to just not do things asyncly during startup.
    if "DATABASE_URL" in os.environ:
        logger.debug("postgresql?")
    syncdb = sqlite3.connect(config.db_filename)
    # setup db tables
    with syncdb:
        cur = syncdb.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_prefixes'")
        if not cur.fetchall():
            syncdb.execute(
                "create table guild_prefixes ( guild int not null constraint table_name_pk primary key, "
                "prefix text not null ); "
            )
        cur = syncdb.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bans'")
        if not cur.fetchall():
            syncdb.execute("create table bans ( user int not null constraint bans_pk primary key, banreason text );  ")
    syncdb.close()


    async def prefix_function(dbot: typing.Union[commands.Bot, commands.AutoShardedBot], message: discord.Message,
                              no_mnts=False):
        mentions = [f'<@{dbot.user.id}> ', f'<@!{dbot.user.id}> ', f'<@{dbot.user.id}>', f'<@!{dbot.user.id}>']
        if not message.guild:
            if no_mnts:
                return config.default_command_prefix
            else:
                # mentions or default or nothing for DMs only
                return mentions + [config.default_command_prefix, ""]
        async with db.execute("SELECT prefix from guild_prefixes WHERE guild=?", (message.guild.id,)) as cur:
            pfx = await cur.fetchone()
            if pfx:
                pfx = pfx[0]
            else:
                pfx = config.default_command_prefix
            if no_mnts:
                return pfx
            else:
                return mentions + [pfx]


    if hasattr(config, "shard_count") and config.shard_count is not None:
        shard_count = config.shard_count
    else:
        shard_count = None
    # if on_ready is firing before guild count is collected, increase guild_ready_timeout
    bot = commands.AutoShardedBot(command_prefix=prefix_function, help_command=None, case_insensitive=True,
                                  shard_count=shard_count, guild_ready_timeout=30,
                                  allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False,
                                                                           replied_user=True))


    @bot.event
    async def on_ready():
        logger.log(35, f"Logged in as {bot.user.name}!")
        logger.log(25, f"{len(bot.guilds)} guild(s)")
        logger.log(25, f"{len(bot.shards)} shard(s)")


    @bot.event
    async def on_shard_ready(shardid):
        logger.info(f"Shard {shardid} ready")


    @bot.event
    async def on_disconnect():
        logger.error("on_disconnect")


    @bot.event
    async def on_shard_disconnect(shardid):
        logger.error(f"on_shard_disconnect {shardid}")


    class StatusCog(commands.Cog):
        def __init__(self, bot):
            self.bot = bot
            self.changestatus.start()

        def cog_unload(self):
            self.changestatus.cancel()

        @tasks.loop(seconds=60)
        async def changestatus(self):
            if datetime.datetime.now().month == 6:  # june (pride month)
                game = discord.Activity(
                    name=f"LGBTQ+ pride in {len(bot.guilds)} server{'' if len(bot.guilds) == 1 else 's'}! | "
                         f"{config.default_command_prefix}help",
                    type=discord.ActivityType.watching)
            else:
                game = discord.Activity(
                    name=f"with your media in {len(bot.guilds)} server{'' if len(bot.guilds) == 1 else 's'} | "
                         f"{config.default_command_prefix}help",
                    type=discord.ActivityType.playing)
            await bot.change_presence(activity=game)

        @changestatus.before_loop
        async def before_printer(self):
            await self.bot.wait_until_ready()


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
                    if await improcessing.contentlength(embed.url):  # prevent adding youtube videos and such
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
                        handleanimated=False, resize=True, forcerenderpool=False, expectresult=True,
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
        with TempFileSession() as tempfilesession:
            async with ctx.channel.typing():
                if allowedtypes:
                    urls = await imagesearch(ctx, len(allowedtypes))
                    files = await saveurls(urls)
                else:
                    files = []
                if files or not allowedtypes:
                    for i, file in enumerate(files):
                        if (imtype := improcessing.mediatype(file)) not in allowedtypes[i]:
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
                        logger.info("Processing...")
                        msgtask = asyncio.create_task(
                            ctx.reply(f"{config.emojis['working']} Processing...", mention_author=False))
                        try:
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
                                    result = await renderpool.submit(func, *args)
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
                                    msg = await msgtask
                                    asyncio.create_task(msg.delete())
                        except Exception as e:  # delete the processing message if it errors
                            msg = await msgtask
                            asyncio.create_task(msg.delete())
                            raise e
                        if result and expectresult:
                            logger.info("Uploading...")
                            if filename is not None:
                                uploadtask = asyncio.create_task(ctx.reply(file=discord.File(result, spoiler=spoiler,
                                                                                             filename=filename)))
                            else:
                                uploadtask = asyncio.create_task(ctx.reply(file=discord.File(result, spoiler=spoiler)))
                            msg = await msgtask
                            uplt = f"{config.emojis['working']} Uploading..."
                            try:
                                await msg.edit(content=uplt)
                            except discord.NotFound:
                                msg = await ctx.reply(uplt)
                            await uploadtask
                            asyncio.create_task(msg.delete())
                            # for f in files:
                            #     try:
                            #         os.remove(f)
                            #     except FileNotFoundError:
                            #         pass
                            # os.remove(result)
                else:
                    logger.warning("No media found.")
                    asyncio.create_task(ctx.send(f"{config.emojis['x']} No file found."))


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


    class Caption(commands.Cog, name="Captioning"):
        """
        Commands to caption media.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.command(aliases=["demotivate", "motivational", "demotivational", "inspire", "uninspire"])
        async def motivate(self, ctx, *, caption):
            """
            Captions media in the style of demotivational posters.

            :param ctx: discord context
            :param caption: The caption text. Optionally add a bottom text with a `|` character.
            :mediaparam media: A video, gif, or image.
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.motivate, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.command(aliases=["toptextbottomtext", "impact", "adviceanimal"])
        async def meme(self, ctx, *, caption):
            """
            Captions media in the style of top text + bottom text memes.

            :param ctx: discord context
            :param caption: The caption text. Optionally add a bottom text with a `|` character.
            :mediaparam media: A video, gif, or image.
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.meme, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.command(aliases=["snapchat", "snap", "snapcap", "snapcaption", "snapchatcap", "classiccaption"])
        async def snapchatcaption(self, ctx, *, caption):
            """
            Captions media in the style of the classic Snapchat caption.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.snapchat, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.command(aliases=["whisper", "wcap", "wcaption"])
        async def whispercaption(self, ctx, *, caption):
            """
            Captions media in the style of the confession website Whisper.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.whisper, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.command(aliases=["news"])
        async def breakingnews(self, ctx, *, caption):
            """
            Create a fake "Breaking News" screencap.
            This command is a clone of https://breakyourownnews.com/
            To quote them: This app is intended for fun, humour and parody - be careful what you make and how it may be
            shared. You should avoid making things which are unlawful, defamatory or likely to cause distress. Have fun
            and be kind!

            :param ctx: discord context
            :param caption: The headline text. Optionally add a bottom "ticker" text with a `|` character.
            :mediaparam media: A video, gif, or image.
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.breakingnews, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.command(aliases=["tenor"])
        async def tenorcap(self, ctx, *, caption):
            """
            Captions media in the style of tenor.

            :param ctx: discord context
            :param caption: The caption text. Optionally add a bottom text with a `|` character.
            :mediaparam media: A video, gif, or image.
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.tenorcap, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.command(name="caption", aliases=["cap"])
        async def captioncommand(self, ctx, *, caption):
            """
            Captions media.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.caption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.command(aliases=["imstuff"])
        async def stuff(self, ctx, *, caption):
            """
            Captions media in the style of the "i'm stuff" meme

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.stuff, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.command(aliases=["eminemcaption", "eminemcap"])
        async def eminem(self, ctx, *, caption):
            """
            Eminem says something below your media.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.eminemcap, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.command(aliases=["peter", "peterexplain", "petersay", "petergriffinexplain", "petergriffinsay"])
        async def petergriffin(self, ctx, *, caption):
            """
            Peter Griffin says something below your media.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.petergriffincap, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.command(aliases=["stretchstuff"])
        async def stuffstretch(self, ctx, *, caption):
            """
            Alternate version of $stuff where RDJ stretches
            in this version, RDJ stretches vertically to the size of whatever text he says
            it's not a bug... its a feature™! (this command exists due to a former bug in $stuff)


            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.stuffstretch, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.command(aliases=["bottomcap", "botcap"])
        async def bottomcaption(self, ctx, *, caption):
            """
            Captions underneath media.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.bottomcaption, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.command(aliases=["esm", "&caption", "essemcaption", "esmbotcaption", "esmcap"])
        async def esmcaption(self, ctx, *, caption):
            """
            Captions media in the style of Essem's esmBot.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.esmcaption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.command(aliases=["twitter", "twitcap", "twittercap"])
        async def twittercaption(self, ctx, *, caption):
            """
            Captions media in the style of a Twitter screenshot.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.twittercap, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.command(aliases=["twitterdark", "twitcapdark", "twittercapdark"])
        async def twittercaptiondark(self, ctx, *, caption):
            """
            Captions media in the style of a dark mode Twitter screenshot.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.twittercapdark, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.command()
        async def freezemotivate(self, ctx, *, caption):
            """
            Ends video with a freeze frame from $motivate.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam video: A video or gif.
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, improcessing.freezemotivate, [["VIDEO", "GIF"]], *caption)

        @commands.command()
        async def freezemotivateaudio(self, ctx, *, caption):
            # TODO: merge this into freezemotivate
            """
            Ends video with a freeze frame from $motivate with custom audio.

            :param ctx: discord context
            :param caption: The caption text.
            :mediaparam video: A video or gif.
            :mediaparam audio: An audio file.
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, improcessing.freezemotivate, [["VIDEO", "GIF"], ["AUDIO"]], *caption)


    class Media(commands.Cog, name="Editing"):
        """
        Basic media editing/processing commands.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.command(aliases=["copy", "nothing", "noop"])
        async def repost(self, ctx):
            """
            Reposts media as-is.

            :param ctx: discord context
            :mediaparam media: Any valid media.
            """
            await improcess(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]])

        @commands.command(aliases=["clean", "remake"])
        async def reencode(self, ctx):
            """
            Re-encodes media.
            Videos become libx264 mp4s, audio files become libmp3lame mp3s, images become pngs.

            :param ctx: discord context
            :mediaparam media: A video, image, or audio file.
            """
            await improcess(ctx, improcessing.allreencode, [["VIDEO", "IMAGE", "AUDIO"]])

        @commands.command(aliases=["audioadd", "dub"])
        async def addaudio(self, ctx):
            """
            Adds audio to media.

            :param ctx: discord context
            :mediaparam media: Any valid media file.
            :mediaparam audio: An audio file.
            """
            await improcess(ctx, improcessing.addaudio, [["IMAGE", "GIF", "VIDEO", "AUDIO"], ["AUDIO"]])

        @commands.command()
        async def jpeg(self, ctx, strength: number_range(0, 100, False, True, 'int') = 30,
                       stretch: number_range(0, 40, num_type='int') = 20,
                       quality: number_range(1, 95, num_type='int') = 10):
            """
            Makes media into a low quality jpeg

            :param ctx: discord context
            :param strength: amount of times to jpegify image. must be between 1 and 100.
            :param stretch: randomly stretch the image by this number on each jpegification. can cause strange effects
            on videos. must be between 0 and 40.
            :param quality: quality of JPEG compression. must be between 1 and 95.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.jpeg, [["VIDEO", "GIF", "IMAGE"]], strength, stretch, quality,
                            handleanimated=True)

        @commands.command()
        async def deepfry(self, ctx, brightness: number_range(0, 5) = 1.5,
                          contrast: number_range(0, 5) = 1.5,
                          sharpness: number_range(0, 5) = 1.5,
                          saturation: number_range(0, 5) = 1.5,
                          noise: number_range(0, 255) = 40,
                          jpegstrength: number_range(0, 100, False, True, 'int') = 20):
            """
            Applies several filters to the input media to make it appear "deep fried" in the style of deep fried memes.
            See https://pillow.readthedocs.io/en/3.0.x/reference/ImageEnhance.html


            :param ctx: discord context
            :param brightness: value of 1 makes no change to the image. must be between 0 and 5.
            :param contrast: value of 1 makes no change to the image. must be between 0 and 5.
            :param sharpness: value of 1 makes no change to the image. must be between 0 and 5.
            :param saturation: value of 1 makes no change to the image. must be between 0 and 5.
            :param noise: value of 0 makes no change to the image. must be between 0 and 255.
            :param jpegstrength: value of 0 makes no change to the image. must be between 0 and 100.
            :mediaparam media: A video, gif, or image.
            """
            if not 0 <= brightness <= 5:
                raise commands.BadArgument(f"Brightness must be between 0 and 5.")
            if not 0 <= contrast <= 5:
                raise commands.BadArgument(f"Contrast must be between 0 and 5.")
            if not 0 <= sharpness <= 5:
                raise commands.BadArgument(f"Sharpness must be between 0 and 5.")
            if not 0 <= saturation <= 5:
                raise commands.BadArgument(f"Saturation must be between 0 and 5.")
            if not 0 <= noise <= 255:
                raise commands.BadArgument(f"Noise must be between 0 and 255.")
            if not 0 < jpegstrength <= 100:
                raise commands.BadArgument(f"JPEG strength must be between 0 and 100.")
            await improcess(ctx, captionfunctions.deepfry, [["VIDEO", "GIF", "IMAGE"]], brightness, contrast, sharpness,
                            saturation, noise, jpegstrength, handleanimated=True)

        @commands.command()
        async def corrupt(self, ctx, strength: number_range(0, 0.5) = 0.05):
            """
            Intentionally glitches media
            Effect is achieved through randomly changing a % of bytes in a jpeg image.

            :param ctx: discord context
            :param strength: % chance to randomly change a byte of the input image.
            :mediaparam media: A video, gif, or image.
            """
            if not 0 <= strength <= 0.5:
                raise commands.BadArgument(f"Strength must be between 0% and 0.5%.")
            await improcess(ctx, captionfunctions.jpegcorrupt, [["VIDEO", "GIF", "IMAGE"]], strength,
                            handleanimated=True)

        @commands.command(aliases=["pad"])
        async def square(self, ctx):
            """
            Pads media into a square shape.

            :param ctx: discord context
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, improcessing.pad, [["VIDEO", "GIF", "IMAGE"]])

        @commands.command(aliases=["size"])
        async def resize(self, ctx, width: int, height: int):
            """
            Resizes an image.

            :param ctx: discord context
            :param width: width of output image. set to -1 to determine automatically based on height and aspect ratio.
            :param height: height of output image. also can be set to -1.
            :mediaparam media: A video, gif, or image.
            """
            if not (1 <= width <= config.max_size or width == -1):
                raise commands.BadArgument(f"Width must be between 1 and "
                                           f"{config.max_size} or be -1.")
            if not (1 <= height <= config.max_size or height == -1):
                raise commands.BadArgument(f"Height must be between 1 and "
                                           f"{config.max_size} or be -1.")
            await improcess(ctx, improcessing.resize, [["VIDEO", "GIF", "IMAGE"]], width, height, resize=False)

        @commands.command(aliases=["short", "kyle"])
        async def wide(self, ctx):
            """
            makes media twice as wide

            :param ctx: discord context
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, improcessing.resize, [["VIDEO", "GIF", "IMAGE"]], "iw*2", "ih")

        @commands.command(aliases=["tall", "long", "antikyle"])
        async def squish(self, ctx):
            """
            makes media twice as tall

            
            """
            await improcess(ctx, improcessing.resize, [["VIDEO", "GIF", "IMAGE"]], "iw", "ih*2")

        @commands.command(aliases=["magic", "magik", "contentawarescale", "liquidrescale"])
        async def magick(self, ctx, strength: number_range(1, 99, num_type='int') = 50):
            """
            Apply imagemagick's liquid/content aware scale to an image.
            This command is a bit slow.
            https://legacy.imagemagick.org/Usage/resize/#liquid-rescale

            :param ctx: discord context
            :param strength: how strongly to compress the image. smaller is stronger. output image will be strength% of
            the original size. must be between 1 and 99.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.magick, [["VIDEO", "GIF", "IMAGE"]], strength, handleanimated=True)

        @commands.command(aliases=["repeat"], hidden=True)
        async def loop(self, ctx):
            await ctx.reply("MediaForge has 2 loop commands.\nUse `$gifloop` to change/limit the amount of times a GIF "
                            "loops. This ONLY works on GIFs.\nUse `$videoloop` to loop a video. This command "
                            "duplicates the video contents."
                            .replace("$", await prefix_function(bot, ctx.message, True)))

        @commands.command(aliases=["gloop"])
        async def gifloop(self, ctx, loop: number_range(-1, lower_incl=True, num_type='int') = 0):
            """
            Changes the amount of times a gif loops
            See $videoloop for videos.

            :param ctx: discord context
            :param loop: number of times to loop. -1 for no loop, 0 for infinite loop.
            :mediaparam media: A gif.
            """
            if not -1 <= loop:
                raise commands.BadArgument(f"Loop must be -1 or more.")
            await improcess(ctx, improcessing.gifloop, [["GIF"]], loop)

        @commands.command(aliases=["vloop"])
        async def videoloop(self, ctx, loop: number_range(1, 15, num_type='int') = 1):
            """
            Loops a video
            This command technically works on GIFs but its better to use `$gifloop` which takes advantage of GIFs'
            loop metadata.
            See $gifloop for gifs.

            :param ctx: discord context
            :param loop: number of times to loop.
            :mediaparam media: A video or GIF.
            """
            if not 1 <= loop <= 15:
                raise commands.BadArgument(f"Loop must be between 1 and 15.")
            await improcess(ctx, improcessing.videoloop, [["VIDEO", "GIF"]], loop)

        @commands.command(aliases=["flip", "rot"])
        async def rotate(self, ctx, rottype: typing.Literal["90", "90ccw", "180", "vflip", "hflip"]):
            """
            Rotates and/or flips media

            :param ctx: discord context
            :param rottype: 90: 90° clockwise, 90ccw: 90° counter clockwise, 180: 180°, vflip: vertical flip, hflip:
            horizontal flip
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, improcessing.rotate, [["GIF", "IMAGE", "VIDEO"]], rottype)

        @commands.command()
        async def hue(self, ctx, h: float):
            """
            Change the hue of media.
            see https://ffmpeg.org/ffmpeg-filters.html#hue

            :param ctx: discord context
            :param h: The hue angle as a number of degrees.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, improcessing.hue, [["GIF", "IMAGE", "VIDEO"]], h)

        @commands.command(aliases=["color", "recolor"])
        async def tint(self, ctx, color: discord.Color):
            """
            Tint media to a color.
            This command first makes the image grayscale, then replaces white with your color.
            The resulting image should be nothing but shades of your color.

            :param ctx: discord context
            :param color: The hex or RGB color to tint to.
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, improcessing.tint, [["GIF", "IMAGE", "VIDEO"]], color)

        @commands.command(aliases=["round", "circlecrop", "roundcrop", "circle", "roundedcorners"])
        async def roundcorners(self, ctx, radiuspercent: number_range(0, 50) = 50.0):
            """
            Round corners of media
            see https://developer.mozilla.org/en-US/docs/Web/CSS/border-radius

            :param ctx: discord context
            :param radiuspercent: How rounded the corners will be. 0 is rectangle, 50 is ellipse.
            :mediaparam media: A video, gif, or image.
            """
            if not 0 <= radiuspercent <= 50:
                raise commands.BadArgument(f"Border radius percent must be between 0 and 50.")
            await improcess(ctx, captionfunctions.roundcorners, [["GIF", "IMAGE", "VIDEO"]], str(radiuspercent),
                            handleanimated=True)

        @commands.command()
        async def volume(self, ctx, volume: number_range(0, 32)):
            """
            Changes the volume of media.
            To make 2x as loud, use `$volume 2`.
            This command changes *perceived loudness*, not the raw audio level.
            WARNING: ***VERY*** LOUD AUDIO CAN BE CREATED

            :param ctx: discord context
            :param volume: number to multiply the percieved audio level by. Must be between 0 and 32.
            :mediaparam media: A video or audio file.
            """
            if not 0 <= volume <= 32:
                raise commands.BadArgument(f"{config.emojis['warning']} Volume must be between 0 and 32.")
            await improcess(ctx, improcessing.volume, [["VIDEO", "AUDIO"]], volume)

        @commands.command()
        async def mute(self, ctx):
            """
            alias for $volume 0

            :param ctx: discord context
            :mediaparam media: A video or audio file.
            """
            await improcess(ctx, improcessing.volume, [["VIDEO", "AUDIO"]], 0)

        @commands.command()
        async def vibrato(self, ctx, frequency: number_range(0.1, 20000) = 5,
                          depth: number_range(0, 1) = 1):
            """
            Applies a "wavy pitch"/vibrato effect to audio.
            officially described as "Sinusoidal phase modulation"
            see https://ffmpeg.org/ffmpeg-filters.html#tremolo

            :param ctx: discord context
            :param frequency: Modulation frequency in Hertz. must be between 0.1 and 20000.
            :param depth: Depth of modulation as a percentage. must be between 0 and 1.
            :mediaparam media: A video or audio file.
            """
            await improcess(ctx, improcessing.vibrato, [["VIDEO", "AUDIO"]], frequency, depth)

        @commands.command()
        async def pitch(self, ctx, numofhalfsteps: number_range(-12, 12) = 12):
            """
            Changes pitch of audio

            :param ctx: discord context
            :param numofhalfsteps: the number of half steps to change the pitch by. `12` raises the pitch an octave and
            `-12` lowers the pitch an octave. must be between -12 and 12.
            :mediaparam media: A video or audio file.
            """
            if not -12 <= numofhalfsteps <= 12:
                raise commands.BadArgument(f"numofhalfsteps must be between -12 and 12.")
            await improcess(ctx, improcessing.pitch, [["VIDEO", "AUDIO"]], numofhalfsteps)

        @commands.command(aliases=["concat", "combinev"])
        async def concatv(self, ctx):
            """
            Makes one video file play right after another.
            The output video will take on all of the settings of the FIRST video.
            The second video will be scaled to fit.

            :param ctx: discord context
            :mediaparam video1: A video or gif.
            :mediaparam video2: A video or gif.
            """
            await improcess(ctx, improcessing.concatv, [["VIDEO", "GIF"], ["VIDEO", "GIF"]])

        @commands.command()
        async def hstack(self, ctx):
            """
            Stacks 2 videos horizontally

            :param ctx: discord context
            :mediaparam video1: A video, image, or gif.
            :mediaparam video2: A video, image, or gif.
            """
            await improcess(ctx, improcessing.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                            "hstack")

        @commands.command()
        async def vstack(self, ctx):
            """
            Stacks 2 videos horizontally

            :param ctx: discord context
            :mediaparam video1: A video, image, or gif.
            :mediaparam video2: A video, image, or gif.
            """
            await improcess(ctx, improcessing.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                            "vstack")

        @commands.command(aliases=["blend"])
        async def overlay(self, ctx, alpha: number_range(0, 1) = 0.5):
            """
            Overlays the second input over the first

            :param ctx: discord context
            :param alpha: the alpha (transparency) of the top video. must be between 0 and 1.
            :mediaparam video1: A video or gif.
            :mediaparam video2: A video or gif.
            """
            await improcess(ctx, improcessing.overlay, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], alpha,
                            "overlay")

        @commands.command(aliases=["overlayadd", "addition"])
        async def add(self, ctx):
            """
            Adds the pixel values of the second video to the first.

            :param ctx: discord context
            :mediaparam video1: A video or gif.
            :mediaparam video2: A video or gif.
            """
            await improcess(ctx, improcessing.overlay, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], 1,
                            "add")

        @commands.command(name="speed")
        async def spcommand(self, ctx, speed: number_range(0.25, 100) = 2):
            """
            Changes the speed of media.
            This command preserves the original FPS, which means speeding up will drop frames. See $fps.

            :param ctx: discord context
            :param speed: Multiplies input video speed by this number. must be between 0.25 and 100.
            :mediaparam media: A video, gif, or audio.
            """
            if not 0.25 <= speed <= 100:
                raise commands.BadArgument(f"Speed must be between 0.25 and 100")
            await improcess(ctx, improcessing.speed, [["VIDEO", "GIF", "AUDIO"]], speed)

        @commands.command(aliases=["shuffle", "stutter", "nervous"])
        async def random(self, ctx, frames: number_range(2, 512, num_type='int') = 30):
            """
            Shuffles the frames of a video around.
            Currently, this command does NOT apply to audio. This is an FFmpeg limitation.
            see https://ffmpeg.org/ffmpeg-filters.html#random

            :param ctx: discord context
            :param frames: Set size in number of frames of internal cache. must be between 2 and 512. default is 30.
            :mediaparam video: A video or gif.
            """
            if not 2 <= frames <= 512:
                raise commands.BadArgument(f"Frames must be between 2 and 512")
            await improcess(ctx, improcessing.random, [["VIDEO", "GIF"]], frames)

        @commands.command()
        async def reverse(self, ctx):
            """
            Reverses media.

            :param ctx: discord context
            :mediaparam video: A video or gif.
            """
            await improcess(ctx, improcessing.reverse, [["VIDEO", "GIF"]])

        @commands.command(aliases=["compress", "quality", "lowerquality", "crf", "qa"])
        async def compressv(self, ctx, crf: number_range(28, 51) = 51, qa: number_range(10, 112) = 20):
            """
            Makes videos terrible quality.
            The strange ranges on the numbers are because they are quality settings in FFmpeg's encoding.
            CRF info is found at https://trac.ffmpeg.org/wiki/Encode/H.264#crf
            audio quality info is found under https://trac.ffmpeg.org/wiki/Encode/AAC#fdk_cbr

            :param ctx: discord context
            :param crf: Controls video quality. Higher is worse quality. must be between 28 and 51.
            :param qa: Audio bitrate in kbps. Lower is worse quality. Must be between 10 and 112.
            :mediaparam video: A video or gif.
            """
            await improcess(ctx, improcessing.quality, [["VIDEO", "GIF"]], crf, qa)

        @commands.command(name="fps")
        async def fpschange(self, ctx, fps: number_range(1, 60)):
            """
            Changes the FPS of media.
            This command keeps the speed the same.
            BEWARE: Changing the FPS of gifs can create strange results due to the strange way GIFs store FPS data.
            GIFs are only stable at certain FPS values. These include 50, 30, 15, 10, and others.
            An important reminder that by default tenor "gifs" are interpreted as mp4s,
            which do not suffer this problem.

            :param ctx: discord context
            :param fps: Frames per second of the output. must be between 1 and 60.
            :mediaparam video: A video or gif.
            """
            await improcess(ctx, improcessing.changefps, [["VIDEO", "GIF"]], fps)

        @commands.command(aliases=["negate", "opposite"])
        async def invert(self, ctx):
            """
            Inverts colors of media

            :param ctx: discord context
            :mediaparam video: A video or gif.
            """
            await improcess(ctx, improcessing.invert, [["VIDEO", "GIF", "IMAGE"]])

        @commands.command()
        async def trim(self, ctx, length: number_range(0, lower_incl=False), start: number_range(0) = 0):
            """
            Trims media.

            :param ctx: discord context
            :param length: Length in seconds to trim the media to.
            :param start: Time in seconds to start the trimmed media at.
            :mediaparam media: A video, gif, or audio file.
            """
            if not 0 < length:
                raise commands.BadArgument(f"Length must be more than 0.")
            if not 0 <= start:
                raise commands.BadArgument(f"Start must be equal to or more than 0.")
            await improcess(ctx, improcessing.trim, [["VIDEO", "GIF", "AUDIO"]], length, start)

        @commands.command()
        async def autotune(self, ctx, CONCERT_A: float = 440, FIXED_PITCH: float = 0.0,
                           FIXED_PULL: float = 0.1, KEY: str = "c", CORR_STR: float = 1.0, CORR_SMOOTH: float = 0.0,
                           PITCH_SHIFT: float = 0.0, SCALE_ROTATE: int = 0, LFO_DEPTH: float = 0.0,
                           LFO_RATE: float = 1.0, LFO_SHAPE: float = 0.0, LFO_SYMM: float = 0.0, LFO_QUANT: int = 0,
                           FORM_CORR: int = 0, FORM_WARP: float = 0.0, MIX: float = 1.0):
            """
            Autotunes media.
            :param ctx: discord context
            :param CONCERT_A: CONCERT A: Value in Hz of middle A, used to tune the entire algorithm.
            :param FIXED_PITCH: FIXED PITCH: Pitch (semitones) toward which pitch is pulled when PULL TO FIXED PITCH is
             engaged. FIXED PITCH = O: middle A. FIXED PITCH = MIDI pitch - 69.
            :param FIXED_PULL: PULL TO FIXED PITCH: Degree to which pitch Is pulled toward FIXED PITCH. O: use original
             pitch. 1: use FIXED PITCH.
            :param KEY: the key it is tuned to. can be any letter a-g, A-G, or X (chromatic scale).
            :param CORR_STR: CORRECTION STRENGTH: Strength of pitch correction. O: no correction. 1: full correction.
            :param CORR_SMOOTH: CORRECTION SMOOTHNESS: Smoothness of transitions between notes when pitch correction is
            used. O: abrupt transitions. 1: smooth transitions.
            :param PITCH_SHIFT: PITCH SHIFT: Number of notes in scale by which output pitch Is shifted.
            :param SCALE_ROTATE: OUTPUT SCALE ROTATE: Number of notes by which the output scale Is rotated In the
            conversion back to semitones from scale notes. Can be used to change the scale between major and minor or
            to change the musical mode.
            :param LFO_DEPTH: LFO DEPTH: Degree to which low frequency oscillator (LFO) Is applied.
            :param LFO_RATE: LFO RATE: Rate (In Hz) of LFO.
            :param LFO_SHAPE: LFO SHAPE: Shape of LFO waveform. -1: square. 0: sine. 1: triangle.
            :param LFO_SYMM: LFO SYMMETRY: Adjusts the rise/fall characteristic of the LFO waveform.
            :param LFO_QUANT: LFO QUANTIZATION: Quantizes the LFO waveform, resulting in chiptune-like effects.
            :param FORM_CORR: FORMANT CORRECTION: Enables formant correction, reducing the "chipmunk effect"
            in pitch shifting.
            :param FORM_WARP: FORMANT WARP: Warps the formant frequencies. Can be used to change gender/age.
            :param MIX: Blends between the modified signal and the delay-compensated Input signal. 1: wet. O: dry.
            :mediaparam media: A video or audio file.
            """
            await improcess(ctx, improcessing.handleautotune, [["VIDEO", "AUDIO"]],
                            CONCERT_A, FIXED_PITCH, FIXED_PULL, KEY, CORR_STR, CORR_SMOOTH, PITCH_SHIFT, SCALE_ROTATE,
                            LFO_DEPTH, LFO_RATE, LFO_SHAPE, LFO_SYMM, LFO_QUANT, FORM_CORR, FORM_WARP, MIX)

        @commands.command(aliases=["uncap", "nocaption", "nocap", "rmcap", "removecaption", "delcap", "delcaption",
                                   "deletecaption", "trimcap", "trimcaption"])
        async def uncaption(self, ctx, frame_to_try: int = 0, tolerance: number_range(0, 100, False) = 95):
            """
            try to remove esm/default style captions from media
            scans the leftmost column of pixels on one frame to attempt to determine where the caption is.

            :param ctx:
            :param frame_to_try: which frame to run caption detection on. -1 uses the last frame.
            :param tolerance: in % how close to white the color must be to count as caption
            :mediaparam media: A video, image, or GIF file
            """
            await improcess(ctx, improcessing.uncaption, [["VIDEO", "IMAGE", "GIF"]], frame_to_try, tolerance)


    class UnicodeEmojiNotFound(commands.BadArgument):
        def __init__(self, argument):
            self.argument = argument
            super().__init__(f'Unicode emoji `{argument}` not found.')


    class UnicodeEmojiConverter(commands.Converter):
        async def convert(self, ctx, argument):
            emoji = emojis.get(argument)
            if not emoji:
                raise UnicodeEmojiNotFound(argument)
            return list(emoji)[0]


    class Conversion(commands.Cog, name="Conversion"):
        """
        Commands to convert media types and download internet-hosted media.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.command(aliases=["filename", "name", "setname"])
        async def rename(self, ctx, filename: str):
            """
            Renames media.
            Note: Discord's spoiler feature is dependent on filenames starting with "SPOILER_". renaming files may
            unspoiler them.

            :param ctx: discord context
            :param filename: the new name of the file
            :mediaparam media: Any valid media.
            """
            await improcess(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]], filename=filename)

        @commands.command(aliases=["spoil", "censor", "cw", "tw"])
        async def spoiler(self, ctx):
            """
            Spoilers media.

            :param ctx: discord context
            :mediaparam media: Any valid media.
            """
            await improcess(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]], spoiler=True)

        @commands.command(aliases=["avatar", "pfp", "profilepicture", "profilepic", "ayowhothismf", "av"])
        async def icon(self, ctx, *, body=None):
            """
            Grabs the icon url of a Discord user or server.

            This command works off IDs. user mentions contain the ID
            internally so mentioning a user will work. To get the icon of a guild, copy the guild id and use that as
            the parameter. To get the icon of a webhook message, copy the message ID and ***in the same channel as
            the message*** use the message ID as the parameter. This will also work for normal users though i have no
            idea why you'd do it that way.


            :param ctx: discord context
            :param body: must contain a user, guild, or message ID. if left blank, the author's avatar will be sent.
            """
            if body is None:
                result = [await improcessing.iconfromsnowflakeid(ctx.author.id, bot, ctx)]
            else:
                id_regex = re.compile(r'([0-9]{15,20})')
                tasks = []
                for m in re.finditer(id_regex, body):
                    tasks.append(improcessing.iconfromsnowflakeid(int(m.group(0)), bot, ctx))
                result = await asyncio.gather(*tasks)
                result = list(filter(None, result))  # remove Nones
            if result:
                await ctx.reply("\n".join(result)[0:2000])
            else:
                await ctx.send(f"{config.emojis['warning']} No valid user, guild, or message ID found.")

        @commands.command(aliases=["youtube", "youtubedownload", "youtubedl", "ytdownload", "download", "dl", "ytdl"])
        async def videodl(self, ctx, videourl, videoformat: typing.Literal["video", "audio"] = "video"):
            """
            Downloads a web hosted video from sites like youtube.
            Any site here works: https://ytdl-org.github.io/youtube-dl/supportedsites.html

            :param ctx: discord context
            :param videourl: the URL of a video or the title of a youtube video.
            :param videoformat: download audio or video.
            """
            # await improcessing.ytdl(url, form)
            with TempFileSession() as tempfilesession:
                async with ctx.channel.typing():
                    # logger.info(url)
                    msg = await ctx.reply(f"{config.emojis['working']} Downloading from site...", mention_author=False)
                    try:
                        r = await improcessing.run_in_exec(ytdownload, videourl, videoformat)
                        if r:
                            tempfiles.reserve_names([r])
                            r = await improcessing.assurefilesize(r, ctx, re_encode=False)
                            if not r:
                                return
                            txt = ""
                            vcodec = await improcessing.get_vcodec(r)
                            acodec = await improcessing.get_acodec(r)
                            # sometimes returns av1 codec
                            if vcodec and vcodec["codec_name"] not in ["h264", "gif", "webp", "png", "jpeg"]:
                                txt += f"The returned video is in the `{vcodec['codec_name']}` " \
                                       f"({vcodec['codec_long_name']}) codec. Discord might not be able embed this " \
                                       f"format. You can use " \
                                       f"`{await prefix_function(bot, ctx.message, True)}reencode` to change the codec, " \
                                       f"though this may increase the filesize or decrease the quality.\n"
                            if acodec and acodec["codec_name"] not in ["aac", "mp3"]:
                                txt += f"The returned video's audio is in the `{vcodec['codec_name']}` " \
                                       f"({vcodec['codec_long_name']}) codec. Some devices cannot play this. " \
                                       f"You can use `{await prefix_function(bot, ctx.message, True)}reencode` " \
                                       f"to change the codec, " \
                                       f"though this may increase the filesize or decrease the quality."
                            await msg.edit(content=f"{config.emojis['working']} Uploading to Discord...")
                            await ctx.reply(txt, file=discord.File(r))
                        else:
                            await ctx.reply(f"{config.emojis['warning']} No available downloads found within Discord's "
                                            f"file upload limit.")
                        # os.remove(r)
                        await msg.delete()
                    except youtube_dl.DownloadError as e:
                        await ctx.reply(f"{config.emojis['2exclamation']} {e}")

        @commands.command(aliases=["gif", "videotogif"])
        async def togif(self, ctx):
            """
            Converts a video to a GIF.

            :param ctx: discord context
            :mediaparam video: A video.
            """
            await improcess(ctx, improcessing.mp4togif, [["VIDEO"]])

        @commands.command(aliases=["apng", "videotoapng", "giftoapng"])
        async def toapng(self, ctx):
            """
            Converts a video or gif to an animated png.

            :param ctx: discord context
            :mediaparam video: A video or gif.
            """
            await improcess(ctx, improcessing.toapng, [["VIDEO", "GIF"]])

        @commands.command(aliases=["audio", "mp3", "tomp3", "aac", "toaac"])
        async def toaudio(self, ctx):
            """
            Converts a video to only audio.

            :param ctx: discord context
            :mediaparam video: A video.
            """
            await improcess(ctx, improcessing.toaudio, [["VIDEO", "AUDIO"]])

        @commands.command()
        async def tenorgif(self, ctx):
            """
            Sends the GIF url for a tenor gif.
            By default, tenor gifs are interpreted as MP4 files due to their superior quality.
            This command gets the gif straight from tenor, making it faster than $videotogif,
            however, some tenor gifs can be lower fps/quality than the converted video.

            :param ctx: discord context
            :mediaparam gif: any gif sent from tenor.
            """
            logger.info("Getting tenor gif...")
            file = await tenorsearch(ctx, True)
            if file:
                await ctx.send(file)
                logger.info("Complete!")
            else:
                await ctx.send(f"{config.emojis['x']} No tenor gif found.")

        @commands.command(aliases=["video", "giftovideo", "tomp4"])
        async def tovideo(self, ctx):
            """
            Converts a GIF to a video.

            :param ctx: discord context
            :mediaparam gif: A gif.
            """
            await improcess(ctx, improcessing.giftomp4, [["GIF"]])

        @commands.command(aliases=["png", "mediatopng"])
        async def topng(self, ctx):
            """
            Converts media to PNG

            :param ctx: discord context
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, improcessing.mediatopng, [["VIDEO", "GIF", "IMAGE"]])

        @commands.command(aliases=["emoji", "emojiimage", "emote", "emoteurl"])
        async def emojiurl(self, ctx, *custom_emojis: discord.PartialEmoji):
            """
            Sends the raw image for a custom Discord emoji.
            Each emoji is sent as a separate message intentionally to allow replying with a media command.

            :param ctx: discord context
            :param custom_emojis: Custom emojis to send the URL of. Be sure to put a space between them.
            """
            if emojis:
                out = []
                for emoji in custom_emojis[:5]:
                    if emoji.is_custom_emoji():
                        out.append(str(emoji.url))
                await ctx.send("\n".join(out))
            else:
                raise commands.BadArgument(f"Your message doesn't contain any custom emojis!")

        @commands.command()
        async def twemoji(self, ctx, *twemojis: UnicodeEmojiConverter):
            """
            Sends the twemoji image for an emoji.
            Twemoji is the open source emoji set that discord desktop and twitter use. https://twemoji.twitter.com/

            :param ctx: discord context
            :param twemojis: Up to 5 default discord/unicode emojis
            """
            if ctx.message.reference:
                msg = ctx.message.reference.resolved.content
            if twemojis:
                for e in twemojis[:5]:
                    chars = []
                    for char in e:
                        chars.append(f"{ord(char):x}")  # get hex code of char
                    chars = "-".join(chars).replace("/", "")
                    fpath = f"rendering/twemoji/72x72/{chars}.png"
                    logger.debug(f"trying twemoji {fpath}")
                    if os.path.exists(fpath):
                        await ctx.reply(file=discord.File(fpath))
            else:
                raise commands.BadArgument(f"No default emojis found!")


    class Image(commands.Cog, name="Creation"):
        """
        Generate images from a template.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.command(name="1984", aliases=["nineteeneightyfour", "georgeorwell"])
        async def f1984(self, ctx, *, caption):
            """
            Creates a custom meme based off of the "living in 1984" comic.

            :param ctx: discord context
            :param caption: The text that the lady checking her phone is saying. Optionally change what is on the
                calendar by writing something after a `|` character.
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("JANUARY 1984")
            await improcess(ctx, captionfunctions.f1984, [], caption)

        @commands.command(aliases=["ltg", "now", "lowtiergod", "youshould"])
        async def yskysn(self, ctx, *, caption):
            """
            Creates a custom meme based off of the popular Low Tier God "You Should... NOW!" edit.

            :param ctx: discord context
            :param caption: The text that will be placed next to LTG. Optionally change the "NOW!" text by writing
                something after a `|` character (or remove it by typing a `|` followed by nothing else).
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("NOW!")
            await improcess(ctx, captionfunctions.yskysn, [], caption)

        @commands.command(aliases=["shes12"])
        async def zamn(self, ctx, *, caption):
            """
            Creates a custom meme based off of the popular "ZAMN😍 SHE'S 12?" meme.

            :param ctx: discord context
            :param caption: The text above your custom image. Optionally change the "ZAMN😍" text by writing
                something after a `|` character (or remove it by typing a `|` followed by nothing else).
            :mediaparam media: An image, video, or gif that Damien will "ZAMN" at
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("ZAMN😍")
            await improcess(ctx, captionfunctions.zamn, [["IMAGE", "VIDEO", "GIF"]], *caption, handleanimated=True)

        @commands.command(aliases=["troll"])
        async def trollface(self, ctx):
            """
            Colors a trollface with an image.

            :param ctx: discord context
            :mediaparam media: A video, gif, or image.
            """
            await improcess(ctx, captionfunctions.trollface, [["VIDEO", "GIF", "IMAGE"]], handleanimated=True)

        @commands.command(aliases=['sus', 'imposter'])
        async def jermatext(self, ctx, *, text="when the imposter is sus!😳"):
            """
            Cut and slice the popular Jerma sus meme to any message
            For any letter not in the original meme, a random slice of the face is selected.
            Based on https://github.com/aechaechaech/Jerma-Imposter-Message-Generator

            :param ctx: discord context
            :param text: The text to cut and splice.
            """
            await improcess(ctx, sus.sus, [], text)

        @commands.command(aliases=["emsay"])
        async def eminemsay(self, ctx, *, text):
            """
            Eminem says something.

            :param ctx: discord context
            :param text: The text to put next to eminem.
            """
            await improcess(ctx, captionfunctions.eminem, [], [text])

        @commands.command(aliases=["customsay"])
        async def imagesay(self, ctx, *, text):
            """
            An image of your choice says something.
            Like `$eminemsay` but for a custom image.

            :param ctx: discord context
            :param text: The text to put next to your image.
            :mediaparam media: An image, video, or gif
            """
            await improcess(ctx, captionfunctions.imagesay, [["IMAGE", "VIDEO", "GIF"]], text, handleanimated=True)

        @commands.command(aliases=["customcap", "imagesaycap", "imagesaycaption", "imagecap", "customsaycap",
                                   "imagecaptionright"])
        async def imagecaption(self, ctx, *, text):
            """
            An image of your choice says something below another image.
            Like `$stuff`, `$eminem` or `$petergriffin` but for a custom image.

            :param ctx: discord context
            :param text: The text to put next to your image.
            :mediaparam media: An image, video, or gif to caption
            :mediaparam image: An image to sit next to the caption text
            """
            await improcess(ctx, captionfunctions.imagesaycap, [["IMAGE", "VIDEO", "GIF"], ["IMAGE"]], text,
                            handleanimated=True)

        @commands.command(aliases=["customcapleft", "imagesaycapleft", "imagesaycaptionleft", "imagecapleft",
                                   "customsaycapleft"])
        async def imagecaptionleft(self, ctx, *, text):
            """
            like $imagecaption but the image is on the left.

            :param ctx: discord context
            :param text: The text to put next to your image.
            :mediaparam media: An image, video, or gif to caption
            :mediaparam image: An image to sit next to the caption text
            """
            await improcess(ctx, captionfunctions.imagesaycapleft, [["IMAGE", "VIDEO", "GIF"], ["IMAGE"]], text,
                            handleanimated=True)

        @commands.command(aliases=["handitover", "takeit", "giveme"])
        async def givemeyourphone(self, ctx):
            """
            Overlays an image over the hand of the boy in the "give me your phone" meme.
            https://knowyourmeme.com/memes/give-me-your-phone

            :param ctx: discord context
            :mediaparam media: The media to be overlayed over his hand.
            """
            await improcess(ctx, captionfunctions.givemeyourphone, [["IMAGE", "VIDEO", "GIF"]], handleanimated=True)

        @commands.command(aliases=["donald", "donalttrump", "trump", "trumptweet", "donaldtrumptweet", "dontweet",
                                   "donal", "donaltweet"])
        async def donaldtweet(self, ctx, *, text):
            """
            Makes a fake Donald Trump tweet.

            :param ctx: discord context
            :param text: The text to put in the fake tweet.
            """
            await improcess(ctx, captionfunctions.dontweet, [], [text])

        @commands.command(aliases=["texttospeak", "speak", "talk", "speech", "espeak"])
        async def tts(self, ctx: commands.Context,
                      voice: typing.Optional[typing.Literal["male", "female", "retro"]] = "male", *, text):
            """
            make an mp3 text-to-speech of a given input
            for modern voices: uses espeak+mbrola on linux, or native tts on windows (OS of the host server)
            for retro TTS: uses commodore sam

            :param ctx: discord ctx
            :param voice: choose what voice you want it to be spoken in. modern TTS voices are "male" or "female", or
                you can use "retro" for a 1980s TTS, just for fun :p
            :param text: the text to speak
            :return: audio file of the spoken text
            """
            # shouldnt happen but sanity check
            if not voice:
                voice = "male"
            await improcess(ctx, improcessing.tts, [], text, voice)

        # WIP
        @commands.command()
        async def epicbirthday(self, ctx: commands.Context, *, text):
            await improcess(ctx, improcessing.epicbirthday, [], text)


    def showcog(cog):
        show_cog = False
        # check if there are any non-hidden commands in the cog, if not, dont show it in the help menu.
        for com in cog.get_commands():
            if not com.hidden:
                show_cog = True
                break
        return show_cog


    def add_long_field(embed: discord.Embed, name: str, value: str) -> discord.Embed:
        """
        add fields every 1024 characters to a discord embed
        :param embed: embed
        :param name: title of embed
        :param value: long value
        :return: updated embed
        """
        if len(value) <= 1024:
            return embed.add_field(name=name, value=value, inline=False)
        else:
            for i, section in enumerate(re.finditer('.{1,1024}', value, flags=re.S)):
                embed.add_field(name=name + f" {i + 1}", value=section[0], inline=False)
        if len(embed) > 6000:
            raise Exception(f"Generated embed exceeds maximum size. ({len(embed)} > 6000)")
        return embed


    class Other(commands.Cog, name="Other"):
        """
        Commands that don't fit in the other categories.
        """

        def __init__(self, bot):
            self.bot: commands.Bot = bot

        @commands.cooldown(60, config.cooldown, commands.BucketType.guild)
        @commands.guild_only()
        @commands.has_guild_permissions(manage_guild=True)
        @commands.command(aliases=["pfx", "setprefix", "changeprefix", "botprefix", "commandprefix"])
        async def prefix(self, ctx, prefix=None):
            """
            Changes the bot's prefix for this guild.

            :param ctx: discord context
            :param prefix: The new prefix for the bot to use.
            """
            if prefix is None or prefix == config.default_command_prefix:
                await db.execute("DELETE FROM guild_prefixes WHERE guild=?", (ctx.guild.id,))
                await db.commit()
                await ctx.reply(f"{config.emojis['check']} Set guild prefix back to global default "
                                f"(`{config.default_command_prefix}`).")

            else:
                if not 50 >= len(prefix) > 0:
                    raise commands.BadArgument(f"prefix must be between 1 and 50 characters.")
                # check for invalid characters by returning all invalid characters
                invalids = re.findall(r"[^a-zA-Z0-9!$%^&()_\-=+,<.>\/?;'[{\]}|]", prefix)
                if invalids:
                    raise commands.BadArgument(f"{config.emojis['x']} Found invalid characters: "
                                               f"{', '.join([discord.utils.escape_markdown(i) for i in invalids])}")
                else:
                    await db.execute("REPLACE INTO guild_prefixes(guild, prefix) VALUES (?,?)",
                                     (ctx.guild.id, prefix))
                    await db.commit()
                    await ctx.reply(f"{config.emojis['check']} Set guild prefix to `{prefix}`")
                    if prefix.isalpha():  # only alphabetic characters
                        await ctx.reply(f"{config.emojis['warning']} Your prefix only contains alphabetic characters. "
                                        f"This could cause normal sentences/words to be interpreted as commands. "
                                        f"This could annoy users.")

        @commands.guild_only()
        @commands.has_guild_permissions(manage_emojis=True)
        @commands.bot_has_guild_permissions(manage_emojis=True)
        @commands.command(aliases=["createemoji"])
        async def addemoji(self, ctx, name):
            """
            Adds a file as an emoji to a server.

            Both MediaForge and the command caller must have the Manage Emojis permission.

            :param ctx: discord context
            :param name: The emoji name. Must be at least 2 characters.
            :mediaparam media: A gif or image.
            """
            await improcess(ctx, improcessing.add_emoji, [["GIF", "IMAGE"]], ctx.guild, name, expectresult=False,
                            resize=False)

        # TODO: fix?
        @commands.guild_only()
        @commands.has_guild_permissions(manage_emojis=True)
        @commands.bot_has_guild_permissions(manage_emojis=True)
        @commands.command(aliases=["createsticker"])
        async def addsticker(self, ctx, stickeremoji: UnicodeEmojiConverter, *, name: str):
            """
            Adds a file as a sticker to a server. Both MediaForge and the command caller must have the Manage Emojis
            and Stickers permission.

            :param ctx: discord context
            :param stickeremoji: The related emoji. Must be a single default emoji.
            :param name: The sticker name. Must be at least 2 characters.
            :mediaparam media: A gif or image.
            """
            await improcess(ctx, improcessing.add_sticker, [["GIF", "IMAGE"]], ctx.guild, stickeremoji, name,
                            expectresult=False, resize=False)

        @commands.command()
        async def bpm(self, ctx):
            """
            Detects bpm of media.

            :param ctx: discord context
            :mediaparam media: Video or audio.
            """
            await improcess(ctx, improcessing.tempo, [["VIDEO", "AUDIO"]], expectresult=False, resize=False)

        @commands.guild_only()
        @commands.has_guild_permissions(manage_guild=True)
        @commands.bot_has_guild_permissions(manage_guild=True)
        @commands.command(aliases=["guildbanner", "serverbanner", "banner"])
        async def setbanner(self, ctx):
            """
            Sets a file as the server banner.
            Server must support banners.

            :param ctx: discord context
            :mediaparam media: An image.
            """
            if "BANNER" not in ctx.guild.features:
                await ctx.reply(f"{config.emojis['x']} This guild does not support banners.")
                return
            await improcess(ctx, improcessing.set_banner, [["IMAGE"]], ctx.guild, expectresult=False,
                            resize=False)

        @commands.guild_only()
        @commands.has_guild_permissions(manage_guild=True)
        @commands.bot_has_guild_permissions(manage_guild=True)
        @commands.command(aliases=["setguildicon", "guildicon", "servericon", "seticon"])
        async def setservericon(self, ctx):
            """
            Sets a file as the server icon.
            If setting a gif, server must support animated icons.

            :param ctx: discord context
            :mediaparam media: An image or gif.
            """
            await improcess(ctx, improcessing.set_icon, [["IMAGE", "GIF"]], ctx.guild, expectresult=False,
                            resize=False)

        @commands.command(aliases=["statistics"])
        async def stats(self, ctx):
            """
            Displays some stats about what the bot is currently doing.

            :param ctx: discord context
            """
            stats = renderpool.stats()
            embed = discord.Embed(color=discord.Color(0xD262BA), title="Statistics",
                                  description="A 'task' is typically processing a single image/frame of a video. Not "
                                              "all commands will use tasks.")
            embed.add_field(name="Queued Tasks", value=f"{stats[0]}")
            embed.add_field(name="Currently Executing Tasks", value=f"{stats[1]}")
            embed.add_field(name="Available Workers", value=f"{config.chrome_driver_instances - stats[1]}")
            embed.add_field(name="Total Workers", value=f"{config.chrome_driver_instances}")
            if isinstance(bot, discord.AutoShardedClient):
                embed.add_field(name="Total Bot Shards", value=f"{len(bot.shards)}")
            await ctx.reply(embed=embed)

        @commands.command(aliases=["shard", "shardstats", "shardinfo"])
        async def shards(self, ctx):
            """
            Displays info about bot shards

            :param ctx: discord context
            """
            embed = discord.Embed(color=discord.Color(0xD262BA), title="Shards",
                                  description="Each shard is a separate connection to Discord that handles a fraction "
                                              "of all servers MediaForge is in.")
            for i, shard in bot.shards.items():
                shard: discord.ShardInfo
                embed.add_field(name=f"Shard #{shard.id}", value=f"{round(shard.latency * 1000)}ms latency")
            await ctx.reply(embed=embed)

        @commands.command(aliases=["discord", "invite", "botinfo"])
        async def about(self, ctx):
            """
            Lists important links related to MediaForge such as the official server.

            :param ctx: discord context
            """
            embed = discord.Embed(color=discord.Color(0xD262BA), title="MediaForge")
            embed.add_field(name="Official MediaForge Discord Server", value=f"https://discord.gg/xwWjgyVqBz")
            embed.add_field(name="top.gg link", value=f"https://top.gg/bot/780570413767983122")
            embed.add_field(name="Vote for MediaForge on top.gg", value=f"https://top.gg/bot/780570413767983122/vote")
            embed.add_field(name="Add MediaForge to your server",
                            value=f"https://discord.com/api/oauth2/authorize?client_id=780570413767983122&permissions=3"
                                  f"79968&scope=bot")
            embed.add_field(name="MediaForge GitHub", value=f"https://github.com/HexCodeFFF/mediaforge")
            await ctx.reply(embed=embed)

        @commands.command(aliases=["privacypolicy"])
        async def privacy(self, ctx):
            """
            Shows MediaForge's privacy policy

            :param ctx: discord context
            """
            embed = discord.Embed(color=discord.Color(0xD262BA), title="Privacy Policy")
            embed.add_field(name="What MediaForge Collects",
                            value=f"MediaForge has a sqlite database with the **sole purpose** of storing "
                                  f"guild-specific command prefixes. **All** other data is *always* deleted when it is "
                                  f"done with. MediaForge displays limited info "
                                  f"about commands being run to the console of the host machine for debugging purposes."
                                  f" This data is not stored either.")
            embed.add_field(name="Contact about data", value=f"There really isn't anything to contact me about since "
                                                             f"MediaForge doesn't have any form of long term data "
                                                             f"storage, but you can join the MediaForge discord "
                                                             f"server (https://discord.gg/QhMyz3n4V7) or raise an "
                                                             f"issue on the GitHub ("
                                                             f"https://github.com/HexCodeFFF/mediaforge).")
            await ctx.reply(embed=embed)

        @commands.command(aliases=["github", "git"])
        async def version(self, ctx):
            """
            Shows information on how this copy of MediaForge compares to the latest code on github.
            https://github.com/HexCodeFFF/mediaforge
            This command returns the output of `git status`.

            :param ctx: discord context
            """
            await improcessing.run_command("git", "fetch")
            status = await improcessing.run_command("git", "status")
            with io.StringIO() as buf:
                buf.write(status)
                buf.seek(0)
                await ctx.reply("Output of `git status` (the differences between this copy of MediaForge and the latest"
                                " code on GitHub)", file=discord.File(buf, filename="gitstatus.txt"))

        @commands.command(aliases=["ffmpeginfo"])
        async def ffmpegversion(self, ctx):
            """
            Shows version information of FFmpeg running on this copy.
            This command returns the output of `ffmpeg -version`.

            :param ctx: discord context
            """
            status = await improcessing.run_command("ffmpeg", "-version")
            with io.StringIO() as buf:
                buf.write(status)
                buf.seek(0)
                await ctx.reply("Output of `ffmpeg -version`", file=discord.File(buf, filename="ffmpegversion.txt"))

        def showcog(self, cog):
            showcog = False
            # check if there are any non-hidden commands in the cog, if not, dont show it in the help menu.
            for com in cog.get_commands():
                if not com.hidden:
                    showcog = True
                    break
            return showcog

        @commands.command()
        async def help(self, ctx, *, inquiry: typing.Optional[str] = None):
            """
            Shows help on bot commands.

            :param ctx: discord context
            :param inquiry: the name of a command or command category. If none is provided, all categories are shown.
            :return: the help text if found
            """
            prefix = await prefix_function(bot, ctx.message, True)
            # unspecified inquiry
            if inquiry is None:
                embed = discord.Embed(title="Help", color=discord.Color(0xB565D9),
                                      description=f"Run `{prefix}help category` to list commands from "
                                                  f"that category.")
                # for every cog
                for c in self.bot.cogs.values():
                    # if there is 1 or more non-hidden command
                    if self.showcog(c):
                        # add field for every cog
                        if not c.description:
                            c.description = "No Description."
                        embed.add_field(name=c.qualified_name, value=c.description)
                await ctx.reply(embed=embed)
            # if the command argument matches the name of any of the cogs that contain any not hidden commands
            elif inquiry.lower() in (coglist := {k.lower(): v for k, v in self.bot.cogs.items() if self.showcog(v)}):
                # get the cog found
                cog = coglist[inquiry.lower()]
                embed = discord.Embed(title=cog.qualified_name,
                                      description=cog.description + f"\nRun `{prefix}help command` for "
                                                                    f"more information on a command.",
                                      color=discord.Color(0xD262BA))
                # add field with description for every command in the cog
                for cmd in sorted(cog.get_commands(), key=lambda x: x.name):
                    if not cmd.hidden:
                        desc = cmd.short_doc if cmd.short_doc else "No Description."
                        embed.add_field(name=f"{prefix}{cmd.name}", value=desc)
                await ctx.reply(embed=embed)
            else:
                # for every bot command
                for bot_cmd in self.bot.commands:
                    # if the name matches inquiry or alias and is not hidden
                    if (bot_cmd.name == inquiry.lower() or inquiry.lower() in bot_cmd.aliases) and not bot_cmd.hidden:
                        # set cmd and continue
                        cmd: discord.ext.commands.Command = bot_cmd
                        break
                else:
                    # inquiry doesnt match cog or command, not found

                    # get all cogs n commands n aliases
                    allcmds = []
                    for c in self.bot.cogs.values():
                        if self.showcog(c):
                            allcmds.append(c.qualified_name.lower())
                    for cmd in self.bot.commands:
                        if not cmd.hidden:
                            allcmds.append(cmd.qualified_name)
                            allcmds += cmd.aliases
                    match = difflib.get_close_matches(inquiry, allcmds, n=1, cutoff=0)[0]
                    raise commands.BadArgument(
                        f"`{inquiry}` is not the name of a command or a command category. "
                        f"Did you mean `{match}`?")
                    # past this assume cmd is defined
                embed = discord.Embed(title=prefix + cmd.name, description=cmd.cog_name,
                                      color=discord.Color(0xEE609C))
                # if command func has docstring
                if cmd.help:
                    # parse it
                    docstring = docstring_parser.parse(cmd.help, style=docstring_parser.DocstringStyle.REST)
                    # format short/long descriptions or say if there is none.
                    if docstring.short_description or docstring.long_description:
                        command_information = \
                            f"{f'**{docstring.short_description}**' if docstring.short_description else ''}" \
                            f"\n{docstring.long_description if docstring.long_description else ''}"
                    else:
                        command_information = "This command has no information."
                    embed = add_long_field(embed, "Command Information", command_information)

                    paramtext = []
                    # for every "clean paramater" (no self or ctx)
                    for param in list(cmd.clean_params.values()):
                        # get command description from docstring
                        paramhelp = discord.utils.get(docstring.params, arg_name=param.name)
                        # not found in docstring
                        if paramhelp is None:
                            paramtext.append(f"**{param.name}** - No description")
                            continue
                        # optional argument (param has a default value)
                        if param.default != param.empty:  # param.empty != None
                            pend = f" (optional, defaults to `{param.default}`)"
                        else:
                            pend = ""
                        # format and add to paramtext list
                        paramhelp.description = paramhelp.description.replace('\n', ' ')
                        paramtext.append(f"**{param.name}** - "
                                         f"{paramhelp.description if paramhelp.description else 'No description'}"
                                         f"{pend}")
                    mediaparamtext = []
                    for mediaparam in re.finditer(re.compile(":mediaparam ([^ :]+): ([^\n]+)"), cmd.help):
                        argname = mediaparam[1]
                        argdesc = mediaparam[2]
                        mediaparamtext.append(f"**{argname}** - {argdesc}")
                    # if there are params found
                    if len(paramtext):
                        # join list and add to help
                        embed = add_long_field(embed, "Parameters", "\n".join(paramtext))
                    if len(mediaparamtext):
                        mval = "*Media parameters are automatically collected from the channel.*\n" + \
                               "\n".join(mediaparamtext)
                        embed = add_long_field(embed, "Media Parameters", mval)
                    if docstring.returns:
                        embed.add_field(name="Returns", value=docstring.returns.description, inline=False)
                else:
                    # if no docstring
                    embed.add_field(name="Command Information", value="This command has no information.", inline=False)
                # cmd.signature is a human readable list of args formatted like the manual usage
                embed.add_field(name="Usage", value=prefix + cmd.name + " " + cmd.signature)
                # if aliases, add
                if cmd.aliases:
                    embed.add_field(name="Aliases", value=", ".join([prefix + a for a in cmd.aliases]))

                await ctx.reply(embed=embed)

        @commands.command(aliases=["ffprobe"])
        async def info(self, ctx):
            """
            Provides info on a media file.
            Info provided is from ffprobe and libmagic.

            :param ctx: discord context
            :mediaparam media: Any media file.
            """
            with TempFileSession() as tempfilesession:
                async with ctx.channel.typing():
                    file = await imagesearch(ctx, 1)
                    if file:
                        file = await saveurls(file)
                        result = await improcessing.ffprobe(file[0])
                        await ctx.reply(f"`{result[1]}` `{result[2]}`\n```{result[0]}```")
                        # os.remove(file[0])
                    else:
                        await ctx.send(f"{config.emojis['x']} No file found.")

        @commands.command()
        async def feedback(self, ctx):
            """
            Give feedback for the bot.
            This sends various links from the github repo for reporting issues or asking questions.

            :param ctx: discord context
            """
            embed = discord.Embed(title="Feedback",
                                  description="Feedback is best given via the GitHub repo, various "
                                              "links are provided below.",
                                  color=discord.Color(0xD262BA))
            embed.add_field(name="Report a bug",
                            value="To report a bug, make an issue at\nhttps://github.com/HexCodeFFF/mediaforge/issues",
                            inline=False)
            embed.add_field(name="Ask a question", value="Have a question? Use the Q&A Discussion "
                                                         "page.\nhttps://github.com/HexCodeFFF/mediaforge/discussions/c"
                                                         "ategories/q-a", inline=False)
            embed.add_field(name="Give an idea",
                            value="Have an idea or suggestion? Use the Ideas Discussion page.\nhtt"
                                  "ps://github.com/HexCodeFFF/mediaforge/discussions/categories/id"
                                  "eas", inline=False)
            embed.add_field(name="Something else?",
                            value="Anything is welcome in the discussion page!\nhttps://github."
                                  "com/HexCodeFFF/mediaforge/discussions", inline=False)
            embed.add_field(name="Why GitHub?",
                            value="Using GitHub for feedback makes it much easier to organize any i"
                                  "ssues and to implement them into the bot's code.")
            await ctx.reply(embed=embed)

        @commands.command()
        async def attributions(self, ctx):
            """
            Lists most libraries and programs this bot uses.

            :param ctx: discord context
            """
            with open("media/attributions.txt", "r") as f:
                await ctx.send(f.read())

        @commands.command(aliases=["pong"])
        async def ping(self, ctx):
            """
            Pong!

            :param ctx: discord context
            :return: API and websocket latency
            """
            start = time.perf_counter()
            message = await ctx.send("Ping...")
            end = time.perf_counter()
            duration = (end - start) * 1000
            await message.edit(content=f'🏓 Pong!\n'
                                       f'API Latency: `{round(duration)}ms`\n'
                                       f'Websocket Latency: `{round(bot.latency * 1000)}ms`')


    class Debug(commands.Cog, name="Owner Only", command_attrs=dict(hidden=True)):
        def __init__(self, bot):
            self.bot = bot

        @commands.command(aliases=["segfault", "segmentationfault"])
        @commands.is_owner()
        async def sigsegv(self, ctx, ftype: typing.Literal["overflow", "oskill", "ctypes"] = "oskill"):
            """
            cause the main process to segfault. used for debugging purposes. seems it wont kill child processes.
            """
            if ftype == "overflow":
                # https://codegolf.stackexchange.com/a/62613
                exec('()' * 7 ** 6)
            elif ftype == "oskill":
                os.kill(os.getpid(), 11)
            elif ftype == "ctypes":
                import ctypes
                ctypes.string_at(0)
            else:
                await ctx.reply("unknown segfault causer.")

        @commands.command()
        @commands.is_owner()
        async def rangetest(self, ctx, arg: number_range(-1.5, 1.5)):
            await ctx.reply(arg)

        @commands.command()
        @commands.is_owner()
        async def replytonothing(self, ctx):
            await ctx.message.delete()
            await ctx.reply("test")

        @commands.command()
        @commands.is_owner()
        async def listmesage(self, ctx):
            async for m in ctx.channel.history(limit=50, before=ctx.message):
                logger.debug(m.type)

        @commands.command()
        @commands.is_owner()
        async def reply(self, ctx):
            await ctx.reply("test")

        @commands.command()
        @commands.is_owner()
        async def say(self, ctx, channel: typing.Optional[typing.Union[discord.TextChannel, discord.User]], *, msg):
            if not channel:
                channel = ctx.channel
            if ctx.channel.permissions_for(ctx.me).manage_messages:
                asyncio.create_task(ctx.message.delete())
            asyncio.create_task(channel.send(msg))

        @commands.command(hidden=True)
        @commands.is_owner()
        async def error(self, _):
            """
            Raise an error
            """
            raise Exception("Exception raised by $error command")

        @commands.command(hidden=True)
        @commands.is_owner()
        async def errorcmd(self, _):
            """
            Raise an error from the commandline
            """
            await improcessing.run_command("ffmpeg", "-hide_banner", "dsfasdfsadfasdfasdf")

        @commands.command(hidden=True)
        @commands.is_owner()
        async def cleartemp(self, ctx):
            """
            Clear the /temp folder
            """
            l = len(glob.glob('temp/*'))
            for f in glob.glob('temp/*'):
                os.remove(f)
            await ctx.send(f"✅ Removed {l} files.")

        @commands.command(hidden=True, aliases=["verify", "check", "watermark", "integrity", "verifywatermark"])
        @commands.is_owner()
        async def checkwatermark(self, ctx):
            """
            searches for MediaForge metadata
            """
            with TempFileSession() as tempfilesession:
                async with ctx.channel.typing():
                    file = await imagesearch(ctx, 1)
                    if file:
                        file = await saveurls(file)
                        result = await improcessing.checkwatermark(file[0])
                        if result:
                            await ctx.reply(f"{config.emojis['working']} This file was made by MediaForge.")
                        else:
                            await ctx.reply(
                                f"{config.emojis['x']} This file does not appear to have been made by MediaForge.")
                    else:
                        await ctx.send(f"{config.emojis['x']} No file found.")

        @commands.command(hidden=True, aliases=["stop", "close", "die", "kill", "murder", "death"])
        @commands.is_owner()
        async def shutdown(self, ctx):
            """
            Shut down the bot
            """
            await ctx.send(f"{config.emojis['check']} Shutting Down...")
            logger.critical("Shutting Down...")
            await renderpool.shutdown()
            if heartbeat.heartbeat_active:
                heartbeat.heartbeatprocess.terminate()
            await bot.close()
            await bot.loop.shutdown_asyncgens()
            await bot.loop.shutdown_default_executor()
            bot.loop.stop()
            bot.loop.close()

        @commands.command()
        @commands.is_owner()
        async def generate_command_list(self, ctx):
            out = ""
            for cog in bot.cogs.values():
                if not showcog(cog):
                    continue
                out += f"### {cog.qualified_name}\n"
                for command in sorted(cog.get_commands(), key=lambda x: x.name):
                    if not command.hidden:
                        out += f"- **${command.name}**: {command.short_doc}\n"
            with io.StringIO() as buf:
                buf.write(out)
                buf.seek(0)
                await ctx.reply(file=discord.File(buf, filename="commands.md"))

        @commands.command(aliases=["beat"])
        @commands.is_owner()
        async def heartbeat(self, ctx):
            if hasattr(config, "heartbeaturl"):
                await fetch(config.heartbeaturl)
                await ctx.reply("Successfully sent heartbeat.")
            else:
                await ctx.reply("No heartbeat URL set in config.")

        @commands.command()
        @commands.is_owner()
        async def ban(self, ctx, user: discord.User, *, reason: typing.Optional[str]):
            async with db.execute("SELECT count(*) from bans WHERE user=?", (user.id,)) as cur:
                if (await cur.fetchone())[0] > 0:  # check if ban exists
                    await ctx.reply(f"{config.emojis['x']} {user.mention} is already banned.")
                else:
                    await db.execute("INSERT INTO bans(user,banreason) values (?, ?)", (user.id, reason))
                    await db.commit()
                    await ctx.reply(f"{config.emojis['check']} Banned {user.mention}.")

        @commands.command()
        @commands.is_owner()
        async def unban(self, ctx, user: discord.User):
            cur = await db.execute("DELETE FROM bans WHERE user=?",
                                   (user.id,))
            await db.commit()
            if cur.rowcount > 0:
                await ctx.reply(f"{config.emojis['check']} Unbanned {user.mention}.")
            else:
                await ctx.reply(f"{config.emojis['x']} {user.mention} is not banned.")


    class Slashscript(commands.Cog, name="Slashscript"):
        """
        Commands that don't fit in the other categories.
        """

        def __init__(self, bot):
            self.bot = bot
            self.slashnemes = {"AA": "a", "AE": "a", "AH": "E", "AO": "o", "AW": "ao", "AY": "ai", "B": "b", "CH": "tS",
                               "D": "d", "DH": "D", "EH": "e", "ER": "er", "EY": "ei", "F": "f", "G": "g", "HH": "h",
                               "IH": "i", "IY": "i", "JH": "dZ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "N",
                               "OW": "o", "OY": "oi", "P": "p", "R": "r", "S": "s", "SH": "S", "T": "t", "TH": "T",
                               "UH": "u", "UW": "u", "V": "v", "W": "w", "Y": "y", "Z": "z", "ZH": "Z"}

        # @commands.command()
        # async def slashscript(self, ctx, *, text):
        #     """
        #     Eminem says something.
        #
        #     
        #     :param text: The text to put next to eminem.
        #     """
        #     await improcess(ctx, captionfunctions.slashscript, [], [text])

        @commands.command(hidden=True, aliases=["slashscript", "slashscriptconvert", "ssconvert"])
        async def sconvert(self, ctx, *, text):
            """
            Converts text into a custom writing system known as SlashScript.
            """
            out = []
            for word in re.finditer("([a-zA-Z0-9!@#$%)>]+|[,.])", text.strip()):
                word = word.group(0)
                word_phonemes = pronouncing.phones_for_word(word.lower())
                if word_phonemes and not word.startswith(">"):  # pronunication known
                    ph_list = (''.join(i for i in word_phonemes[0] if not i.isdigit())).split(" ")
                    out.append(''.join(self.slashnemes[ph] for ph in ph_list if ph in self.slashnemes))
                elif word.startswith(">") or word in [".", ","]:
                    out.append(word.replace(">", ""))
                else:
                    await ctx.reply(f"No pronunciation found for `{word}`. To render literal slashnemes, begin the "
                                    f"word with `>`.")
                    return
            out = " ".join(out)
            # clear out any whitespace touching punctuation
            out = re.sub(r"(\s(?=[,.])|(?<=[,.])\s)", "", out)
            await improcess(ctx, captionfunctions.slashscript, [], [out])


    @bot.listen()
    async def on_command(ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            logger.log(25,
                       f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.id}) ran "
                       f"'{ctx.message.content}' in DMs")
        else:
            logger.log(25,
                       f"@{ctx.message.author.name}#{ctx.message.author.discriminator}"
                       f" ({ctx.message.author.display_name}) ({ctx.message.author.id}) "
                       f"ran '{ctx.message.content}' in channel "
                       f"#{ctx.channel.name} ({ctx.channel.id}) in server {ctx.guild} ({ctx.guild.id})")


    @bot.listen()
    async def on_message(message: discord.Message):
        if message.author == bot.user:
            return
        if message.content.strip() in [f"<@{bot.user.id}>", f"<@!{bot.user.id}>"]:
            pfx = await prefix_function(bot, message, True)
            await message.reply(f"My command prefix is `{pfx}`, or you can "
                                f"mention me! Run `{pfx}help` for bot help.", delete_after=10,
                                mention_author=False)


    @bot.listen()
    async def on_command_completion(ctx):
        logger.log(35,
                   f"Command '{ctx.message.content}' by "
                   f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.id}) "
                   f"is complete!")


    @bot.check
    async def banned_users(ctx: commands.Context):
        if await bot.is_owner(ctx.author):
            return True
        async with db.execute("SELECT banreason from bans WHERE user=?", (ctx.author.id,)) as cur:
            ban = await cur.fetchone()
        if ban:
            outtext = "You are banned from this bot"
            if ban[0]:
                outtext += f" for the following reason: \n\n{ban[0]}\n\n"
            else:
                outtext += f".\n"
            outtext += f"To appeal this, "
            if bot.owner_id == 214511018204725248:  # my ID
                outtext += "raise an issue at https://github.com/HexCodeFFF/mediaforge/issues"
            else:
                outtext += "contact the bot owner."
            raise commands.CheckFailure(outtext)
        else:
            return True


    @bot.check
    def block_filter(ctx: commands.Context):
        # TODO: implement advanced regex-based filter to prevent filter bypass
        # this command is exempt because it only works on URLs and there have been issues with r/okbr
        if ctx.command.name == "videodl":
            return True
        for block in config.blocked_words:
            if block.lower() in ctx.message.content.lower():
                raise commands.CheckFailure("Your command contains one or more blocked words.")
        return True


    @bot.listen()
    async def on_command_error(ctx: commands.Context, commanderror: commands.CommandError):
        async def dmauthor(*args, **kwargs):
            try:
                return await ctx.reply(*args, **kwargs)
            except discord.Forbidden:
                logger.warning(f"Reply to {ctx.message.id} and dm to {ctx.author.id} failed. Aborting.")

        async def reply(*args, **kwargs):
            try:
                if ctx.guild and not ctx.channel.permissions_for(ctx.me).send_messages:
                    logger.debug(f"No permissions to reply to {ctx.message.id}, trying to DM author.")
                    return await dmauthor(*args, **kwargs)
                return await ctx.reply(*args, **kwargs)
            except discord.Forbidden:
                logger.debug(f"Forbidden to reply to {ctx.message.id}, trying to DM author")
                return await dmauthor(*args, **kwargs)

        async def logandreply(message):
            if ctx.guild:
                ch = f"channel #{ctx.channel.name} ({ctx.channel.id}) in server {ctx.guild} ({ctx.guild.id})"
            else:
                ch = "DMs"
            logger.warning(f"Command '{ctx.message.content}' by "
                           f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.id}) "
                           f"in {ch} failed due to {message}.")
            await reply(message)

        global renderpool
        if isinstance(commanderror, concurrent.futures.process.BrokenProcessPool):
            renderpool = improcessing.initializerenderpool()
        errorstring = str(commanderror)
        if isinstance(commanderror, discord.Forbidden):
            await dmauthor(f"{config.emojis['x']} I don't have permissions to send messages in that channel.")
            logger.warning(commanderror)
        if isinstance(commanderror, discord.ext.commands.errors.CommandNotFound):
            if ctx.message.content.strip().lower() in ["$w", "$wa", "$waifu", "$h", "$ha", "$husbando", "$wx", "$hx",
                                                       "$m", "$ma", "$marry", "$mx"]:
                # this command is spammed so much, fuckn ignore it
                # https://mudae.fandom.com/wiki/List_of_Commands#.24waifu_.28.24w.29
                logger.debug(f"Ignoring {ctx.message.content}")
                return
            # remove prefix, remove excess args
            cmd = ctx.message.content[len(ctx.prefix):].split(' ')[0]
            allcmds = []
            for botcom in bot.commands:
                if not botcom.hidden:
                    allcmds.append(botcom.name)
                    allcmds += botcom.aliases
            prefix = await prefix_function(bot, ctx.message, True)
            match = difflib.get_close_matches(cmd, allcmds, n=1, cutoff=0)[0]
            err = f"{config.emojis['exclamation_question']} Command `{prefix}{cmd}` does not exist. " \
                  f"Did you mean **{prefix}{match}**?"
            if not (cmd.startswith("$") and all([i.isdecimal() or i in ".," for i in cmd.replace("$", "")])):
                # exclude just numbers/decimals, it annoys people
                await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NotOwner):
            err = f"{config.emojis['x']} You are not authorized to use this command."
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandOnCooldown):
            err = f"{config.emojis['clock']} {errorstring}"
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.UserInputError):
            err = f"{config.emojis['warning']} {errorstring}"
            if ctx.command:
                prefix = await prefix_function(bot, ctx.message, True)
                err += f" Run `{prefix}help {ctx.command}` to see how to use this command."
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NoPrivateMessage):
            err = f"{config.emojis['warning']} {errorstring}"
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CheckFailure):
            err = f"{config.emojis['x']} {errorstring}"
            await logandreply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError) and \
                isinstance(commanderror.original, improcessing.NonBugError):
            await logandreply(f"{config.emojis['2exclamation']} {str(commanderror.original)[:1000]}")
        else:
            if isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError):
                commanderror = commanderror.original
            logger.error(commanderror, exc_info=(type(commanderror), commanderror, commanderror.__traceback__))
            embed = discord.Embed(color=0xed1c24, description="Please report this error with the attached "
                                                              "traceback file to the GitHub.")
            embed.add_field(name=f"{config.emojis['2exclamation']} Report Issue to GitHub",
                            value=f"[Create New Issue](https://github.com/HexCodeFFF/mediaforge"
                                  f"/issues/new?labels=bug&template=bug_report.md&title"
                                  f"={urllib.parse.quote(str(commanderror), safe='')[:848]})\n[View Issu"
                                  f"es](https://github.com/HexCodeFFF/mediaforge/issues)")
            with io.BytesIO() as buf:
                trheader = f"DATETIME:{datetime.datetime.now()}\nCOMMAND:{ctx.message.content}\nTRACEBACK:\n"
                buf.write(bytes(trheader + ''.join(
                    traceback.format_exception(etype=type(commanderror), value=commanderror,
                                               tb=commanderror.__traceback__)), encoding='utf8'))
                buf.seek(0)
                await reply((f"{config.emojis['2exclamation']} `{get_full_class_name(commanderror)}: "
                             f"{errorstring}`")[:2000],
                            file=discord.File(buf, filename="traceback.txt"), embed=embed)


    class DiscordListsPost(commands.Cog):
        def __init__(self, bot):
            self.bot = bot
            self.api = discordlists.Client(self.bot)  # Create a Client instance
            if config.bot_list_data:
                for k, v in config.bot_list_data.items():
                    if "token" in v and v["token"]:
                        self.api.set_auth(k, v["token"])
            self.api.start_loop()  # Posts the server count automatically every 30 minutes

        @commands.command(hidden=True)
        @commands.is_owner()
        async def post(self, ctx: commands.Context):
            """
            Manually posts guild count using discordlists.py (BotBlock)
            """
            try:
                result = await self.api.post_count()
            except Exception as e:
                await ctx.send(f"Request failed: `{e}`")
                return

            await ctx.send("Successfully manually posted server count ({:,}) to {:,} lists."
                           "\nFailed to post server count to {:,} lists.".format(self.api.server_count,
                                                                                 len(result["success"].keys()),
                                                                                 len(result["failure"].keys())))


    async def create_db():
        global db
        db = await aiosqlite.connect(config.db_filename)


    class CreateDB(commands.Cog):
        def __init__(self, bot):
            self.bot = bot
            asyncio.get_event_loop().run_until_complete(create_db())


    heartbeat.init()

    # from ?tag cooldown mapping
    _cd = commands.CooldownMapping.from_cooldown(1.0, config.cooldown, commands.BucketType.member)


    @bot.check
    async def cooldown_check(ctx):
        # no cooldown for help
        if ctx.command.name == "help":
            return True
        # owner(s) are exempt from cooldown
        if await bot.is_owner(ctx.message.author):
            logger.debug("Owner ran command, exempt from cooldown.")
            return True
        # Then apply a bot check that will run before every command
        # Very similar to ?tag cooldown mapping but in Bot scope instead of Cog scope
        bucket = _cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after, commands.BucketType.user)
        return True


    logger.debug(f"initializing cogs")
    if config.bot_list_data:
        logger.info("bot list data found. botblock will start when bot is ready.")
        bot.add_cog(DiscordListsPost(bot))
    bot.add_cog(CreateDB(bot))
    bot.add_cog(Caption(bot))
    bot.add_cog(Media(bot))
    bot.add_cog(Conversion(bot))
    bot.add_cog(Image(bot))
    bot.add_cog(Other(bot))
    bot.add_cog(Debug(bot))
    bot.add_cog(Slashscript(bot))
    bot.add_cog(StatusCog(bot))

    logger.debug("running bot")
    bot.run(config.bot_token)
