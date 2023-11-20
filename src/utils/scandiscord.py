"""
Miscellaneous helper functions for commands
"""

import json

import discord
import regex as re
from discord.ext import commands

import config
from core.clogs import logger
from utils.common import fetch
from utils.web import contentlength

tenor_url_regex = re.compile(r"https?://tenor\.com/view/([^-]+-)*(\d+)/?")


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
                    tenor = await fetch(
                        f"https://tenor.googleapis.com/v2/posts?ids={gif_id}&key={config.tenor_key}&limit=1")
                    tenor = json.loads(tenor)
                    detectedfiles.append(tenor['results'][0]['media_formats']['gif']['url'])
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
                logger.info("lottie sticker ignored.")
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
                f"https://tenor.googleapis.com/v2/posts?ids={m.embeds[0].url.split('-').pop()}&key={config.tenor_key}")
            tenor = json.loads(tenor)
            if 'error' in tenor:
                logger.error(tenor['error'])
                await ctx.send(f"{config.emojis['2exclamation']} Tenor Error! `{tenor['error']}`")
                return False
            else:
                if gif:
                    return tenor['results'][0]['media_formats']['gif']['url']
                else:
                    return tenor['results'][0]['media_formats']['mp4']['url']
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
