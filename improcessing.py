import os
import random
import string

import wand
from wand.image import Image
from wand.display import display
from wand.drawing import Drawing
from wand.font import Font
from wand.color import Color
from wand.image import BaseImage

futura = os.path.abspath("fonts/caption.otf").replace("\\", "/")


def get_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))


async def imsave(image):
    extension = "png"
    while True:
        name = f"temp/{get_random_string(8)}.{extension}"
        if not os.path.exists(name):
            image.save(filename=name)
            return name


async def imcaption(image, cap):  # `image` is a file path and `cap` is a str
    # image = "text-jpg"
    with Image(filename=image) as img:
        with Image(width=img.width, height=1000, background=Color("White")) as capimg:
            capimg.options['pango:align'] = 'center'
            capimg.options['pango:wrap'] = 'word-char'
            capimg.options['pango:single-paragraph'] = 'false'
            wand.font = futura
            capimg.font_size = int(img.width / 13 * 1.333)
            capimg.pseudo(capimg.width, capimg.height, pseudo=f"pango:{cap}")
            capimg.gravity = "center"
            capimg.extent(width=img.width, height=int(capimg.height + img.width / 13))
            capimg.merge_layers('flatten')
            return await imsave(capimg)
