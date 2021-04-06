from tempfiles import temp_file
import discord
from improcessing import saveurl


def stickerurl(sticker: discord.Sticker):
    return f"https://discord.com/sticker/{sticker.id}/{sticker.image}.json"


def lottiestickertogif(sticker: discord.Sticker):
    if sticker.format != "lottie":
        raise Exception("Non-lottie sticker passed to lottiestickertogif()")
    url = stickerurl(sticker)
    sticker = saveurl(url)
