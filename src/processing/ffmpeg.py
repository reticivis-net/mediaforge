import glob
import math

import discord
import humanize
from discord.ext import commands

import config
import processing.common
import processing.vips.caption
import processing.vips.vipsutils
import utils.tempfiles
from processing.ffprobe import *
from utils.tempfiles import reserve_tempfile


async def edit_msg_with_webhookmessage_polyfill(msg: typing.Union[discord.Message, discord.WebhookMessage],
                                                delete_after=None, **kwargs):
    """
    helper function to add `delete_after` support to WebhookMessage
    """
    if isinstance(msg, discord.WebhookMessage):
        async def wait_and_delete(msg):
            await asyncio.sleep(delete_after)
            await msg.delete()

        await msg.edit(**kwargs)  # WebhookMessage doesn't have a delete_after attribute!
        if delete_after:
            asyncio.create_task(wait_and_delete(msg))
    else:
        await msg.edit(**kwargs, delete_after=delete_after)


async def ensureduration(media, ctx: commands.Context):
    """
    ensures that media is under or equal to the config minimum frame count and fps
    :param media: media to trim
    :param ctx: discord context
    :return: processed media or original media, within config.max_frames
    """
    if await ctx.bot.is_owner(ctx.author):
        logger.debug(f"bot owner is exempt from duration checks.")
        return media
    if await mediatype(media) != "VIDEO":
        return media
    max_fps = config.max_fps if hasattr(config, "max_fps") else None
    fps = await get_frame_rate(media)
    if fps > max_fps:
        logger.debug(f"Capping FPS of {media} from {fps} to {max_fps}")
        media = await changefps(media, max_fps)
    # the function that splits frames actually has a vsync thing so this is more accurate to what's generated
    max_frames = config.max_frames if hasattr(config, "max_frames") else None
    fps = await get_frame_rate(media)
    try:
        dur = await get_duration(media)
    except Exception as e:
        dur = 0
        logger.debug(e)
    frames = int(fps * dur)
    if max_frames is None or frames <= max_frames:
        return media
    else:
        newdur = max_frames / fps
        tmsg = f"{config.emojis['warning']} input file is too long (~{frames} frames)! " \
               f"Trimming to {round(newdur, 1)}s (~{max_frames} frames)... "
        logger.debug(tmsg)
        msg = await ctx.reply(tmsg)
        media = await trim(media, newdur)
        try:
            await edit_msg_with_webhookmessage_polyfill(msg, delete_after=5, content=tmsg + "Done!")
        except discord.NotFound as e:
            logger.debug(e)
        return media


async def hasaudio(video):
    return bool(
        await run_command("ffprobe", "-i", video, "-show_streams", "-select_streams", "a", "-loglevel", "panic"))


async def forceaudio(video):
    """
    gives videos with no audio a silent audio stream
    :param video: file
    :return: video filename
    """
    if await hasaudio(video):
        return video
    else:
        outname = reserve_tempfile("mp4")
        await run_command("ffmpeg", "-hide_banner", "-i", video, "-f", "lavfi", "-i", "anullsrc", "-c:v", "png",
                          "-c:a", "aac", "-map", "0:v", "-map", "1:a", "-shortest", "-fps_mode", "vfr", outname)

        return outname


async def twopasscapvideo(video, maxsize: int, audio_bitrate=128000):
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
        if target_video_bitrate <= 0:
            raise NonBugError("Cannot fit video into Discord.")
        logger.info(f"trying to force {video} ({humanize.naturalsize(size)}) "
                    f"under {humanize.naturalsize(maxsize)} with tolerance {tolerance}. "
                    f"trying {humanize.naturalsize(target_video_bitrate / 8)}/s")
        pass1log = utils.tempfiles.temp_file_name()
        outfile = reserve_tempfile("mp4")
        await run_command('ffmpeg', '-y', '-i', video, '-c:v', 'h264', '-b:v', str(target_video_bitrate), '-pass', '1',
                          '-f', 'mp4', '-passlogfile', pass1log,
                          'NUL' if sys.platform == "win32" else "/dev/null")
        await run_command('ffmpeg', '-i', video, '-c:v', 'h264', '-b:v', str(target_video_bitrate), '-pass', '2',
                          '-passlogfile', pass1log, '-c:a', 'aac', '-b:a', str(audio_bitrate), "-f", "mp4", "-movflags",
                          "+faststart", outfile)
        # log files are pass1log-N.log and pass1log-N.log.mbtree where N is an int, easiest to just glob them all
        for f in glob.glob(pass1log + "*"):
            reserve_tempfile(f)
        if (size := os.path.getsize(outfile)) < maxsize:

            logger.info(f"successfully created {humanize.naturalsize(size)} video!")
            return outfile
        else:

            logger.info(f"tolerance {tolerance} failed. output is {humanize.naturalsize(size)}")
    raise NonBugError(f"Unable to fit {video} within {humanize.naturalsize(maxsize)}")


async def intelligentdownsize(media, maxsize: int):
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
        resized = await resize(media, new_w, new_h, delete_orig=False)
        if (size := os.path.getsize(resized)) < maxsize:
            logger.info(f"successfully created {humanize.naturalsize(size)} media!")
            return resized
        else:
            logger.info(f"tolerance {tolerance} failed. output is {humanize.naturalsize(size)}")


async def assurefilesize(media, re_encode=True):
    """
    compresses files to fit within config set discord limit

    :param re_encode: try to reencode media?
    :param media: media
    :return: filename of fixed media if it works, False if it still is too big.
    """
    if not media:
        raise ReturnedNothing(f"assurefilesize() was passed no media.")
    mt = await mediatype(media)
    size = os.path.getsize(media)
    if size > config.way_too_big_size:
        raise NonBugError(f"Resulting file is {humanize.naturalsize(size)}. "
                          f"Aborting upload since resulting file is over "
                          f"{humanize.naturalsize(config.way_too_big_size)}")
    if size < config.file_upload_limit:
        return media
    if mt == "VIDEO":
        # fancy ffmpeg based video thing
        return await twopasscapvideo(media, config.file_upload_limit)
    elif mt in ["IMAGE", "GIF"]:
        # file size should be roughly proportional to # of pixels so we can work with that :3
        return await intelligentdownsize(media, config.file_upload_limit)
    else:
        raise NonBugError(f"File is too big to upload.")


async def mp4togif(mp4):
    outname = reserve_tempfile("gif")
    await run_command("ffmpeg", "-i", mp4,
                      # prevent partial frames, makes filesize worse but fixes issues with transparency
                      "-gifflags", "-transdiff",
                      "-vf",
                      # cap fps because gifs are wackyyyyyy
                      "fps=fps='min(source_fps,50)',"
                      # make and use nice palette
                      "split[s0][s1];[s0]palettegen=reserve_transparent=1[p];[s1][p]paletteuse=bayer",
                      # i fucking hate gifs so much man
                      "-fps_mode", "vfr",
                      outname)

    return outname


async def reencode(mp4):  # reencodes mp4 as libx264 since the png format used cant be played by like literally anything
    assert (mt := await mediatype(mp4)) in ["VIDEO", "GIF"], f"file {mp4} with type {mt} passed to reencode()"
    # only reencode if need to ;)
    vcodec, acodec = await va_codecs(mp4)
    vcode = ["copy"] if vcodec == "h264" else ["libx264", "-pix_fmt", "yuv420p", "-vf",
                                               "scale=ceil(iw/2)*2:ceil(ih/2)*2"]
    acode = ["copy"] if acodec == "aac" else ["aac", "-q:a", "2"]
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", mp4, "-c:v", *vcode, "-c:a", *acode,
                      "-max_muxing_queue_size", "9999", "-movflags", "+faststart", outname)

    return outname


async def allreencode(file):
    mt = await mediatype(file)
    if mt == "IMAGE":
        return await mediatopng(file)
    elif mt == "VIDEO":
        return await reencode(file)
    elif mt == "AUDIO":
        outname = reserve_tempfile("mp3")
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
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", gif, "-movflags", "faststart", "-pix_fmt", "yuv420p",
                      "-sws_flags", "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf",
                      "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-fps_mode", "vfr", outname)

    return outname


async def toaudio(media):
    """
    converts video to only audio
    :param media: video or audio ig
    :return: aac
    """
    name = reserve_tempfile("mp3")  # discord wont embed aac
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-vn", name)

    return name


async def mediatopng(media):
    """
    converts media to png
    :param media: media
    :return: png
    """
    outname = reserve_tempfile("png")
    await run_command("ffmpeg", "-hide_banner", "-i", media, "-frames:v", "1", "-c:v", "png", "-pix_fmt", "yuva420p",
                      outname)

    return outname


# https://stackoverflow.com/questions/65728616/how-to-get-ffmpeg-to-consistently-apply-speed-effect-to-first-few-frames
async def speed(file, sp):
    """
    changes speed of media
    :param file: media
    :param sp: speed to multiply media by
    :return: processed media
    """

    mt = await mediatype(file)
    if mt == "AUDIO":
        outname = reserve_tempfile("mp3")
        duration = await get_duration(file)
        await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter_complex",
                          f"{expanded_atempo(sp)}", "-t", str(duration / float(sp)), "-c:a", "libmp3lame", outname)
    else:
        outname = reserve_tempfile("mp4")
        fps = await get_frame_rate(file)
        duration = await get_duration(file)
        await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-filter_complex",
                          f"[0:v]setpts=PTS/{sp},fps={fps}[v];[0:a]{expanded_atempo(sp)}[a]",
                          "-map", "[v]", "-map", "[a]", "-t", str(duration / float(sp)), "-c:v", "png", "-fps_mode",
                          "vfr", outname)
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
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-vf", "reverse", "-af", "areverse",
                      "-c:v", "png", "-fps_mode", "vfr", outname)

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
    outname = reserve_tempfile("mp4")
    #
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter:v", f"random=frames={frames}",
                      "-c:v", "png", "-fps_mode", "vfr", outname)

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
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-crf", str(crf), "-c:a", "aac", "-b:a",
                      f"{qa}k", "-fps_mode", "vfr", outname)

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
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-r", str(fps), "-c:a", "copy", "-c:v", "png",
                      outname)
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
    outname = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf", f"negate", "-c:v", "png", "-fps_mode", "vfr",
                      outname)

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
        outname = reserve_tempfile("png")
    else:
        outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf",
                      "pad=width='max(iw,ih)':height='max(iw,ih)':x='(ih-iw)/2':y='(iw-ih)/2':color=white", "-c:v",
                      "png", "-fps_mode", "vfr", outname)

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
    outname = reserve_tempfile("gif")
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
    outname = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-stream_loop", str(loop), "-i", file, "-vcodec", "copy", outname)

    return outname


async def imageaudio(file0, file1):
    """
    combines an image and an audio file into a video
    :param files: [image, audio]
    :return: video
    """
    audio = file1
    image = file0
    outname = reserve_tempfile("mp4")
    duration = await get_duration(audio)  # it is a couple seconds too long without it :(
    await run_command("ffmpeg", "-hide_banner", "-i", audio, "-loop", "1", "-i", image, "-pix_fmt", "yuv420p", "-vf",
                      "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-c:a", "aac", "-shortest", "-t",
                      str(duration), outname)

    return outname


async def addaudio(file0, file1, loops=0):
    """
    adds audio to media
    :param files: [media, audiotoadd]
    :return: video or audio
    """
    # TODO: this can trim media short? not sure why...
    audio = file1
    media = file0
    mt = await mediatype(media)
    if mt == "IMAGE":
        # no use reinventing the wheel
        return await imageaudio(file0, file1)
    elif mt == "GIF":
        # GIF case is like imageaudio, but with stream_loop instead of loop.
        outname = reserve_tempfile("mp4")
        if loops >= 0:
            # if the gif is set to loop a fixed amount of times, cut out at the longest stream.
            await run_command("ffmpeg", "-hide_banner", "-i", audio, "-stream_loop", str(loops), "-i", media,
                              "-pix_fmt", "yuv420p", "-vf",
                              "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-c:a", "aac", "-q:a", "2",
                              "-fps_mode", "vfr",
                              outname)
        else:
            # if it's set to loop infinitely, cut out when the audio ends.
            duration = await get_duration(audio)  # it is a couple seconds too long without it :(
            await run_command("ffmpeg", "-hide_banner", "-i", audio, "-stream_loop", str(loops), "-i", media,
                              "-pix_fmt", "yuv420p", "-vf",
                              "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-c:a", "aac", "-q:a", "2",
                              "-fps_mode", "vfr",
                              "-shortest", "-t", str(duration), outname)
    else:
        media = await forceaudio(media)
        # yes, qa works backwards on aac vs mp3. no, i dont know why.
        if mt == "AUDIO":
            outname = reserve_tempfile("mp3")
            audiosettings = ["-c:a", "libmp3lame", "-q:a", "0"]
        else:
            outname = reserve_tempfile("mp4")
            audiosettings = ["-c:a", "aac", "-q:a", "2"]
        await run_command("ffmpeg", "-i", media, "-i", audio, "-max_muxing_queue_size", "4096", "-filter_complex",
                          "[0:a][1:a]amix=inputs=2:dropout_transition=100000:duration=longest[a];[a]volume=2[a]",
                          "-map", "0:v?", "-map", "[a]", *audiosettings, outname)

    return outname


async def concatv(file0, file1):
    """
    concatenates 2 videos
    :param files: [video, video]
    :return: combined video
    """
    video0 = await forceaudio(file0)
    fixedvideo0 = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "png", "-c:a", "copy", "-ar", "48000",
                      "-max_muxing_queue_size", "4096", "-fps_mode", "vfr", fixedvideo0)
    video1 = await forceaudio(file1)
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = reserve_tempfile("mp4")

    # https://superuser.com/a/1136305/1001487
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf",
                      f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:-2:-2:color=black", "-c:v",
                      "png", "-c:a", "copy", "-ar", "48000", "-fps_mode", "vfr", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)

    concatdemuxer = reserve_tempfile("txt")
    with open(concatdemuxer, "w+") as f:
        f.write(f"file '{fixedvideo0}'\nfile '{fixedfixedvideo1}'")
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-safe", "0", "-f", "concat", "-i", concatdemuxer, "-c:v", "png",
                      "-c:a", "copy", outname)

    if (await mediatype(file0)) == "GIF" and (await mediatype(file1)) == "GIF":
        outname = await mp4togif(outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1, concatdemuxer]:
    #     os.remove(file)
    return outname


async def naive_vstack(file0, file1):
    """
    stacks media assuming files are same width
    """
    mts = await asyncio.gather(mediatype(file0), mediatype(file1))
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        return await processing.common.run_parallel(processing.vips.vipsutils.naive_stack, file0, file1)
    else:
        out = reserve_tempfile("mp4")
        await run_command("ffmpeg", "-i", file0, "-i", file1, "-filter_complex",
                          "[0]format=pix_fmts=yuva420p[0f];"
                          "[1]format=pix_fmts=yuva420p[1f];"
                          "[0f][1f]vstack=inputs=2", "-c:v", "png", "-fs", config.max_temp_file_size, "-fps_mode",
                          "vfr", out)

        if "VIDEO" in mts:
            return out
        else:  # gif and image only
            return await mp4togif(out)
        # return await processing.vips.vstack(file0, file1)


async def stack(file0, file1, style):
    """
    stacks media
    :param files: [media, media]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
    mts = [await mediatype(file0), await mediatype(file1)]
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":  # easier to just make this an edge case
        return await processing.common.run_parallel(processing.vips.vipsutils.stack, file0, file1, style)
    if style == 'hstack':
        scaling_logic = "scale2ref=oh*mdar:ih"
    else:
        scaling_logic = "scale2ref=iw:ow/mdar"

    mixaudio = all(await asyncio.gather(hasaudio(file0), hasaudio(file1)))
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-hide_banner", "-i", file0, "-i", file1,
                      "-filter_complex",
                      f"[0]setpts=PTS-STARTPTS,format=yuva420p[0v];"
                      f"[1]setpts=PTS-STARTPTS,format=yuva420p[1v];"
                      # rescale stacked
                      f"[1v][0v]{scaling_logic}[b][a];"
                      # stack
                      f"[a][b]{'h' if style == 'hstack' else 'v'}stack=inputs=2" + \
                      # mix audio
                      (f";amix=inputs=2:dropout_transition=0" if mixaudio else ""),
                      "-c:v", "png", "-c:a", "aac", "-q:a", "2", "-fps_mode", "vfr", outname)

    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    if mts[0] != "VIDEO" and mts[1] != "VIDEO":  # one or more gifs and no videos
        outname = await mp4togif(outname)
    return outname


async def overlay(file0, file1, alpha: float, mode: str = 'overlay'):
    """
    stacks media
    :param file0: file 0
    :param file1: file 1
    :param alpha: opacity of top media, 0-1
    :param mode: blend mode
    :return: processed media
    """
    assert mode in ['overlay', 'add']
    assert 0 <= alpha <= 1
    mts = [await mediatype(file0), await mediatype(file1)]

    outname = reserve_tempfile("mp4")
    blendlogic = ""
    if mode == "overlay":
        blendlogic = f"overlay"
    elif mode == "add":
        blendlogic = f"blend=all_mode='addition'"

    mixaudio = all(await asyncio.gather(hasaudio(file0), hasaudio(file1)))

    await run_command("ffmpeg", "-hide_banner", "-i", file0, "-i", file1, "-filter_complex",
                      # clean inputs
                      f"[0]setpts=PTS-STARTPTS,format=yuva420p[0v];"
                      f"[1]setpts=PTS-STARTPTS,format=yuva420p,"
                      # set alpha
                      f"colorchannelmixer=aa={alpha}[1v];"
                      # rescale overlay
                      f"[1v][0v]scale2ref[b][a];"
                      # blend
                      f"[a][b]{blendlogic}" + \
                      # mix audio
                      (f";amix=inputs=2:dropout_transition=0" if mixaudio else ""),
                      "-c:v", "png", "-c:a", "aac", "-q:a", "2", "-fps_mode", "vfr", outname)

    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        outname = await mediatopng(outname)
    # one or more gifs and no videos
    elif mts[0] != "VIDEO" and mts[1] != "VIDEO":
        outname = await mp4togif(outname)
    return outname


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
    out = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-t", str(length), "-ss", str(start), "-c:v", "png",
                      "-fps_mode", "vfr", out)

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
    if await ctx.bot.is_owner(ctx.author):
        logger.debug(f"bot owner is exempt from downsize checks")
        return file
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
    out = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-i", file, "-vf", types[rottype] + ",format=yuva420p", "-c:v", "png", "-fps_mode",
                      "vfr", out)

    if mt == "GIF":
        out = await mp4togif(out)
    return out


async def volume(file, vol):
    mt = await mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4"
    }
    out = reserve_tempfile(exts[mt])
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
    out = reserve_tempfile(exts[mt])
    if mt == "AUDIO":
        audiosettings = ["-c:a", "libmp3lame", "-q:a", "0"]
    else:
        audiosettings = ["-c:a", "aac", "-q:a", "2", "-c:v", "copy"]

    await run_command("ffmpeg", "-i", file, "-af", f"vibrato=f={frequency}:d={depth}", "-strict", "-1", *audiosettings,
                      out)

    return out


async def pitch(file, p=12):
    mt = await mediatype(file)
    exts = {
        "AUDIO": "mp3",
        "VIDEO": "mp4"
    }
    out = reserve_tempfile(exts[mt])
    # http://www.geekybob.com/post/Adjusting-Pitch-for-MP3-Files-with-FFmpeg
    asetrate = max(int(48000 * 2 ** (p / 12)), 1)
    atempo = 2 ** (-p / 12)
    logger.debug((p, asetrate, atempo))
    af = f"asetrate=r={asetrate},{expanded_atempo(atempo)},aresample=48000"
    if mt == "AUDIO":
        audiosettings = ["libmp3lame", "-q:a", "0"]
    else:
        audiosettings = ["aac", "-q:a", "2", "-c:v", "copy"]
    await run_command("ffmpeg", "-i", file, "-ar", "48000", "-af", af, "-strict", "-1", "-c:a", *audiosettings, out)

    return out


async def resize(image, width, height, delete_orig=True):
    """
    resizes image

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
    out = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-i", image, "-pix_fmt", "yuva420p", "-max_muxing_queue_size", "9999", "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp+bitexact",
                      "-vf", f"scale='{width}:{height}',setsar=1:1", "-c:v", "png", "-pix_fmt", "yuva420p", "-c:a",
                      "copy", "-fps_mode", "vfr", out)

    if mt == "GIF":
        out = await mp4togif(out)
    elif mt == "VIDEO":
        out = await reencode(out)
    return out


async def hue(file, h: float):
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    mt = await mediatype(file)
    out = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-i", file, "-vf", f"hue=h={h},format=yuva420p", "-c:v", "png", "-fps_mode", "vfr", out)

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
    out = reserve_tempfile(exts[mt])
    # https://stackoverflow.com/a/3380739/9044183
    r, g, b = map(lambda x: x / 255, col.to_rgb())
    await run_command("ffmpeg", "-i", file, "-vf",
                      f"hue=s=0,"  # make grayscale
                      f"lutrgb=r=val*{r}:g=val*{g}:b=val*{b}:a=val,"  # basically set white to our color 
                      f"format=yuva420p", "-c:v", "png", "-fps_mode", "vfr", out)

    if mt == "GIF":
        out = await mp4togif(out)
    return out


async def epicbirthday(text: str):
    out = reserve_tempfile("mp4")
    birthdaytext = await tts(text)
    nameimage = reserve_tempfile("png")
    raise NotImplementedError
    # TODO: replace with modern caption
    # await renderpool.renderpool.submit(captionfunctions.epicbirthdaytext, text, nameimage)
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
    outname = reserve_tempfile(exts[mt])
    await run_command('ffmpeg', '-i', file, '-filter:v', f'crop={w}:{h}:{x}:{y}', "-c:v", "png", outname)
    if mt == "GIF":
        outname = await mp4togif(outname)

    return outname


async def trim_top(file, trim_size):
    mt = await mediatype(file)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outname = reserve_tempfile(exts[mt])
    await run_command('ffmpeg', '-i', file, '-filter:v', f'crop=out_h=ih-{trim_size}:y={trim_size}', "-c:v", "png",
                      "-fps_mode", "vfr",
                      outname)

    if mt == "GIF":
        outname = await mp4togif(outname)
    return outname


async def toapng(video):
    outname = reserve_tempfile("png")
    await run_command("ffmpeg", "-i", video, "-f", "apng", "-fps_mode", "vfr", outname)

    return outname
    # ffmpeg method, removes dependence on apngasm but bigger and worse quality
    # outname = reserve_tempfile("png")
    # await run_command("ffmpeg", "-i", video, "-f", "apng", "-plays", "0", outname)


async def motivate(media, captions: typing.Sequence[str]):
    text = await processing.common.run_parallel(processing.vips.caption.motivate_text, captions,
                                                processing.vips.vipsutils.ImageSize(*await get_resolution(media)))
    mt = await mediatype(media)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outfile = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-i", media, "-i", text, "-filter_complex",
                      "[0]pad=w=iw+(iw/60):h=ih+(iw/60):x=(iw/120):y=(iw/120):color=black[0p0];"
                      "[0p0]pad=w=iw+(iw/30):h=ih+(iw/30):x=(iw/60):y=(iw/60):color=white[0p1];"
                      "[0p1]pad=w=iw:h=ih+(iw/30):x=0:y=0[0p2];"
                      "[0p2][1]vstack=inputs=2[s];"
                      "[s]pad=w=iw+(iw/5):h=ih+(iw/10)+(iw/30):x=(iw/10):y=(iw/10):color=black",
                      "-c:v", "png", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)

    if mt == "GIF":
        outfile = await mp4togif(outfile)
    return outfile


async def naive_overlay(im1, im2):
    mts = [await mediatype(im1), await mediatype(im2)]
    outname = reserve_tempfile("mp4")
    await run_command("ffmpeg", "-i", im1, "-i", im2, "-filter_complex", "overlay", "-c:v", "png", "-fs",
                      config.max_temp_file_size, "-fps_mode", "vfr", outname)
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        outname = await mediatopng(outname)
    # one or more gifs and no videos
    elif mts[0] != "VIDEO" and mts[1] != "VIDEO":
        outname = await mp4togif(outname)

    return outname


async def freezemotivateaudio(video, audio, *caption):
    """
    ends video with motivate caption
    :param video: video
    :param audio: audio
    :param caption: caption to pass to motivate()
    :return: processed media
    """
    lastframe = await frame_n(video, -1)
    clastframe = await motivate(lastframe, caption)
    freezeframe = await imageaudio(clastframe, audio)
    final = await concatv(video, freezeframe)
    return final


async def freezemotivate(video, *caption):
    return await freezemotivateaudio(video, "rendering/what.mp3", *caption)


async def round_corners(media, border_radius=10):
    mt = await mediatype(media)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outfile = reserve_tempfile(exts[mt])
    # https://stackoverflow.com/a/62400465/9044183
    await run_command("ffmpeg", "-i", media, "-filter_complex",
                      f"format=yuva420p,"
                      f"geq=lum='p(X,Y)':a='"
                      f"if(gt(abs(W/2-X),W/2-{border_radius})*gt(abs(H/2-Y),"
                      f"H/2-{border_radius}),"
                      f"if(lte(hypot({border_radius}-(W/2-abs(W/2-X)),"
                      f"{border_radius}-(H/2-abs(H/2-Y))),"
                      f"{border_radius}),255,0),255)'",
                      "-c:v", "png", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)

    return outfile


async def twitter_caption(media, captions, dark=True):
    mt = await mediatype(media)
    # get_resolution call is separate so we can use for border radius
    width, height = await get_resolution(media)
    # get text
    text = await processing.common.run_parallel(processing.vips.caption.twitter_text, captions,
                                                processing.vips.vipsutils.ImageSize(width, height), dark)
    border_radius = width * (16 / 500)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outfile = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-i", media, "-i", text, "-filter_complex",
                      # round corners
                      # https://stackoverflow.com/a/62400465/9044183
                      # copied from round_corners here for efficiency as 1 ffmpeg stream
                      f"[0]format=yuva420p,"
                      f"geq=lum='p(X,Y)':a='"
                      f"if(gt(abs(W/2-X),W/2-{border_radius})*gt(abs(H/2-Y),"
                      f"H/2-{border_radius}),"
                      f"if(lte(hypot({border_radius}-(W/2-abs(W/2-X)),"
                      f"{border_radius}-(H/2-abs(H/2-Y))),"
                      f"{border_radius}),255,0),255)'[media];"
                      # add padding around media
                      f"[media]pad=w=iw+(iw*(12/500)*2):"
                      f"h=ih+(iw*(12/500)):"
                      f"x=(iw*(12/500)):"
                      f"y=0:color=#00000000[media];"
                      # stack
                      f"[1][media]vstack=inputs=2[stacked];"
                      # add background
                      f"[stacked]split=2[bg][fg];"
                      f"[bg]drawbox=c={'#15202b' if dark else '#ffffff'}:replace=1:t=fill[bg];"
                      f"[bg][fg]overlay=format=auto",
                      "-c:v", "png", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)

    if mt == "GIF":
        outfile = await mp4togif(outfile)
    return outfile


async def trollface(media):
    mt = await mediatype(media)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outfile = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-i", media,
                      "-i", "rendering/images/trollface/bottom.png",
                      "-i", "rendering/images/trollface/mask.png",
                      "-i", "rendering/images/trollface/top.png",
                      "-filter_complex",
                      # resize input media
                      "[0]scale=500:407[media];"
                      # mask input media
                      "[2:v]alphaextract[mask];"
                      "[media][mask]alphamerge[media];"
                      # overlay bottom and top
                      "[1:v][media]overlay[media];"
                      "[media][3:v]overlay",
                      "-c:v", "png", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)

    if mt == "GIF":
        outfile = await mp4togif(outfile)
    return outfile


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


async def deepfry(media, brightness, contrast, sharpness, saturation, noise):
    mt = await mediatype(media)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outfile = reserve_tempfile(exts[mt])

    await run_command("ffmpeg", "-i", media, "-vf",
                      f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation},"
                      f"unsharp=luma_msize_x=7:luma_msize_y=7:luma_amount={sharpness},"
                      f"noise=alls={noise}", "-fps_mode", "vfr", outfile)

    if mt == "GIF":
        outfile = await mp4togif(outfile)

    return outfile


async def give_me_your_phone_now(media):
    mt = await mediatype(media)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outfile = reserve_tempfile(exts[mt])

    await run_command("ffmpeg", "-i", media, "-i", "rendering/images/givemeyourphone.jpg", "-filter_complex",
                      # fit insize 200x200 box
                      "[0]scale=w=200:h=200:force_original_aspect_ratio=decrease[rescaled];"
                      # overlay centered at expected position
                      "[1][rescaled]overlay=x=150+((200-overlay_w)/2):y=350+((200-overlay_h)/2)", "-fps_mode", "vfr",
                      outfile)

    if mt == "GIF":
        outfile = await mp4togif(outfile)

    return outfile


async def speech_bubble(media, position: typing.Literal["top", "bottom"] = "top",
                        color: typing.Literal["transparent", "white", "black"] = "transparent"):
    mt = await mediatype(media)
    exts = {
        "VIDEO": "mp4",
        "GIF": "mp4",
        "IMAGE": "png"
    }
    outfile = reserve_tempfile(exts[mt])

    if color == "transparent":
        await run_command("ffmpeg", "-i", media, "-i", "rendering/images/speechbubble.png",
                          "-filter_complex",
                          # mask input media
                          "[1:v][0:v]scale2ref[mask][media];"
                          f"[mask]{'vflip,' if position == 'bottom' else ''}format=yuva420p,alphaextract,negate[mask2];"
                          "[media][mask2]alphamerge",
                          "-c:v", "png", "-c:a", "copy", "-fps_mode", "vfr", outfile)
    else:
        mask_filters = []
        if position == "bottom":
            mask_filters.append("vflip")
        if color == "black":
            mask_filters.append("negate")
        if mask_filters:
            mask_filter = f"[mask]{','.join(mask_filters)}[mask];"
        else:
            mask_filter = ""

        await run_command("ffmpeg", "-i", media, "-i", "rendering/images/speechbubble.png",
                          "-filter_complex",
                          # mask input media
                          "[1:v][0:v]scale2ref[mask][media];"
                          f"{mask_filter}"
                          "[media][mask]overlay",
                          "-c:v", "png", "-c:a", "copy", "-fps_mode", "vfr", outfile)
    if mt == "GIF":
        outfile = await mp4togif(outfile)

    return outfile
