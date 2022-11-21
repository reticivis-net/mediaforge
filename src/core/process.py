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
                  resize=True, expectimage=True, uploadresult=True, queue=True, run_parallel=False, **kwargs):
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
    :param run_parallel: for sync functions only, run without blocking
    :return: filename of processed media
    """

    result = None
    msgs = []

    async def reply(st):
        return await ctx.reply(f"{config.emojis['working']} {st}", mention_author=False)

    async def updatestatus(st):
        nonlocal msgs
        try:
            if not msgs:
                msgs.append(await reply(st))
            else:
                msgs.append(await msgs[-1].edit(content=f"{config.emojis['working']} {st}",
                                                allowed_mentions=discord.AllowedMentions.none()))
        except discord.NotFound:
            msgs.append(await reply(st))

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
                # only update with queue message if there is a queue
                if queue and v2queue.sem.locked():
                    await updatestatus("Your command is in the queue...")

                # run func
                async def run():
                    nonlocal args
                    nonlocal files
                    logger.info("Processing...")
                    await updatestatus("Processing...")
                    # remove too long videossss
                    for i, f in enumerate(files):
                        files[i] = await processing.ffmpeg.ensureduration(f, ctx)
                    # prepare args
                    if inputs:
                        args = files + list(args)
                    # some commands arent coros (usually no-ops) so this is a good check to make
                    if inspect.iscoroutinefunction(func):
                        command_result = await func(*args, **kwargs)
                    else:
                        if run_parallel:
                            command_result = await processing.common.run_parallel(func, *args, **kwargs)
                        else:
                            logger.warning(f"{func} is not coroutine")
                            command_result = func(*args, **kwargs)
                    if expectimage and command_result:
                        mt = await processing.ffmpeg.mediatype(command_result)
                        if mt == "VIDEO":
                            command_result = await processing.ffmpeg.reencode(command_result)
                        command_result = await processing.ffmpeg.assurefilesize(command_result)
                    return command_result

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
                        result.deletesoon()
        else:  # no media found but media expected
            logger.info("No media found.")
            await ctx.reply(f"{config.emojis['x']} No file found.")
    except Exception as e:
        await asyncio.gather(*[msg.delete() for msg in msgs], return_exceptions=True)
        raise e
    # delete message
    await asyncio.gather(*[msg.delete() for msg in msgs], return_exceptions=True)
    return result
