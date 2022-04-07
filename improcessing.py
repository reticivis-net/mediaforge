# standard libs
import asyncio
import concurrent.futures
import glob
import json
import math
import multiprocessing
import os
import shutil
import subprocess
import sys
import typing
from fractions import Fraction

import aiohttp
# pip libs
import apng
import aubio
import humanize
import nextcord as discord
import numpy
from PIL import Image, UnidentifiedImageError
from nextcord.ext import commands

if sys.platform == "win32":  # this hopefully wont cause any problems :>
    from winmagic import magic
else:
    import magic

# project files
import autotune
import captionfunctions
import chromiumrender
import config
import tempfiles
from clogs import logger
from tempfiles import temp_file

"""
This file contains functions for processing and editing media
"""


class NonBugError(Exception):
    """When this is raised instead of a normal Exception, on_command_error() will not attach a traceback or github
    link. """
    pass


class CMDError(Exception):
    """raised by run_command"""
    pass


class ReturnedNothing(Exception):
    """raised by improcess()"""
    pass


def pass_temp_session(fn, args, kwargs, sessionlist):
    """used in Pool to pass the current TempFileSession into the process"""
    tempfiles.globallist = sessionlist
    result = fn(*args, **kwargs)
    tempfiles.globallist = None
    return result


class MyProcess(multiprocessing.Process):
    def start(self):
        super(MyProcess, self).start()


# https://stackoverflow.com/a/65966787/9044183
class Pool:
    def __init__(self, nworkers):
        self._executor = concurrent.futures.ProcessPoolExecutor(nworkers, initializer=chromiumrender.initdriver)
        self._nworkers = nworkers
        self._submitted = 0
        # loop = asyncio.get_event_loop()
        # loop.run_until_complete(self.init())

    async def init(self):
        await asyncio.gather(*([self.submit(chromiumrender.initdriver)] * self._nworkers))

    async def submit(self, fn, *args, ses=None, **kwargs):
        self._submitted += 1
        if ses is None:
            ses = tempfiles.get_session_list()
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(self._executor, pass_temp_session, fn, args, kwargs, ses)
        try:
            return await fut
        finally:
            self._submitted -= 1

    async def shutdown(self):
        await asyncio.wait([self.submit(chromiumrender.closedriver)] * self._nworkers)
        self._executor.shutdown(wait=True)

    def stats(self):
        queued = max(0, self._submitted - self._nworkers)
        executing = min(self._submitted, self._nworkers)
        return queued, executing


def updatechromedriver():
    pass


def initializerenderpool():
    """
    Start the worker pool
    :return: the worker pool
    """
    global renderpool
    try:
        # looks like it uses less memory
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass
    logger.info(f"Starting {config.chrome_driver_instances} pool processes...")
    # renderpool = multiprocessing.Pool(config.chrome_driver_instances, initializer=chromiumrender.initdriver)
    renderpool = Pool(config.chrome_driver_instances)
    return renderpool


# https://fredrikaverpil.github.io/2017/06/20/async-and-await-with-subprocesses/
async def run_command(*args):
    """
    run a cli command

    :param args: the args of the command, what would normally be seperated by a space
    :return: the result of the command
    """
    # https://stackoverflow.com/a/56884806/9044183
    # set proccess priority low
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.BELOW_NORMAL_PRIORITY_CLASS
        nicekwargs = {"startupinfo": startupinfo}
    else:
        nicekwargs = {"preexec_fn": lambda: os.nice(10)}

    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        **nicekwargs
    )

    # Status
    logger.info(f"'{args[0]}' started with PID {process.pid}")
    logger.log(11, f"PID {process.pid}: {args}")

    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()

    try:
        result = stdout.decode().strip() + stderr.decode().strip()
    except UnicodeDecodeError:
        result = stdout.decode("ascii", 'ignore').strip() + stderr.decode("ascii", 'ignore').strip()
    # Progress
    if process.returncode == 0:
        logger.debug(f"PID {process.pid} Done.")
        logger.debug(f"Results: {result}")
    else:

        logger.error(
            f"PID {process.pid} Failed: {args} result: {result}",
        )
        # adds command output to traceback
        raise CMDError(f"Command {args} failed.") from CMDError(result)
    # Result

    # Return stdout
    return result


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


async def ffmpegsplit(media):
    """
    splits the input file into frames
    :param media: file
    :return: [list of files, ffmpeg key to find files]
    """
    logger.info("Splitting frames...")
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-vsync", "1", f"{media.split('.')[0]}_%09d.png")
    files = glob.glob(f"{media.split('.')[0]}_*.png")
    tempfiles.reserve_names(files)

    return files, f"{media.split('.')[0]}_%09d.png"


async def splitaudio(video):
    """
    splits audio from a file
    :param video: file
    :return: filename of audio (aac) if file has audio, False if it doesn't
    """
    ifaudio = await run_command("ffprobe", "-i", video, "-show_streams", "-select_streams", "a", "-loglevel", "panic")
    if ifaudio:
        logger.info("Splitting audio...")
        name = temp_file("aac")
        await run_command("ffmpeg", "-hide_banner", "-i", video, "-vn", "-acodec", "aac", "-q:a", "2", name)
        return name
    else:
        logger.info("No audio detected.")
        return False


async def forceaudio(video):
    """
    gives videos with no audio a silent audio stream
    :param video: file
    :return: video filename
    """
    ifaudio = await run_command("ffprobe", "-i", video, "-show_streams", "-select_streams", "a", "-loglevel", "panic")
    if ifaudio:
        return video
    else:
        outname = temp_file("mp4")
        await run_command("ffmpeg", "-hide_banner", "-i", video, "-f", "lavfi", "-i", "anullsrc", "-c:v", "png",
                          "-c:a", "aac", "-map", "0:v", "-map", "1:a", "-shortest", outname)
        return outname


async def compresspng(png):
    """
    compress a png file with pngquant
    :param png: file
    :return: filename of compressed png
    """
    # return png
    outname = temp_file("png")
    await run_command("pngquant", "--output", outname, png)  # "--quality=0-80",
    return outname


async def twopasscapvideo(video: str, maxsize: int, audio_bitrate=128000):
    """
    attempts to intelligently cap video filesize with two pass encoding

    :param video: video file (str path)
    :param maxsize: max size (in bytes) of output file
    :param audio_bitrate: optionally specify an audio bitrate in bits per second
    :return: new video file below maxsize
    """
    if (size := os.path.getsize(video)) < maxsize:
        return video
    # https://trac.ffmpeg.org/wiki/Encode/H.264#twopass
    duration = await get_duration(video)
    # bytes to bits
    target_total_bitrate = (maxsize * 8) / duration
    for tolerance in [.98, .95, .90, .75, .5]:
        target_video_bitrate = (target_total_bitrate - audio_bitrate) * tolerance
        assert target_video_bitrate > 0
        logger.info(f"trying to force {video} ({humanize.naturalsize(size)}) "
                    f"under {humanize.naturalsize(maxsize)} with tolerance {tolerance}. "
                    f"trying {humanize.naturalsize(target_video_bitrate / 8)}/s")
        pass1log = temp_file("log")
        outfile = temp_file("mp4")
        await run_command('ffmpeg', '-y', '-i', video, '-c:v', 'h264', '-b:v', str(target_video_bitrate), '-pass', '1',
                          '-f', 'mp4', '-passlogfile', pass1log,
                          'NUL' if sys.platform == "win32" else "/dev/null")
        await run_command('ffmpeg', '-i', video, '-c:v', 'h264', '-b:v', str(target_video_bitrate), '-pass', '2',
                          '-passlogfile', pass1log, '-c:a', 'aac', '-b:a', str(audio_bitrate), "-f", "mp4", "-movflags",
                          "+faststart", outfile)
        if (size := os.path.getsize(outfile)) < maxsize:
            logger.info(f"successfully created {humanize.naturalsize(size)} video!")
            return outfile
        else:
            logger.info(f"tolerance {tolerance} failed. output is {humanize.naturalsize(size)}")
    raise NonBugError(f"Unable to fit {video} within {humanize.naturalsize(maxsize)}")


async def intelligentdownsize(media: str, maxsize: int):
    """
    tries to intelligently downsize media to fit within maxsize

    :param media: media path str
    :param maxsize: max size in bytes
    :return: new media file below maxsize
    """

    size = os.path.getsize(media)
    w, h = await get_resolution(media)
    for tolerance in [.98, .95, .90, .75, .5]:
        reduction_ratio = (maxsize / size) * tolerance
        # this took me longer to figure out than i am willing to admit
        new_w = math.floor(math.sqrt(reduction_ratio * (w ** 2)))
        new_h = math.floor(math.sqrt(reduction_ratio * (h ** 2)))
        logger.info(f"trying to resize from {w}x{h} to {new_w}x{new_h} (~{reduction_ratio} reduction)")
        resized = await resize(media, new_w, new_h)
        if (size := os.path.getsize(resized)) < maxsize:
            logger.info(f"successfully created {humanize.naturalsize(size)} media!")
            return resized
        else:
            logger.info(f"tolerance {tolerance} failed. output is {humanize.naturalsize(size)}")


async def assurefilesize(media: str, ctx: commands.Context, re_encode=True):
    """
    compresses files to fit within config set discord limit

    :param re_encode: try to reencode media?
    :param media: media
    :param ctx: discord context
    :return: filename of fixed media if it works, False if it still is too big.
    """
    if not media:
        raise ReturnedNothing(f"assurefilesize() was passed no media.")
    mt = await mediatype(media)
    if mt == "VIDEO":
        # this is in assurefilesize since all output media gets sent through here
        # it removes transparency if its an actual video and not a gif, since like nothing can play transparent videos
        # also forces audio to aac since audio recoding is a lot more noticable so i have to use copy for some reason
        if re_encode:
            media = await reencode(media)
    size = os.path.getsize(media)
    if size > config.way_too_big_size:
        raise NonBugError(f"Resulting file is {humanize.naturalsize(size)}. "
                          f"Aborting upload since resulting file is over "
                          f"{humanize.naturalsize(config.way_too_big_size)}")
    if size < config.file_upload_limit:
        return media
    msg = await ctx.reply(f"{config.emojis['warning']} Resulting file too big! ({humanize.naturalsize(size)}) "
                          f"Downsizing result...", mention_author=False)
    if mt == "VIDEO":
        # fancy ffmpeg based video thing
        try:
            video = await twopasscapvideo(media, config.file_upload_limit)
            await msg.delete()
            return video
        except Exception as e:
            await msg.delete()
            raise e
    elif mt in ["IMAGE", "GIF"]:
        # file size should be roughly proportional to # of pixels so we can work with that :3
        try:
            video = await intelligentdownsize(media, config.file_upload_limit)
            await msg.delete()
            return video
        except Exception as e:
            await msg.delete()
            raise e
    else:
        raise NonBugError(f"File is too big to upload.")


async def watermark(media):
    if (await mediatype(media)) == "AUDIO":  # exiftool doesnt support it :/
        try:
            t = temp_file(media.split(".")[-1])
            await run_command("ffmpeg", "-i", media, "-c", "copy", "-metadata", "artist=MediaForge", t)
            shutil.copy2(t, media)
            os.remove(t)
        except CMDError:
            logger.warning(f"ffmpeg audio watermarking of {media} failed")
    else:
        try:
            await run_command("exiftool", "-overwrite_original", "-artist=MediaForge", media)
        except CMDError:
            logger.warning(f"exiftool watermarking of {media} failed")


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


async def run_in_exec(func, *args, **kwargs):
    """
    prevents intense non-async functions from blocking event loop
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


async def ensureduration(media, ctx: typing.Union[commands.Context, None]):
    """
    ensures that media is under or equal to the config minimum frame count
    :param media: media to trim
    :param ctx: discord context
    :return: processed media or original media, within config.max_frames
    """
    # the function that splits frames actually has a vsync thing so this is more accurate to what's generated
    fps = await get_frame_rate(media)
    dur = await get_duration(media)
    frames = int(fps * dur)
    if frames <= config.max_frames:
        return media
    else:
        newdur = config.max_frames / fps
        if ctx is not None:
            tmsg = f"{config.emojis['warning']} input file is too long (~{frames} frames)! Trimming to {round(newdur, 1)}" \
                   f"s (~{config.max_frames} frames)... "
            msg = await ctx.reply(tmsg)
        media = await trim(media, newdur)
        if ctx is not None:
            await msg.edit(content=tmsg + " Done!", delete_after=5)
        return media


# async def forcesize(files):
#     # this code is bugged, it shuffles frames around...
#     logger.info("Forcing all frames to same size...")
#     res = await get_resolution(files[0])
#     out = []
#     jobs = []
#     for f in files:
#         n = temp_file("png")
#         out.append(n)
#         # captionfunctions.resize(f, res, n)
#         jobs.append(renderpool.submit(captionfunctions.resize, f, res, n))
#     await asyncio.wait(jobs)
#     return out


async def handleanimated(media: typing.Union[str, typing.List[str]], capfunction: callable, ctx: commands.Context,
                         *caption):
    """
    handles processing functions that only work in singular frames and applies to videos/gifs
    :param media: image, video, or gif
    :param capfunction: function to process media with
    :param ctx: discord context
    :param caption: other params (usually caption)
    :return: processed media
    """
    mediaargs = []
    if isinstance(media, list):
        mediaargs = media[1:]
        media = media[0]
    imty = await mediatype(media)
    logger.info(f"Detected type {imty}.")
    if imty is None:
        raise Exception(f"File {media} is invalid!")
    elif imty == "IMAGE":
        logger.info(f"Processing frame...")
        # media = minimagesize(media, 200)
        result = await renderpool.submit(capfunction, [media] + mediaargs if mediaargs else media, caption)
        # capped = await run_in_exec(result.get)
        return await compresspng(result)
    elif imty == "VIDEO" or imty == "GIF":
        media = await ensureduration(media, ctx)
        frames, name = await ffmpegsplit(media)
        audio = await splitaudio(media)
        fps = await get_frame_rate(media)
        # logger.info(
        #     f"Processing {len(frames)} frames with {min(len(frames), POOLWORKERS)} processes...")

        logger.info(f"Processing {len(frames)} frames...")
        framefuncs = []

        ses = tempfiles.get_session_list()
        for i, frame in enumerate(frames):
            framefuncs.append(renderpool.submit(capfunction, [frame] + mediaargs if mediaargs else frame, caption,
                                                frame.replace('.png', '_rendered.png'), ses=ses))
        await asyncio.wait(framefuncs)
        tempfiles.reserve_names(glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*')))
        # result = renderpool.starmap_async(capfunction, capargs)
        # await run_in_exec(result.get)
        # result = await renderpool.
        logger.info(f"Joining {len(frames)} frames...")
        # frames = await forcesize(glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*')))

        if imty == "GIF":
            frames = glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*'))
            outname = temp_file("gif")
            await run_command("gifski", "--quiet", "--fast", "--output", outname, "--fps", str(fps), "--width", "1000",
                              *frames)
        else:  # imty == "VIDEO":
            outname = temp_file("mp4")
            frames = name.replace('.png', '_rendered.png')
            if audio:
                await run_command("ffmpeg", "-hide_banner", "-r", str(fps), "-i", frames,
                                  "-i", audio, "-c:a", "aac", "-shortest",
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
            else:
                await run_command("ffmpeg", "-hide_banner", "-r", str(fps), "-i", frames,
                                  "-c:v", "libx264", "-crf", "25", "-pix_fmt", "yuv420p",
                                  "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2", outname)
        # cleanup
        # logger.info("Cleaning files...")
        # for f in glob.glob(name.replace('%09d', '*')):
        #     try:
        #         os.remove(f)
        #     except FileNotFoundError:
        #         pass
        # for f in glob.glob(name.replace('.png', '_rendered.png').replace('%09d', '*')):
        #     try:
        #         os.remove(f)
        #     except FileNotFoundError:
        #         pass
        return outname


async def mp4togif(mp4):
    """
    converts mp4 to gif
    :param mp4: mp4
    :return: gif
    """
    frames, name = await ffmpegsplit(mp4)
    fps = await get_frame_rate(mp4)
    outname = temp_file("gif")
    n = glob.glob(name.replace('%09d', '*'))
    if len(n) <= 1:
        raise NonBugError(f"Output file only has {len(n)} frames, GIFs must have at least 2.")
    else:
        await run_command("gifski", "--quiet", "--fast", "--output", outname, "--fps", str(fps), *n)
        # logger.info("Cleaning files...")
        # for f in glob.glob(name.replace('%09d', '*')):
        #     os.remove(f)
        return outname


async def toapng(video):
    frames, name = await ffmpegsplit(video)
    fps = await get_frame_rate(video)
    fps = Fraction(1 / fps).limit_denominator()
    outname = temp_file("png")
    # apngasm input is strange
    await run_command("apngasm", outname, name.replace('%09d', '000000001'), str(fps.numerator), str(fps.denominator),
                      "-i1")
    return outname
    # ffmpeg method, removes dependence on apngasm but bigger and worse quality
    # outname = temp_file("png")
    # await run_command("ffmpeg", "-i", video, "-f", "apng", "-plays", "0", outname)


async def reencode(mp4):  # reencodes mp4 as libx264 since the png format used cant be played by like literally anything
    assert (mt := await mediatype(mp4)) in ["VIDEO", "GIF"], f"file {mp4} with type {mt} passed to reencode()"
    # only reencode if need to ;)
    vcodec, acodec = await va_codecs(mp4)
    vcode = ["copy"] if vcodec == "h264" else ["libx264", "-pix_fmt", "yuv420p", "-vf",
                                               "scale=ceil(iw/2)*2:ceil(ih/2)*2"]
    acode = ["copy"] if acodec == "aac" else ["aac", "-q:a", "2"]
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", mp4, "-c:v", *vcode, "-c:a", *acode,
                      "-max_muxing_queue_size", "9999", "-movflags", "+faststart", outname)
    return outname


async def allreencode(file):
    mt = await mediatype(file)
    if mt == "IMAGE":
        return await compresspng(await mediatopng(file))
    elif mt == "VIDEO":
        return await reencode(file)
    elif mt == "AUDIO":
        outname = temp_file("mp3")
        await run_command("ffmpeg", "-hide_banner", "-i", file, "-c:a", "libmp3lame", outname)
        return outname
    else:
        raise Exception(f"{file} of type {mt} cannot be re-encoded")


async def giftomp4(gif):
    """
    converts gif to mp4
    :param gif: gif
    :return: mp4
    """
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", gif, "-movflags", "faststart", "-pix_fmt", "yuv420p",
                      "-sws_flags", "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf",
                      "scale=trunc(iw/2)*2:trunc(ih/2)*2", outname)

    return outname


async def toaudio(media):
    """
    converts video to only audio
    :param media: video or audio ig
    :return: aac
    """
    name = temp_file("mp3")  # discord wont embed aac
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-vn", name)
    return name


async def mediatopng(media):
    """
    converts media to png
    :param media: media
    :return: png
    """
    outname = temp_file("png")
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-frames:v", "1", "-c:v", "png", "-pix_fmt", "yuva420p",
                      outname)

    return outname


async def ffprobe(file):
    return [await run_command("ffprobe", "-hide_banner", file), magic.from_file(file, mime=False),
            magic.from_file(file, mime=True)]


# https://stackoverflow.com/questions/65728616/how-to-get-ffmpeg-to-consistently-apply-speed-effect-to-first-few-frames
async def speed(file, sp):
    """
    changes speed of media
    :param file: media
    :param sp: speed to multiply media by
    :return: processed media
    """
    # TODO: some weird bug here caused by 100fps gifski gifs that slows down gifs?

    mt = await mediatype(file)
    if mt == "AUDIO":
        outname = temp_file("mp3")
        duration = await get_duration(file)
        await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter_complex",
                          f"{expanded_atempo(sp)}", "-t", str(duration / float(sp)), "-c:a", "libmp3lame", outname)
    else:
        outname = temp_file("mp4")
        fps = await get_frame_rate(file)
        duration = await get_duration(file)
        await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-filter_complex",
                          f"[0:v]setpts=PTS/{sp},fps={fps}[v];[0:a]{expanded_atempo(sp)}[a]",
                          "-map", "[v]", "-map", "[a]", "-t", str(duration / float(sp)), "-c:v", "png", outname)
        if await count_frames(outname) < 2:
            raise NonBugError("Output file has less than 2 frames. Try reducing the speed.")
        if mt == "GIF":
            outname = await mp4togif(outname)
    return outname


async def reverse(file):
    """
    reverses media (-1x speed)
    :param file: media
    :return: procesed media
    """
    mt = await mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-vf", "reverse", "-af", "areverse",
                      "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def random(file, frames: int):
    """
    shuffle frames
    :param file: media
    :param frames: number of frames in internal cache
    :return: procesed media
    """
    mt = await mediatype(file)
    outname = temp_file("mp4")
    #
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter:v", f"random=frames={frames}",
                      "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def quality(file, crf, qa):
    """
    changes quality of videos/gifs with ffmpeg compression
    :param file: media
    :param crf: FFmpeg CRF param
    :param qa: audio bitrate
    :return: processed media
    """
    mt = await mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-crf", str(crf), "-c:a", "aac", "-b:a",
                      f"{qa}k", outname)
    # png cannot be supported here because crf and qa are libx264 params lmao
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def changefps(file, fps):
    """
    changes FPS of media
    :param file: media
    :param fps: FPS
    :return: processed media
    """
    mt = await mediatype(file)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-r", str(fps), "-c", "copy", "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def invert(file):
    """
    inverts colors
    :param file: media
    :return: processed media
    """
    mt = await mediatype(file)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outname = temp_file(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf", f"negate", "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def pad(file):
    """
    pads media into a square shape
    :param file: media
    :return: processed media
    """
    mt = await mediatype(file)
    if mt == "IMAGE":
        outname = temp_file("png")
    else:
        outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf",
                      "pad=width='max(iw,ih)':height='max(iw,ih)':x='(ih-iw)/2':y='(iw-ih)/2':color=white", "-c:v",
                      "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def gifloop(file, loop):
    """
    loops a gif
    :param file: gif
    :param loop: # of times to loop
    :return: processed media
    """
    outname = temp_file("gif")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-loop", str(loop), "-vcodec", "copy", outname)
    return outname


async def videoloop(file, loop):
    """
    loops a gif
    :param file: gif
    :param loop: # of times to loop
    :return: processed media
    """
    mt = await mediatype(file)
    exts = {
        "VIDEO": "mp4",
        "GIF": "gif"
    }
    outname = temp_file(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-stream_loop", str(loop), "-i", file, "-vcodec", "copy", outname)
    return outname


async def imageaudio(files):
    """
    combines an image and an audio file into a video
    :param files: [image, audio]
    :return: video
    """
    audio = files[1]
    image = files[0]
    outname = temp_file("mp4")
    duration = await get_duration(audio)  # it is a couple seconds too long without it :(
    await run_command("ffmpeg", "-hide_banner", "-i", audio, "-loop", "1", "-i", image, "-pix_fmt", "yuv420p", "-vf",
                      "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-c:a", "aac", "-shortest", "-t",
                      str(duration), outname)
    return outname


async def addaudio(files, loops=0):
    """
    adds audio to media
    :param files: [media, audiotoadd]
    :return: video or audio
    """
    # TODO: this can trim media short? not sure why...
    audio = files[1]
    media = files[0]
    mt = await mediatype(media)
    if mt == "IMAGE":
        # no use reinventing the wheel
        return await imageaudio(files)
    elif mt == "GIF":
        # GIF case is like imageaudio, but with stream_loop instead of loop.
        outname = temp_file("mp4")
        if loops >= 0:
            # if the gif is set to loop a fixed amount of times, cut out at the longest stream.
            await run_command("ffmpeg", "-hide_banner", "-i", audio, "-stream_loop", str(loops), "-i", media,
                              "-pix_fmt", "yuv420p", "-vf",
                              "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-c:a", "aac", "-q:a", "2",
                              outname)
        else:
            # if it's set to loop infinitely, cut out when the audio ends.
            duration = await get_duration(audio)  # it is a couple seconds too long without it :(
            await run_command("ffmpeg", "-hide_banner", "-i", audio, "-stream_loop", str(loops), "-i", media,
                              "-pix_fmt", "yuv420p", "-vf",
                              "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-c:a", "aac", "-q:a", "2",
                              "-shortest", "-t", str(duration), outname)
        return outname
    else:
        media = await forceaudio(media)
        # yes, qa works backwards on aac vs mp3. no, i dont know why.
        if mt == "AUDIO":
            outname = temp_file("mp3")
            audiosettings = ["-c:a", "libmp3lame", "-q:a", "0"]
        else:
            outname = temp_file("mp4")
            audiosettings = ["-c:a", "aac", "-q:a", "2"]
        await run_command("ffmpeg", "-i", media, "-i", audio, "-max_muxing_queue_size", "4096", "-filter_complex",
                          "[0:a][1:a]amix=inputs=2:dropout_transition=100000:duration=longest[a];[a]volume=2[a]",
                          "-map", "0:v?", "-map", "[a]", *audiosettings, outname)
        return outname


async def concatv(files):
    """
    concatenates 2 videos
    :param files: [video, video]
    :return: combined video
    """
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "png", "-c:a", "copy", "-ar", "48000",
                      "-max_muxing_queue_size", "4096", fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")

    # https://superuser.com/a/1136305/1001487
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf",
                      f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:-2:-2:color=black", "-c:v",
                      "png", "-c:a", "copy", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    concatdemuxer = temp_file("txt")
    with open(concatdemuxer, "w+") as f:
        f.write(f"file '{fixedvideo0}'\nfile '{fixedfixedvideo1}'".replace(config.temp_dir, ""))
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-f", "concat", "-i", concatdemuxer, "-c:v", "png", "-c:a", "copy",
                      outname)
    if (await mediatype(files[0])) == "GIF" and (await mediatype(files[1])) == "GIF":
        outname = await mp4togif(outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1, concatdemuxer]:
    #     os.remove(file)
    return outname


async def stack(files, style):
    """
    stacks media
    :param files: [media, media]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
    mts = [await mediatype(files[0]), await mediatype(files[1])]
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":  # easier to just make this an edge case
        return await imagestack(files, style)
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "png", "-c:a", "copy", "-ar", "48000",
                      "-max_muxing_queue_size", "4096", fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")
    if style == "hstack":
        scale = f"scale=-2:{h}"
    else:
        scale = f"scale={w}:-2"
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf", scale, "-c:v",
                      "png", "-c:a", "copy", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    outname = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", fixedvideo0, "-i", fixedfixedvideo1, "-filter_complex",
                      f"{'h' if style == 'hstack' else 'v'}stack=inputs=2;amix=inputs=2:dropout_transition=0", "-c:v",
                      "png", "-c:a", "aac", "-q:a", "2", outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    if mts[0] != "VIDEO" and mts[1] != "VIDEO":  # one or more gifs and no videos
        outname = await mp4togif(outname)
    return outname


async def overlay(files, alpha: float, mode: str = 'overlay'):
    """
    stacks media
    :param files: [media, media]
    :param alpha: opacity of top media, 0-1
    :param mode: blend mode
    :return: processed media
    """
    assert mode in ['overlay', 'add']
    assert 0 <= alpha <= 1
    mts = [await mediatype(files[0]), await mediatype(files[1])]
    video0 = await forceaudio(files[0])
    fixedvideo0 = temp_file("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "png", "-c:a", "copy", "-ar", "48000",
                      "-max_muxing_queue_size", "4096", fixedvideo0)
    video1 = await forceaudio(files[1])
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = temp_file("mp4")
    scale = f"scale={w}:{h}"
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf", scale, "-c:v",
                      "png", "-c:a", "copy", "-ar", "48000", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)
    outname = temp_file("mp4")
    blendlogic = ""
    if mode == "overlay":
        blendlogic = f"[0v][1v]overlay"
    elif mode == "add":
        blendlogic = f"[1v][0v]blend=all_mode='addition':eof_action=repeat:shortest=0:repeatlast=1"
    await run_command("ffmpeg", "-hide_banner", "-i", fixedvideo0, "-i", fixedfixedvideo1, "-filter_complex",
                      f"[0:v]setpts=PTS-STARTPTS[0v];[1:v]setpts=PTS-STARTPTS,colorchannelmixer=aa={alpha}[1v];"
                      f"{blendlogic};amix=inputs=2:dropout_transition=0", "-c:v",
                      "png", "-c:a", "aac", "-q:a", "2", outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        outname = await mediatopng(outname)
    # one or more gifs and no videos
    elif mts[0] != "VIDEO" and mts[1] != "VIDEO":
        outname = await mp4togif(outname)
    return outname


# https://stackoverflow.com/a/30228789/9044183
async def imagestack(files, style):
    """
    stack() calls this function since ffmpeg can be weird about pngs
    :param files: [image,image]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
    image0 = Image.open(files[0]).convert("RGBA")
    image1 = Image.open(files[1]).convert("RGBA")
    if style == "vstack":
        width = image0.size[0]
        ratio1 = image1.size[1] / image1.size[0]
        height1 = width * ratio1
        image1 = image1.resize((int(width), int(height1)), resample=Image.BICUBIC)
        outimg = Image.new("RGBA", (width, image0.size[1] + image1.size[1]))
        outimg.alpha_composite(image0)
        outimg.alpha_composite(image1, (0, image0.size[1]))
    else:
        height = image0.size[1]
        ratio1 = image1.size[0] / image1.size[1]
        width1 = height * ratio1
        image1 = image1.resize((int(width1), int(height)), resample=Image.BICUBIC)
        outimg = Image.new("RGBA", (image0.size[0] + image1.size[0], height))
        outimg.alpha_composite(image0)
        outimg.alpha_composite(image1, (image0.size[0], 0))
    outname = temp_file("png")
    outimg.save(outname)
    outname = await compresspng(outname)
    return outname


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
    frame = temp_file("png")
    await run_command("ffmpeg", "-hide_banner", "-i", video, "-vf", f"select='eq(n,{n})'", "-vframes", "1",
                      frame)
    return frame


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
    clastframe = await handleanimated(lastframe, captionfunctions.motivate, None, *caption)
    freezeframe = await imageaudio([clastframe, audio])
    final = await concatv([video, freezeframe])
    return final


async def trim(file, length, start=0):
    """
    trims media to length seconds
    :param file: media
    :param length: duration to set video to in seconds
    :param start: time in seconds to begin the trimmed video
    :return: processed media
    """
    mt = await mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4",
        "GIF": "mp4"
    }
    dur = await get_duration(file)
    if start > dur:
        raise NonBugError(f"Trim start ({start}s) is outside the range of the file ({dur}s)")
    out = temp_file(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-t", str(length), "-ss", str(start), "-c:v", "png", out)
    if mt == "GIF":
        out = await mp4togif(out)
    return out


async def ensuresize(ctx, file, minsize, maxsize):
    """
    Ensures valid media is between minsize and maxsize in resolution
    :param ctx: discord context
    :param file: media
    :param minsize: minimum width/height in pixels
    :param maxsize: maximum height in pixels
    :return: original or resized media
    """
    resized = False
    if await mediatype(file) not in ["IMAGE", "VIDEO", "GIF"]:
        return file
    w, h = await get_resolution(file)
    owidth = w
    oheight = h
    if w < minsize:
        # the min(-1,maxsize) thing is to prevent a case where someone puts in like a 1x1000 image and it gets resized
        # to 200x200000 which is very large so even though it wont preserve aspect ratio it's an edge case anyways

        file = await resize(file, minsize, f"min(-1, {maxsize * 2})")
        w, h = await get_resolution(file)
        resized = True
    if h < minsize:
        file = await resize(file, f"min(-1, {maxsize * 2})", minsize)
        w, h = await get_resolution(file)
        resized = True
    if w > maxsize:
        file = await resize(file, maxsize, "-1")
        w, h = await get_resolution(file)
        resized = True
    if h > maxsize:
        file = await resize(file, "-1", maxsize)
        w, h = await get_resolution(file)
        resized = True
    if resized:
        logger.info(f"Resized from {owidth}x{oheight} to {w}x{h}")
        await ctx.reply(f"Resized input media from {int(owidth)}x{int(oheight)} to {int(w)}x{int(h)}.", delete_after=5,
                        mention_author=False)
    return file


async def rotate(file, rottype):
    types = {  # command input to ffmpeg vf
        "90": "transpose=1",
        "90ccw": "transpose=2",
        "180": "vflip,hflip",
        "vflip": "vflip",
        "hflip": "hflip"
    }
    mt = await mediatype(file)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    out = temp_file(exts[mt])
    await run_command("ffmpeg", "-i", file, "-vf", types[rottype] + ",format=yuva420p", "-c:v", "png", out)
    if mt == "GIF":
        out = await mp4togif(out)
    return out


async def volume(file, vol):
    mt = await mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4"
    }
    out = temp_file(exts[mt])
    # convert vol % to db
    # http://www.sengpielaudio.com/calculator-loudness.htm
    if vol > 0:
        vol = 10 * math.log(vol, 2)
        # for some reason aac has audio caps but libmp3lame works fine lol
        await run_command("ffmpeg", "-i", file, "-af", f"volume={vol}dB", "-strict", "-1", "-c:a", "libmp3lame", out)
    else:
        await run_command("ffmpeg", "-i", file, "-af", f"volume=0", "-strict", "-1", "-c:a", "libmp3lame", out)

    return out


def nthroot(num: float, n: float):
    return num ** (1 / n)


def expanded_atempo(arg: float):
    """
    expand atempo's limits from [0.5, 100] to (0, infinity) using daisy chaining
    """
    assert arg > 0, "atempo must be greater than 0"
    if 0.5 <= arg <= 100:  # if number already in normal limits
        return f"atempo={arg}"  # return with one atempo
    else:
        # use log to determine minimum number of atempos needed to achieve desired atempo
        numofatempos = math.ceil(math.log(arg, 0.5 if arg < 0.5 else 100))
        # construct one atempo statement
        atempo = f"atempo={nthroot(arg, numofatempos)}"
        # daisy chain them
        return ",".join([atempo for _ in range(numofatempos)])


async def vibrato(file, frequency=5, depth=0.5):  # https://ffmpeg.org/ffmpeg-filters.html#tremolo
    mt = await mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4"
    }
    out = temp_file(exts[mt])
    if mt == "AUDIO":
        audiosettings = ["-c:a", "libmp3lame", "-q:a", "0"]
    else:
        audiosettings = ["-c:a", "aac", "-q:a", "2"]

    await run_command("ffmpeg", "-i", file, "-af", f"vibrato=f={frequency}:d={depth}", "-strict", "-1", *audiosettings,
                      out)
    return out


async def pitch(file, p=12):
    mt = await mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4"
    }
    out = temp_file(exts[mt])
    # http://www.geekybob.com/post/Adjusting-Pitch-for-MP3-Files-with-FFmpeg
    asetrate = max(int(48000 * 2 ** (p / 12)), 1)
    atempo = 2 ** (-p / 12)
    logger.debug((p, asetrate, atempo))
    af = f"asetrate=r={asetrate},{expanded_atempo(atempo)},aresample=48000"
    if mt == "AUDIO":
        audiosettings = ["libmp3lame", "-q:a", "0"]
    else:
        audiosettings = ["aac", "-q:a", "2"]
    await run_command("ffmpeg", "-i", file, "-ar", "48000", "-af", af, "-strict", "-1", "-c:a", *audiosettings, out)
    return out


async def resize(image, width, height, ensure_duration=True):
    """
    resizes image

    :param ensure_duration: trim video/gif file if too long
    :param image: file
    :param width: new width, thrown directly into ffmpeg so it can be things like -1 or iw/2
    :param height: new height, same as width
    :return: processed media
    """
    mt = await mediatype(image)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    out = temp_file(exts[mt])
    if ensure_duration and mt in ["VIDEO", "GIF"]:
        image = await ensureduration(image, None)
    await run_command("ffmpeg", "-i", image, "-pix_fmt", "yuva420p", "-max_muxing_queue_size", "9999", "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp+bitexact",
                      "-vf", f"scale='{width}:{height}',setsar=1:1", "-c:v", "png", "-pix_fmt", "yuva420p", "-c:a",
                      "copy", out)

    if mt == "GIF":
        out = await mp4togif(out)
    elif mt == "VIDEO":
        out = await reencode(out)
    return out


async def checkwatermark(file):
    # see watermark()
    etdata = await run_command("exiftool", "-artist", "-json", file)
    logger.info(etdata)
    etdata = json.loads(etdata)[0]
    if "Artist" in etdata:
        if etdata["Artist"] == "MediaForge":
            return True
    return False


async def count_emoji(guild: discord.Guild):
    anim = 0
    static = 0
    for emoji in guild.emojis:
        if emoji.animated:
            anim += 1
        else:
            static += 1
    return {"animated": anim, "static": static}


async def add_emoji(file, guild: discord.Guild, name):
    """
    adds emoji to guild
    :param file: emoji to add
    :param guild: guild to add it to
    :param name: emoji name
    :return: result text
    """
    with open(file, "rb") as f:
        data = f.read()
    try:
        emoji = await guild.create_custom_emoji(name=name, image=data, reason="$addemoji command")
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to create an emoji. Make sure I have the Manage Emojis " \
               f"permission. "
    except discord.HTTPException as e:
        logger.error(e, exc_info=(type(e), e, e.__traceback__))
        return f"{config.emojis['2exclamation']} Something went wrong trying to add your emoji! ```{e}```"
    else:
        count = await count_emoji(guild)
        if emoji.animated:
            return f"{config.emojis['check']} Animated emoji successfully added: " \
                   f"{emoji}\n{guild.emoji_limit - count['animated']} slots are left."
        else:
            return f"{config.emojis['check']} Emoji successfully added: " \
                   f"{emoji}\n{guild.emoji_limit - count['static']} slots are left."


async def add_sticker(file, guild: discord.Guild, sticker_emoji, name):
    """
    adds sticker to guild
    :param file: sticker to add
    :param guild: guild to add it to
    :param sticker_emoji "related" emoji of the sticker
    :param name: sticker name
    :return: result text
    """
    file = discord.File(file)
    try:
        await guild.create_sticker(name=name, emoji=sticker_emoji, file=file, reason="$addsticker command",
                                   description=" ")
        # description MUST NOT be empty. see https://github.com/nextcord/nextcord/issues/165
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to create a sticker. Make sure I have the Manage " \
               f"Emojis and Stickers permission. "
    except discord.HTTPException as e:
        logger.error(e, exc_info=(type(e), e, e.__traceback__))
        toreturn = f"{config.emojis['2exclamation']} Something went wrong trying to add your sticker! ```{e}```"
        if "Invalid Asset" in str(e):
            toreturn += "\nNote: `Invalid Asset` means Discord does not accept this file format. Stickers are only " \
                        "allowed to be png or apng."
        return toreturn
    else:
        return f"{config.emojis['check']} Sticker successfully added.\n" \
               f"\n{guild.sticker_limit - len(guild.stickers)} slots are left."


async def set_banner(file, guild: discord.Guild):
    """
    sets guild banner
    :param file: banner file
    :param guild: guild to add it to
    :return:
    """
    with open(file, "rb") as f:
        data = f.read()
    try:
        await guild.edit(banner=bytes(data))
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to set your banner. Make sure I have the Manage Server " \
               f"permission. "
    except discord.HTTPException as e:
        return f"{config.emojis['2exclamation']} Something went wrong trying to set your banner! ```{e}```"
    else:
        return f"{config.emojis['check']} Successfully changed guild banner."


async def set_icon(file, guild: discord.Guild):
    """
    sets guild icon
    :param file: icon file
    :param guild: guild to add it to
    :return:
    """
    if (await mediatype(file)) == "GIF" and "ANIMATED_ICON" not in guild.features:
        return f"{config.emojis['x']} This guild does not support animated icons."
    with open(file, "rb") as f:
        data = f.read()
    try:
        await guild.edit(icon=bytes(data))
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to set your icon. Make sure I have the Manage Server " \
               f"permission. "
    except discord.HTTPException as e:
        return f"{config.emojis['2exclamation']} Something went wrong trying to set your icon! ```{e}```"
    else:
        return "Successfully changed guild icon."


async def contentlength(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        # i used to make a head request to check size first, but for some reason head requests can be super slow
        async with session.get(url) as resp:
            if resp.status == 200:
                if "Content-Length" not in resp.headers:  # size of file to download
                    return False
                else:
                    return int(resp.headers["Content-Length"])


async def iconfromsnowflakeid(snowflake: int, bot, ctx):
    try:
        user = await bot.fetch_user(snowflake)
        return str(user.avatar.url)
    except (discord.NotFound, discord.Forbidden):
        pass
    try:
        guild = await bot.fetch_guild(snowflake)
        return str(guild.icon.url)
    except (discord.NotFound, discord.Forbidden):
        pass
    try:  # get the icon through a message author to support webhook/pk icons
        msg = await ctx.channel.fetch_message(snowflake)
        return str(msg.author.avatar.url)
    except (discord.NotFound, discord.Forbidden):
        pass
    return None


async def handleautotune(media: str, *params):
    audio = await splitaudio(media)
    assert audio, "Video file must have audio."
    wav = temp_file("wav")
    await run_command("ffmpeg", "-i", audio, "-ac", "1", wav)  # "-acodec", "",
    outwav = temp_file("wav")
    # run in separate process to avoid possible segfault crashes and cause its totally blocking
    with concurrent.futures.ProcessPoolExecutor(1) as executor:
        await asyncio.get_event_loop().run_in_executor(executor, autotune.autotune, wav, outwav, *params)
    mt = await mediatype(media)
    if mt == "AUDIO":
        outname = temp_file("mp3")
        await run_command("ffmpeg", "-i", outwav, "-c:a", "libmp3lame", outname)
        return outname
    elif mt == "VIDEO":
        outname = temp_file("mp4")
        # https://superuser.com/a/1137613/1001487
        # combine video of original file with new audio

        # shawty it's a wav you cant make it acodec copy 💀
        await run_command("ffmpeg", "-i", media, "-i", outwav, "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map",
                          "1:a:0", outname)
        return outname


async def hue(file, h: float):
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    mt = await mediatype(file)
    out = temp_file(exts[mt])
    await run_command("ffmpeg", "-i", file, "-vf", f"hue=h={h},format=yuva420p", "-c:v", "png", out)
    if mt == "GIF":
        out = await mp4togif(out)
    return out


async def tint(file, col: discord.Color):
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    mt = await mediatype(file)
    out = temp_file(exts[mt])
    # https://stackoverflow.com/a/3380739/9044183
    r, g, b = map(lambda x: x / 255, col.to_rgb())
    await run_command("ffmpeg", "-i", file, "-vf", f"hue=s=0,"  # make grayscale
                                                   f"lutrgb=r=val*{r}:g=val*{g}:b=val*{b}:a=val,"  # basically set 
    # white to our color 
                                                   f"format=yuva420p", "-c:v", "png", out)
    if mt == "GIF":
        out = await mp4togif(out)
    return out


async def fetch(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        async with session.get(url) as response:
            if response.status != 200:
                response.raise_for_status()
            return await response.text()


async def tempofunc(media: str) -> typing.Optional[float]:
    """
    detects BPM of media using aubio
    :param media: path to media
    :return: BPM if detected or None
    """
    # https://github.com/aubio/aubio/blob/master/python/demos/demo_bpm_extract.py
    audio = await splitaudio(media)
    assert audio, "Video file must have audio."
    wav = temp_file("wav")
    await run_command("ffmpeg", "-i", audio, "-ac", "1", "-ar", "44100", wav)
    with aubio.source(wav) as src:
        win_s = 1024  # fft size
        hop_s = 512  # hop size
        samplerate = 44100  # hardcoded just in case
        aubiotempo = aubio.tempo("default", win_s, hop_s, samplerate)

        # list of beats, in samples
        beats = []

        # total number of frames read
        total_frames = 0
        while True:
            samples, read = src()
            is_beat = aubiotempo(samples)
            if is_beat:
                this_beat = aubiotempo.get_last_s()
                # logger.debug(f"{this_beat / float(samplerate):f}")
                beats.append(this_beat)
            total_frames += read
            if read < hop_s:
                break
        logger.debug(beats)
        if len(beats) > 1:
            bpms = 60. / numpy.diff(beats)
            return float(numpy.median(bpms))
        else:
            return None


async def tempo(media: str):
    res = await tempofunc(media)
    if res:
        return f"Detected BPM of **~{round(res, 1)}**"
    else:
        return f"{config.emojis['warning']} Not enough beats found to detect BPM."
        # print len(beats)


async def tts(text: str, model: typing.Literal["male", "female", "retro"] = "male"):
    ttswav = temp_file("wav")
    outname = temp_file("mp3")
    if model == "retro":
        await run_command("node", "sam/bundle.js", "--moderncmu", "--wav", ttswav, text)
    else:
        # espeak is a fucking nightmare on windows and windows has good native tts anyways sooooo
        if sys.platform == "win32":
            # https://docs.microsoft.com/en-us/dotnet/api/system.speech.synthesis.voicegender?view=netframework-4.8
            voice = str({"male": 1, "female": 2}[model])
            await run_command("powershell", "-File", "tts.ps1", ttswav, text, voice)
        else:
            await run_command("espeak", "-s", "150", text, "-v", "mb-us2" if model == "male" else "mb-us1",
                              "-w", ttswav)
    await run_command("ffmpeg", "-hide_banner", "-i", ttswav, "-c:a", "libmp3lame", outname)
    return outname


async def epicbirthday(text: str):
    out = temp_file("mp4")
    birthdaytext = await tts(text)
    nameimage = temp_file("png")
    await renderpool.submit(captionfunctions.epicbirthdaytext, text, nameimage)
    # when to show the text
    betweens = [
        "between(n,294,381)",
        "between(n,520,551)",
        "between(n,1210,1294)",
        "between(n,1428,1467)",
        "between(n,2024,2109)",
    ]
    await run_command("ffmpeg", "-hide_banner", "-nostdin",
                      "-i", "rendering/epicbirthday.mp4",
                      "-i", birthdaytext,
                      "-i", nameimage,
                      "-filter_complex",
                      # split the tts audio
                      "[1:a] volume=10dB,asplit=5 [b1][b2][b3][b4][b5]; "
                      # delay to correspond with video
                      "[b1] adelay=9530:all=1 [d1];"
                      "[b2] adelay=17133:all=1 [d2];"
                      "[b3] adelay=40000:all=1 [d3];"
                      "[b4] adelay=47767:all=1 [d4];"
                      # last one is long
                      "[b5] atempo=0.5,adelay=67390:all=1 [d5];"
                      "[0:a] volume=-5dB [a0];"
                      # combine audio
                      "[a0][d1][d2][d3][d4][d5] amix=inputs=6:normalize=0 [outa];"
                      # add text
                      f"[0:v][2:v] overlay=enable='{'+'.join(betweens)}' [outv]",
                      # map to output
                      "-map", "[outv]",
                      "-map", "[outa]",
                      out)
    return out


async def crop(file, w, h, x, y):
    mt = await mediatype(file)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outname = temp_file(exts[mt])
    await run_command('ffmpeg', '-i', file, '-filter:v', f'crop={w}:{h}:{x}:{y}', "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


def rgb_to_lightness(r, g, b):
    """
    adapted from colorsys.rgb_to_hls()
    :param r: red from 0-1
    :param g: green from 0-1
    :param b: blue from 0-1
    :return: lightness from 0-1
    """
    maxc = max(r, g, b)
    minc = min(r, g, b)
    return (minc + maxc) / 2.0


async def uncaption(file, frame_to_try: int, tolerance: int):
    frame_to_try = await frame_n(file, frame_to_try)
    # https://github.com/esmBot/esmBot/blob/master/natives/uncaption.cc
    # comically naive approach but apparently works :p
    with Image.open(frame_to_try) as im:
        im = im.convert("RGB")
        # get first pixel of every row
        pixels = list(im.getdata())
        width, height = im.size
        hpixels = pixels[::width]
        row_to_cut = 0
        for i, pixel in enumerate(hpixels):
            # if lightness is less than tolerance
            if rgb_to_lightness(pixel[0] / 255, pixel[1] / 255, pixel[2] / 255) < tolerance / 100:
                row_to_cut = i
                break
    # should be 0 if no caption or all caption
    if row_to_cut == 0:
        raise NonBugError("Unable to detect caption. Try to adjust `frame_to_try`. Run `$help uncaption` for help.")
    return await crop(file, width, height - row_to_cut, 0, row_to_cut)
