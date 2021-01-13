import contextlib
import io
import logging
import os
import random
import re
import subprocess
import sys
from PIL import Image

import imgkit
from improcessing import filetostring, temp_file, options


# stolen code https://stackoverflow.com/questions/6116978/how-to-replace-multiple-substrings-of-a-string
def replaceall(text, rep):
    # use these three lines to do the replacement
    rep = dict((re.escape(k), v) for k, v in rep.items())
    # Python 3 renamed dict.iteritems to dict.items so use rep.items() for latest versions
    pattern = re.compile("|".join(rep.keys()))
    text = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
    return text


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


def motivate(image, caption, tosavename=None):
    logging.info(f"[improcessing] Rendering {image}...")

    with Image.open(image) as im:
        imagewidth = im.size[0] * 1.1 + 16  # weird adding is to estimate final size based on styling
    replacedict = {
        "margin: 30px;": f"margin: {imagewidth * 0.05}px;",
        "font-size: 80px;": f"font-size: {imagewidth * 0.133}px;",
        "font-size: 40px;": f"font-size: {imagewidth * 0.067}px;",
        "<base href='./'>": f"<base href='file://{'/' if sys.platform == 'win32' else ''}{os.path.abspath('rendering')}'> ",
        "CaptionText1": caption[0],
        "CaptionText2": caption[1],
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("motivate.html"), replacedict)
    rendered = imgkitstring(torender, tosavename)
    return rendered


def meme(image, caption, tosavename=None):
    logging.info(f"[improcessing] Rendering {image}...")
    with Image.open(image) as im:
        imagewidth = im.size[0]
    replacedict = {
        "font-size: 10vw;": f"font-size: {imagewidth / 10}px;",
        "<base href='./'>": f"<base href='file://{'/' if sys.platform == 'win32' else ''}{os.path.abspath('rendering')}'> ",
        "CaptionText1": caption[0],
        "CaptionText2": caption[1],
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("meme.html"), replacedict)
    rendered = imgkitstring(torender, tosavename)
    return rendered


def halfsize(image, caption, tosavename=None):  # caption arg kept here for compatibility with handleanimated()
    logging.info(f"[improcessing] Downsizing {image}...")
    if tosavename is None:
        name = temp_file("png")
    else:
        name = tosavename
    subprocess.call("ffmpeg", "-i", image, "-vf", "scale=iw/2:ih/2", name,
                    stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return name


def jpeg(image, params: list, tosavename=None):
    if tosavename is None:
        name = temp_file("png")
    else:
        name = tosavename
    im = Image.open(image)
    im = im.convert("RGB")
    strength = params[0]
    stretch = params[1]
    quality = params[2]
    size = im.size
    for i in range(strength):
        im = im.resize((size[0] + random.randint(-stretch, stretch), size[1] + random.randint(-stretch, stretch)),
                       Image.NEAREST)
        stream = io.BytesIO()
        im.save(stream, format="JPEG", quality=quality)  # save image as jpeg to bytes
        stream.seek(0)
        im = Image.open(stream, formats=["JPEG"])
    im = im.resize(size)
    im.save(name)
    return name


def speed(media):
    pass


def imgkitstring(torender, tosavename=None):
    if tosavename is None:
        tosavename = temp_file("png")
    imgkit.from_string(torender, tosavename, options=options)
    return tosavename
