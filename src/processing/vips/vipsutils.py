import dataclasses
import html
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


async def generic_caption_stack(media: str, capfunc: callable, captions: typing.Sequence[str], *args, reverse=False):
    size = ImageSize(*await processing.ffprobe.get_resolution(media))
    captext = await run_parallel(capfunc, *args, captions, size)
    args = (media, captext) if reverse else (captext, media)
    return await processing.ffmpeg.naive_vstack(*args)


async def generic_caption_overlay(media: str, capfunc: callable, captions: typing.Sequence[str], *args):
    size = ImageSize(*await processing.ffprobe.get_resolution(media))
    captext = await run_parallel(capfunc, captions, size, *args)
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
    # dilate the text with a squared-off gaussian mask
    # https://github.com/libvips/libvips/discussions/2123#discussioncomment-3950916
    mask = pyvips.Image.gaussmat(radius / 2, 0.0001, separable=True)
    mask *= 10
    shadow = image[3].convsep(mask).cast(pyvips.BandFormat.UCHAR)
    # recolor shadow
    shadow = shadow.new_from_image(color) \
        .bandjoin(shadow) \
        .copy(interpretation=pyvips.Interpretation.SRGB)
    # composite
    text = shadow.composite2(image, pyvips.BlendMode.OVER)
    return text


def overlay_in_middle(background: pyvips.Image, foreground: pyvips.Image) -> pyvips.Image:
    return background.composite2(foreground, pyvips.BlendMode.OVER,
                                 x=((background.width - foreground.width) // 2),
                                 y=((background.height - foreground.height) // 2))


def stack(file0, file1):
    # load files
    file0 = pyvips.Image.new_from_file(file0)
    file1 = pyvips.Image.new_from_file(file1)
    # stack
    out = file0.join(file1, pyvips.Direction.VERTICAL, expand=True, background=0xffffff, align=pyvips.Align.CENTRE)
    # save
    outfile = TempFile("png", only_delete_in_main_process=True)
    out.pngsave(outfile)
    return outfile
