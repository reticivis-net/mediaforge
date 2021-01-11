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


def ffmpegsplit(image):
    logging.info("[improcessing] Splitting frames...")
    subprocess.call(f"ffmpeg -i {image} -vsync 0 {image.replace('.', '')}%09d.png", stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    files = glob.glob(f"{image.replace('.', '')}*.png")
    return files, f"{image.replace('.', '')}%09d.png"


async def handleanimated(image, caption, capfunction):
    try:
        with Image.open(image) as im:
            anim = getattr(im, "is_animated", False)
    except Exception:  # invalid image or video?
        logging.warning("Failed to open as image... handling unimplemented.")
        # https://stackoverflow.com/a/56526114/9044183
        mime = magic.Magic(mime=True)
        filename = mime.from_file(image)
        if filename.find('video') != -1:
            print('it is video')
    if anim:
        logging.info("[improcessing] Gif or similair detected...")
        frames, name = ffmpegsplit(image)
        fps = get_frame_rate(image)
        logging.info("[improcessing] Processing frames...")
        for i, f in enumerate(frames):
            await capfunction(f, caption, f.replace('.png', 'rendered.png'))
            os.remove(f)
        logging.info("[improcessing] Joining frames...")
        extension = "gif"
        while True:
            outname = f"temp/{get_random_string(8)}.{extension}"
            if not os.path.exists(outname):
                break
        subprocess.call(f"gifski -o {outname} --fps {fps} {name.replace('.png', 'rendered.png').replace('%09d', '*')}",
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return outname
    else:
        await capfunction(image, caption)


async def imcaption(image, caption, tosavename=None):
    logging.info("[improcessing] Rendering image...")
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
