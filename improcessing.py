# standard libs
import concurrent.futures
import glob
import json
import math
import shutil
import os
import sys
import asyncio
# pip libs
import typing

import aiohttp
import discord.ext
from PIL import Image, UnidentifiedImageError
from discord.ext import commands

if sys.platform == "win32":  # this hopefully wont cause any problems :>
    from winmagic import magic
else:
    import magic
# project files
from tempfiles import temp_file
import captionfunctions
import humanize
import chromiumrender
import config
import tempfiles
from clogs import logger

"""
This file contains functions for processing and editing media
"""


class NonBugError(Exception):
    """When this is raised instead of a normal Exception, on_command_error() will not attach a traceback or github
    link. """
    pass


class CMDError(Exception):
    """raised by run_command"""
    pass


class ReturnedNothing(Exception):
    """raised by improcess()"""
    pass


def pass_temp_session(fn, args, kwargs, sessionlist):
    """used in Pool to pass the current TempFileSession into the process"""
    tempfiles.globallist = sessionlist
    result = fn(*args, **kwargs)
    tempfiles.globallist = None
    return result


# https://stackoverflow.com/a/65966787/9044183
class Pool:
    def __init__(self, nworkers, initf, initargs=()):
        self._executor = concurrent.futures.ProcessPoolExecutor(nworkers, initializer=initf, initargs=initargs)
        self._nworkers = nworkers
        self._submitted = 0

    async def submit(self, fn, *args, ses=None, **kwargs):
        self._submitted += 1
        if ses is None:
            ses = tempfiles.get_session_list()
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(self._executor, pass_temp_session, fn, args, kwargs, ses)
        try:
            return await fut
        finally:
            self._submitted -= 1

    async def shutdown(self):
        await asyncio.wait([renderpool.submit(chromiumrender.closedriver)] * self._nworkers)
        self._executor.shutdown(wait=True)

    def stats(self):
        queued = max(0, self._submitted - self._nworkers)
        executing = min(self._submitted, self._nworkers)
        return queued, executing


def initializerenderpool():
    """
    Start the worker pool
    :return: the worker pool
    """
    global renderpool
    logger.info(f"Starting {config.chrome_driver_instances} pool processes...")
    # renderpool = multiprocessing.Pool(config.chrome_driver_instances, initializer=chromiumrender.initdriver)
    renderpool = Pool(config.chrome_driver_instances, chromiumrender.initdriver)
    return renderpool


def filetostring(f):
    """
    reads a file to a string
    :param f: file path of file
    :return: contents of file
    """
    with open(f, 'r', encoding="UTF-8") as file:
        data = file.read()
    return data


# https://fredrikaverpil.github.io/2017/06/20/async-and-await-with-subprocesses/
async def run_command(*args):
    """
    run a cli command
    :param args: the args of the command, what would normally be seperated by a space
    :return: the result of the command
    """
    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Status
    logger.log(21, f"PID {process.pid} Started: {args}")

    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()

    # Progress
    if process.returncode == 0:
        logger.debug(f"PID {process.pid} Done.")
        logger.debug(f"Results: {stdout.decode().strip() + stderr.decode().strip()}")
    else:
        logger.error(
            f"PID {process.pid} Failed: {args} result: {stderr.decode().strip()}",
        )
        # adds command output to traceback
        raise CMDError(f"Command {args} failed.") from CMDError(stderr.decode().strip())
    result = stdout.decode().strip() + stderr.decode().strip()
    # Result

    # Return stdout
    return result


# https://askubuntu.com/questions/110264/how-to-find-frames-per-second-of-any-video-file
async def get_frame_rate(filename):
    """
    gets the FPS of a file
    :param filename: filename
    :return: FPS
    """
    logger.info("Getting FPS...")
    out = await run_command("ffprobe", filename, "-v", "0", "-select_streams", "v", "-print_format", "flat",
                            "-show_entries", "stream=r_frame_rate")
    rate = out.split('=')[1].strip()[1:-1].split('/')
    if len(rate) == 1:
        return float(rate[0])
    if len(rate) == 2:
        return float(rate[0]) / float(rate[1])
    return -1


# https://superuser.com/questions/650291/how-to-get-video-duration-in-seconds
async def get_duration(filename):
    """
    gets the duration of a file
    :param filename: filename
    :return: duration
    """
    logger.info("Getting duration...")
    out = await run_command("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", filename)
    if out == "N/A":  # happens with APNGs?
        # https://stackoverflow.com/a/38114903/9044183
        dur2 = await run_command("ffprobe", filename, "-count_frames", "-show_entries",
                                 "stream=nb_read_frames,avg_frame_rate,r_frame_rate", "-print_format", "json", "-v",
                                 "quiet")
        dur2 = json.loads(dur2)
        dur2 = dur2["streams"][0]
        avg_fps = dur2["avg_frame_rate"].split("/")
        if len(avg_fps) == 1:
            avg_fps = float(avg_fps[0])
        elif len(avg_fps) == 2:
            avg_fps = float(avg_fps[0]) / float(avg_fps[1])
        return float(dur2["nb_read_frames"]) / avg_fps

    return float(out)


async def get_resolution(filename):
    """
    gets the resolution of a file
    :param filename: filename
    :return: [width, height]
    """
    out = await run_command("ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
                            filename)
    out = out.split("x")
    return [float(out[0]), float(out[1])]


async def ffmpegsplit(media):
    """
    splits the input file into frames
    :param media: file
    :return: [list of files, ffmpeg key to find files]
    """
    logger.info("Splitting frames...")
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-vsync", "1", f"{media.split('.')[0]}_%09d.png")
    files = glob.glob(f"{media.split('.')[0]}_*.png")
    tempfiles.reserve_names(files)

    return files, f"{media.split('.')[0]}_%09d.png"


async def splitaudio(video):
    """
    splits audio from a file
    :param video: file
    :return: filename of audio (aac) if file has audio, False if it doesn't
    """
    ifaudio = await run_command("ffprobe", "-i", video, "-show_streams", "-select_streams", "a", "-loglevel", "error")
    if ifaudio:
        logger.info("Splitting audio...")
        name = temp_file("aac")
        await run_command("ffmpeg", "-hide_banner", "-i", video, "-vn", "-acodec", "aac", name)
        return name
    else:
        logger.info("No audio detected.")
        return False


async def forceaudio(video):
    """
    gives videos with no audio a silent audio stream
    :param video: file
    :return: video filename
    """
    ifaudio = await run_command("ffprobe", "-i", video, "-show_streams", "-select_streams", "a", "-loglevel", "error")
    if ifaudio:
        return video
    else:
        outname = temp_file("mp4")
        await run_command("ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "anullsrc", "-i", video, "-c:v", "png",
                          "-c:a", "aac",
                          "-map", "0:a", "-map", "1:v", "-shortest", outname)
        return outname


async def compresspng(png):
    """
    compress a png file with pngquant
    :param png: file
    :return: filename of compressed png
    """

    outname = temp_file("png")
    await run_command("pngquant", "--quality=0-80", "--output", outname, png)
    return outname


async def assurefilesize(media: str, ctx: discord.ext.commands.Context):
    """
    downsizes files up to 5 times if they are over discord's upload limit
    :param media: media
    :param ctx: discord context
    :return: filename of fixed media if it works, False if it still is too big.
    """
    if not media:
        raise ReturnedNothing(f"assurefilesize() was passed no media.")
    mt = mediatype(media)
    if mt == "VIDEO":
        # this is in assurefilesize since all output media gets sent through here
        # it removes transparency if its a actual video and not a gif, since like nothing can play transparent videos
        media = await reencode(media)
    for i in range(5):
        size = os.path.getsize(media)
        logger.info(f"Resulting file is {humanize.naturalsize(size)}")
        if size > config.way_too_big_size:
            await ctx.send(f"{config.emojis['warning']} Resulting file is {humanize.naturalsize(size)}. "
                           f"File is way too big.")
            return
        # https://www.reddit.com/r/discordapp/comments/aflp3p/the_truth_about_discord_file_upload_limits/
        if size >= config.file_upload_limit:
            if mt in ["VIDEO", "IMAGE", "GIF"]:
                logger.info("Image too big!")
                msg = await ctx.reply(
                    f"{config.emojis['warning']} Resulting file too big! ({humanize.naturalsize(size)}) "
                    f"Downsizing result...")
                imagenew = await resize(media, "iw/2", "ih/2")
                # imagenew = await handleanimated(media, captionfunctions.halfsize, ctx)
                media = imagenew
                await msg.delete()
            else:
                await ctx.send(f"{config.emojis['warning']} Audio file is too big to upload.")
                return False
        if os.path.getsize(media) < config.file_upload_limit:
            return media
    await ctx.send(f"{config.emojis['warning']} Max downsizes reached. File is way too big.")
    return False


async def watermark(media):
    if mediatype(media) == "AUDIO":  # exiftool doesnt support it :/
        try:
            t = temp_file("mp3")
            await run_command("ffmpeg", "-i", media, "-c", "copy", "-metadata", "artist=MediaForge", t)
            shutil.copy2(t, media)
            os.remove(t)
        except CMDError:
            logger.warning(f"ffmpeg audio watermarking of {media} failed")
    else:
        try:
            await run_command("exiftool", "-overwrite_original", "-artist=MediaForge", media)
        except CMDError:
            logger.warning(f"exiftool watermarking of {media} failed")


def mediatype(image):
    """
    Gets basic type of media
    :param image: filename of media
    :return: can be VIDEO, AUDIO, GIF, IMAGE or None (invalid or other).
    """
    if image.endswith(".m4a"):
        return "AUDIO"  # idfk
    mime = magic.from_file(image, mime=True)
    if mime.startswith("video"):
        return "VIDEO"
    elif mime.startswith("audio"):
        return "AUDIO"
    elif mime.startswith("image"):
        try:
            with Image.open(image) as im:
                anim = getattr(im, "is_animated", False)
            if anim:
                return "GIF"  # gifs dont have to be animated but if they aren't its easier to treat them like pngs
            else:
                return "IMAGE"
        except UnidentifiedImageError:
            return None
    return None


async def run_in_exec(func, *args, **kwargs):
    """
    prevents intense non-async functions from blocking event loop
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


async def ensureduration(media, ctx: typing.Union[commands.Context, None]):
    """
    ensures that media is under or equal to the config minimum frame count
    :param media: media to trim
    :param ctx: discord context
    :return: processed media or original media, within config.max_frames
    """
    # the function that splits frames actually has a vsync thing so this is more accurate to what's generated
    fps = await get_frame_rate(media)
    dur = await get_duration(media)
    frames = int(fps * dur)
    if frames < config.max_frames:
        return media
    else:
        newdur = config.max_frames / fps
        if ctx is not None:
            tmsg = f"{config.emojis['warning']} input file is too long (~{frames} frames)! Trimming to {round(newdur, 1)}" \
                   f"s (~{config.max_frames} frames)... "
            msg = await ctx.reply(tmsg)
        media = await trim(media, newdur)
        if ctx is not None:
            await msg.edit(content=tmsg + " Done!", delete_after=5)
        return media


# async def forcesize(files):
#     # this code is bugged, it shuffles frames around...
#     logger.info("Forcing all frames to same size...")
#     res = await get_resolution(files[0])
#     out = []
#     jobs = []
#     for f in files:
#         n = temp_file("png")
#         out.append(n)
#         # captionfunctions.resize(f, res, n)
#         jobs.append(renderpool.submit(captionfunctions.resize, f, res, n))
#     await asyncio.wait(jobs)
#     return out


async def handleanimated(media: str, capfunction: callable, ctx, *caption):
    """
    handles processing functions that only work in singular frames and applies to videos/gifs
    :param media: image, video, or gif
    :param capfunction: function to process media with
    :param ctx: discord context
    :param caption: other params (usually caption)
    :return: processed media
    """
    imty = mediatype(media)
    logger.info(f"Detected type {imty}.")
    if imty is None:
        raise Exception(f"File {media} is invalid!")
    elif imty == "IMAGE":
        logger.info(f"Processing frame...")
        # media = minimagesize(media, 200)
        result = await renderpool.submit(capfunction, media, caption)
        # capped = await run_in_exec(result.get)
        return await compresspng(result)
    elif imty == "VIDEO" or imty == "GIF":
        media = await ensureduration(media, ctx)
        frames, name = await ffmpegsplit(media)
        audio = await splitaudio(media)
        fps = await get_frame_rate(media)
        # logger.info(
        #     f"Processing {len(frames)} frames with {min(len(frames), POOLWORKERS)} processes...")

        logger.info(f"Processing {len(frames)} frames...")
        framefuncs = []

        ses = tempfiles.get_session_list()
        for i, frame in enumerate(frames):
            framefuncs.append(renderpool.submit(capfunction, frame, caption, frame.replace('.png', '_rendered.png'),
                                                ses=ses))
        await asyncio.wait(framefuncs)
        tempfiles.reserve_names(glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*')))
        # result = renderpool.starmap_async(capfunction, capargs)
        # await run_in_exec(result.get)
        # result = await renderpool.
        logger.info(f"Joining {len(frames)} frames...")
        # frames = await forcesize(glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*')))

        if imty == "GIF":
            frames = glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*'))
            outname = temp_file("gif")
            await run_command("gifski", "--quiet", "--fast", "-o", outname, "--fps", str(fps), "--width", "1000",
                              *frames)
        else:  # imty == "VIDEO":
            outname = temp_file("mp4")
            frames = name.replace('.png', '_rendered.png')
            if audio:
                await run_command("ffmpeg", "-hide_banner", "-r", str(fps), "-i", frames,
                                  "-i", audio, "-c:a", "aac", "-shortest",
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
            else:
                await run_command("ffmpeg", "-hide_banner", "-r", str(fps), "-i", frames,
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
        # cleanup
        # logger.info("Cleaning files...")
        # for f in glob.glob(name.replace('%09d', '*')):
        #     try:
        #         os.remove(f)
        #     except FileNotFoundError:
        #         pass
        # for f in glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*')):
        #     try:
        #         os.remove(f)
        #     except FileNotFoundError:
        #         pass
        return outname


async def mp4togif(mp4):
    """
    converts mp4 to gif
    :param mp4: mp4
    :return: gif
    """
    mime = magic.Magic(mime=True)
    filename = mime.from_file(mp4)
    if filename.find('video') == -1:
        return False
    frames, name = await ffmpegsplit(mp4)
    fps = await get_frame_rate(mp4)
    outname = temp_file("gif")
    n = glob.glob(name.replace('%09d', '*'))
    if len(n) <= 1:
        raise NonBugError(f"Output file only has {len(n)} frames, GIFs must have at least 2.")
    else:
        await run_command("gifski", "--quiet", "--fast", "-o", outname, "--fps", str(fps), *n)
        # logger.info("Cleaning files...")
        # for f in glob.glob(name.replace('%09d', '*')):
        #     os.remove(f)
        return outname


async def reencode(mp4):  # reencodes mp4 as libx264 since the png format used cant be played by like literally anything
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", mp4, "-c:v", "libx264", "-c:a", "copy", "-pix_fmt", "yuv420p",
                      "-max_muxing_queue_size", "9999",
                      "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", outname)
    return outname


async def giftomp4(gif):
    """
    converts gif to mp4
    :param gif: gif
    :return: mp4
    """
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", gif, "-movflags", "faststart", "-pix_fmt", "yuv420p",
                      "-sws_flags", "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf",
                      "scale=trunc(iw/2)*2:trunc(ih/2)*2", outname)

    return outname


async def toaudio(media):
    """
    converts video to only audio
    :param media: video or audio ig
    :return: aac
    """
    name = temp_file("mp3")  # discord wont embed aac
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-vn", name)
    return name


async def mediatopng(media):
    """
    converts media to png
    :param media: media
    :return: png
    """
    outname = temp_file("png")
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-frames:v", "1", outname)

    return outname


async def ffprobe(file):
    return [await run_command("ffprobe", "-hide_banner", file), magic.from_file(file, mime=False),
            magic.from_file(file, mime=True)]


# https://stackoverflow.com/questions/65728616/how-to-get-ffmpeg-to-consistently-apply-speed-effect-to-first-few-frames
async def speed(file, sp):
    """
    changes speed of media
    :param file: media
    :param sp: speed to multiply media by
    :return: processed media
    """
    # TODO: some weird bug here caused by 100fps gifski gifs that slows down gifs?
    outname = temp_file("mp4")
    mt = mediatype(file)
    fps = await get_frame_rate(file)
    duration = await get_duration(file)
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-filter_complex",
                      f"[0:v]setpts=PTS/{sp},fps={fps}[v];[0:a]atempo={sp}[a]",
                      "-map", "[v]", "-map", "[a]", "-t", str(duration / float(sp)), "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def reverse(file):
    """
    reverses media (-1x speed)
    :param file: media
    :return: procesed media
    """
    mt = mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-vf", "reverse", "-af", "areverse",
                      "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def quality(file, crf, qa):
    """
    changes quality of videos/gifs with ffmpeg compression
    :param file: media
    :param crf: FFmpeg CRF param
    :param qa: audio bitrate
    :return: processed media
    """
    mt = mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-crf", str(crf), "-c:a", "aac", "-ar",
                      str(qa), outname)
    # png cannot be supported here because crf and qa are libx264 params lmao
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def changefps(file, fps):
    """
    changes FPS of media
    :param file: media
    :param fps: FPS
    :return: processed media
    """
    mt = mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter:v", f"fps=fps={fps}", "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def pad(file):
    """
    pads media into a square shape
    :param file: media
    :return: processed media
    """
    mt = mediatype(file)
    if mt == "IMAGE":
        outname = temp_file("png")
    else:
        outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf",
                      "pad=width='max(iw,ih)':height='max(iw,ih)':x='(ih-iw)/2':y='(iw-ih)/2':color=white", "-c:v",
                      "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def gifloop(file, loop):
    """
    loops a gif
    :param file: gif
    :param loop: # of times to loop
    :return: processed media
    """
    outname = temp_file("gif")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-loop", str(loop), "-vcodec", "copy", outname)
    return outname


async def videoloop(file, loop):
    """
    loops a gif
    :param file: gif
    :param loop: # of times to loop
    :return: processed media
    """
    mt = mediatype(file)
    exts = {
        "VIDEO": "mp4",
        "GIF": "gif"
    }
    outname = temp_file(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-stream_loop", str(loop), "-i", file, "-vcodec", "copy", outname)
    return outname


async def imageaudio(files):
    """
    combines an image an an audio file into a video
    :param files: [image, audio]
    :return: video
    """
    audio = files[1]
    image = files[0]
    outname = temp_file("mp4")
    duration = await get_duration(audio)  # it is a couple seconds too long without it :(
    await run_command("ffmpeg", "-hide_banner", "-i", audio, "-loop", "1", "-i", image, "-vf",
                      "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-c:a", "aac", "-shortest", "-t",
                      str(duration), outname)
    return outname


async def addaudio(files):
    """
    adds audio to media
    :param files: [media, audiotoadd]
    :return: video or audio
    """
    # TODO: this can trim media short? not sure why...
    audio = files[1]
    media = files[0]
    mt = mediatype(media)
    if mt == "IMAGE":
        # no use reinventing the wheel
        return await imageaudio(files)
    else:
        media = await forceaudio(media)
        if mt == "AUDIO":
            outname = temp_file("mp3")
        else:
            outname = temp_file("mp4")
        await run_command("ffmpeg", "-i", media, "-i", audio, "-filter_complex",
                          "[0:a][1:a]amix=inputs=2:dropout_transition=100000:duration=longest[a];[a]volume=2[a]",
                          "-map", "0:v?", "-map", "[a]", "-c:a", "aac", outname)
        return outname


async def concatv(files):
    """
    concatenates 2 videos
    :param files: [video, video]
    :return: combined video
    """
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "png", "-c:a", "aac", "-ar", "48000",
                      "-max_muxing_queue_size", "4096", fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")

    # https://superuser.com/a/1136305/1001487
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf",
                      f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:-2:-2:color=black", "-c:v",
                      "png", "-c:a", "aac", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    concatdemuxer = temp_file("txt")
    with open(concatdemuxer, "w+") as f:
        f.write(f"file '{fixedvideo0}'\nfile '{fixedfixedvideo1}'".replace(config.temp_dir, ""))
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-f", "concat", "-i", concatdemuxer, "-c:v", "png", "-c:a", "aac",
                      outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1, concatdemuxer]:
    #     os.remove(file)
    return outname


async def stack(files, style):
    """
    stacks media
    :param files: [media, media]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
    mts = [mediatype(files[0]), mediatype(files[1])]
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":  # easier to just make this an edge case
        return await imagestack(files, style)
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "png", "-c:a", "aac", "-ar", "48000",
                      "-max_muxing_queue_size", "4096", fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")
    if style == "hstack":
        scale = f"scale=-2:{h}"
    else:
        scale = f"scale={w}:-2"
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf", scale, "-c:v",
                      "png", "-c:a", "aac", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", fixedvideo0, "-i", fixedfixedvideo1, "-filter_complex",
                      f"{'h' if style == 'hstack' else 'v'}stack=inputs=2;amix=inputs=2:dropout_transition=0", "-c:v",
                      "png", "-c:a",
                      "aac", outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    if mts[0] != "VIDEO" and mts[1] != "VIDEO":  # one or more gifs and no videos
        outname = await mp4togif(outname)
    return outname


async def overlay(files, opacity: float):
    """
    stacks media
    :param files: [media, media]
    :param opacity: opacity of top media, 0-1
    :return: processed media
    """
    assert 0 <= opacity <= 1
    mts = [mediatype(files[0]), mediatype(files[1])]
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "png", "-c:a", "aac", "-ar", "48000",
                      "-max_muxing_queue_size", "4096", fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")
    scale = f"scale={w}:{h}"
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf", scale, "-c:v",
                      "png", "-c:a", "aac", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", fixedvideo0, "-i", fixedfixedvideo1, "-filter_complex",
                      f"[1:v]geq=r='r(X,Y)':a='{opacity}*alpha(X,Y)'[1v];"
                      f"[0:v][1v]overlay;amix=inputs=2:dropout_transition=0", "-c:v",
                      "png", "-c:a",
                      "aac", outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        outname = await mediatopng(outname)
    # one or more gifs and no videos
    elif mts[0] != "VIDEO" and mts[1] != "VIDEO":
        outname = await mp4togif(outname)
    return outname


# https://stackoverflow.com/a/30228789/9044183
async def imagestack(files, style):
    """
    stack() calls this function since ffmpeg can be weird about pngs
    :param files: [image,image]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
    image0 = Image.open(files[0]).convert("RGBA")
    image1 = Image.open(files[1]).convert("RGBA")
    if style == "vstack":
        width = image0.size[0]
        ratio1 = image1.size[1] / image1.size[0]
        height1 = width * ratio1
        image1 = image1.resize((int(width), int(height1)), resample=Image.BICUBIC)
        outimg = Image.new("RGBA", (width, image0.size[1] + image1.size[1]))
        outimg.alpha_composite(image0)
        outimg.alpha_composite(image1, (0, image0.size[1]))
    else:
        height = image0.size[1]
        ratio1 = image1.size[0] / image1.size[1]
        width1 = height * ratio1
        image1 = image1.resize((int(width1), int(height)), resample=Image.BICUBIC)
        outimg = Image.new("RGBA", (image0.size[0] + image1.size[0], height))
        outimg.alpha_composite(image0)
        outimg.alpha_composite(image1, (image0.size[0], 0))
    outname = temp_file("png")
    outimg.save(outname)
    outname = await compresspng(outname)
    return outname


async def freezemotivate(files, *caption):
    """
    ends video with motivate caption
    :param files: media
    :param caption: caption to pass to motivate()
    :return: processed media
    """
    if isinstance(files, list):  # audio specified
        video = files[0]
        audio = files[1]
    else:  # just default to song lol!
        video = files
        audio = "rendering/what.mp3"
    framecount = await run_command('ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                                   'stream=nb_read_frames', '-of', 'default=nokey=1:noprint_wrappers=1', video)
    framecount = int(framecount)
    lastframe = temp_file("png")
    await run_command("ffmpeg", "-hide_banner", "-i", video, "-vf", f"select='eq(n,{framecount - 1})'", "-vframes", "1",
                      lastframe)
    clastframe = await handleanimated(lastframe, captionfunctions.motivate, None, *caption)
    freezeframe = await imageaudio([clastframe, audio])
    final = await concatv([video, freezeframe])
    return final


async def trim(file, length, start=0):
    """
    trims media to length seconds
    :param file: media
    :param length: duration to set video to in seconds
    :param start: time in seconds to begin the trimmed video
    :return: processed media
    """
    mt = mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4",
        "GIF": "mp4"
    }
    dur = await get_duration(file)
    if start > dur:
        raise NonBugError(f"Trim start ({start}s) is outside the range of the file ({dur}s)")
    out = temp_file(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-t", str(length), "-ss", str(start), "-c:v", "png", out)
    if mt == "GIF":
        out = await mp4togif(out)
    return out


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
    if mediatype(file) not in ["IMAGE", "VIDEO", "GIF"]:
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


async def rotate(file, rottype):
    types = {  # command input to ffmpeg vf
        "90": "transpose=1",
        "90ccw": "transpose=2,",
        "180": "vflip,hflip",
        "vflip": "vflip",
        "hflip": "hflip"
    }
    mt = mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    out = temp_file(exts[mt])
    await run_command("ffmpeg", "-i", file, "-vf", types[rottype] + ",format=yuva420p", "-c:v", "png", out)
    if mt == "GIF":
        out = await mp4togif(out)
    return out


async def volume(file, vol):
    mt = mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4"
    }
    out = temp_file(exts[mt])
    # convert vol % to db
    # http://www.sengpielaudio.com/calculator-loudness.htm
    if vol > 0:
        vol = 10 * math.log(vol, 2)
        # for some reason aac has audio caps but libmp3lame works fine lol
        await run_command("ffmpeg", "-i", file, "-af", f"volume={vol}dB", "-strict", "-1", "-c:a", "libmp3lame", out)
    else:
        await run_command("ffmpeg", "-i", file, "-af", f"volume=0", "-strict", "-1", "-c:a", "libmp3lame", out)

    return out


async def vibrato(file, frequency=5, depth=0.5):  # https://ffmpeg.org/ffmpeg-filters.html#tremolo
    mt = mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4"
    }
    out = temp_file(exts[mt])
    await run_command("ffmpeg", "-i", file, "-af", f"vibrato=f={frequency}:d={depth}", "-strict", "-1", "-c:a", "aac",
                      out)
    return out


async def resize(image, width, height):
    """
    resizes image

    :param image: file
    :param width: new width, thrown directly into ffmpeg so it can be things like -1 or iw/2
    :param height: new height, same as width
    :return: processed media
    """
    mt = mediatype(image)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    out = temp_file(exts[mt])
    if mt in ["VIDEO", "GIF"]:
        image = await ensureduration(image, None)
    await run_command("ffmpeg", "-i", image, "-pix_fmt", "yuva444p", "-max_muxing_queue_size", "9999", "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp+bitexact",
                      "-vf", f"scale='{width}:{height}',setsar=1:1", "-c:v", "png", "-pix_fmt", "yuva444p", out)

    if mt == "GIF":
        out = await mp4togif(out)
    elif mt == "VIDEO":
        out = await reencode(out)
    return out


async def checkwatermark(file):
    # see watermark()
    etdata = await run_command("exiftool", "-artist", "-json", file)
    logger.info(etdata)
    etdata = json.loads(etdata)[0]
    if "Artist" in etdata:
        if etdata["Artist"] == "MediaForge":
            return True
    return False


async def count_emoji(guild: discord.Guild):
    anim = 0
    static = 0
    for emoji in guild.emojis:
        if emoji.animated:
            anim += 1
        else:
            static += 1
    return {"animated": anim, "static": static}


async def add_emoji(file, guild: discord.Guild, name):
    """
    adds emoji to guild
    :param file: emoji to add
    :param guild: guild to add it to
    :param name: emoji name
    :return:
    """
    with open(file, "rb") as f:
        data = f.read()
    try:
        emoji = await guild.create_custom_emoji(name=name, image=data, reason="$addemoji command")
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to create an emoji. Make sure I have the Manage Emojis " \
               f"permission. "
    except discord.HTTPException as e:
        return f"{config.emojis['2exclamation']} Something went wrong trying to add your emoji! ```{e}```"
    else:
        count = await count_emoji(guild)
        if emoji.animated:
            return f"{config.emojis['check']} Animated emoji successfully added: " \
                   f"{emoji}\n{guild.emoji_limit - count['animated']} slots are left."
        else:
            return f"{config.emojis['check']} Emoji successfully added: " \
                   f"{emoji}\n{guild.emoji_limit - count['static']} slots are left."


async def set_banner(file, guild: discord.Guild):
    """
    sets guild banner
    :param file: banner file
    :param guild: guild to add it to
    :return:
    """
    with open(file, "rb") as f:
        data = f.read()
    try:
        await guild.edit(banner=bytes(data))
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to set your banner. Make sure I have the Manage Server " \
               f"permission. "
    except discord.HTTPException as e:
        return f"{config.emojis['2exclamation']} Something went wrong trying to set your banner! ```{e}```"
    else:
        return f"{config.emojis['check']} Successfully changed guild banner."


async def set_icon(file, guild: discord.Guild):
    """
    sets guild icon
    :param file: icon file
    :param guild: guild to add it to
    :return:
    """
    if mediatype(file) == "GIF" and "ANIMATEd_ICON" not in guild.features:
        return f"{config.emojis['x']} This guild does not support animated icons."
    with open(file, "rb") as f:
        data = f.read()
    try:
        await guild.edit(icon=bytes(data))
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to set your icon. Make sure I have the Manage Server " \
               f"permission. "
    except discord.HTTPException as e:
        return f"{config.emojis['2exclamation']} Something went wrong trying to set your icon! ```{e}```"
    else:
        return "Successfully changed guild icon."


async def contentlength(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        # i used to make a head request to check size first, but for some reason head requests can be super slow
        async with session.get(url) as resp:
            if resp.status == 200:
                if "Content-Length" not in resp.headers:  # size of file to download
                    return False
                else:
                    return int(resp.headers["Content-Length"])


async def iconfromsnowflakeid(snowflake: int, bot, ctx):
    try:
        user = await bot.fetch_user(snowflake)
        return str(user.avatar_url)
    except (discord.NotFound, discord.Forbidden):
        pass
    try:
        guild = await bot.fetch_guild(snowflake)
        return str(guild.icon_url)
    except (discord.NotFound, discord.Forbidden):
        pass
    try:  # get the icon through a message author to support webhook/pk icons
        msg = await ctx.channel.fetch_message(snowflake)
        return str(msg.author.avatar_url)
    except (discord.NotFound, discord.Forbidden):
        pass
    return None
