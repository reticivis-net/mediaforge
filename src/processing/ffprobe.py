import json
import sys
import apng
if sys.platform == "win32":  # this hopefully wont cause any problems :>
    from winmagic import magic
else:
    import magic
from PIL import Image, UnidentifiedImageError

from processing.common import *


async def is_apng(filename):
    out = await run_command("ffprobe", filename, "-v", "panic", "-select_streams", "v:0", "-print_format", "json",
                            "-show_entries", "stream=codec_name")
    data = json.loads(out)
    if len(data["streams"]):  # 0 if audio file because it selects v:0, audio cannot be apng
        return data["streams"][0]["codec_name"] == "apng"
    else:
        return False


# https://askubuntu.com/questions/110264/how-to-find-frames-per-second-of-any-video-file
async def get_frame_rate(filename):
    """
    gets the FPS of a file
    :param filename: filename
    :return: FPS
    """
    logger.info("Getting FPS...")
    out = await run_command("ffprobe", filename, "-v", "panic", "-select_streams", "v:0", "-print_format", "json",
                            "-show_entries", "stream=r_frame_rate,codec_name")
    data = json.loads(out)
    if data["streams"][0]["codec_name"] == "apng":  # ffmpeg no likey apng
        parsedapng = apng.APNG.open(filename)
        apnglen = 0
        # https://wiki.mozilla.org/APNG_Specification#.60fcTL.60:_The_Frame_Control_Chunk
        for png, control in parsedapng.frames:
            if control.delay_den == 0:
                control.delay_den = 100
            apnglen += control.delay / control.delay_den
        return len(parsedapng.frames) / apnglen
    else:
        rate = data["streams"][0]["r_frame_rate"].split("/")
        if len(rate) == 1:
            return float(rate[0])
        if len(rate) == 2:
            return float(rate[0]) / float(rate[1])
        return -1


# https://superuser.com/questions/650291/how-to-get-video-duration-in-seconds
async def get_duration(filename):
    """
    gets the duration of a file
    :param filename: filename
    :return: duration
    """
    logger.info("Getting duration...")
    out = await run_command("ffprobe", "-v", "panic", "-show_entries", "format=duration", "-of",
                            "default=noprint_wrappers=1:nokey=1", filename)
    if out == "N/A":  # happens with APNGs
        # no garuntee that its an APNG here but i dont have any other plans so i want it to raise an exception
        parsedapng = apng.APNG.open(filename)
        apnglen = 0
        # https://wiki.mozilla.org/APNG_Specification#.60fcTL.60:_The_Frame_Control_Chunk
        for png, control in parsedapng.frames:
            if control.delay_den == 0:
                control.delay_den = 100
            apnglen += control.delay / control.delay_den
        return apnglen
    else:
        return float(out)


async def get_resolution(filename):
    """
    gets the resolution of a file
    :param filename: filename
    :return: [width, height]
    """
    out = await run_command("ffprobe", "-v", "panic", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height:stream_tags=rotate",
                            "-print_format", "json", filename)
    out = json.loads(out)
    w = out["streams"][0]["width"]
    h = out["streams"][0]["height"]
    # if rotated in metadata, swap width and height
    if "tags" in out["streams"][0]:
        if "rotate" in out["streams"][0]["tags"]:
            rot = float(out["streams"][0]["tags"]["rotate"])
            if rot % 90 == 0 and not rot % 180 == 0:
                w, h = h, w
    return [w, h]


async def get_vcodec(filename):
    """
    gets the codec of a video
    :param filename: filename
    :return: dict containing "codec_name" and "codec_long_name"
    """
    out = await run_command("ffprobe", "-v", "panic", "-select_streams", "v:0", "-show_entries",
                            "stream=codec_name,codec_long_name",
                            "-print_format", "json", filename)
    out = json.loads(out)
    if out["streams"]:
        return out["streams"][0]
    else:
        # only checks for video codec, audio files return Nothinng
        return None


async def get_acodec(filename):
    """
    gets the codec of audio
    :param filename: filename
    :return: dict containing "codec_name" and "codec_long_name"
    """
    out = await run_command("ffprobe", "-v", "panic", "-select_streams", "a:0", "-show_entries",
                            "stream=codec_name,codec_long_name",
                            "-print_format", "json", filename)
    out = json.loads(out)
    if out["streams"]:
        return out["streams"][0]
    else:
        return None


async def va_codecs(filename):
    out = await run_command('ffprobe', '-v', 'panic', '-show_entries', 'stream=codec_name,codec_type', '-print_format',
                            'json', filename)
    out = json.loads(out)
    acodec = None
    vcodec = None
    if out["streams"]:
        for stream in out["streams"]:
            if stream["codec_type"] == "video" and vcodec is None:
                vcodec = stream["codec_name"]
            elif stream["codec_type"] == "audio" and acodec is None:
                acodec = stream["codec_name"]
        return vcodec, acodec
    else:
        return None


async def mediatype(image):
    """
    Gets basic type of media
    :param image: filename of media
    :return: can be VIDEO, AUDIO, GIF, IMAGE or None (invalid or other).
    """
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
    probe = await run_command('ffprobe', '-v', 'panic', '-count_packets', '-show_entries',
                              'stream=codec_type,codec_name,nb_read_packets',
                              '-print_format', 'json', image)
    props = {
        "video": False,
        "audio": False,
        "gif": False,
        "image": False
    }
    probe = json.loads(probe)
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


async def ffprobe(file):
    return [await run_command("ffprobe", "-hide_banner", file), magic.from_file(file, mime=False),
            magic.from_file(file, mime=True)]


async def count_frames(video):
    # https://stackoverflow.com/a/28376817/9044183
    return int(await run_command("ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
                                 "stream=nb_read_packets", "-of", "csv=p=0", video))


async def frame_n(video, n: int):
    framecount = await count_frames(video)
    if not -1 <= n < framecount:
        raise NonBugError(f"Frame {n} does not exist.")
    if n == -1:
        n = framecount - 1
    frame = TempFile("png")
    await run_command("ffmpeg", "-hide_banner", "-i", video, "-vf", f"select='eq(n,{n})'", "-vframes", "1",
                      frame)
    return frame
