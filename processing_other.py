import shutil
from fractions import Fraction

from processing_ffmpeg import ffmpegsplit
from processing_ffprobe import *
from v2tempfiles import TempFile


async def watermark(media):
    if (await mediatype(media)) == "AUDIO":  # exiftool doesnt support it :/
        try:
            t = TempFile(media.split(".")[-1])
            await run_command("ffmpeg", "-i", media, "-c", "copy", "-metadata", "artist=MediaForge", t)
            # TODO: aiofiles ffs
            shutil.copy2(t, media)
            os.remove(t)
        except CMDError:
            logger.warning(f"ffmpeg audio watermarking of {media} failed")
    else:
        try:
            await run_command("exiftool", "-overwrite_original", "-artist=MediaForge", media)
        except CMDError:
            logger.warning(f"exiftool watermarking of {media} failed")


async def toapng(video):
    frames, name = await ffmpegsplit(video)
    fps = await get_frame_rate(video)
    fps = Fraction(1 / fps).limit_denominator()
    outname = TempFile("png")
    # apngasm input is strange
    await run_command("apngasm", outname, name.replace('%09d', '000000001'), str(fps.numerator), str(fps.denominator),
                      "-i1")
    return outname
    # ffmpeg method, removes dependence on apngasm but bigger and worse quality
    # outname = TempFile("png")
    # await run_command("ffmpeg", "-i", video, "-f", "apng", "-plays", "0", outname)


async def freezemotivate(files, *caption):
    """
    ends video with motivate caption
    :param files: media
    :param caption: caption to pass to motivate()
    :return: processed media
    """
    if isinstance(files, list):  # audio specified
        video = files[0]
        audio = files[1]
    else:  # just default to song lol!
        video = files
        audio = "rendering/what.mp3"
    lastframe = await frame_n(video, -1)
    # TODO: update to modern
    # clastframe = await handleanimated(lastframe, captionfunctions.motivate, None, *caption)
    # freezeframe = await imageaudio([clastframe, audio])
    # final = await concatv([video, freezeframe])
    # return final


async def checkwatermark(file):
    # see watermark()
    etdata = await run_command("exiftool", "-artist", "-json", file)
    logger.info(etdata)
    etdata = json.loads(etdata)[0]
    if "Artist" in etdata:
        if etdata["Artist"] == "MediaForge":
            return True
    return False


