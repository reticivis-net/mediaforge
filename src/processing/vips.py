import math
import typing

import pyvips

import processing.ffmpeg
import processing.ffprobe
from processing.common import run_parallel
from utils.tempfiles import TempFile


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
    # DOESNT WORK ON WINDOWS IDK WHY
    out = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.otf")
    # generate text
    out = pyvips.Image.text(
        captions[0],
        font=f"Twemoji Color Emoji,FuturaExtraBlackCondensed {fontsize}px",
        rgba=True,
        fontfile="rendering/fonts/caption.otf",
        align=pyvips.Align.CENTRE,
        width=textwidth
    )
    # overlay white background
    out = out.composite((255, 255, 255, 255), mode=pyvips.BlendMode.DEST_OVER)
    # pad text to image width
    out = out.gravity(pyvips.CompassDirection.CENTRE, width, out.height + fontsize, extend=pyvips.Extend.WHITE)
    # save and return
    # because it's run in executor, tempfiles
    outfile = TempFile("png", only_delete_in_main_process=True, todelete=False)
    out.pngsave(outfile)
    return outfile


def motivate_text(captions: typing.Sequence[str], width: int):
    size = width / 5
    width = math.floor(width + (width / 60))
    width = math.floor(width + (width / 30))
    if captions[0]:
        # technically redundant but adds twemoji font
        toptext = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.otf")
        # generate text
        toptext = pyvips.Image.text(
            f"<span foreground=\"white\">{captions[0]}</span>",
            font=f"Twemoji Color Emoji,TimesNewRoman {size}px",
            rgba=True,
            fontfile="rendering/fonts/times new roman.ttf",
            align=pyvips.Align.CENTRE,
            width=width
        )
        toptext = toptext.gravity(pyvips.CompassDirection.CENTRE, toptext.width, toptext.height + (size / 4),
                                  extend=pyvips.Extend.BLACK)
    if captions[1]:
        # technically redundant but adds twemoji font
        bottomtext = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.otf")
        # generate text
        bottomtext = pyvips.Image.text(
            f"<span foreground=\"white\">{captions[1]}</span>",
            font=f"Twemoji Color Emoji,TimesNewRoman {int(size * 0.4)}px",
            rgba=True,
            fontfile="rendering/fonts/times new roman.ttf",
            align=pyvips.Align.CENTRE,
            width=width
        )
        bottomtext = bottomtext.gravity(pyvips.CompassDirection.CENTRE, bottomtext.width,
                                        bottomtext.height + (size / 4),
                                        extend=pyvips.Extend.BLACK)
    if captions[0] and captions[1]:
        out = toptext.join(bottomtext, pyvips.Direction.VERTICAL, expand=True, background=[0, 0, 0, 255],
                           align=pyvips.Align.CENTRE)
    else:
        if captions[0]:
            out = toptext
        elif captions[1]:
            out = bottomtext
        else:  # shouldnt happen but why not
            out = pyvips.Image.new_from_list([[0, 0, 0, 255]])
    # overlay black background
    out = out.composite((0, 0, 0, 255), mode=pyvips.BlendMode.DEST_OVER)
    # pad text to target width
    out = out.gravity(pyvips.CompassDirection.CENTRE, width, out.height, extend=pyvips.Extend.BACKGROUND,
                      background=[0, 0, 0, 255])
    outfile = TempFile("png", only_delete_in_main_process=True)
    out.pngsave(outfile)
    return outfile


def stack(file0, file1):
    file0 = pyvips.Image.new_from_file(file0)
    file1 = pyvips.Image.new_from_file(file1)
    out = file0.join(file1, pyvips.Direction.VERTICAL, expand=True, background=0xffffff, align=pyvips.Align.CENTRE)
    outfile = TempFile("png", only_delete_in_main_process=True)
    out.pngsave(outfile)
    return outfile

# print(esmcaption(["h👍💜🏳️‍🌈🏳️‍⚧️i"], 1000))
