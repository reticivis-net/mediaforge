import asyncio
import concurrent.futures
import functools
import typing

import pyvips

from utils.tempfiles import TempFile


async def run_parallel(syncfunc: typing.Callable, *args: tuple, **kwargs: dict):
    """
    uses concurrent.futures.ProcessPoolExecutor to run CPU-bound functions in their own process

    :param syncfunc: the blocking function
    :return: the result of the blocking function
    """
    with concurrent.futures.ProcessPoolExecutor(1) as pool:
        return await asyncio.get_running_loop().run_in_executor(pool, functools.partial(syncfunc, *args, **kwargs))


def text():
    out = pyvips.Image.text(".", fontfile="rendering/fonts/slkscr.ttf")
    out = pyvips.Image.text("test😀.", font="Twemoji Color Emoji, Silkscreen 200px", rgba=True,
                            fontfile="rendering/fonts/TwemojiCOLR0.ttf")
    out.pngsave("out.png")


def esmcaption(caption: str, width: int):
    # https://github.com/esmBot/esmBot/blob/121615df63bdcff8ee42330d8a67a33a18bb463b/natives/caption.cc#L28-L50
    # constants used by esmbot
    fontsize = width / 10
    textwidth = width - (width / 12.5)
    # technically redundant but adds twemoji font
    out = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.ttf")
    # generate text
    out = pyvips.Image.text(caption, font=f"Twemoji Color Emoji, Futura Extra Black Condensed {fontsize}", rgba=True,
                            fontfile="rendering/fonts/caption.otf", align=pyvips.Align.CENTRE, width=textwidth)
    # pad text to image width
    out = out.gravity(pyvips.CompassDirection.CENTRE, width, out.height, pyvips.Extend.WHITE)
    # save and return
    outfile = TempFile("png")
    out.pngsave(outfile)
    return outfile

def stack(file0, file1):
    raise NotImplementedError