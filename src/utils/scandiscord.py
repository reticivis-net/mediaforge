"""
Miscellaneous helper functions for commands
"""
# TODO: reddit moment caption
import asyncio
import inspect
import json

import discord
import regex as re
from discord.ext import commands

import config
import processing.other
import processing.ffprobe
import processing.ffmpeg
import processing.common
from src.clogs import logger
from utils.common import fetch
from utils.web import saveurls, contentlength

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


async def handletenor(m: discord.Message, ctx: commands.Context, gif=False):
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
                    resize=True, expectresult=True, filename=None, spoiler=False):
    """
    The core function of the bot. Gathers media and sends it to the proper function.

    :param ctx: discord context. media is gathered using imagesearch() with this.
    :param func: function to process input media with
    :param allowedtypes: list of lists of strings. each inner list is an argument, the strings it contains are the
    types that arg must be. or just False/[] if no media needed
    :param args: any non-media arguments, passed into func()
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

    try:
        if allowedtypes:
            urls = await imagesearch(ctx, len(allowedtypes))
            files = await saveurls(urls)
        else:
            files = []
        if files or not allowedtypes:
            for i, file in enumerate(files):
                if (imtype := await processing.ffprobe.mediatype(file)) not in allowedtypes[i]:
                    await ctx.reply(
                        f"{config.emojis['warning']} Media #{i + 1} is {imtype}, it must be: "
                        f"{', '.join(allowedtypes[i])}")
                    logger.warning(f"Media {i} type {imtype} is not in {allowedtypes[i]}")
                    # for f in files:
                    #     os.remove(f)
                    break
                else:
                    if await processing.ffmpeg.is_apng(file):
                        asyncio.create_task(ctx.reply(f"{config.emojis['warning']} Media #{i + 1} is an apng, w"
                                                      f"hich FFmpeg and MediaForge have limited support for. Ex"
                                                      f"pect errors.", delete_after=10))
                    if resize:
                        files[i] = await processing.ffmpeg.ensuresize(ctx, file, config.min_size, config.max_size)
            else:
                pt = "Processing... (this may take a while or, if a severe error occurs, may not finish)"
                logger.info("Processing...")
                if allowedtypes:
                    await updatestatus(pt)
                else:
                    # Downloading message doesnt exist, create it
                    msg = await ctx.reply(f"{config.emojis['working']} {pt}", mention_author=False)
                if allowedtypes:
                    if len(files) == 1:
                        filesforcommand = files[0]
                    else:
                        filesforcommand = files.copy()
                    if inspect.iscoroutinefunction(func):
                        result = await func(filesforcommand, *args)
                    else:
                        logger.warning(f"{func} is not coroutine!")
                        result = func(filesforcommand, *args)
                else:
                    result = await func(*args)
                if expectresult:
                    if not result:
                        raise processing.common.ReturnedNothing(f"Expected image, {func} returned nothing.")
                    result = await processing.ffmpeg.assurefilesize(result, ctx)
                    await processing.other.watermark(result)
                else:
                    if not result:
                        raise processing.common.ReturnedNothing(f"Expected string, {func} returned nothing.")
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


