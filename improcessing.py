import asyncio
import glob
import logging
import os
import random
import string
import subprocess
import sys
import discord.ext
import imgkit
from PIL import Image
from winmagic import magic
from multiprocessing import Pool
import functools
import captionfunctions
import humanize


def disable_logging(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logging.disable(logging.INFO)
        result = func(*args, **kwargs)
        logging.disable(logging.NOTSET)
        return result

    return wrapper


options = {
    "enable-local-file-access": None,
    "format": "png",
    "transparent": None,
    "width": 1,
    "quiet": None
}


def filetostring(f):
    with open(f, 'r') as file:
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
async def run_command(*args):  # TODO: sanitize this... this means change all str inputs to lists... ugh
    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Status
    logging.info(f"Started: {args}, pid={process.pid}", flush=True)

    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()

    # Progress
    if process.returncode == 0:
        logging.info(
            f"Done: {args}, pid={process.pid}, result: {stdout.decode().strip()}",
            flush=True,
        )
    else:
        logging.error(
            f"Failed: {args}, pid={process.pid}, result: {stderr.decode().strip()}",
            flush=True,
        )
    result = stdout.decode().strip() + stderr.decode().strip()
    # Result

    # Return stdout
    return result


@disable_logging
def imgkitstring(torender, tosavename=None):
    if tosavename is None:
        name = temp_file("png")
        imgkit.from_string(torender, name, options=options)
        return name
    else:
        imgkit.from_string(torender, tosavename, options=options)
        return tosavename


# https://askubuntu.com/questions/110264/how-to-find-frames-per-second-of-any-video-file
def get_frame_rate(filename):
    logging.info("[improcessing] Getting FPS...")
    if not os.path.exists(filename):
        sys.stderr.write("ERROR: filename %r was not found!" % (filename,))
        return -1
    out = subprocess.check_output(
        ["ffprobe", filename, "-v", "0", "-select_streams", "v", "-print_format", "flat", "-show_entries",
         "stream=r_frame_rate"])
    rate = out.split(b'=')[1].strip()[1:-1].split(b'/')  # had to change to byte for some reason lol!
    if len(rate) == 1:
        return float(rate[0])
    if len(rate) == 2:
        return float(rate[0]) / float(rate[1])
    return -1


async def ffmpegsplit(image):
    logging.info("[improcessing] Splitting frames...")
    await run_command("ffmpeg", "-i", image, "-vsync", "1", f"{image.split('.')[0]}%09d.png")
    files = glob.glob(f"{image.split('.')[0]}*.png")
    return files, f"{image.split('.')[0]}%09d.png"


async def splitaudio(video):
    logging.info("[improcessing] Splitting audio...")
    name = temp_file("aac")
    result = await run_command("ffmpeg", "-i", video, "-vn", "-acodec", "copy", name)
    logging.info(result)
    if "Output file #0 does not contain any stream" in result:
        return False
    return name


async def compresspng(png):
    extension = "png"
    outname = temp_file("png")
    await run_command("pngquant", "--quality=0-80", "--o", outname, png)
    os.remove(png)
    return outname


async def assurefilesize(image: str, ctx: discord.ext.commands.Context):
    for i in range(5):
        # https://www.reddit.com/r/discordapp/comments/aflp3p/the_truth_about_discord_file_upload_limits/
        size = os.path.getsize(image)
        logging.info(f"Resulting file is {humanize.naturalsize(size)}")
        if size >= 8388119:
            logging.info("Image too big!")
            msg = await ctx.send(f"⚠ Resulting file too big! ({humanize.naturalsize(size)}) Downsizing result...")
            await ctx.trigger_typing()
            image = await handleanimated(image, "", captionfunctions.halfsize)
            await msg.delete()
        if os.path.getsize(image) < 8388119:
            return image
    await ctx.send(f"⚠ Max downsizes reached. File is way too big.")
    return False


async def handleanimated(image: str, caption, capfunction):
    try:
        with Image.open(image) as im:
            anim = getattr(im, "is_animated", False)
    except IOError:  # either invalid file or a valid video
        # https://stackoverflow.com/a/56526114/9044183
        mime = magic.Magic(mime=True)
        filename = mime.from_file(image)
        if filename.find('video') != -1:
            logging.warning("[improcessing] Video detected.")
            frames, name = await ffmpegsplit(image)
            audio = await splitaudio(image)
            fps = get_frame_rate(image)
            logging.info("[improcessing] Processing frames...")
            capargs = []
            for i, frame in enumerate(frames):
                capargs.append((frame, caption, frame.replace('.png', '_rendered.png')))
            pool = Pool(32)
            pool.starmap_async(capfunction, capargs)
            pool.close()
            pool.join()
            logging.info("[improcessing] Joining frames...")
            outname = temp_file("mp4")
            if audio:
                await run_command("ffmpeg", "-r", str(fps), "-start_number", "1", "-i",
                                  name.replace('.png', '_rendered.png'),
                                  "-i", audio, "-c:a", "aac", "-shortest",
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
                os.remove(audio)
            else:
                await run_command("ffmpeg", "-r", str(fps), "-start_number", "1", "-i",
                                  name.replace('.png', '_rendered.png'),
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
            # cleanup
            logging.info("[improcessing] Cleaning files...")
            for f in glob.glob(name.replace('%09d', '*')):
                os.remove(f)

            return outname
        else:
            raise Exception("File given is not valid image or video.")
    else:
        if anim:  # gif
            logging.info("[improcessing] Gif or similair detected.")
            logging.info("[improcessing] Splitting frames...")
            frames, name = await ffmpegsplit(image)
            fps = get_frame_rate(image)
            logging.info("[improcessing] Processing frames...")
            capargs = []
            for i, frame in enumerate(frames):
                capargs.append((frame, caption, frame.replace('.png', '_rendered.png')))
            pool = Pool(32)
            pool.starmap(capfunction, capargs)
            pool.close()
            pool.join()
            logging.info("[improcessing] Joining frames...")
            outname = temp_file("gif")
            await run_command(
                "gifski", "-o", outname, "--fps", str(fps), name.replace('.png', '_rendered.png').replace('%09d', '*'))
            logging.info("[improcessing] Cleaning files...")
            for f in glob.glob(name.replace('%09d', '*')):
                os.remove(f)
            return outname
        else:  # normal image
            return await compresspng(capfunction(image, caption))


async def mp4togif(mp4):
    mime = magic.Magic(mime=True)
    filename = mime.from_file(mp4)
    if filename.find('video') == -1:
        return False
    frames, name = await ffmpegsplit(mp4)
    fps = get_frame_rate(mp4)
    outname = temp_file("gif")
    await run_command("gifski", "-o", outname, "--fps", str(fps), name.replace('%09d', '*'))
    logging.info("[improcessing] Cleaning files...")
    for f in glob.glob(name.replace('%09d', '*')):
        os.remove(f)
    return outname


async def giftomp4(gif):
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-i", gif, "-movflags", "faststart", "-pix_fmt", "yuv420p", "-vf",
                      "scale=trunc(iw/2)*2:trunc(ih/2)*2", outname)

    return outname


async def mediatopng(media):
    outname = temp_file("png")
    await run_command("ffmpeg", "-i", media, "-frames:v", "1", outname)

    return outname


async def ffprobe(file):
    return await run_command("ffprobe", "-hide_banner", file)
