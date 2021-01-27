# standard libs
import glob
import logging
import multiprocessing
import os
import random
import string
import sys
import asyncio
import functools
from multiprocessing import Pool
# pip libs
import discord.ext
from PIL import Image, UnidentifiedImageError

if sys.platform == "win32":  # this hopefully wont cause any problems :>
    from winmagic import magic
else:
    import magic
# project files
import captionfunctions
import humanize
import chromiumrender
import config


def initializerenderpool():
    """
    Start the worker pool
    :return: the worker pool
    """
    global renderpool
    logging.info(f"Starting {config.chrome_driver_instances} pool processes...")
    renderpool = multiprocessing.Pool(config.chrome_driver_instances, initializer=chromiumrender.initdriver)
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


def get_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))


def temp_file(extension="png"):
    """
    generates the name of a non-existing file for usage in temp/
    :param extension: the extension of the file
    :return: the name of the file (no file is created by this function)
    """
    while True:
        name = f"temp/{get_random_string(8)}.{extension}"
        if not os.path.exists(name):
            return name


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
    """
    gets the FPS of a file
    :param filename: filename
    :return: FPS
    """
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
    """
    gets the duration of a file
    :param filename: filename
    :return: duration
    """
    logging.info("Getting duration...")
    out = await run_command("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", filename)
    return float(out)


async def get_resolution(filename):
    """
    gets the resolution of a file
    :param filename: filename
    :return: [width, height]
    """
    out = await run_command("ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
                            filename)
    return out.split("x")


async def ffmpegsplit(media):
    """
    splits the input file into frames
    :param media: file
    :return: [list of files, ffmpeg key to find files]
    """
    logging.info("Splitting frames...")
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-vsync", "1", "-vf", "scale='max(200,iw)':-1",
                      f"{media.split('.')[0]}%09d.png")
    files = glob.glob(f"{media.split('.')[0]}*.png")

    return files, f"{media.split('.')[0]}%09d.png"


async def splitaudio(video):
    """
    splits audio from a file
    :param video: file
    :return: filename of audio (aac) if file has audio, False if it doesn't
    """
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
        await run_command("ffmpeg", "-hide_banner", "-f", "lavfi", "-i", "anullsrc", "-i", video, "-c:v", "libx264",
                          "-c:a", "aac",
                          "-map", "0:a", "-map", "1:v", "-shortest", outname)
        os.remove(video)
        return outname


async def compresspng(png):
    """
    compress a png file with pngquant
    :param png: file
    :return: filename of compressed png
    """
    outname = temp_file("png")
    await run_command("pngquant", "--quality=0-80", "--o", outname, png)
    os.remove(png)
    return outname


async def assurefilesize(media: str, ctx: discord.ext.commands.Context):
    """
    downsizes files up to 5 times if they are over discord's upload limit
    :param media: media
    :param ctx: discord context
    :return: filename of fixed media if it works, False if it still is too big.
    """
    for i in range(5):
        size = os.path.getsize(media)
        logging.info(f"Resulting file is {humanize.naturalsize(size)}")
        # https://www.reddit.com/r/discordapp/comments/aflp3p/the_truth_about_discord_file_upload_limits/
        if size >= 8388119:
            logging.info("Image too big!")
            msg = await ctx.send(
                f"{config.emojis['warning']} Resulting file too big! ({humanize.naturalsize(size)}) Downsizing result...")
            imagenew = await handleanimated(media, captionfunctions.halfsize, ctx)
            os.remove(media)
            media = imagenew
            await msg.delete()
        if os.path.getsize(media) < 8388119:
            return media
    await ctx.send(f"{config.emojis['warning']} Max downsizes reached. File is way too big.")
    return False


def minimagesize(image, minsize):
    """
    resizes image to be at least minsize wide
    :param image: image
    :param minsize: minimum width in pixels
    :return: image with width at least minsize
    """
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
    :return: can be VIDEO, AUDIO, GIF, IMAGE or None (invalid or other).
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


def run_in_exec(func, *args, **kwargs):
    """
    prevents intense non-async functions from blocking event loop
    """
    loop = asyncio.get_running_loop()
    return loop.run_in_executor(None, lambda: func(*args, **kwargs))


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
    logging.info(f"Detected type {imty}.")
    if imty is None:
        raise Exception(f"File {media} is invalid!")
    elif imty == "IMAGE":
        logging.info(f"Processing frame...")
        media = minimagesize(media, 200)
        result = renderpool.apply_async(capfunction, (media, caption))
        capped = await run_in_exec(result.get)
        return await compresspng(capped)
    elif imty == "VIDEO" or imty == "GIF":
        frames, name = await ffmpegsplit(media)
        audio = await splitaudio(media)
        fps = await get_frame_rate(media)
        # logging.info(
        #     f"Processing {len(frames)} frames with {min(len(frames), POOLWORKERS)} processes...")
        if len(frames) > config.max_frames:
            await ctx.reply(
                f"{config.emojis['warning']} Input file has {len(frames)} frames, maximum allowed is {config.max_frames}.")
            logging.warning(f"⚠ Input file has {len(frames)} frames, maximum allowed is {config.max_frames}.")
            return
        logging.info(f"Processing {len(frames)} frames...")
        capargs = []
        for i, frame in enumerate(frames):
            capargs.append((frame, caption, frame.replace('.png', '_rendered.png')))
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
    await run_command("gifski", "--quiet", "--fast", "-o", outname, "--fps", str(fps), name.replace('%09d', '*'))
    logging.info("Cleaning files...")
    for f in glob.glob(name.replace('%09d', '*')):
        os.remove(f)
    return outname


async def giftomp4(gif):
    """
    converts gif to mp4
    :param gif: gif
    :return: mp4
    """
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", gif, "-movflags", "faststart", "-pix_fmt", "yuv420p", "-vf",
                      "scale=trunc(iw/2)*2:trunc(ih/2)*2", outname)

    return outname


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
# TODO: some way to preserve gif transparency?
async def speed(file, sp):
    """
    changes speed of media
    :param file: media
    :param sp: speed to multiply media by
    :return: processed media
    """
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
    """
    reverses media (-1x speed)
    :param file: media
    :return: procesed media
    """
    mt = mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-vf", "reverse", "-af", "areverse",
                      outname)
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
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter:v", f"fps=fps={fps}", outname)
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
                      "pad=width='max(iw,ih)':height='max(iw,ih)':x='(ih-iw)/2':y='(iw-ih)/2':color=white", outname)
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
    await run_command("ffmpeg", "-hide_banner", "-i", audio, "-loop", "1", "-i", image, "-c:v", "libx264",
                      "-c:a", "aac", "-shortest", "-t", str(duration), outname)
    return outname


async def concatv(files):
    """
    concatenates 2 videos
    :param files: [video, video]
    :return: combined video
    """
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
    """
    stacks media
    :param files: [media, media]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
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
    """
    stack() calls this function since ffmpeg can be weird about pngs
    :param files: [image,image]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
    raise NotImplementedError("images are a weird edge case i'll get to later")


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
    for file in [lastframe, clastframe]:
        os.remove(file)
    return final


async def trim(file, length):
    """
    trims media to length seconds
    :param file: media
    :param length: duration to trim
    :return: processed media
    """
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
