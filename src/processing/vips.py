import asyncio
import concurrent.futures
import functools
import typing

import pyvips

import processing.ffmpeg
import processing.ffprobe
from utils.tempfiles import TempFile


async def run_parallel(syncfunc: typing.Callable, *args, **kwargs):
    """
    uses concurrent.futures.ProcessPoolExecutor to run CPU-bound functions in their own process

    :param syncfunc: the blocking function
    :return: the result of the blocking function
    """
    with concurrent.futures.ProcessPoolExecutor(1) as pool:
        return await asyncio.get_running_loop().run_in_executor(pool, functools.partial(syncfunc, *args, **kwargs))


async def generic_caption_stack(media: str, capfunc: callable, captions: typing.Sequence[str], reverse=False):
    width, height = await processing.ffprobe.get_resolution(media)
    captext = await run_parallel(capfunc, captions, width)
    args = (media, captext) if reverse else (captext, media)
    return await processing.ffmpeg.naive_vstack(*args)


def esmcaption(captions: typing.Sequence[str], width: int):
    # https://github.com/esmBot/esmBot/blob/121615df63bdcff8ee42330d8a67a33a18bb463b/natives/caption.cc#L28-L50
    # constants used by esmbot
    fontsize = width / 10
    textwidth = width - (width / 12.5)
    # technically redundant but adds twemoji font
    out = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.ttf")
    # generate text
    # TODO: emojis fucking broke again waaha
    out = pyvips.Image.text(f"{captions[0]}",
                            font=f"Twemoji Color Emoji, Futura Extra Black Condensed {fontsize}",
                            rgba=True, fontfile="rendering/fonts/caption.otf", align=pyvips.Align.CENTRE,
                            width=textwidth)
    # overlay white background
    out2 = out.composite((255, 255, 255, 255), mode=pyvips.BlendMode.DEST_OVER)
    # pad text to image width
    out2 = out2.gravity(pyvips.CompassDirection.CENTRE, width, out.height + fontsize, extend=pyvips.Extend.WHITE)
    # save and return
    # because it's run in executor, tempfiles
    outfile = TempFile("png", only_delete_in_main_process=True)
    out2.pngsave(outfile)
    return outfile


def stack(file0, file1):
    file0 = pyvips.Image.new_from_file(file0)
    file1 = pyvips.Image.new_from_file(file1)
    out = file0.join(file1, direction=pyvips.Direction.VERTICAL, expand=True, background=0xffffff)
    outfile = TempFile("png", False)
    out.pngsave(outfile)
    return outfile
