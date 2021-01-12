import logging
import os
import subprocess
import sys

from PIL import Image

from improcessing import replaceall, filetostring, imgkitstring, get_random_string, run_command, temp_file


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
    subprocess.call(f"ffmpeg -i {image} -vf scale=iw/2:ih/2 {name}",
                    stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    return name
