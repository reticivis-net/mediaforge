import typing

import processing.common
from processing import vips as vips
from processing.ffmpeg.ffprobe import get_resolution, frame_n
from processing.ffmpeg.ffutils import gif_output
from processing.ffmpeg.other import imageaudio, concatv
from utils.tempfiles import reserve_tempfile
from processing.common import run_command


@gif_output
async def motivate(media, captions: typing.Sequence[str]):
    text = await processing.common.run_parallel(vips.caption.motivate_text, captions,
                                                vips.vipsutils.ImageSize(*await get_resolution(media)))
    outfile = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-i", media, "-i", text, "-filter_complex",
                      "[0]pad=w=iw+(iw/60):h=ih+(iw/60):x=(iw/120):y=(iw/120):color=black[0p0];"
                      "[0p0]pad=w=iw+(iw/30):h=ih+(iw/30):x=(iw/60):y=(iw/60):color=white[0p1];"
                      "[0p1]pad=w=iw:h=ih+(iw/30):x=0:y=0[0p2];"
                      "[0p2][1]vstack=inputs=2[s];"
                      "[s]pad=w=iw+(iw/5):h=ih+(iw/10)+(iw/30):x=(iw/10):y=(iw/10):color=black",
                      "-c:v", "ffv1", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)
    return outfile


async def freezemotivateaudio(video, audio, *caption):
    """
    ends video with motivate caption
    :param video: video
    :param audio: audio
    :param caption: caption to pass to motivate()
    :return: processed media
    """
    # TODO: this shit dont work
    lastframe = await frame_n(video, -1)
    clastframe = await motivate(lastframe, caption)
    freezeframe = await imageaudio(clastframe, audio)
    final = await concatv(video, freezeframe)
    return final


async def freezemotivate(video, *caption):
    return await freezemotivateaudio(video, "rendering/what.mp3", *caption)


@gif_output
async def twitter_caption(media, captions, dark=True):
    # get_resolution call is separate so we can use for border radius
    width, height = await get_resolution(media)
    # get text
    text = await processing.common.run_parallel(vips.caption.twitter_text, captions,
                                                vips.vipsutils.ImageSize(width, height), dark)
    border_radius = width * (16 / 500)
    outfile = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-i", media, "-i", text, "-filter_complex",
                      # round corners
                      # https://stackoverflow.com/a/62400465/9044183
                      # copied from round_corners here for efficiency as 1 ffmpeg stream
                      f"[0]format=rgba,"
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
                      "-c:v", "ffv1", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)
    return outfile
