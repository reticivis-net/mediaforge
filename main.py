# standard libs
import asyncio
import concurrent.futures
import datetime
import difflib
import glob
import inspect
import io
import json
import logging
import os
import sqlite3
import traceback
import typing
import urllib.parse

# pip libs
import aiofiles
import aiohttp
import aiosqlite
import discord
import discordlists
import emoji
import humanize
import pronouncing
import regex as re
import youtube_dl
from discord.ext import commands

# project files
import captionfunctions
import config
import improcessing
import lottiestickers
import sus
import tempfiles
from clogs import logger
from improcessing import NonBugError, mp4togif
from tempfiles import TempFileSession, get_random_string, temp_file

"""
This file contains the discord.py functions, which call other files to do the actual processing.
"""

# TODO: reddit moment caption

ready = False
if __name__ == "__main__":  # prevents multiprocessing workers from running bot code
    logger.log(25, "Hello World!")
    logger.info(f"discord.py {discord.__version__}")
    renderpool = improcessing.initializerenderpool()
    if not os.path.exists(config.temp_dir.rstrip("/")):
        os.mkdir(config.temp_dir.rstrip("/"))
    for f in glob.glob(f'{config.temp_dir}*'):
        os.remove(f)
    logger.debug("Initializing DB")
    # create table if it doesnt exist
    # this isnt done with aiosqlite because its easier to just not do things asyncly during startup.
    db = sqlite3.connect(config.db_filename)
    with db:
        cur = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_prefixes'")
        if not cur.fetchall():
            db.execute("create table guild_prefixes("
                       "guild int not null constraint table_name_pk primary key,prefix text not null)")
    db.close()


    async def prefix_function(dbot: commands.Bot, message: discord.Message):
        if not message.guild:
            return config.default_command_prefix
        async with aiosqlite.connect(config.db_filename) as db:
            async with db.execute("SELECT prefix from guild_prefixes WHERE guild=?", (message.guild.id,)) as cur:
                pfx = await cur.fetchone()
                if pfx:
                    return pfx[0]
                else:
                    return config.default_command_prefix


    bot = commands.Bot(command_prefix=prefix_function, help_command=None, case_insensitive=True)


    @bot.event
    async def on_ready():
        global ready
        logger.log(35, f"Logged in as {bot.user.name}!")
        if not ready:
            ready = True
            while True:
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
                await asyncio.sleep(60)


    async def fetch(url):
        async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    response.raise_for_status()
                return await response.text()


    def ytdownload(vid, form):
        while True:
            name = f"temp/{get_random_string(12)}"
            if len(glob.glob(name + ".*")) == 0:
                break
        opts = {
            "max_filesize": config.file_upload_limit,
            "quiet": True,
            "outtmpl": f"{name}.%(ext)s",
            "default_search": "auto",
            "logger": logging,
            "merge_output_format": "mp4",
            "format": 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio'
        }
        if form == "audio":
            opts['format'] = "bestaudio/best[ext=mp3]"
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        with youtube_dl.YoutubeDL(opts) as ydl:
            ydl.download([vid])
        filename = glob.glob(name + ".*")
        if len(filename) > 0:
            return filename[0]
        else:
            return None


    async def handlemessagesave(m: discord.Message):
        """
        handles saving of media from discord messages
        :param m: a discord message
        :return: list of file URLs detected in the message
        """
        detectedfiles = []
        if len(m.embeds):
            for embed in m.embeds:
                if embed.type == "gifv":
                    # https://github.com/esmBot/esmBot/blob/master/utils/imagedetect.js#L34
                    tenor = await fetch(
                        f"https://api.tenor.com/v1/gifs?ids={embed.url.split('-').pop()}&key={config.tenor_key}")
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
                if sticker.image_url:
                    detectedfiles.append(str(sticker.image_url))
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
                        if config.max_file_size < size:  # file size to download must be under ~50MB
                            raise improcessing.NonBugError(f"File is too big ({humanize.naturalsize(size)})!")
                    logger.info(f"Saving url {url} as {name}")
                    f = await aiofiles.open(name, mode='wb')
                    await f.write(await resp.read())
                    await f.close()
                else:
                    logger.error(f"aiohttp status {resp.status}")
                    logger.error(f"aiohttp status {await resp.read()}")
                    raise Exception(f"aiohttp status {resp.status} {await resp.read()}")
        if tenorgif:
            name = await improcessing.mp4togif(name)
        if lottie:
            name = await renderpool.submit(lottiestickers.lottiestickertogif, name)
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
        :param allowedtypes: list of lists of strings. each inner list is an argument, the strings it contains are the types that arg must be. or just False/[] if no media needed
        :param args: any non-media arguments, passed into func()
        :param handleanimated: if func() only works on still images, set to True to process each frame individually.
        :param expectresult: is func() supposed to return a result? if true, it expects an image. if false, can use a string.
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
                                f"{config.emojis['warning']} Media #{i + 1} is {imtype}, it must be: {', '.join(allowedtypes[i])}")
                            logger.warning(f"Media {i} type {imtype} is not in {allowedtypes[i]}")
                            # for f in files:
                            #     os.remove(f)
                            break
                        else:
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
                            await msg.edit(content=f"{config.emojis['working']} Uploading...")
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


    class Caption(commands.Cog, name="Captioning"):
        """
        Commands to caption media.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["demotivate", "motivational", "demotivational"])
        async def motivate(self, ctx, *, caption):
            """
            Captions media in the style of demotivational posters.
            :Usage=$motivate `toptext`|`bottomtext`
            :Param=caption - The caption text. Optionally add a bottom text with a `|` character.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.motivate, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def meme(self, ctx, *, caption):
            """
            Captions media in the style of top text + bottom text memes.

            :Usage=$meme `toptext`|`bottomtext`
            :Param=caption - The caption text. Optionally add a bottom text with a `|` character.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.meme, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["tenor"])
        async def tenorcap(self, ctx, *, caption):
            """
            Captions media in the style of tenor.

            :Usage=$tenorcap `toptext`|`bottomtext`
            :Param=caption - The caption text. Optionally add a bottom text with a `|` character.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.tenorcap, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.command(name="caption", aliases=["cap"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def captioncommand(self, ctx, *, caption):
            """
            Captions media.

            :Usage=$caption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.caption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["imstuff"])
        async def stuff(self, ctx, *, caption):
            """
            Captions media in the style of the "i'm stuff" meme

            :Usage=$stuff `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.stuff, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["eminemcaption", "eminemcap"])
        async def eminem(self, ctx, *, caption):
            """
            Eminem says something below your media.

            :Usage=$eminem `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.eminemcap, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["stretchstuff"])
        async def stuffstretch(self, ctx, *, caption):
            """
            Alternate version of $stuff where RDJ stretches
            in this version, RDJ stretches vertically to the size of whatever text he says
            it's not a bug... its a feature™! (this command exists due to a former bug in $stuff)


            :Usage=$stuffstretch `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.stuffstretch, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.command(aliases=["bottomcap", "botcap"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def bottomcaption(self, ctx, *, caption):
            """
            Captions underneath media.

            :Usage=$bottomcaption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.bottomcaption, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["esm", "&caption", "essemcaption", "esmbotcaption", "esmcap"])
        async def esmcaption(self, ctx, *, caption):
            """
            Captions media in the style of Essem's esmBot.

            :Usage=$esmcaption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.esmcaption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["twitter", "twitcap", "twittercap"])
        async def twittercaption(self, ctx, *, caption):
            """
            Captions media in the style of a Twitter screenshot.

            :Usage=$twittercaption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.twittercap, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["twitterdark", "twitcapdark", "twittercapdark"])
        async def twittercaptiondark(self, ctx, *, caption):
            """
            Captions media in the style of a dark mode Twitter screenshot.

            :Usage=$twittercaption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.twittercapdark, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def freezemotivate(self, ctx, *, caption):
            """
            Ends video with a freeze frame from $motivate.

            :Usage=$freezemotivate `text`
            :Param=caption - The caption text.
            :Param=video - A video or gif. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, improcessing.freezemotivate, [["VIDEO", "GIF"]], *caption)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def freezemotivateaudio(self, ctx, *, caption):
            # TODO: merge this into freezemotivate
            """
            Ends video with a freeze frame from $motivate with custom audio.

            :Usage=$freezemotivateaudio `text`
            :Param=caption - The caption text.
            :Param=video - A video or gif. (automatically found in channel)
            :Param=audio - An audio file. (automatically found in channel)
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

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["copy", "nothing", "noop"])
        async def repost(self, ctx):
            """
            Reposts media as-is.
            :Usage=$repost
            :Param=media - Any valid media. (automatically found in channel)
            """
            await improcess(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["clean", "remake"])
        async def reencode(self, ctx):
            """
            Re-encodes media.
            Videos become libx264 mp4s, audio files become libmp3lame mp3s, images become pngs.
            :Usage=reencode
            :Param=media - A video, image, or audio file. (automatically found in channel)
            """
            await improcess(ctx, improcessing.allreencode, [["VIDEO", "IMAGE", "AUDIO"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["audioadd", "dub"])
        async def addaudio(self, ctx):
            """
            Adds audio to media.

            :Usage=$addaudio
            :Param=media - Any valid media file. (automatically found in channel)
            :Param=audio - An audio file. (automatically found in channel)
            """
            await improcess(ctx, improcessing.addaudio, [["IMAGE", "GIF", "VIDEO", "AUDIO"], ["AUDIO"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def jpeg(self, ctx, strength: int = 30, stretch: int = 20, quality: int = 10):
            """
            Makes media into a low quality jpeg

            :Usage=$jpeg `[strength]` `[stretch]` `[quality]`
            :Param=strength - amount of times to jpegify image. must be between 1 and 100. defaults to 30.
            :Param=stretch - randomly stretch the image by this number on each jpegification. can cause strange effects on videos. must be between 0 and 40. defaults to 20.
            :Param=quality - quality of JPEG compression. must be between 1 and 95. defaults to 10.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            if not 0 < strength <= 100:
                await ctx.send(f"{config.emojis['warning']} Strength must be between 0 and 100.")
                return
            if not 0 <= stretch <= 40:
                await ctx.send(f"{config.emojis['warning']} Stretch must be between 0 and 40.")
                return
            if not 1 <= quality <= 95:
                await ctx.send(f"{config.emojis['warning']} Quality must be between 1 and 95.")
                return
            await improcess(ctx, captionfunctions.jpeg, [["VIDEO", "GIF", "IMAGE"]], strength, stretch, quality,
                            handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def deepfry(self, ctx, brightness: float = 1.5, contrast: float = 1.5, sharpness: float = 1.5,
                          saturation: float = 1.5, noise: int = 40, jpegstrength: int = 20):
            """
            Applies several filters to the input media to make it appear "deep fried" in the style of deep fried memes.
            See https://pillow.readthedocs.io/en/3.0.x/reference/ImageEnhance.html

            :Usage=$deepfry
            :Param=brightness - value of 1 makes no change to the image. must be between 0 and 5. defaults to 1.5.
            :Param=contrast - value of 1 makes no change to the image. must be between 0 and 5. defaults to 1.5.
            :Param=sharpness - value of 1 makes no change to the image. must be between 0 and 5. defaults to 1.5.
            :Param=saturation - value of 1 makes no change to the image. must be between 0 and 5. defaults to 1.5.
            :Param=noise - value of 0 makes no change to the image. must be between 0 and 255. defaults to 40.
            :Param=jpegstrength - value of 0 makes no change to the image. must be between 0 and 100. defaults to 20.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            if not 0 <= brightness <= 5:
                await ctx.send(f"{config.emojis['warning']} Brightness must be between 0 and 5.")
                return
            if not 0 <= contrast <= 5:
                await ctx.send(f"{config.emojis['warning']} Contrast must be between 0 and 5.")
                return
            if not 0 <= sharpness <= 5:
                await ctx.send(f"{config.emojis['warning']} Sharpness must be between 0 and 5.")
                return
            if not 0 <= saturation <= 5:
                await ctx.send(f"{config.emojis['warning']} Saturation must be between 0 and 5.")
                return
            if not 0 <= noise <= 255:
                await ctx.send(f"{config.emojis['warning']} Noise must be between 0 and 255.")
                return
            if not 0 < jpegstrength <= 100:
                await ctx.send(f"{config.emojis['warning']} JPEG strength must be between 0 and 100.")
                return
            await improcess(ctx, captionfunctions.deepfry, [["VIDEO", "GIF", "IMAGE"]], brightness, contrast, sharpness,
                            saturation, noise, jpegstrength, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def corrupt(self, ctx, strength: float = 0.05):
            """
            Intentionally glitches media
            Effect is achieved through randomly changing a % of bytes in a jpeg image.

            :Usage=$corrupt `strength`
            :Param=strength - % chance to randomly change a byte of the input image. defaults to 0.05%
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            if not 0 <= strength <= 0.5:
                await ctx.send(f"{config.emojis['warning']} Strength must be between 0% and 0.5%.")
                return
            await improcess(ctx, captionfunctions.jpegcorrupt, [["VIDEO", "GIF", "IMAGE"]], strength,
                            handleanimated=True)

        @commands.command(aliases=["pad"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def square(self, ctx):
            """
            Pads media into a square shape.

            :Usage=$square
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, improcessing.pad, [["VIDEO", "GIF", "IMAGE"]])

        @commands.command(aliases=["size"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def resize(self, ctx, width: int, height: int):
            """
            Resizes an image.

            :Usage=$resize `width` `height`
            :Param=width - width of output image. set to -1 to determine automatically based on height and aspect ratio.
            :Param=height - height of output image. also can be set to -1.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            if not (1 <= width <= config.max_size or width == -1):
                await ctx.send(f"{config.emojis['warning']} Width must be between 1 and "
                               f"{config.max_size} or be -1.")
                return
            if not (1 <= height <= config.max_size or height == -1):
                await ctx.send(f"{config.emojis['warning']} Height must be between 1 and "
                               f"{config.max_size} or be -1.")
                return
            await improcess(ctx, improcessing.resize, [["VIDEO", "GIF", "IMAGE"]], width, height, resize=False)

        @commands.command(aliases=["short", "kyle"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def wide(self, ctx):
            """
            makes media twice as wide

            :Usage=$wide
            """
            await improcess(ctx, improcessing.resize, [["VIDEO", "GIF", "IMAGE"]], "iw*2", "ih")

        @commands.command(aliases=["tall", "long", "antikyle"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def squish(self, ctx):
            """
            makes media twice as tall

            :Usage=$wide
            """
            await improcess(ctx, improcessing.resize, [["VIDEO", "GIF", "IMAGE"]], "iw", "ih*2")

        @commands.command(aliases=["magic", "magik", "contentawarescale", "liquidrescale"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def magick(self, ctx, strength: int = 50):
            """
            Apply imagemagick's liquid/content aware scale to an image.
            This command is a bit slow.
            https://legacy.imagemagick.org/Usage/resize/#liquid-rescale

            :Usage=$magick `[strength]`
            :Param=strength - how strongly to compress the image. smaller is stronger. output image will be strength% of the original size. must be between 1 and 99. defaults to 50.
            :Param=media - A video, gif, or image. (automatically found in channel)

            """
            if not 1 <= strength <= 99:
                await ctx.send(f"{config.emojis['warning']} Strength must be between 1 and 99.")
                return
            await improcess(ctx, captionfunctions.magick, [["VIDEO", "GIF", "IMAGE"]], strength, handleanimated=True)

        @commands.command(aliases=["repeat"], hidden=True)
        async def loop(self, ctx):
            await ctx.reply("MediaForge has 2 loop commands.\nUse `$gifloop` to change/limit the amount of times a GIF "
                            "loops. This ONLY works on GIFs.\nUse `$videoloop` to loop a video. This command "
                            "duplicates the video contents."
                            .replace("$", await prefix_function(bot, ctx.message)))

        @commands.command(aliases=["gloop"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def gifloop(self, ctx, loop: int = 0):
            """
            Changes the amount of times a gif loops
            See $videoloop for videos.

            :Usage=$gifloop `[loop]`
            :Param=loop - number of times to loop. -1 for no loop, 0 for infinite loop.
            :Param=media - A gif. (automatically found in channel)
            """
            if not -1 <= loop:
                await ctx.send(f"{config.emojis['warning']} Loop must be -1 or more.")
                return
            await improcess(ctx, improcessing.gifloop, [["GIF"]], loop)

        @commands.command(aliases=["vloop"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def videoloop(self, ctx, loop: int = 1):
            """
            Loops a video
            This command technically works on GIFs but its better to use `$gifloop` which takes advantage of GIFs'
            loop metadata.
            See $gifloop for gifs.

            :Usage=$loop `[loop]`
            :Param=loop - number of times to loop.
            :Param=media - A video or GIF. (automatically found in channel)
            """
            if not 1 <= loop <= 15:
                await ctx.send(f"{config.emojis['warning']} Loop must be between 1 and 15.")
                return
            await improcess(ctx, improcessing.videoloop, [["VIDEO", "GIF"]], loop)

        @commands.command(aliases=["flip", "rot"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def rotate(self, ctx, rot):
            """
            Rotates and/or flips media

            :Usage=$rotate `type`
            :Param=type - 90: 90° clockwise, 90ccw: 90° counter clockwise, 180: 180°, vflip: vertical flip, hflip: horizontal flip
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            types = ["90", "90ccw", "180", "vflip", "hflip"]
            rot = rot.lower()
            if rot not in types:
                await ctx.send(f"{config.emojis['warning']} Rotation type must be: {', '.join(rot)}")
                return
            await improcess(ctx, improcessing.rotate, [["GIF", "IMAGE", "VIDEO"]], rot)

        @commands.command()
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def volume(self, ctx, volume: float):
            """
            Changes the volume of media.
            To make 2x as loud, use `$volume 2`.
            This command changes *perceived loudness*, not the raw audio level.
            WARNING: ***VERY*** LOUD AUDIO CAN BE CREATED

            :Usage=$volume `volume`
            :Param=volume - number to multiply the percieved audio level by. Must be between 0 and 32.
            :Param=media - A video or audio file. (automatically found in channel)
            """
            if not 0 <= volume <= 32:
                await ctx.send(f"{config.emojis['warning']} Volume must be between 0 and 32.")
                return
            await improcess(ctx, improcessing.volume, [["VIDEO", "AUDIO"]], volume)

        @commands.command()
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def vibrato(self, ctx, frequency: float = 5, depth: float = 1):
            """
            Applies a "wavy pitch"/vibrato effect to audio.
            officially described as "Sinusoidal phase modulation"
            see https://ffmpeg.org/ffmpeg-filters.html#tremolo
            :Usage=$vibrato `[frequency]` `[depth]`
            :Param=frequency - Modulation frequency in Hertz. must be between 0.1 and 20000. defaults to 5.
            :Param=depth - Depth of modulation as a percentage. must be between 0 and 1. defaults to 1.
            :Param=media - A video or audio file. (automatically found in channel)
            """
            if not 0.1 <= frequency <= 20000:
                await ctx.send(f"{config.emojis['warning']} Frequency must be between 0.1 and 20000.")
                return
            if not 0 <= depth <= 1:
                await ctx.send(f"{config.emojis['warning']} Depth must be between 0 and 1.")
                return
            await improcess(ctx, improcessing.vibrato, [["VIDEO", "AUDIO"]], frequency, depth)

        @commands.command(aliases=["concat", "combinev"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def concatv(self, ctx):
            """
            Makes one video file play right after another.
            The output video will take on all of the settings of the FIRST video. The second video will be scaled to fit.

            :Usage=$concatv
            :Param=video1 - A video or gif. (automatically found in channel)
            :Param=video2 - A video or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.concatv, [["VIDEO", "GIF"], ["VIDEO", "GIF"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def hstack(self, ctx):
            """
            Stacks 2 videos horizontally

            :Usage=$hstack
            :Param=video1 - A video, image, or gif. (automatically found in channel)
            :Param=video2 - A video, image, or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                            "hstack")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def vstack(self, ctx):
            """
            Stacks 2 videos horizontally

            :Usage=$vstack
            :Param=video1 - A video, image, or gif. (automatically found in channel)
            :Param=video2 - A video, image, or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                            "vstack")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def overlay(self, ctx, opacity: float = 0.5):
            """
            Overlays the second input over the first

            :Usage=$vstack
            :Param=opacity - the opacity of the top video. must be between 0 and 1. defaults to 0.5.
            :Param=video1 - A video or gif. (automatically found in channel)
            :Param=video2 - A video or gif. (automatically found in channel)
            """
            if not 0 <= opacity <= 1:
                await ctx.send(f"{config.emojis['warning']} Opacity must be between 0 and 1.")
                return
            await improcess(ctx, improcessing.overlay, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], opacity)

        @commands.command(name="speed")
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def spcommand(self, ctx, speed: float = 2):
            """
            Changes the speed of media.
            This command preserves the original FPS, which means speeding up will drop frames. See $fps.

            :Usage=$speed `[speed]`
            :Param=speed - Multiplies input video speed by this number. must be between 0.5 and 10. defaults to 2.
            :Param=video - A video or gif. (automatically found in channel)
            """
            # i want this to allow 0.25 but fuckin atempo's minimum is 0.5
            if not 0.5 <= speed <= 10:
                await ctx.send(f"{config.emojis['warning']} Speed must be between 0.5 and 10")
                return
            await improcess(ctx, improcessing.speed, [["VIDEO", "GIF"]], speed)

        @commands.command(aliases=["shuffle", "stutter", "nervous"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def random(self, ctx, frames: int = 30):
            """
            Shuffles the frames of a video around.
            Currently this command does NOT apply to audio. This is an FFmpeg limitation.
            see https://ffmpeg.org/ffmpeg-filters.html#random

            :Usage=random `[frames]`
            :Param=frames - Set size in number of frames of internal cache. must be between 2 and 512. default is 30.
            :Param=video - A video or gif. (automatically found in channel)
            """
            if not 2 <= frames <= 512:
                await ctx.send(f"{config.emojis['warning']} Frames must be between 2 and 512")
                return
            await improcess(ctx, improcessing.random, [["VIDEO", "GIF"]], frames)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def reverse(self, ctx):
            """
            Reverses media.

            :Usage=$reverse
            :Param=video - A video or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.reverse, [["VIDEO", "GIF"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def compressv(self, ctx, crf: float = 51, qa: float = 20):
            """
            Makes videos terrible quality.
            The strange ranges on the numbers are because they are quality settings in FFmpeg's encoding.
            CRF info is found at https://trac.ffmpeg.org/wiki/Encode/H.264#crf
            audio quality info is found under https://trac.ffmpeg.org/wiki/Encode/AAC (see `-b:a`)

            :Usage=$compressv `[crf]` `[qa]`
            :Param=crf - Controls video quality. Higher is worse quality. must be between 28 and 51. defaults to 51.
            :Param=qa - Audio bitrate in kbps. Lower is worse quality. Must be between 10 and 112. defaults to 20.
            :Param=video - A video or gif. (automatically found in channel)

            """
            if not 28 <= crf <= 51:
                await ctx.send(f"{config.emojis['warning']} CRF must be between 28 and 51.")
                return
            if not 10 <= qa <= 112:
                await ctx.send(f"{config.emojis['warning']} qa must be between 1 and 112.")
                return
            await improcess(ctx, improcessing.quality, [["VIDEO", "GIF"]], crf, qa)

        @commands.command(name="fps")
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def fpschange(self, ctx, fps: float):
            """
            Changes the FPS of media.
            This command keeps the speed the same.
            BEWARE: Changing the FPS of gifs can create strange results due to the strange way GIFs store FPS data.
            GIFs are only stable at certain FPS values. These include 50, 30, 15, 10, and others.
            An important reminder that by default tenor "gifs" are interpreted as mp4s, which do not suffer this problem.

            :Usage=$fps `[fps]`
            :Param=fps - Frames per second of the output. must be between 1 and 60.
            :Param=video - A video or gif. (automatically found in channel)
            """
            if not 1 <= fps <= 60:
                await ctx.send(f"{config.emojis['warning']} FPS must be between 1 and 60.")
                return
            await improcess(ctx, improcessing.changefps, [["VIDEO", "GIF"]], fps)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def trim(self, ctx, length: float, start: float = 0):
            """
            Trims media.

            :Usage=$trim `[length]` `start`
            :Param=length - Length in seconds to trim the media to.
            :Param=start - Time in seconds to start the trimmed media at.
            :Param=media - A video, gif, or audio file. (automatically found in channel)
            """
            if not 0 < length:
                await ctx.send(f"{config.emojis['warning']} Length must be more than 0.")
                return
            if not 0 <= start:
                await ctx.send(f"{config.emojis['warning']} Start must be equal to or more than 0.")
                return
            await improcess(ctx, improcessing.trim, [["VIDEO", "GIF", "AUDIO"]], length, start)


    def emojis_in(text):
        emoji_list = []
        data = re.findall(r'\X', text)
        flags = re.findall(u'[\U0001F1E6-\U0001F1FF]', text)
        for word in data:
            if any(char in emoji.UNICODE_EMOJI['en'] for char in word):
                emoji_list.append(word)
        return emoji_list + flags


    class Conversion(commands.Cog, name="Conversion"):
        """
        Commands to convert media types and download internet-hosted media.
        """

        def __init__(self, bot):
            self.bot = bot

        # superceded by $addaudio
        # @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        # @commands.command()
        # async def imageaudio(self, ctx):
        #     """
        #     Combines an image and audio into a video.
        #
        #     :Usage=$imageaudio
        #     :Param=image - An image. (automatically found in channel)
        #     :Param=audio - An audio file. (automatically found in channel)
        #     """
        #     await improcess(ctx, improcessing.imageaudio, [["IMAGE"], ["AUDIO"]])
        @commands.command(aliases=["filename", "name", "setname"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def rename(self, ctx, filename: str):
            """
            Renames media.
            Note: Discord's spoiler feature is dependent on filenames starting with "SPOILER_". renaming files may unspoiler them.

            :Usage=$rename `name`
            :Param=media - Any valid media. (automatically found in channel)
            """
            await improcess(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]], filename=filename)

        @commands.command(aliases=["spoil", "censor", "cw", "tw"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def spoiler(self, ctx):
            """
            Spoilers media.

            :Usage=$spoiler
            :Param=media - Any valid media. (automatically found in channel)
            """
            await improcess(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]], spoiler=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["avatar", "pfp", "profilepicture", "profilepic", "ayowhothismf", "av"])
        async def icon(self, ctx, *, userorserver=None):
            """
            Grabs the icon url of a Discord user or server.
            This command works off IDs. user mentions contain the ID internally so mentioning a user will work.
            To get the icon of a guild, copy the guild id and use that as the parameter.
            To get the icon of a webhook message, copy the message ID and ***in the same channel as the message*** use the message ID as the parameter. This will also work for normal users though i have no idea why you'd do it that way.

            :Usage=$icon `body`
            :Param=body - must contain a user, guild, or message ID. if left blank, the author's avatar will be sent.
            """
            if userorserver is None:
                result = [await improcessing.iconfromsnowflakeid(ctx.author.id, bot, ctx)]
            else:
                id_regex = re.compile(r'([0-9]{15,20})')
                tasks = []
                for m in re.finditer(id_regex, userorserver):
                    tasks.append(improcessing.iconfromsnowflakeid(int(m.group(0)), bot, ctx))
                result = await asyncio.gather(*tasks)
                result = list(filter(None, result))  # remove Nones
            if result:
                await ctx.reply("\n".join(result)[0:2000])
            else:
                await ctx.send(f"{config.emojis['warning']} No valid user, guild, or message ID found.")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["youtube", "youtubedownload", "youtubedl", "ytdownload", "download", "dl", "ytdl"])
        async def videodl(self, ctx, url, form="video"):
            """
            Downloads a web hosted video from sites like youtube.
            Any site here works: https://ytdl-org.github.io/youtube-dl/supportedsites.html

            :Usage=$ytdl `videourl` `format`
            :Param=videourl - the URL of a video or the title of a youtube video.
            :Param=format - download audio or video, defaults to video.
            """
            types = ["video", "audio"]
            form = form.lower()
            if form not in types:
                await ctx.reply(f"{config.emojis['warning']} Download format must be `video` or `audio`.")
                return
            # await improcessing.ytdl(url, form)
            with TempFileSession() as tempfilesession:
                async with ctx.channel.typing():
                    # logger.info(url)
                    msg = await ctx.reply(f"{config.emojis['working']} Downloading from site...", mention_author=False)
                    try:
                        r = await improcessing.run_in_exec(ytdownload, url, form)
                        if r:
                            tempfiles.reserve_names([r])
                            r = await improcessing.assurefilesize(r, ctx)
                            await msg.edit(content=f"{config.emojis['working']} Uploading to Discord...")
                            await ctx.reply(file=discord.File(r))
                        else:
                            await ctx.reply(f"{config.emojis['warning']} No available downloads found within Discord's "
                                            f"file upload limit.")
                        # os.remove(r)
                        await msg.delete()
                    except youtube_dl.DownloadError as e:
                        await ctx.reply(f"{config.emojis['2exclamation']} {e}")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["gif", "videotogif"])
        async def togif(self, ctx):
            """
            Converts a video to a GIF.

            :Usage=$togif
            :Param=video - A video. (automatically found in channel)
            """
            await improcess(ctx, improcessing.mp4togif, [["VIDEO"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["apng", "videotoapng", "giftoapng"])
        async def toapng(self, ctx):
            """
            Converts a video or gif to an animated png.

            :Usage=$toapng
            :Param=video - A video or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.toapng, [["VIDEO", "GIF"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["audio", "mp3", "tomp3", "aac", "toaac"])
        async def toaudio(self, ctx):
            """
            Converts a video to only audio.

            :Usage=$toaudio
            :Param=video - A video. (automatically found in channel)
            """
            await improcess(ctx, improcessing.toaudio, [["VIDEO", "AUDIO"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def tenorgif(self, ctx):
            """
            Sends the GIF url for a tenor gif.
            By default, tenor gifs are interpreted as MP4 files due to their superior quality.
            This command gets the gif straight from tenor, making it faster than $videotogif,
            however, some tenor gifs can be lower fps/quality than the converted video.

            :Usage=$tenorgif
            :Param=gif - any gif sent from tenor. (automatically found in channel)
            """
            logger.info("Getting tenor gif...")
            file = await tenorsearch(ctx, True)
            if file:
                await ctx.send(file)
                logger.info("Complete!")
            else:
                await ctx.send(f"{config.emojis['x']} No tenor gif found.")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["video", "giftovideo", "tomp4"])
        async def tovideo(self, ctx):
            """
            Converts a GIF to a video.

            :Usage=$tovideo
            :Param=gif - A gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.giftomp4, [["GIF"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["png", "mediatopng"])
        async def topng(self, ctx):
            """
            Converts media to PNG

            :Usage=$topng
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, improcessing.mediatopng, [["VIDEO", "GIF", "IMAGE"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["emoji", "emojiimage", "emote", "emoteurl"])
        async def emojiurl(self, ctx, *emojis: discord.PartialEmoji):
            """
            Sends the raw image for a custom Discord emoji.
            Each emoji is sent as a separate message intentionally to allow replying with a media command.

            :Usage=$emojiurl `emojis`
            :Param=emojis - Custom emojis to send the URL of. Be sure to put a space between them.
            """
            if emojis:
                out = []
                for emoji in emojis:
                    out.append(str(emoji.url))
                await ctx.send("\n".join(out))
            else:
                await ctx.reply(f"{config.emojis['warning']} Your message doesn't contain any custom emojis!")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def twemoji(self, ctx, *, msg):
            """
            Sends the twemoji image for an emoji.
            Twemoji is the open source emoji set that discord desktop and twitter use. https://twemoji.twitter.com/

            :Usage=$twemoji `emoji`
            :Param=emoji - Up to 5 default emojis.
            """
            if ctx.message.reference:
                msg = ctx.message.reference.resolved.content
            emojis = emojis_in(msg)[:5]
            if emojis:
                for e in emojis:
                    chars = []
                    for char in e:
                        chars.append(f"{ord(char):x}")  # get hex code of char
                    chars = "-".join(chars).replace("/", "")
                    fpath = f"rendering/twemoji/72x72/{chars}.png"
                    logger.debug(f"trying twemoji {fpath}")
                    if os.path.exists(fpath):
                        await ctx.reply(file=discord.File(fpath))
            else:
                await ctx.reply(f"{config.emojis['x']} No default emojis found!")


    class Image(commands.Cog, name="Creation"):
        """
        Generate images from a template.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.command(aliases=["troll"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def trollface(self, ctx):
            """
            Colors a trollface with an image.

            :Usage=$trollface
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.trollface, [["VIDEO", "GIF", "IMAGE"]], handleanimated=True)

        @commands.command(aliases=['sus', 'imposter'])
        async def jermatext(self, ctx, *, text="when the imposter is sus!😳"):
            """
            Cut and slice the popular Jerma sus meme to any message
            For any letter not in the original meme, a random slice of the face is selected.
            Based on https://github.com/aechaechaech/Jerma-Imposter-Message-Generator

            :Usage=$sus `text`
            :Param=text - The text to cut and splice.
            """
            await improcess(ctx, sus.sus, [], text)

        @commands.command(aliases=["emsay"])
        async def eminemsay(self, ctx, *, text):
            """
            Eminem says something.

            :Usage=$eminem `text`
            :Param=text - The text to put next to eminem.
            """
            await improcess(ctx, captionfunctions.eminem, [], [text])

        @commands.command(aliases=["handitover", "takeit", "giveme"])
        async def givemeyourphone(self, ctx):
            """
            Overlays an image over the hand of the boy in the "give me your phone" meme.
            https://knowyourmeme.com/memes/give-me-your-phone

            :Usage=$givemeyourphone
            :Param=media - The media to be overlayed over his hand. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.givemeyourphone, [["IMAGE", "VIDEO", "GIF"]], handleanimated=True)

        @commands.command(aliases=["donald", "donalttrump", "trump", "trumptweet", "donaldtrumptweet", "dontweet",
                                   "donal", "donaltweet"])
        async def donaldtweet(self, ctx, *, text):
            """
            Makes a fake Donald Trump tweet.

            :Usage=donaldtweet `text`
            :Param=text - The text to put in the fake tweet.
            """
            await improcess(ctx, captionfunctions.dontweet, [], [text])


    def showcog(cog):
        show_cog = False
        # check if there are any non-hidden commands in the cog, if not, dont show it in the help menu.
        for com in cog.get_commands():
            if not com.hidden:
                show_cog = True
                break
        return show_cog


    class Other(commands.Cog, name="Other"):
        """
        Commands that don't fit in the other categories.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.cooldown(1, config.cooldown, commands.BucketType.guild)
        @commands.guild_only()
        @commands.has_guild_permissions(manage_guild=True)
        @commands.command(aliases=["pfx", "setprefix", "changeprefix", "botprefix", "commandprefix"])
        async def prefix(self, ctx, prefix=None):
            """
            Changes the bot's prefix for this guild.

            :Usage=prefix `prefix`
            :Param=prefix - The new prefix for the bot to use.
            """
            if prefix is None:
                async with aiosqlite.connect(config.db_filename) as db:
                    await db.execute("DELETE FROM guild_prefixes WHERE guild=?", (ctx.guild.id,))
                    await db.commit()
                await ctx.reply(f"{config.emojis['check']} Set guild prefix back to global default "
                                f"(`{config.default_command_prefix}`).")

            else:
                if not 50 >= len(prefix) > 0:
                    await ctx.reply(f"{config.emojis['x']} prefix must be between 1 and 50 characters.")
                    return
                # check for invalid characters by returning all invalid characters
                invalids = re.findall(r"[^a-zA-Z0-9!$%^&()_\-=+,<.>\/?;:'[{\]}|]", prefix)
                if invalids:
                    await ctx.reply(f"{config.emojis['x']} Found invalid characters: "
                                    f"{', '.join([discord.utils.escape_markdown(i) for i in invalids])}")
                else:
                    async with aiosqlite.connect(config.db_filename) as db:
                        await db.execute("REPLACE INTO guild_prefixes(guild, prefix) VALUES (?,?)",
                                         (ctx.guild.id, prefix))
                        await db.commit()
                    await ctx.reply(f"{config.emojis['check']} Set guild prefix to `{prefix}`")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.guild_only()
        @commands.has_guild_permissions(manage_emojis=True)
        @commands.bot_has_guild_permissions(manage_emojis=True)
        @commands.command(aliases=["createemoji"])
        async def addemoji(self, ctx, name):
            """
            Adds a file as an emoji to a server. Both MediaForge and the command caller must have the Manage Emojis permission.

            :Usage=$addemoji `caption`
            :Param=name - The emoji name. Must be at least 2 characters.
            :Param=media - A gif or image. (automatically found in channel)
            """
            await improcess(ctx, improcessing.add_emoji, [["GIF", "IMAGE"]], ctx.guild, name, expectresult=False,
                            resize=False)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.guild_only()
        @commands.has_guild_permissions(manage_guild=True)
        @commands.bot_has_guild_permissions(manage_guild=True)
        @commands.command(aliases=["guildbanner", "serverbanner", "banner"])
        async def setbanner(self, ctx):
            """
            Sets a file as the server banner.
            Server must support banners.

            :Usage=$setbanner
            :Param=media - An image. (automatically found in channel)
            """
            if "BANNER" not in ctx.guild.features:
                await ctx.reply(f"{config.emojis['x']} This guild does not support banners.")
                return
            await improcess(ctx, improcessing.set_banner, [["IMAGE"]], ctx.guild, expectresult=False,
                            resize=False)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.guild_only()
        @commands.has_guild_permissions(manage_guild=True)
        @commands.bot_has_guild_permissions(manage_guild=True)
        @commands.command(aliases=["setguildicon", "guildicon", "servericon", "seticon"])
        async def setservericon(self, ctx):
            """
            Sets a file as the server icon.
            If setting a gif, server must support animated icons.

            :Usage=$seticon
            :Param=media - An image or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.set_icon, [["IMAGE", "GIF"]], ctx.guild, expectresult=False,
                            resize=False)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["statistics"])
        async def stats(self, ctx):
            """
            Displays some stats about what the bot is currently doing.

            :Usage=$stats
            """
            stats = renderpool.stats()
            embed = discord.Embed(color=discord.Color(0xD262BA), title="Statistics",
                                  description="A 'task' is typically processing a single image/frame of a video. Not "
                                              "all commands will use tasks.")
            embed.add_field(name="Queued Tasks", value=f"{stats[0]}")
            embed.add_field(name="Currently Executing Tasks", value=f"{stats[1]}")
            embed.add_field(name="Available Workers", value=f"{config.chrome_driver_instances - stats[1]}")
            embed.add_field(name="Total Workers", value=f"{config.chrome_driver_instances}")
            await ctx.reply(embed=embed)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["discord", "invite", "botinfo"])
        async def about(self, ctx):
            """
            Lists important links related to MediaForge such as the official server.

            :Usage=$stats
            """
            embed = discord.Embed(color=discord.Color(0xD262BA), title="MediaForge")
            embed.add_field(name="Official MediaForge Discord Server", value=f"https://discord.gg/xwWjgyVqBz")
            embed.add_field(name="top.gg link", value=f"https://top.gg/bot/780570413767983122")
            embed.add_field(name="Vote for MediaForge on top.gg", value=f"https://top.gg/bot/780570413767983122/vote")
            embed.add_field(name="Add MediaForge to your server",
                            value=f"https://discord.com/api/oauth2/authorize?client_id=780570413767983122&permissions=3"
                                  f"79968&scope=bot")
            embed.add_field(name="MediaForge GitHub", value=f"https://github.com/HexCodeFFF/captionbot")
            await ctx.reply(embed=embed)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["privacypolicy"])
        async def privacy(self, ctx):
            """
            Shows MediaForge's privacy policy

            :Usage=$privacy
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
                                                             f"https://github.com/HexCodeFFF/captionbot).")
            await ctx.reply(embed=embed)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["github", "git"])
        async def version(self, ctx):
            """
            Shows information on how this copy of MediaForge compares to the latest code on github.
            https://github.com/HexCodeFFF/captionbot
            This command returns the output of `git status`.

            :Usage=$version
            """
            await improcessing.run_command("git", "fetch")
            status = await improcessing.run_command("git", "status")
            with io.StringIO() as buf:
                buf.write(status)
                buf.seek(0)
                await ctx.reply("Output of `git status` (the differences between this copy of MediaForge and the latest"
                                " code on GitHub)", file=discord.File(buf, filename="gitstatus.txt"))

        @commands.command()
        async def help(self, ctx, *, arg=None):
            """
            Shows the help message.

            :Usage=$help `[inquiry]`
            :Param=inquiry - the name of a command or command category. If none is provided, all categories are shown.
            """
            prefix = await prefix_function(bot, ctx.message)
            if arg is None:
                embed = discord.Embed(title="Help", color=discord.Color(0xB565D9),
                                      description=f"Run `{prefix}help category` to list commands from "
                                                  f"that category.")
                for c in bot.cogs.values():
                    if showcog(c):
                        if not c.description:
                            c.description = "No Description."
                        embed.add_field(name=c.qualified_name, value=c.description)
                embed.add_field(name="Tips", value="A list of tips for using the bot.")
                await ctx.reply(embed=embed)
            elif arg.lower() in ["tips", "tip"]:
                embed = discord.Embed(title="Tips", color=discord.Color(0xD262BA))
                for tip, tipv in config.tips.items():
                    embed.add_field(name=tip, value=tipv, inline=False)
                await ctx.reply(embed=embed)
            # if the command argument matches the name of any of the cogs that contain any not hidden commands
            elif arg.lower() in [c.lower() for c, v in self.bot.cogs.items() if showcog(v)]:
                cogs_lower = {k.lower(): v for k, v in bot.cogs.items()}
                cog = cogs_lower[arg.lower()]
                embed = discord.Embed(title=cog.qualified_name,
                                      description=cog.description + f"\nRun `{prefix}help command` for "
                                                                    f"more information on a command.",
                                      color=discord.Color(0xD262BA))
                for cmd in sorted(cog.get_commands(), key=lambda x: x.name):
                    if not cmd.hidden:
                        desc = cmd.short_doc if cmd.short_doc else "No Description."
                        embed.add_field(name=f"{prefix}{cmd.name}", value=desc)
                await ctx.reply(embed=embed)
            # elif arg.lower() in [c.name for c in bot.commands]:
            else:
                for all_cmd in bot.commands:
                    if (all_cmd.name == arg.lower() or arg.lower() in all_cmd.aliases) and not all_cmd.hidden:
                        cmd: discord.ext.commands.Command = all_cmd
                        break
                else:
                    await ctx.reply(
                        f"{config.emojis['warning']} `{arg}` is not the name of a command or a command category!")
                    return
                embed = discord.Embed(title=prefix + cmd.name, description=cmd.cog_name,
                                      color=discord.Color(0xEE609C))
                fields = {}
                fhelp = []
                for line in cmd.help.split("\n"):
                    if line.startswith(":"):
                        if line.split("=")[0].strip(":") in fields:
                            fields[line.split("=")[0].strip(":")] += "\n" + "=".join(line.split("=")[1:])
                        else:
                            fields[line.split("=")[0].strip(":")] = "=".join(line.split("=")[1:])
                    else:
                        fhelp.append(line)
                fhelp = "\n".join(fhelp)
                embed.add_field(name="Command Information", value=fhelp.replace("$", prefix),
                                inline=False)
                for k, v in fields.items():
                    if k == "Param":
                        k = "Parameters"
                    embed.add_field(name=k, value=v.replace("$", prefix), inline=False)
                if cmd.aliases:
                    embed.add_field(name="Aliases", value=", ".join([prefix + a for a in cmd.aliases]))
                await ctx.reply(embed=embed)

        @commands.command(aliases=["ffprobe"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def info(self, ctx):
            """
            Provides info on a media file.
            Info provided is from ffprobe and libmagic.

            :Usage=$info
            :Param=media - Any media file. (automatically found in channel)
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
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def feedback(self, ctx):
            """
            Give feedback for the bot.
            This sends various links from the github repo for reporting issues or asking questions.

            :Usage=$feedback
            """
            embed = discord.Embed(title="Feedback",
                                  description="Feedback is best given via the GitHub repo, various "
                                              "links are provided below.",
                                  color=discord.Color(0xD262BA))
            embed.add_field(name="Report a bug",
                            value="To report a bug, make an issue at\nhttps://github.com/HexCodeFFF/captionbot/issues",
                            inline=False)
            embed.add_field(name="Ask a question", value="Have a question? Use the Q&A Discussion "
                                                         "page.\nhttps://github.com/HexCodeFFF/captionbot/discussions/c"
                                                         "ategories/q-a", inline=False)
            embed.add_field(name="Give an idea",
                            value="Have an idea or suggestion? Use the Ideas Discussion page.\nhtt"
                                  "ps://github.com/HexCodeFFF/captionbot/discussions/categories/id"
                                  "eas", inline=False)
            embed.add_field(name="Something else?",
                            value="Anything is welcome in the discussion page!\nhttps://github."
                                  "com/HexCodeFFF/captionbot/discussions", inline=False)
            embed.add_field(name="Why GitHub?",
                            value="Using GitHub for feedback makes it much easier to organize any i"
                                  "ssues and to implement them into the bot's code.")
            await ctx.reply(embed=embed)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def attributions(self, ctx):
            """
            Lists most libraries and programs this bot uses.
            :Usage=$attributions
            """
            with open("media/attributions.txt", "r") as f:
                await ctx.send(f.read())

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command(aliases=["pong"])
        async def ping(self, ctx):
            """
            Pong!
            :Usage=$ping
            """
            await ctx.reply(f"🏓 Pong! `{round(bot.latency * 1000, 1)}ms`")


    class Debug(commands.Cog, name="Owner Only", command_attrs=dict(hidden=True)):
        def __init__(self, bot):
            self.bot = bot

        @commands.command()
        @commands.is_owner()
        async def say(self, ctx, channel: typing.Optional[typing.Union[discord.TextChannel, discord.User]], *, msg):
            if not channel:
                channel = ctx.channel
            if ctx.me.permissions_in(ctx.channel).manage_messages:
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

        @commands.command(hidden=True, aliases=["stop", "close", "die", "kill"])
        @commands.is_owner()
        async def shutdown(self, ctx):
            """
            Shut down the bot
            """
            await ctx.send(f"{config.emojis['check']} Shutting Down...")
            logger.log(25, "Shutting Down...")
            await renderpool.shutdown()
            await bot.close()

        @commands.command()
        @commands.is_owner()
        async def generate_command_list(self, ctx):
            out = ""
            for cog in bot.cogs.values():
                if not showcog(cog): continue
                out += f"### {cog.qualified_name}\n"
                for command in sorted(cog.get_commands(), key=lambda x: x.name):
                    if not command.hidden:
                        out += f"- **${command.name}**: {command.short_doc}\n"
            with io.StringIO() as buf:
                buf.write(out)
                buf.seek(0)
                await ctx.reply(file=discord.File(buf, filename="commands.md"))


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
        #     :Usage=$eminem `text`
        #     :Param=text - The text to put next to eminem.
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
                                    f"word with `>`.", allowed_mentions=discord.AllowedMentions.none())
                    return
            out = " ".join(out)
            # clear out any whitespace touching punctuation
            out = re.sub(r"(\s(?=[,.])|(?<=[,.])\s)", "", out)
            await improcess(ctx, captionfunctions.slashscript, [], [out])


    def logcommand(cmd):
        cmd = cmd.replace("\n", "\\n")
        if len(cmd) > 100:
            cmd = cmd[:100] + "..."
        return cmd


    @bot.listen()
    async def on_command(ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            logger.log(25,
                       f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ran "
                       f"'{logcommand(ctx.message.content)}' in DMs")
        else:
            logger.log(25,
                       f"@{ctx.message.author.name}#{ctx.message.author.discriminator}"
                       f" ({ctx.message.author.display_name}) ran '{logcommand(ctx.message.content)}' in channel "
                       f"#{ctx.channel.name} in server {ctx.guild}")


    @bot.listen()
    async def on_message(message):
        if f"<@{bot.user.id}>" in message.content or f"<@!{bot.user.id}>" in message.content:
            await message.reply(f"My command prefix is `{await prefix_function(bot, message)}`.", delete_after=10)


    @bot.listen()
    async def on_command_completion(ctx):
        logger.log(35,
                   f"Command '{logcommand(ctx.message.content)}' by @{ctx.message.author.name}#{ctx.message.author.discriminator} "
                   f"is complete!")


    def get_full_class_name(obj):
        module = obj.__class__.__module__
        if module is None or module == str.__class__.__module__:
            return obj.__class__.__name__
        return module + '.' + obj.__class__.__name__


    @bot.check
    def block_filter(ctx):
        # this command is exempt because it only works on URLs and there have been issues with r/okbr
        if ctx.command.name == "videodl":
            return True
        for block in config.blocked_words:
            if block.lower() in ctx.message.content.lower():
                raise commands.CheckFailure("Your command contains one or more blocked words.")
        return True


    @bot.listen()
    async def on_command_error(ctx, commanderror):
        global renderpool
        if isinstance(commanderror, concurrent.futures.process.BrokenProcessPool):
            renderpool = improcessing.initializerenderpool()
        errorstring = discord.utils.escape_mentions(discord.utils.escape_markdown(str(commanderror)))
        if isinstance(commanderror, discord.Forbidden):
            if not ctx.me.permissions_in(ctx.channel).send_messages:
                if ctx.me.permissions_in(ctx.author).send_messages:
                    err = f"{config.emojis['x']} I don't have permissions to send messages in that channel."
                    await ctx.author.send(err)
                    logger.warning(err)
                    return
                else:
                    logger.warning("No permissions to send in command channel or to DM author.")
        if isinstance(commanderror, discord.ext.commands.errors.CommandNotFound):
            msg = ctx.message.content
            cmd = discord.utils.escape_mentions(msg.split(' ')[0])
            allcmds = []
            for botcom in bot.commands:
                if not botcom.hidden:
                    allcmds.append(botcom.name)
                    allcmds += botcom.aliases
            prefix = await prefix_function(bot, ctx.message)
            match = difflib.get_close_matches(cmd.replace(prefix, "", 1), allcmds, n=1, cutoff=0)[0]
            err = f"{config.emojis['exclamation_question']} Command `{cmd}` does not exist. " \
                  f"Did you mean **{prefix}{match}**?"
            logger.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NotOwner):
            err = f"{config.emojis['x']} You are not authorized to use this command."
            logger.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandOnCooldown):
            err = f"{config.emojis['clock']} {errorstring}"
            logger.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.MissingRequiredArgument):
            err = f"{config.emojis['question']} {errorstring}"
            logger.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.BadArgument):
            err = f"{config.emojis['warning']} Bad Argument! Did you put text where a number should be? `{errorstring}`"
            logger.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NoPrivateMessage):
            err = f"{config.emojis['warning']} {errorstring}"
            logger.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CheckFailure):
            err = f"{config.emojis['x']} {errorstring}"
            logger.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError) and \
                isinstance(commanderror.original, improcessing.NonBugError):
            await ctx.reply(f"{config.emojis['2exclamation']}" +
                            discord.utils.escape_mentions(str(commanderror.original)[:1000]))
        else:
            if isinstance(commanderror, discord.ext.commands.errors.CommandInvokeError):
                commanderror = commanderror.original
            logger.error(commanderror, exc_info=(type(commanderror), commanderror, commanderror.__traceback__))
            with TempFileSession() as tempfilesession:
                tr = temp_file("txt")
                trheader = f"DATETIME:{datetime.datetime.now()}\nCOMMAND:{ctx.message.content}\nTRACEBACK:\n"
                with open(tr, "w+", encoding="UTF-8") as t:
                    t.write(trheader + ''.join(
                        traceback.format_exception(etype=type(commanderror), value=commanderror,
                                                   tb=commanderror.__traceback__)))
                embed = discord.Embed(color=0xed1c24, description="Please report this error with the attached "
                                                                  "traceback file to the GitHub.")
                embed.add_field(name=f"{config.emojis['2exclamation']} Report Issue to GitHub",
                                value=f"[Create New Issue](https://github.com/HexCodeFFF/captionbot"
                                      f"/issues/new?labels=bug&template=bug_report.md&title"
                                      f"={urllib.parse.quote(str(commanderror)[:128], safe='')})\n[View Issu"
                                      f"es](https://github.com/HexCodeFFF/captionbot/issues)")
                await ctx.reply(f"{config.emojis['2exclamation']} `{get_full_class_name(commanderror)}: "
                                f"{errorstring[:128]}`",
                                file=discord.File(tr, filename="traceback.txt"), embed=embed)


    async def periodic():
        while True:
            try:
                await fetch(config.heartbeaturl)
                logger.debug("Succesfully sent heartbeat.")
            except aiohttp.ClientResponseError as e:
                logger.error(e, exc_info=(type(e), e, e.__traceback__))
            await asyncio.sleep(config.heartbeatfrequency)


    class HealthChecksio(commands.Cog):
        def __init__(self, bot):
            self.bot = bot
            if hasattr(config, "heartbeaturl") and config.heartbeaturl:
                logger.debug(f"Heartbeat URL is {config.heartbeaturl}")
                loop = asyncio.get_event_loop()
                loop.create_task(periodic())


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


    # bot.remove_command('help')
    logger.debug(f"initializing cogs")
    if config.bot_list_data:
        logger.info("initializing BotBlock")
        bot.add_cog(DiscordListsPost(bot))
    bot.add_cog(Caption(bot))
    bot.add_cog(Media(bot))
    bot.add_cog(Conversion(bot))
    bot.add_cog(Image(bot))
    bot.add_cog(Other(bot))
    bot.add_cog(Debug(bot))
    bot.add_cog(Slashscript(bot))
    bot.add_cog(HealthChecksio(bot))

    logger.debug("running bot")
    bot.run(config.bot_token)
