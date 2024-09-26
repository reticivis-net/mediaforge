import asyncio
import math

import config
import processing.common
from core.clogs import logger
from processing.ffmpeg.conversion import videotogif, mediatopng
from processing.ffmpeg.ffprobe import mediatype, get_duration, hasaudio, get_resolution
from utils.tempfiles import reserve_tempfile
from processing.common import run_command, NonBugError
import processing.vips as vips


async def forceaudio(video):
    """
    gives videos with no audio a silent audio stream
    :param video: file
    :return: video filename
    """
    if await hasaudio(video):
        return video
    else:
        outname = reserve_tempfile("mkv")
        await run_command("ffmpeg", "-hide_banner", "-i", video, "-f", "lavfi", "-i", "anullsrc", "-c:v", "ffv1",
                          "-c:a", "flac", "-map", "0:v", "-map", "1:a", "-shortest", "-fps_mode", "vfr", outname)

        return outname


def gif_output(f):
    """
    if the input is a gif, make the output a gif
    """

    async def wrapper(media, *args, **kwargs):
        mt = await mediatype(media)
        out = await f(media, *args, **kwargs)
        if mt == "GIF":
            out = await videotogif(out)
        return out

    return wrapper


def dual_gif_output(f):
    """
    if there are two gifs, make the output a gif if its a good idea
    """

    async def wrapper(media1, media2, *args, **kwargs):
        mt1 = await mediatype(media1)
        mt2 = await mediatype(media2)
        out = await f(media1, media2, *args, **kwargs)
        # if there are gifs, but no videos, convert to gif
        if (mt1 == "GIF" or mt2 == "GIF") and not (mt1 == "VIDEO" or mt2 == "VIDEO"):
            out = await videotogif(out)
        return out

    return wrapper


async def naive_vstack(file0, file1):
    """
    stacks media assuming files are same width
    """
    mts = await asyncio.gather(mediatype(file0), mediatype(file1))
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        # sometimes can be ffv1 mkvs with 1 frame, which vips has no idea what to do with
        file0, file1 = await asyncio.gather(mediatopng(file0), mediatopng(file1))
        return await processing.common.run_parallel(vips.vipsutils.naive_stack, file0, file1)
    else:
        out = reserve_tempfile("mkv")
        await run_command("ffmpeg", "-i", file0, "-i", file1, "-filter_complex",
                          "[0]format=pix_fmts=rgba[0f];"
                          "[1]format=pix_fmts=rgba[1f];"
                          "[0f][1f]vstack=inputs=2", "-c:v", "ffv1",
                          # "-fs", config.max_temp_file_size,
                          "-fps_mode", "vfr", out)

        if "VIDEO" in mts:
            return out
        else:  # gif and image only
            return await videotogif(out)
        # return await processing.vips.vstack(file0, file1)


async def ensuresize(ctx, file, minsize, maxsize):
    """
    Ensures valid media is between minsize and maxsize in resolution
    :param ctx: discord context
    :param file: media
    :param minsize: minimum width/height in pixels
    :param maxsize: maximum height in pixels
    :return: original or resized media
    """
    resized = False
    if await mediatype(file) not in ["IMAGE", "VIDEO", "GIF"]:
        return file
    w, h = await get_resolution(file)
    owidth = w
    oheight = h
    if w < minsize:
        # the min(-1,maxsize) thing is to prevent a case where someone puts in like a 1x1000 image and it gets resized
        # to 200x200000 which is very large so even though it wont preserve aspect ratio it's an edge case anyways

        file = await resize(file, minsize, f"min(-1, {maxsize * 2})")
        w, h = await get_resolution(file)
        resized = True
    if h < minsize:
        file = await resize(file, f"min(-1, {maxsize * 2})", minsize)
        w, h = await get_resolution(file)
        resized = True
    if await ctx.bot.is_owner(ctx.author):
        logger.debug(f"bot owner is exempt from downsize checks")
        return file
    if w > maxsize:
        file = await resize(file, maxsize, "-1")
        w, h = await get_resolution(file)
        resized = True
    if h > maxsize:
        file = await resize(file, "-1", maxsize)
        w, h = await get_resolution(file)
        resized = True
    if resized:
        logger.info(f"Resized from {owidth}x{oheight} to {w}x{h}")
        await ctx.reply(f"Resized input media from {int(owidth)}x{int(oheight)} to {int(w)}x{int(h)}.", delete_after=5,
                        mention_author=False)
    return file


def nthroot(num: float, n: float):
    return num ** (1 / n)


def expanded_atempo(arg: float):
    """
    expand atempo's limits from [0.5, 100] to (0, infinity) using daisy chaining
    """
    assert arg > 0, "atempo must be greater than 0"
    if 0.5 <= arg <= 100:  # if number already in normal limits
        return f"atempo={arg}"  # return with one atempo
    else:
        # use log to determine minimum number of atempos needed to achieve desired atempo
        numofatempos = math.ceil(math.log(arg, 0.5 if arg < 0.5 else 100))
        # construct one atempo statement
        atempo = f"atempo={nthroot(arg, numofatempos)}"
        # daisy chain them
        return ",".join([atempo for _ in range(numofatempos)])


@gif_output
async def crop(file, w, h, x, y):
    outname = reserve_tempfile("mkv")
    await run_command('ffmpeg', '-i', file, '-filter:v', f'crop={w}:{h}:{x}:{y}', "-c:v", "ffv1", outname)
    return outname


@gif_output
async def trim_top(file, trim_size):
    outname = reserve_tempfile("mkv")
    await run_command('ffmpeg', '-i', file, '-filter:v', f'crop=out_h=ih-{trim_size}:y={trim_size}', "-c:v", "ffv1",
                      "-fps_mode", "vfr",
                      outname)
    return outname


@dual_gif_output
async def naive_overlay(im1, im2):
    mts = [await mediatype(im1), await mediatype(im2)]
    outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-i", im1, "-i", im2, "-filter_complex", "overlay=format=auto", "-c:v", "ffv1", "-fs",
                      config.max_temp_file_size, "-fps_mode", "vfr", outname)
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        outname = await mediatopng(outname)
    return outname


def rgb_to_lightness(r, g, b):
    """
    adapted from colorsys.rgb_to_hls()
    :param r: red from 0-1
    :param g: green from 0-1
    :param b: blue from 0-1
    :return: lightness from 0-1
    """
    maxc = max(r, g, b)
    minc = min(r, g, b)
    return (minc + maxc) / 2.0


async def repeat_shorter_video(video1, video2):
    """
    repeats last frame of the shorter video until the duration of the longer video
    if someone has a better solution https://superuser.com/q/1854904/1001487
    :return: processed media
    """
    im1 = await mediatype(video1) == "IMAGE"
    im2 = await mediatype(video2) == "IMAGE"
    if im1 and im2:
        return video1, video2
    dur1 = 0 if im1 else await get_duration(video1)
    dur2 = 0 if im2 else await get_duration(video2)
    if dur1 > dur2:
        new_vid2 = reserve_tempfile("mkv")
        # the +0.001 is a jank way to force it to round up and it WORKS
        await run_command("ffmpeg", "-i", video2, "-vf", f"tpad=stop_mode=clone:stop_duration={dur1}",
                          "-c:v", "ffv1", "-c:a", "flac", new_vid2)
        return video1, new_vid2
    elif dur2 > dur1:
        new_vid1 = reserve_tempfile("mkv")
        await run_command("ffmpeg", "-i", video1, "-vf", f"tpad=stop_mode=clone:stop_duration={dur2}",
                          "-c:v", "ffv1", "-c:a", "flac", new_vid1)
        return new_vid1, video2
    else:  # == case
        return video1, video2


async def scale2ref(video, reference):
    w, h = await get_resolution(reference)
    return await resize(video, w, h)


@gif_output
async def changefps(file, fps):
    """
    changes FPS of media
    :param file: media
    :param fps: FPS
    :return: processed media
    """
    outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-r", str(fps), "-c:a", "copy", "-c:v", "ffv1",
                      outname)
    return outname


@gif_output
async def trim(file, length, start=0):
    """
    trims media to length seconds
    :param file: media
    :param length: duration to set video to in seconds
    :param start: time in seconds to begin the trimmed video
    :return: processed media
    """
    out = reserve_tempfile("mkv")
    dur = await get_duration(file)
    if start > dur:
        raise NonBugError(f"Trim start ({start}s) is outside the range of the file ({dur}s)")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-t", str(length), "-ss", str(start), "-c:v", "ffv1",
                      "-c:a", "flac", "-fps_mode", "vfr", out)
    return out


@gif_output
async def resize(image, width, height):
    """
    resizes image

    :param image: file
    :param width: new width, thrown directly into ffmpeg so it can be things like -1 or iw/2
    :param height: new height, same as width
    :return: processed media
    """
    out = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-i", image, "-max_muxing_queue_size", "9999", "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp+bitexact",
                      "-vf", f"scale='{width}:{height}',setsar=1:1", "-c:v", "ffv1", "-pix_fmt", "rgba", "-c:a",
                      "copy", "-fps_mode", "vfr", out)
    return out
