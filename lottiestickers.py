import os

import discord
import lottie
from lottie.exporters import exporters
from lottie.importers import importers

from tempfiles import temp_file


def stickerurl(sticker: discord.Sticker):
    return f"https://discord.com/stickers/{sticker.id}/{sticker.image}.json"


def lottiestickertogif(sticker):  # passed the lottie json file
    # https://gitlab.com/mattbas/python-lottie/-/blob/master/bin/lottie_convert.py#L112
    importer = importers.items["lottie"]
    outfile = temp_file("gif")  # generates filename ending with .gif
    exporter = exporters.get_from_filename(outfile)
    an = importer.process(sticker)
    exporter.process(an, outfile)
    return outfile


if __name__ == "__main__":
    lottiestickertogif("rendering/lottietest.json")
