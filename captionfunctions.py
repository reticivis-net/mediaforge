import io
import random
import re
import subprocess
from PIL import Image
import chromiumrender
from improcessing import filetostring, temp_file


# stolen code https://stackoverflow.com/questions/6116978/how-to-replace-multiple-substrings-of-a-string
def replaceall(text, rep):
    # use these three lines to do the replacement
    rep = dict((re.escape(k), v) for k, v in rep.items())
    # Python 3 renamed dict.iteritems to dict.items so use rep.items() for latest versions
    pattern = re.compile("|".join(rep.keys()))
    text = pattern.sub(lambda m: rep[re.escape(m.group(0))], text)
    return text


def sanitizehtml(caption):
    if isinstance(caption, list):
        caption[:] = [c.replace("&", '&amp;').replace("<", '&lt;').replace(">", '&gt;').replace("\"", '&quot;')
                          .replace("'", '&#039;') for c in caption]
    else:
        caption = caption.replace("&", '&amp;').replace("<", '&lt;').replace(">", '&gt;').replace("\"", '&quot;') \
            .replace("'", '&#039;')
    return caption


def esmcaption(image, caption, tosavename=None):
    if tosavename is None:
        tosavename = temp_file("png")
    caption = sanitizehtml(caption)
    replacedict = {
        "CaptionText": caption,
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("esmcaption.html"), replacedict)
    chromiumrender.html2png(torender, tosavename)
    return tosavename


def caption(image, caption, tosavename=None):
    if tosavename is None:
        tosavename = temp_file("png")
    caption = sanitizehtml(caption)
    replacedict = {
        "CaptionText": caption,
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("mycaption.html"), replacedict)
    chromiumrender.html2png(torender, tosavename)
    return tosavename


def bottomcaption(image, caption, tosavename=None):
    if tosavename is None:
        tosavename = temp_file("png")
    caption = sanitizehtml(caption)
    replacedict = {
        "CaptionText": caption,
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("mycaptionbottom.html"), replacedict)
    chromiumrender.html2png(torender, tosavename)
    return tosavename


def motivate(image, caption, tosavename=None):
    if tosavename is None:
        tosavename = temp_file("png")
    caption = sanitizehtml(caption)
    replacedict = {
        "CaptionText1": caption[0],
        "CaptionText2": caption[1],
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("motivate.html"), replacedict)
    chromiumrender.html2png(torender, tosavename)
    return tosavename


def meme(image, caption, tosavename=None):
    if tosavename is None:
        tosavename = temp_file("png")
    caption = sanitizehtml(caption)
    replacedict = {
        "CaptionText1": caption[0],
        "CaptionText2": caption[1],
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("meme.html"), replacedict)
    chromiumrender.html2png(torender, tosavename)
    return tosavename


def twittercap(image, caption, tosavename=None):
    if tosavename is None:
        tosavename = temp_file("png")
    caption = sanitizehtml(caption)
    replacedict = {
        "CaptionText1": caption,
        "rendering/demoimage.png": image
    }
    torender = replaceall(filetostring("twittercaption.html"), replacedict)
    chromiumrender.html2png(torender, tosavename)
    return tosavename


def halfsize(image, caption, tosavename=None):  # caption arg kept here for compatibility with handleanimated()

    if tosavename is None:
        name = temp_file("png")
    else:
        name = tosavename
    subprocess.check_call(["ffmpeg", "-i", image, "-vf", "scale=iw/2:ih/2", name],
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
