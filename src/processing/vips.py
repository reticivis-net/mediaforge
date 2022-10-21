import dataclasses
import html
import math
import typing

import pyvips

import processing.ffmpeg
import processing.ffprobe
from processing.common import run_parallel
from utils.tempfiles import TempFile


@dataclasses.dataclass
class ImageSize:
    width: int
    height: int


async def generic_caption_stack(media: str, capfunc: callable, captions: typing.Sequence[str], reverse=False):
    size = ImageSize(*await processing.ffprobe.get_resolution(media))
    captext = await run_parallel(capfunc, captions, size)
    args = (media, captext) if reverse else (captext, media)
    return await processing.ffmpeg.naive_vstack(*args)


async def generic_caption_overlay(media: str, capfunc: callable, captions: typing.Sequence[str]):
    size = ImageSize(*await processing.ffprobe.get_resolution(media))
    captext = await run_parallel(capfunc, captions, size)
    return await processing.ffmpeg.naive_overlay(media, captext)


def escape(arg: str | typing.Sequence[str]):
    if isinstance(arg, str):
        return html.escape(arg)
    else:
        return [html.escape(s) for s in arg]


def outline(image: pyvips.Image, radius: int | None = None, color: typing.Sequence[int] | None = None) -> pyvips.Image:
    if color is None:
        color = [0, 0, 0]
    if radius is None:
        radius = image.width // 1000
    # wee bit of aliasing
    scaling_factor = 2
    # we need to make the text image large enough to hold the extra edges
    text = image.embed(radius, radius, image.width + 2 * radius, image.height + 2 * radius)
    # only care about alpha channel
    text_shadow = text[3]
    if scaling_factor > 1:
        # resize bigger
        text_shadow = text[3].resize(scaling_factor, kernel=pyvips.Kernel.LINEAR)
    # dilate the text mask, this step does no antialiasing hence done at scaled resolution
    circle_mask = pyvips.Image.black(radius * scaling_factor * 2 + 1, radius * scaling_factor * 2 + 1) \
        .add(128) \
        .draw_circle(255, radius * scaling_factor, radius * scaling_factor, radius * scaling_factor, fill=True)
    text_shadow = text_shadow.dilate(circle_mask)
    if scaling_factor > 1:
        # resize back to 1x
        text_shadow = text_shadow.resize(1 / scaling_factor, kernel=pyvips.Kernel.LANCZOS3)
    # paint black
    text_shadow = text_shadow.new_from_image(color) \
        .bandjoin(text_shadow) \
        .copy(interpretation="srgb")
    # composite
    text = text_shadow.composite(text, "over")
    return text


def esmcaption(captions: typing.Sequence[str], size: ImageSize):
    captions = escape(captions)
    # https://github.com/esmBot/esmBot/blob/121615df63bdcff8ee42330d8a67a33a18bb463b/natives/caption.cc#L28-L50
    # constants used by esmbot
    fontsize = size.width / 10
    textwidth = size.width - (size.width / 12.5)
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
    out = out.gravity(pyvips.CompassDirection.CENTRE, size.width, out.height + fontsize, extend=pyvips.Extend.WHITE)
    # save and return
    # because it's run in executor, tempfiles
    outfile = TempFile("png", only_delete_in_main_process=True, todelete=False)
    out.pngsave(outfile)
    return outfile


def motivate_text(captions: typing.Sequence[str], size: ImageSize):
    captions = escape(captions)
    textsize = size.width / 5
    width = math.floor(size.width + (size.width / 60))
    width = math.floor(width + (width / 30))
    toptext = None
    bottomtext = None
    if captions[0]:
        # technically redundant but adds twemoji font
        toptext = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.otf")
        # generate text
        toptext = pyvips.Image.text(
            f"<span foreground=\"white\">{captions[0]}</span>",
            font=f"Twemoji Color Emoji,TimesNewRoman {textsize}px",
            rgba=True,
            fontfile="rendering/fonts/times new roman.ttf",
            align=pyvips.Align.CENTRE,
            width=width
        )
        toptext = toptext.gravity(pyvips.CompassDirection.CENTRE, toptext.width, toptext.height + (textsize / 4),
                                  extend=pyvips.Extend.BLACK)
    if captions[1]:
        # technically redundant but adds twemoji font
        bottomtext = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.otf")
        # generate text
        bottomtext = pyvips.Image.text(
            f"<span foreground=\"white\">{captions[1]}</span>",
            font=f"Twemoji Color Emoji,TimesNewRoman {int(textsize * 0.4)}px",
            rgba=True,
            fontfile="rendering/fonts/times new roman.ttf",
            align=pyvips.Align.CENTRE,
            width=width
        )
        bottomtext = bottomtext.gravity(pyvips.CompassDirection.CENTRE, bottomtext.width,
                                        bottomtext.height + (textsize / 4),
                                        extend=pyvips.Extend.BLACK)
    if toptext and bottomtext:
        out = toptext.join(bottomtext, pyvips.Direction.VERTICAL, expand=True, background=[0, 0, 0, 255],
                           align=pyvips.Align.CENTRE)
    else:
        if toptext:
            out = toptext
        elif bottomtext:
            out = bottomtext
        else:  # shouldnt happen but why not
            raise Exception("missing toptext and bottomtext")
            # out = pyvips.Image.new_from_list([[0, 0, 0, 255]])
    # overlay black background
    out = out.composite2((0, 0, 0, 255), mode=pyvips.BlendMode.DEST_OVER)
    # pad text to target width
    out = out.gravity(pyvips.CompassDirection.CENTRE, width, out.height, extend=pyvips.Extend.BACKGROUND,
                      background=[0, 0, 0, 255])
    outfile = TempFile("png", only_delete_in_main_process=True)
    out.pngsave(outfile)
    return outfile


def meme_text(captions: typing.Sequence[str], size: ImageSize):
    captions = escape(captions)
    # blank image
    overlay = pyvips.Image.black(size.width, size.height).new_from_image([0, 0, 0, 0]).copy(
        interpretation=pyvips.enums.Interpretation.RGB)

    if captions[0]:
        # technically redundant but adds twemoji font
        toptext = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.otf")
        # generate text
        toptext = pyvips.Image.text(
            f"<span foreground=\"white\">{captions[0].upper()}</span>",
            font=f"Twemoji Color Emoji,Impact",
            rgba=True,
            fontfile="rendering/fonts/ImpactMix.ttf",
            align=pyvips.Align.CENTRE,
            width=int(size.width * .95),
            height=int((size.height * .95) / 3)
        )
        overlay = overlay.composite2(toptext, pyvips.BlendMode.OVER,
                                     x=((size.width - toptext.width) / 2),
                                     y=int(size.height * .025))
    if captions[1]:
        # technically redundant but adds twemoji font
        bottomtext = pyvips.Image.text(".", fontfile="rendering/fonts/TwemojiCOLR0.otf")
        # generate text
        bottomtext = pyvips.Image.text(
            f"<span foreground=\"white\">{captions[1].upper()}</span>",
            font=f"Twemoji Color Emoji,Impact",
            rgba=True,
            fontfile="rendering/fonts/ImpactMix.ttf",
            align=pyvips.Align.CENTRE,
            width=int(size.width * .95),
            height=int((size.height * .95) / 3)
        )
        overlay = overlay.composite2(bottomtext, pyvips.BlendMode.OVER,
                                     x=((size.width - bottomtext.width) / 2),
                                     y=int(size.height / 3 * 2))

    overlay = outline(overlay, overlay.width // 200)
    outfile = TempFile("png", todelete=False)
    overlay.pngsave(outfile)
    return outfile


def stack(file0, file1):
    file0 = pyvips.Image.new_from_file(file0)
    file1 = pyvips.Image.new_from_file(file1)
    out = file0.join(file1, pyvips.Direction.VERTICAL, expand=True, background=0xffffff, align=pyvips.Align.CENTRE)
    outfile = TempFile("png", only_delete_in_main_process=True)
    out.pngsave(outfile)
    return outfile

# print(esmcaption(["h👍💜🏳️‍🌈🏳️‍⚧️i"], 1000))
# print(meme_text(["topto top topt otp otp top", "bottom"], ImageSize(1000, 1000)))
