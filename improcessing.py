import asyncio
import functools
import glob
import logging
import multiprocessing
import os
import random
import string
import sys
from multiprocessing import Pool
import discord.ext
import numpy as np
from PIL import Image, UnidentifiedImageError
import captionfunctions
import humanize
import chromiumrender

if sys.platform == "win32":  # this hopefully wont cause any problems :>
    from winmagic import magic
else:
    import magic

MAXFRAMES = 1024  # to prevent gigantic mp4s from clogging stuff


# renderpool = None


def initializerenderpool():
    global renderpool
    poolprocesses = 20
    logging.info(f"Starting {poolprocesses} pool processes...")
    renderpool = multiprocessing.Pool(poolprocesses, initializer=chromiumrender.initdriver)
    return renderpool


def filetostring(f):
    with open(f, 'r', encoding="UTF-8") as file:
        data = file.read()
    return data


def get_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))


def temp_file(extension="png"):
    while True:
        name = f"temp/{get_random_string(8)}.{extension}"
        if not os.path.exists(name):
            return name


# https://fredrikaverpil.github.io/2017/06/20/async-and-await-with-subprocesses/
async def run_command(*args):
    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Status
    logging.log(21, f"PID {process.pid} Started: {args}")

    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()

    # Progress
    if process.returncode == 0:
        logging.debug(f"PID {process.pid} Done.")
        logging.debug(f"Results: {stdout.decode().strip() + stderr.decode().strip()}")
    else:
        logging.error(
            f"PID {process.pid} Failed: {args} result: {stderr.decode().strip()}",
        )
        # adds command output to traceback
        raise Exception(f"Command {args} failed.") from Exception(stderr.decode().strip())
    result = stdout.decode().strip() + stderr.decode().strip()
    # Result

    # Return stdout
    return result


# https://askubuntu.com/questions/110264/how-to-find-frames-per-second-of-any-video-file
async def get_frame_rate(filename):
    logging.info("Getting FPS...")
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
    logging.info("Getting duration...")
    out = await run_command("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", filename)
    return float(out)


async def get_resolution(filename):
    out = await run_command("ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
                            filename)
    return out.split("x")


async def ffmpegsplit(image):
    logging.info("Splitting frames...")
    await run_command("ffmpeg", "-hide_banner", "-i", image, "-vsync", "1", "-vf", "scale='max(200,iw)':-1",
                      f"{image.split('.')[0]}%09d.png")
    files = glob.glob(f"{image.split('.')[0]}*.png")

    return files, f"{image.split('.')[0]}%09d.png"


async def splitaudio(video):
    ifaudio = await run_command("ffprobe", "-i", video, "-show_streams", "-select_streams", "a", "-loglevel", "error")
    if ifaudio:
        logging.info("Splitting audio...")
        name = temp_file("aac")
        await run_command("ffmpeg", "-hide_banner", "-i", video, "-vn", "-acodec", "copy", name)
        return name
    else:
        logging.info("No audio detected.")
        return False


async def forceaudio(video):
    ifaudio = await run_command("ffprobe", "-i", video, "-show_streams", "-select_streams", "a", "-loglevel", "error")
    if ifaudio:
        return video
    else:
        outname = temp_file("mp4")
        await run_command("ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "anullsrc", "-i", video, "-c:v", "libx264",
                          "-c:a", "aac",
                          "-map", "0:a", "-map", "1:v", "-shortest", outname)
        os.remove(video)
        return outname


async def compresspng(png):
    outname = temp_file("png")
    await run_command("pngquant", "--quality=0-80", "--o", outname, png)
    os.remove(png)
    return outname


async def assurefilesize(image: str, ctx: discord.ext.commands.Context):
    for i in range(5):
        size = os.path.getsize(image)
        logging.info(f"Resulting file is {humanize.naturalsize(size)}")
        # https://www.reddit.com/r/discordapp/comments/aflp3p/the_truth_about_discord_file_upload_limits/
        if size >= 8388119:
            logging.info("Image too big!")
            msg = await ctx.send(f"⚠ Resulting file too big! ({humanize.naturalsize(size)}) Downsizing result...")
            imagenew = await handleanimated(image, captionfunctions.halfsize, ctx)
            os.remove(image)
            image = imagenew
            await msg.delete()
        if os.path.getsize(image) < 8388119:
            return image
    await ctx.send(f"⚠ Max downsizes reached. File is way too big.")
    return False


def minimagesize(image, minsize):
    im = Image.open(image)
    if im.size[0] < minsize:
        logging.info(f"Image is {im.size}, Upscaling image...")
        im = im.resize((minsize, round(im.size[1] * (minsize / im.size[0]))), Image.BICUBIC)
        name = temp_file("png")
        im.save(name)
        return name
    else:
        return image


def mediatype(image):
    """
    Gets basic type of media
    :param image: filename of media
    :return: can be VIDEO, AUDIO, GIF, IMAGE or None.
    """
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


def run_in_executor(f):  # wrapper to prevent intense non-async functions from blocking event loop
    @functools.wraps(f)
    def inner(*args, **kwargs):
        loop = asyncio.get_running_loop()
        return loop.run_in_executor(None, lambda: f(*args, **kwargs))

    return inner


@run_in_executor
def unblockpool(workers, *args, initializer=None):
    if initializer is None:
        pool = Pool(workers)
    else:
        pool = Pool(workers, initializer=initializer)
    pool.starmap_async(*args)
    pool.close()
    pool.join()


@run_in_executor
def run_in_exec(func, *args, **kwargs):
    return func(*args, **kwargs)


async def handleanimated(image: str, capfunction: callable, ctx, *caption,
                         webengine=False):
    imty = mediatype(image)
    logging.info(f"Detected type {imty}.")
    if imty is None:
        raise Exception(f"File {image} is invalid!")
    elif imty == "IMAGE":
        logging.info(f"Processing frame...")
        image = minimagesize(image, 200)
        result = renderpool.apply_async(capfunction, (image, caption))
        capped = await run_in_exec(result.get)
        return await compresspng(capped)
    elif imty == "VIDEO" or imty == "GIF":
        frames, name = await ffmpegsplit(image)
        audio = await splitaudio(image)
        fps = await get_frame_rate(image)
        # logging.info(
        #     f"Processing {len(frames)} frames with {min(len(frames), POOLWORKERS)} processes...")
        if len(frames) > MAXFRAMES:
            await ctx.reply(f"⚠ Input file has {len(frames)} frames, maximum allowed is {MAXFRAMES}.")
            logging.warning(f"⚠ Input file has {len(frames)} frames, maximum allowed is {MAXFRAMES}.")
            return
        logging.info(f"Processing {len(frames)} frames...")
        capargs = []
        for i, frame in enumerate(frames):
            capargs.append((frame, caption, frame.replace('.png', '_rendered.png')))
        # to keep from blocking discord loop
        # if webengine:  # not every caption command requires the webengine
        #     await unblockpool(min(len(frames), 8), capfunction,
        #                       capargs, initializer=chromiumrender.initdriver)
        # else:
        #     await unblockpool(min(len(frames), 16), capfunction, capargs)

        # for frame in capargs:
        #     async with renderlock:
        #         await run_in_exec(capfunction, *frame)
        result = renderpool.starmap_async(capfunction, capargs)
        await run_in_exec(result.get)
        logging.info(f"Joining {len(frames)} frames...")
        if imty == "GIF":
            outname = temp_file("gif")
            await run_command(
                "gifski", "--quiet", "--fast", "-o", outname, "--fps", str(fps), "--width", "1000",
                name.replace('.png', '_rendered.png').replace('%09d', '*'))
        else:  # imty == "VIDEO":
            outname = temp_file("mp4")
            if audio:
                await run_command("ffmpeg", "-hide_banner", "-r", str(fps), "-start_number", "1", "-i",
                                  name.replace('.png', '_rendered.png'),
                                  "-i", audio, "-c:a", "aac", "-shortest",
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
                os.remove(audio)
            else:
                await run_command("ffmpeg", "-hide_banner", "-r", str(fps), "-start_number", "1", "-i",
                                  name.replace('.png', '_rendered.png'),
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
        # cleanup
        logging.info("Cleaning files...")
        for f in glob.glob(name.replace('%09d', '*')):
            os.remove(f)

        return outname


async def mp4togif(mp4):
    mime = magic.Magic(mime=True)
    filename = mime.from_file(mp4)
    if filename.find('video') == -1:
        return False
    frames, name = await ffmpegsplit(mp4)
    fps = await get_frame_rate(mp4)
    outname = temp_file("gif")
    await run_command("gifski", "--quiet", "--fast", "-o", outname, "--fps", str(fps), name.replace('%09d', '*'))
    logging.info("Cleaning files...")
    for f in glob.glob(name.replace('%09d', '*')):
        os.remove(f)
    return outname


async def giftomp4(gif):
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", gif, "-movflags", "faststart", "-pix_fmt", "yuv420p", "-vf",
                      "scale=trunc(iw/2)*2:trunc(ih/2)*2", outname)

    return outname


async def mediatopng(media):
    outname = temp_file("png")
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-frames:v", "1", outname)

    return outname


async def ffprobe(file):
    return [await run_command("ffprobe", "-hide_banner", file), magic.from_file(file, mime=False),
            magic.from_file(file, mime=True)]


# https://stackoverflow.com/questions/65728616/how-to-get-ffmpeg-to-consistently-apply-speed-effect-to-first-few-frames
# TODO: some way to preserve gif transparency?
async def speed(file, sp):
    outname = temp_file("mp4")
    mt = mediatype(file)
    fps = await get_frame_rate(file)
    duration = await get_duration(file)
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-filter_complex",
                      f"[0:v]setpts=PTS/{sp},fps={fps}[v];[0:a]atempo={sp}[a]",
                      "-map", "[v]", "-map", "[a]", "-t", str(duration / float(sp)), outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def reverse(file):
    mt = mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-vf", "reverse", "-af", "areverse",
                      outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def quality(file, crf, qa):
    mt = mediatype(file)
    outname = temp_file("mp4")
    ifaudio = await run_command("ffprobe", "-i", file, "-show_streams", "-select_streams", "a", "-loglevel", "error")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-crf", str(crf), "-c:a", "aac", "-ar",
                      str(qa), outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def changefps(file, fps):
    mt = mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter:v", f"fps=fps={fps}", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def pad(file):
    mt = mediatype(file)
    if mt == "IMAGE":
        outname = temp_file("png")
    else:
        outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf",
                      "pad=width='max(iw,ih)':height='max(iw,ih)':x='(ih-iw)/2':y='(iw-ih)/2':color=white", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def imageaudio(files):
    audio = files[1]
    image = files[0]
    outname = temp_file("mp4")
    duration = await get_duration(audio)  # it is a couple seconds too long without it :(
    await run_command("ffmpeg", "-hide_banner", "-i", audio, "-loop", "1", "-i", image, "-c:v", "libx264",
                      "-c:a", "aac", "-shortest", "-t", str(duration), outname)
    return outname


async def concatv(files):
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "libx264", "-c:a", "aac", "-ar", "48000",
                      fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")

    # https://superuser.com/a/1136305/1001487
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-vf",
                      f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:-2:-2:color=black", "-c:v",
                      "libx264", "-c:a", "aac", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    concatdemuxer = temp_file("txt")
    with open(concatdemuxer, "w+") as f:
        f.write(f"file '{fixedvideo0}'\nfile '{fixedfixedvideo1}'".replace("temp/", ""))
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-f", "concat", "-i", concatdemuxer, "-c:v", "libx264", "-c:a", "aac",
                      outname)
    for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1, concatdemuxer]:
        os.remove(file)
    return outname


async def stack(files, style):
    if mediatype(files[0]) == "IMAGE" and mediatype(files[1]) == "IMAGE":  # easier to just make this an edge case
        return await imagestack(files, style)
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "libx264", "-c:a", "aac", "-ar", "48000",
                      fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")
    if style == "hstack":
        scale = f"scale=-2:{h}"
    else:
        scale = f"scale={w}:-2"
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-vf", scale, "-c:v",
                      "libx264", "-c:a", "aac", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", fixedvideo0, "-i", fixedfixedvideo1, "-filter_complex",
                      f"{'h' if style == 'hstack' else 'v'}stack=inputs=2;amix=inputs=2", "-c:v", "libx264", "-c:a",
                      "aac", outname)
    for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
        os.remove(file)
    return outname


# https://stackoverflow.com/a/30228789/9044183
async def imagestack(files, style):
     raise NotImplementedError("images are a weird edge case i'll get to later")


async def freezemotivate(files, *caption):
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
    for file in [lastframe, clastframe]:
        os.remove(file)
    return final


async def trim(file, length):
    mt = mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4",
        "GIF": "mp4"
    }
    out = temp_file(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-t", str(length), out)
    if mt == "GIF":
        out = await mp4togif(out)
    return out
