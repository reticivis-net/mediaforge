import asyncio
import glob
import logging
import os
import random
import string
import subprocess
import sys
import imgkit
from PIL import Image
import re
from winmagic import magic
from multiprocessing import Pool
import functools


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


# stolen code https://stackoverflow.com/questions/6116978/how-to-replace-multiple-substrings-of-a-string
def replaceall(text, rep):
    # use these three lines to do the replacement
    rep = dict((re.escape(k), v) for k, v in rep.items())
    # Python 3 renamed dict.iteritems to dict.items so use rep.items() for latest versions
    pattern = re.compile("|".join(rep.keys()))
    text = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
    return text


async def run_command(args):
    """Run command in subprocess.
    Example from:
        http://asyncio.readthedocs.io/en/latest/subprocess.html
    """
    # Create subprocess
    process = await asyncio.create_subprocess_shell(
        args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Status
    print("Started: %s, pid=%s" % (args, process.pid), flush=True)

    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()

    # Progress
    if process.returncode == 0:
        print(
            "Done: %s, pid=%s, result: %s"
            % (args, process.pid, stdout.decode().strip()),
            flush=True,
        )
    else:
        print(
            "Failed: %s, pid=%s, result: %s"
            % (args, process.pid, stderr.decode().strip()),
            flush=True,
        )

    # Result
    result = stdout.decode().strip()

    # Return stdout
    return result


@disable_logging
def imgkitstring(torender, tosavename=None):
    if tosavename is None:
        extension = "png"
        while True:
            name = f"temp/{get_random_string(8)}.{extension}"
            if not os.path.exists(name):
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
    await run_command(f"ffmpeg -i {image} -vsync 1 {image.split('.')[0]}%09d.png")
    files = glob.glob(f"{image.split('.')[0]}*.png")
    return files, f"{image.split('.')[0]}%09d.png"


async def splitaudio(video):
    logging.info("[improcessing] Splitting audio...")
    extension = "aac"
    while True:
        name = f"temp/{get_random_string(8)}.{extension}"
        if not os.path.exists(name):
            break
    await run_command(f"ffmpeg -i {video} -vn -acodec copy {name}")
    return name


def imcaption(image, caption, tosavename=None):
    logging.info(f"[improcessing] Rendering {image}...")
    with Image.open(image) as im:
        imagewidth = im.size[0]  # seems ineffecient but apparently fast?
    replacedict = {
        "calc((100vw / 13) * (16 / 12))": f"{(imagewidth / 13)}pt",
        "calc((100vw / 2) / 13)": f"{(imagewidth / 2) / 13}px",
        "<base href='./'>": f"<base href='file://{'/' if sys.platform == 'win32' else ''}{os.path.abspath('rendering')}'> ",
        "CaptionText": caption,
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("caption.html"), replacedict)
    rendered = imgkitstring(torender, tosavename)
    return rendered


async def handleanimated(image, caption, capfunction):
    try:
        with Image.open(image) as im:
            anim = getattr(im, "is_animated", False)
    except IOError:  # either invalid file or a valid video
        # https://stackoverflow.com/a/56526114/9044183
        mime = magic.Magic(mime=True)
        filename = mime.from_file(image)
        if filename.find('video') != -1:
            logging.warning("[improcessing] Video detected.")
            logging.info("[improcessing] Splitting frames...")
            frames, name = await ffmpegsplit(image)
            audio = await splitaudio(image)
            fps = get_frame_rate(image)
            logging.info("[improcessing] Processing frames...")
            capargs = []
            for i, frame in enumerate(frames):
                capargs.append((frame, caption, frame.replace('.png', '_rendered.png')))
            pool = Pool(16)
            pool.starmap_async(imcaption, capargs)
            pool.close()
            pool.join()
            logging.info("[improcessing] Joining frames...")
            extension = "mp4"
            while True:
                outname = f"temp/{get_random_string(8)}.{extension}"
                if not os.path.exists(outname):
                    break
            await run_command(f"ffmpeg -r {fps} -start_number 1 -i {name.replace('.png', '_rendered.png')} "
                              f"-i {audio} -c:a aac -shortest "
                              f"-c:v libx264 -crf 25 -pix_fmt yuv420p "
                              f"-vf \"crop=trunc(iw/2)*2:trunc(ih/2)*2\" {outname}")
            # cleanup
            logging.info("[improcessing] Cleaning files...")
            for f in glob.glob(name.replace('%09d', '*')):
                os.remove(f)
            os.remove(audio)
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
            pool.starmap(imcaption, capargs)
            pool.close()
            pool.join()
            logging.info("[improcessing] Joining frames...")
            extension = "gif"
            while True:
                outname = f"temp/{get_random_string(8)}.{extension}"
                if not os.path.exists(outname):
                    break
            await run_command(
                f"gifski -o {outname} --fps {fps} {name.replace('.png', '_rendered.png').replace('%09d', '*')}")
            logging.info("[improcessing] Cleaning files...")
            for f in glob.glob(name.replace('%09d', '*')):
                os.remove(f)
            return outname
        else:  # normal image
            await capfunction(image, caption)
