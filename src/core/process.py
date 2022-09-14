import asyncio
import inspect

import discord
from discord.ext import commands

import config
import processing.common
import processing.ffmpeg
import processing.ffprobe
from core import v2queue
from core.clogs import logger
from utils.scandiscord import imagesearch
from utils.web import saveurls


async def process(ctx: commands.Context, func: callable, inputs: list, *args,
                  resize=True, expectimage=True, uploadresult=True, queue=True):
    """
    The core function of the bot. Gathers media and sends it to the proper function.

    :param ctx: discord context. media is gathered using imagesearch() with this.
    :param func: function to process input media with
    :param inputs: list of lists of strings. each inner list is an argument, the strings it contains are the
        types that arg must be. or just False/[] if no media needed
    :param args: any non-media arguments, passed into func()
    :param resize: automatically up/downsize the inputs?
    :param expectimage: is func() supposed to return a result? if true, it expects an image. if false, can use a
        string.
    :param uploadresult: if true, uploads the result automatically.
    :param queue: if true, command must wait for open slot in queue to process.
    :return: filename of processed media
    """

    result = None
    msg = None

    async def reply(st):
        return await ctx.reply(f"{config.emojis['working']} {st}", mention_author=False)

    async def updatestatus(st):
        nonlocal msg
        try:
            if msg is None:
                msg = await reply(st)
            else:
                msg = await msg.edit(content=f"{config.emojis['working']} {st}",
                                     allowed_mentions=discord.AllowedMentions.none())
        except discord.NotFound:
            msg = await reply(st)

    if inputs:
        # nothing to download sometimes
        await updatestatus(f"Downloading...")

    try:
        # get media from channel
        if inputs:
            urls = await imagesearch(ctx, len(inputs))
            files = await saveurls(urls)
        else:
            files = []
        # if media found or none needed
        if files or not inputs:
            # check that each file is correct type
            for i, file in enumerate(files):
                # if file is incorrect type
                if (imtype := await processing.ffprobe.mediatype(file)) not in inputs[i]:
                    # send message and break
                    await ctx.reply(
                        f"{config.emojis['warning']} Media #{i + 1} is {imtype}, it must be: "
                        f"{', '.join(inputs[i])}")
                    logger.info(f"Media {i} type {imtype} is not in {inputs[i]}")
                    break
                else:
                    # send warning for apng
                    if await processing.ffmpeg.is_apng(file):
                        asyncio.create_task(ctx.reply(f"{config.emojis['warning']} Media #{i + 1} is an apng, w"
                                                      f"hich FFmpeg and MediaForge have limited support for. Ex"
                                                      f"pect errors.", delete_after=10))
                    # resize if needed
                    if resize:
                        files[i] = await processing.ffmpeg.ensuresize(ctx, file, config.min_size, config.max_size)
            # files are of correcte type, begin to process
            else:
                await updatestatus("Your command is in the queue...")
                # prepare args
                if inputs:
                    args = files + list(args)

                # run func
                async def run():
                    logger.info("Processing...")
                    asyncio.create_task(updatestatus("Processing..."))
                    # some commands arent coros (usually no-ops) so this is a good check to make
                    if inspect.iscoroutinefunction(func):
                        return await func(*args)
                    else:
                        logger.warning(f"{func} is not coroutine!")
                        return func(*args)

                # only queue if needed
                if queue:
                    async with v2queue.sem:
                        result = await run()
                else:
                    result = await run()
                # check results are as expected
                if expectimage:  # file expected
                    if not result:
                        raise processing.common.ReturnedNothing(f"Expected image, {func} returned nothing.")
                    # fit within discord limit
                    result = await processing.ffmpeg.assurefilesize(result, ctx)
                else:  # status string expected
                    if not result:
                        raise processing.common.ReturnedNothing(f"Expected string, {func} returned nothing.")
                    else:
                        await ctx.reply(result)

                # if we need to upload image, do that
                if result and expectimage:
                    logger.info("Uploading...")
                    await updatestatus("Uploading...")
                    if uploadresult:
                        await ctx.reply(file=discord.File(result))
        else:  # no media found but media expected
            logger.info("No media found.")
            await ctx.reply(f"{config.emojis['x']} No file found.")
    except Exception as e:
        # delete message before raising exception
        if isinstance(msg, discord.Message):
            await msg.delete()
        raise e
    # delete message
    if isinstance(msg, discord.Message):
        await msg.delete()
    return result
