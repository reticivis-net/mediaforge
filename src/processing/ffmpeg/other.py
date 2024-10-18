import math

import discord
import asyncio
from core.clogs import logger
import typing

import processing.common
from processing.ffmpeg.conversion import mediatopng
import processing.vips as vips
from processing.ffmpeg.ffprobe import mediatype, get_duration, get_frame_rate, count_frames, get_resolution, hasaudio
from processing.ffmpeg.ffutils import gif_output, expanded_atempo, forceaudio, dual_gif_output, scale2ref, changefps, \
    resize
from utils.tempfiles import reserve_tempfile
from processing.common import run_command, NonBugError


@gif_output
async def speed(file, sp):
    """
    changes speed of media
    :param file: media
    :param sp: speed to multiply media by
    :return: processed media
    """

    # https://stackoverflow.com/questions/65728616/how-to-get-ffmpeg-to-consistently-apply-speed-effect-to-first-few-frames
    mt = await mediatype(file)
    outname = reserve_tempfile("mkv")
    if mt == "AUDIO":
        duration = await get_duration(file)
        await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter_complex",
                          f"{expanded_atempo(sp)}", "-t", str(duration / float(sp)), "-c:a", "flac", outname)
    else:
        fps = await get_frame_rate(file)
        duration = await get_duration(file)
        await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-filter_complex",
                          f"[0:v]setpts=PTS/{sp},fps={fps}[v];[0:a]{expanded_atempo(sp)}[a]",
                          "-map", "[v]", "-map", "[a]", "-t", str(duration / float(sp)), "-c:v", "ffv1", "-c:a", "flac",
                          "-fps_mode",
                          "vfr", outname)
        if await count_frames(outname) < 2:
            raise NonBugError("Output file has less than 2 frames. Try reducing the speed.")

    return outname


@gif_output
async def reverse(file):
    """
    reverses media (-1x speed)
    :param file: media
    :return: procesed media
    """
    outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-vf", "reverse", "-af", "areverse",
                      "-c:v", "ffv1", "-fps_mode", "vfr", outname)
    return outname


@gif_output
async def random(file, frames: int):
    """
    shuffle frames
    :param file: media
    :param frames: number of frames in internal cache
    :return: procesed media
    """
    outname = reserve_tempfile("mkv")
    #
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-filter:v", f"random=frames={frames}",
                      "-c:v", "ffv1", "-fps_mode", "vfr", outname)
    return outname


@gif_output
async def quality(file, crf, qa):
    """
    changes quality of videos/gifs with ffmpeg compression
    :param file: media
    :param crf: FFmpeg CRF param
    :param qa: audio bitrate
    :return: processed media
    """
    outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-i", await forceaudio(file), "-crf", str(crf), "-c:a", "aac", "-b:a",
                      f"{qa}k", "-fps_mode", "vfr", outname)

    # png cannot be supported here because crf and qa are libx264 params lmao
    return outname


@gif_output
async def invert(file):
    """
    inverts colors
    :param file: media
    :return: processed media
    """
    outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf", f"negate", "-c:v", "ffv1", "-fps_mode", "vfr",
                      outname)
    return outname


@gif_output
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
        outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-i", file, "-vf",
                      "pad=width='max(iw,ih)':height='max(iw,ih)':x='(ih-iw)/2':y='(iw-ih)/2':color=white", "-c:v",
                      "ffv1", "-fps_mode", "vfr", outname)
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
        "VIDEO": "mkv",
        "GIF": "gif"
    }
    outname = reserve_tempfile(exts[mt])
    await run_command("ffmpeg", "-hide_banner", "-stream_loop", str(loop), "-i", file, "-vcodec", "copy", outname)

    return outname


async def imageaudio(image, audio):
    """
    combines an image and an audio file into a video
    :param files: [image, audio]
    :return: video
    """
    image = await mediatopng(image)  # -loop 1 only works with proper images
    outname = reserve_tempfile("mkv")
    duration = await get_duration(audio)  # it is a couple seconds too long without it :(
    await run_command("ffmpeg", "-hide_banner", "-i", audio, "-loop", "1", "-i", image, "-pix_fmt", "yuv420p", "-vf",
                      "crop=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "ffv1", "-c:a", "flac", "-shortest", "-t",
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
        outname = reserve_tempfile("mkv")
        if loops >= 0:
            # if the gif is set to loop a fixed amount of times, cut out at the longest stream.
            await run_command("ffmpeg", "-hide_banner", "-i", audio, "-stream_loop", str(loops), "-i", media,
                              "-c:v", "ffv1", "-c:a", "flac",
                              "-fps_mode", "vfr",
                              outname)
        else:
            # if it's set to loop infinitely, cut out when the audio ends.
            duration = await get_duration(audio)  # it is a couple seconds too long without it :(
            await run_command("ffmpeg", "-hide_banner", "-i", audio, "-stream_loop", str(loops), "-i", media,
                              "-c:v", "ffv1", "-c:a", "flac",
                              "-fps_mode", "vfr",
                              "-shortest", "-t", str(duration), outname)
    else:
        media = await forceaudio(media)
        outname = reserve_tempfile("mkv")
        await run_command("ffmpeg", "-i", media, "-i", audio, "-max_muxing_queue_size", "4096", "-filter_complex",
                          "[0:a][1:a]amix=inputs=2:dropout_transition=100000:duration=longest[a];[a]volume=2[a]",
                          "-map", "0:v?", "-map", "[a]", "-c:v", "copy", "-c:a", "flac", outname)

    return outname


@dual_gif_output
async def concatv(file0, file1):
    """
    concatenates 2 videos
    :param files: [video, video]
    :return: combined video
    """
    video0 = file0  # await forceaudio(file0)
    fixedvideo0 = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-i", video0, "-c:v", "ffv1", "-c:a", "copy", "-ar",
                      "48000",
                      "-max_muxing_queue_size", "4096", "-fps_mode", "vfr", fixedvideo0)
    video1 = file1  # await forceaudio(file1)
    w, h = await get_resolution(video0)
    fps = await get_frame_rate(video0)
    fixedvideo1 = reserve_tempfile("mkv")

    # https://superuser.com/a/1136305/1001487
    await run_command("ffmpeg", "-hide_banner", "-i", video1, "-sws_flags",
                      "spline+accurate_rnd+full_chroma_int+full_chroma_inp", "-vf",
                      f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:-2:-2:color=black", "-c:v",
                      "ffv1", "-c:a", "copy", "-ar", "48000", "-fps_mode", "vfr", fixedvideo1)
    fixedfixedvideo1 = await changefps(fixedvideo1, fps)

    concatdemuxer = reserve_tempfile("txt")
    with open(concatdemuxer, "w+") as f:
        f.write(f"file '{fixedvideo0}'\nfile '{fixedfixedvideo1}'")
    outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-safe", "0", "-f", "concat", "-i", concatdemuxer, "-c:v", "ffv1",
                      "-c:a", "copy", outname)
    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1, concatdemuxer]:
    #     os.remove(file)
    return outname


@dual_gif_output
async def stack(file0, file1, style):
    """
    stacks media
    :param files: [media, media]
    :param style: "hstack" or "vstack"
    :return: processed media
    """
    mts = [await mediatype(file0), await mediatype(file1)]
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":  # easier to just make this an edge case
        # sometimes can be ffv1 mkvs with 1 frame, which vips has no idea what to do with
        file0, file1 = await asyncio.gather(mediatopng(file0), mediatopng(file1))
        return await processing.common.run_parallel(vips.vipsutils.stack, file0, file1, style)
    # file0, file1 = await repeat_shorter_video(file0, file1)  # scale2ref is fucky
    w0, h0 = await get_resolution(file0)
    w1, h1 = await get_resolution(file1)
    aspect1 = w1 / h1
    if style == 'hstack':
        # scaling_logic = "scale2ref=oh*mdar:ih"
        file1 = await resize(file1, h0 * aspect1, h0)
    else:
        # scaling_logic = "scale2ref=iw:ow/mdar"
        file1 = await resize(file1, w0, w0 / aspect1)

    mixaudio = all(await asyncio.gather(hasaudio(file0), hasaudio(file1)))
    outname = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-hide_banner", "-i", file0, "-i", file1,
                      "-filter_complex",
                      f"[0]setpts=PTS-STARTPTS,format=rgba[0v];"
                      f"[1]setpts=PTS-STARTPTS,format=rgba[1v];"
                      # stack
                      f"[0v][1v]{'h' if style == 'hstack' else 'v'}stack=inputs=2" + \
                      # mix audio
                      (f";amix=inputs=2:dropout_transition=0" if mixaudio else ""),
                      "-c:v", "ffv1", "-c:a", "flac", "-fps_mode", "vfr", outname)

    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    return outname


@dual_gif_output
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

    outname = reserve_tempfile("mkv")
    blendlogic = ""
    if mode == "overlay":
        blendlogic = f"overlay=format=auto"
    elif mode == "add":
        blendlogic = f"blend=all_mode='addition'"

    mixaudio = all(await asyncio.gather(hasaudio(file0), hasaudio(file1)))
    file0 = await scale2ref(file0, file1)  # scale2ref is fucky
    await run_command("ffmpeg", "-hide_banner", "-i", file0, "-i", file1, "-filter_complex",
                      # clean inputs
                      f"[0]setpts=PTS-STARTPTS,format=rgba[0v];"
                      f"[1]setpts=PTS-STARTPTS,format=rgba,"
                      # set alpha
                      f"colorchannelmixer=aa={alpha}[1v];"
                      # blend
                      f"[0v][1v]{blendlogic}" + \
                      # mix audio
                      (f";amix=inputs=2:dropout_transition=0" if mixaudio else ""),
                      "-c:v", "ffv1", "-c:a", "flac", "-fps_mode", "vfr", outname)

    # for file in [video0, video1, fixedvideo1, fixedvideo0, fixedfixedvideo1]:
    #     os.remove(file)
    if mts[0] == "IMAGE" and mts[1] == "IMAGE":
        outname = await mediatopng(outname)
    return outname


@gif_output
async def rotate(file, rottype):
    types = {  # command input to ffmpeg vf
        "90": "transpose=1",
        "90ccw": "transpose=2",
        "180": "vflip,hflip",
        "vflip": "vflip",
        "hflip": "hflip"
    }
    out = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-i", file, "-vf", types[rottype] + ",format=rgba", "-c:v", "ffv1", "-fps_mode",
                      "vfr", out)
    return out


async def volume(file, vol):
    # TODO :test
    out = reserve_tempfile("mkv")
    # convert vol % to db
    # http://www.sengpielaudio.com/calculator-loudness.htm
    if vol > 0:
        vol = 10 * math.log(vol, 2)
        # for some reason aac has audio caps but libmp3lame works fine lol
        await run_command("ffmpeg", "-i", file, "-af", f"volume={vol}dB", "-strict", "-1", "-c:a", "flac", out)
    else:
        await run_command("ffmpeg", "-i", file, "-af", f"volume=0", "-strict", "-1", "-c:a", "flac", out)

    return out


async def vibrato(file, frequency=5, depth=0.5):  # https://ffmpeg.org/ffmpeg-filters.html#tremolo
    out = reserve_tempfile("mkv")

    await run_command("ffmpeg", "-i", file, "-af", f"vibrato=f={frequency}:d={depth}", "-strict", "-1",
                      "-c:v", "copy", "-c:a", "flac", out)

    return out


async def pitch(file, p=12):
    out = reserve_tempfile("mkv")
    # https://stackoverflow.com/a/71898956/9044183
    samplerate = await run_command("ffprobe", "-v", "error", "-select_streams", "a", "-of",
                                   "default=noprint_wrappers=1:nokey=1", "-show_entries", "stream=sample_rate", file)
    samplerate = int(samplerate)
    # http://www.geekybob.com/post/Adjusting-Pitch-for-MP3-Files-with-FFmpeg
    asetrate = max(int(samplerate * 2 ** (p / 12)), 1)
    atempo = 2 ** (-p / 12)
    logger.debug((p, asetrate, atempo))
    af = f"asetrate=r={asetrate},{expanded_atempo(atempo)},aresample={samplerate}"
    await run_command("ffmpeg", "-i", file, "-af", af, "-strict", "-1", "-c:v", "copy",
                      "-c:a", "flac", out)

    return out


@gif_output
async def hue(file, h: float):
    out = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-i", file, "-vf", f"hue=h={h},format=rgba", "-c:v", "ffv1", "-fps_mode", "vfr",
                      out)
    return out


@gif_output
async def tint(file, col: discord.Color):
    out = reserve_tempfile("mkv")
    # https://stackoverflow.com/a/3380739/9044183
    r, g, b = map(lambda x: x / 255, col.to_rgb())
    await run_command("ffmpeg", "-i", file, "-vf",
                      f"hue=s=0,"  # make grayscale
                      f"lutrgb=r=val*{r}:g=val*{g}:b=val*{b}:a=val,"  # basically set white to our color 
                      f"format=rgba", "-c:v", "ffv1", "-fps_mode", "vfr", out)
    return out


@gif_output
async def round_corners(media, border_radius=10):
    outfile = reserve_tempfile("mkv")
    # https://stackoverflow.com/a/62400465/9044183
    await run_command("ffmpeg", "-i", media, "-filter_complex",
                      f"format=rgba,"
                      f"geq=lum='p(X,Y)':a='"
                      f"if(gt(abs(W/2-X),W/2-{border_radius})*gt(abs(H/2-Y),"
                      f"H/2-{border_radius}),"
                      f"if(lte(hypot({border_radius}-(W/2-abs(W/2-X)),"
                      f"{border_radius}-(H/2-abs(H/2-Y))),"
                      f"{border_radius}),255,0),255)'",
                      "-c:v", "ffv1", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)
    return outfile


@gif_output
async def deepfry(media, brightness, contrast, sharpness, saturation, noise):
    outfile = reserve_tempfile("mkv")

    await run_command("ffmpeg", "-i", media, "-vf",
                      f"eq=contrast={contrast}:brightness={brightness}:saturation={saturation},"
                      f"unsharp=luma_msize_x=7:luma_msize_y=7:luma_amount={sharpness},"
                      f"noise=alls={noise}", "-fps_mode", "vfr", outfile)
    return outfile


@gif_output
async def speech_bubble(media, position: typing.Literal["top", "bottom"] = "top",
                        color: typing.Literal["transparent", "white", "black"] = "transparent"):
    mt = await mediatype(media)
    outfile = reserve_tempfile("mkv")

    bubble = await scale2ref("rendering/images/speechbubble.png", media)

    if color == "transparent":
        await run_command("ffmpeg", "-i", media, "-i", bubble,
                          "-filter_complex",
                          f"[1:v]format=rgba,{'vflip,' if position == 'bottom' else ''}alphaextract,negate[mask];"
                          "[0:v][mask]alphamerge",
                          "-c:v", "ffv1", "-c:a", "copy", "-fps_mode", "vfr", outfile)
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

        await run_command("ffmpeg", "-i", media, "-i", bubble,
                          "-filter_complex",
                          # mask input media
                          f"{mask_filter}"
                          "[0:v][1:v]overlay=format=auto",
                          "-c:v", "png" if mt == "IMAGE" else "ffv1", "-c:a", "copy", "-fps_mode", "vfr", outfile)
    return outfile
