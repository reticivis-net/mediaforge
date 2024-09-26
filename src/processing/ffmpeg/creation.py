import processing.common
from processing import vips as vips
from processing.common import tts, run_command
from processing.ffmpeg.ffutils import gif_output
from utils.tempfiles import reserve_tempfile


async def epicbirthday(text: str):
    out = reserve_tempfile("mkv")
    birthdaytext = await tts(text)
    nameimage = await processing.common.run_parallel(vips.creation.epicbirthdaytext, text)
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
                      f"[0:v][2:v] overlay=format=auto:enable='{'+'.join(betweens)}:x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2' [outv]",
                      # map to output
                      "-map", "[outv]",
                      "-map", "[outa]",
                      out)

    return out


@gif_output
async def trollface(media):
    outfile = reserve_tempfile("mkv")
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
                      "[1:v][media]overlay=format=auto[media];"
                      "[media][3:v]overlay=format=auto",
                      "-c:v", "ffv1", "-c:a", "copy", "-fps_mode", "vfr",
                      outfile)
    return outfile


@gif_output
async def give_me_your_phone_now(media):
    outfile = reserve_tempfile("mkv")
    await run_command("ffmpeg", "-i", media, "-i", "rendering/images/givemeyourphone.jpg", "-filter_complex",
                      # fit insize 200x200 box
                      "[0]scale=w=200:h=200:force_original_aspect_ratio=decrease[rescaled];"
                      # overlay centered at expected position
                      "[1][rescaled]overlay=format=auto:x=150+((200-overlay_w)/2):y=350+((200-overlay_h)/2)",
                      "-fps_mode", "vfr",
                      outfile)
    return outfile
