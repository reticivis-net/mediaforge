import os
import random
import string

import wand
from PIL import Image, ImageFont, ImageDraw

futura = ImageFont.truetype("fonts/caption.otf")


def get_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))


def wrap(font, text, line_width):
    words = text.split()

    lines = []
    line = []

    for word in words:
        newline = ' '.join(line + [word])

        w, h = font.getsize(newline)

        if w > line_width:
            lines.append(' '.join(line))
            line = [word]
        else:
            line.append(word)

    if line:
        lines.append(' '.join(line))

    return ('\n'.join(lines)).strip()


async def imsave(image):
    extension = "png"
    while True:
        name = f"temp/{get_random_string(8)}.{extension}"
        if not os.path.exists(name):
            image.save(name)
            return name


async def imcaption(image, cap):  # `image` is a file path and `cap` is a str

    im = Image.open(image)
    futuralocal = ImageFont.truetype("fonts/caption.otf", int(im.width / 13 * 1.333),
                                     layout_engine=ImageFont.LAYOUT_RAQM)
    cap = wrap(futuralocal, cap, im.width - ((im.width / 25) * 2))
    capsize = futuralocal.getsize_multiline(cap, spacing=8)
    imcap = Image.new("RGB", (im.width, capsize[1] + im.width), "#fff")
    d = ImageDraw.Draw(imcap)
    d.multiline_text(((im.width - capsize[0]) // 2, (imcap.height - capsize[1]) // 2), cap, (0, 0, 0), font=futuralocal,
                     align='center', spacing=8)
    return await imsave(imcap)
