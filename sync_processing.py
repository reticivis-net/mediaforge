import sys
import typing
from dataclasses import dataclass

import ffmpeg
from PIL import Image, UnidentifiedImageError

if sys.platform == "win32":  # this hopefully wont cause any problems :>
    from winmagic import magic
else:
    import magic

from tempfilesv2 import TempFile
from clogs import logger

number = int | float


@dataclass
class XY:
    # both PIL and FFmpeg have (0,0) in the top left
    x: number
    y: number


typeexts = {
    "VIDEO": "mp4",
    "GIF": "gif",
    "AUDIO": "m4a",
    "IMAGE": "png",
}


def mediatype(image: str | TempFile):
    """
    Gets basic type of media
    :param image: filename of media
    :return: can be VIDEO, AUDIO, GIF, IMAGE or None (invalid or other).
    """
    if isinstance(image, TempFile):
        if image.type:
            return image.type
    # ffmpeg doesn't work well with detecting images so let PIL do that
    mime = magic.from_file(image, mime=True)
    try:
        with Image.open(image) as im:
            anim = getattr(im, "is_animated", False)
        if anim:
            logger.debug(f"identified type {mime} with animated frames as GIF")
            return "GIF"  # gifs dont have to be animated but if they aren't its easier to treat them like pngs
        else:
            logger.debug(f"identified type {mime} with no animated frames as IMAGE")
            return "IMAGE"
    except UnidentifiedImageError:
        logger.debug(f"UnidentifiedImageError on {image}")
    # PIL isn't sure so let ffmpeg take control
    probe = ffmpeg.probe(image, count_packets=None)

    props = {
        "video": False,
        "audio": False,
        "gif": False,
        "image": False
    }
    for stream in probe["streams"]:
        if stream["codec_type"] == "audio":  # only can be pure audio
            props["audio"] = True
        elif stream["codec_type"] == "video":  # could be video or image or gif sadly
            if "nb_read_packets" in stream and int(stream["nb_read_packets"]) != 1:  # if there are multiple frames
                if stream["codec_name"] == "gif":  # if gif
                    # should have been detected in the previous step but cant hurt to be too sure
                    props["gif"] = True  # gif
                else:  # multiple frames, not gif
                    props["video"] = True  # video!!
            else:  # if there is only one frame
                props["image"] = True  # it's an image
                # yes, this will mark 1 frame/non-animated gifs as images.
                # this is intentional behavior as most commands treat gifs as videos
    # ok so a container can have multiple formats, we need to return based on expected priority
    if props["video"]:
        return "VIDEO"
    if props["gif"]:
        return "GIF"
    if props["audio"]:
        return "AUDIO"
    if props["image"]:
        return "IMAGE"
    logger.debug(f"mediatype None due to unclassified type {mime}")
    return None


def captionoverlay(base: TempFile, overlay: TempFile, pos: XY) -> TempFile:
    """
    extend a transparent single frame caption to a video
    :param base: media to caption
    :param overlay: generated caption stuff, put on top for masking potential
    :param pos: position of base relative to generated caption
    :return:
    """
    base = ffmpeg.input(base)
    overlay = ffmpeg.input(overlay)
    (
        ffmpeg
            .overlay(base, overlay, x=pos.x, y=pos.y)
            .output(out := TempFile("mp4"))
            .run()
    )
    return out


def examplecaption(media: TempFile, captions: tuple = ()) -> tuple[TempFile, XY]:
    pass


def smartcaption(capfunc: typing.Callable[[TempFile, tuple], tuple[TempFile, XY]],
                 media: TempFile,
                 captions: tuple = ()) -> TempFile:
    mt = mediatype(media)
    if mt == "AUDIO":
        raise Exception(f"attempted to caption audio file {mt}")
    capbase, capxy = capfunc(media, captions)
    return captionoverlay(capbase, media, capxy)
