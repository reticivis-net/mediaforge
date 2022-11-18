import typing

import discord
from discord import app_commands
from discord.ext import commands

import config
import processing.ffmpeg
from core.process import process
from utils.common import prefix_function
import processing.vips.other
import processing.other


class Media(commands.Cog, name="Editing"):
    """
    Basic media editing/processing commands.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["copy", "nothing", "noop"])
    async def repost(self, ctx):
        """
        Reposts media as-is.

        :param ctx: discord context
        :mediaparam media: Any valid media.
        """
        await process(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]])

    @commands.hybrid_command(aliases=["clean", "remake"])
    async def reencode(self, ctx):
        """
        Re-encodes media.
        Videos become libx264 mp4s, audio files become libmp3lame mp3s, images become pngs.

        :param ctx: discord context
        :mediaparam media: A video, image, or audio file.
        """
        await process(ctx, processing.ffmpeg.allreencode, [["VIDEO", "IMAGE", "AUDIO"]])

    @commands.hybrid_command(aliases=["audioadd", "dub"])
    async def addaudio(self, ctx, loops: commands.Range[int, -1, 100] = -1):
        """
        Adds audio to media.

        :param ctx: discord context
        :param loops: Amount of times to loop a gif. -1 loops infinitely, 0 only once. Must be between -1 and 100.
        :mediaparam media: Any valid media file.
        :mediaparam audio: An audio file.
        """
        await process(ctx, processing.ffmpeg.addaudio, [["IMAGE", "GIF", "VIDEO", "AUDIO"], ["AUDIO"]], loops)

    @commands.hybrid_command()
    async def jpeg(self, ctx, strength: commands.Range[int, 1, 100] = 30,
                   stretch: commands.Range[int, 0, 40] = 20,
                   quality: commands.Range[int, 1, 95] = 10):
        """
        Makes media into a low quality jpeg

        :param ctx: discord context
        :param strength: amount of times to jpegify image. must be between 1 and 100.
        :param stretch: randomly stretch the image by this number on each jpegification. can cause strange effects
        on videos. must be between 0 and 40.
        :param quality: quality of JPEG compression. must be between 1 and 95.
        :mediaparam media: An image.
        """
        await process(ctx, processing.vips.other.jpeg, [["IMAGE"]], strength, stretch, quality, run_parallel=True)

    @commands.hybrid_command()
    async def deepfry(self, ctx, brightness: commands.Range[float, -1, 1] = 0.5,
                      contrast: commands.Range[float, 0, 5] = 1.5,
                      sharpness: commands.Range[float, 0, 5] = 1.5,
                      saturation: commands.Range[float, 0, 3] = 1.5,
                      noise: commands.Range[float, 0, 100] = 20):
        """
        Applies many filters to the input to make it appear "deep-fried" in the style of deep-fried memes.


        :param ctx: discord context
        :param brightness: value of 0 makes no change to the image. must be between -1 and 1.
        :param contrast: value of 1 makes no change to the image. must be between 0 and 5.
        :param sharpness: value of 0 makes no change to the image. must be between 0 and 5.
        :param saturation: value of 1 makes no change to the image. must be between 0 and 3.
        :param noise: value of 0 makes no change to the image. must be between 0 and 100.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.deepfry, [["VIDEO", "GIF", "IMAGE"]], brightness, contrast, sharpness,
                      saturation, noise)

    @commands.hybrid_command(aliases=["pad"])
    async def square(self, ctx):
        """
        Pads media into a square shape.

        :param ctx: discord context
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.pad, [["VIDEO", "GIF", "IMAGE"]])

    @commands.hybrid_command(aliases=["size"])
    async def resize(self, ctx, width: int, height: int):
        """
        Resizes an image.

        :param ctx: discord context
        :param width: width of output image. set to -1 to determine automatically based on height and aspect ratio.
        :param height: height of output image. also can be set to -1.
        :mediaparam media: A video, gif, or image.
        """
        if not (1 <= width <= config.max_size or width == -1):
            raise commands.BadArgument(f"Width must be between 1 and "
                                       f"{config.max_size} or be -1.")
        if not (1 <= height <= config.max_size or height == -1):
            raise commands.BadArgument(f"Height must be between 1 and "
                                       f"{config.max_size} or be -1.")
        await process(ctx, processing.ffmpeg.resize, [["VIDEO", "GIF", "IMAGE"]], width, height, resize=False)

    @commands.hybrid_command(aliases=["short", "kyle"])
    async def wide(self, ctx):
        """
        makes media twice as wide

        :param ctx: discord context
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.resize, [["VIDEO", "GIF", "IMAGE"]], "iw*2", "ih")

    @commands.hybrid_command(aliases=["tall", "long", "antikyle"])
    async def squish(self, ctx):
        """
        makes media twice as tall


        """
        await process(ctx, processing.ffmpeg.resize, [["VIDEO", "GIF", "IMAGE"]], "iw", "ih*2")

    @commands.hybrid_command(aliases=["magic", "magik", "contentawarescale", "liquidrescale"])
    async def magick(self, ctx, strength: commands.Range[int, 1, 99] = 50):
        """
        Apply imagemagick's liquid/content aware scale to an image.
        This command is a bit slow.
        https://legacy.imagemagick.org/Usage/resize/#liquid-rescale

        :param ctx: discord context
        :param strength: how strongly to compress the image. smaller is stronger. output image will be strength% of
        the original size. must be between 1 and 99.
        :mediaparam media: An image.
        """
        # TODO: add support for gifs/videos
        await process(ctx, processing.other.magickone, [["IMAGE"]], strength)

    @commands.hybrid_command(aliases=["repeat"], hidden=True)
    async def loop(self, ctx):
        """see $gifloop or $videoloop"""
        await ctx.reply("MediaForge has 2 loop commands.\nUse `$gifloop` to change/limit the amount of times a GIF "
                        "loops. This ONLY works on GIFs.\nUse `$videoloop` to loop a video. This command "
                        "duplicates the video contents.")

    @commands.hybrid_command(aliases=["gloop"])
    async def gifloop(self, ctx, loop: commands.Range[int, -1] = 0):
        """
        Changes the amount of times a gif loops
        See $videoloop for videos.

        :param ctx: discord context
        :param loop: number of times to loop. -1 for no loop, 0 for infinite loop.
        :mediaparam media: A gif.
        """

        await process(ctx, processing.ffmpeg.gifloop, [["GIF"]], loop)

    @commands.hybrid_command(aliases=["vloop"])
    async def videoloop(self, ctx, loop: commands.Range[int, 1, 15] = 1):
        """
        Loops a video
        See $gifloop for gifs.

        :param ctx: discord context
        :param loop: number of times to loop.
        :mediaparam media: A video.
        """
        await process(ctx, processing.ffmpeg.videoloop, [["VIDEO"]], loop)

    @commands.hybrid_command(aliases=["flip", "rot"])
    async def rotate(self, ctx, rottype: typing.Literal["90", "90ccw", "180", "vflip", "hflip"]):
        """
        Rotates and/or flips media

        :param ctx: discord context
        :param rottype: 90: 90° clockwise, 90ccw: 90° counter clockwise, 180: 180°, vflip: vertical flip, hflip:
        horizontal flip
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.rotate, [["GIF", "IMAGE", "VIDEO"]], rottype)

    @commands.hybrid_command()
    async def hue(self, ctx, h: float):
        """
        Change the hue of media.
        see https://ffmpeg.org/ffmpeg-filters.html#hue

        :param ctx: discord context
        :param h: The hue angle as a number of degrees.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.hue, [["GIF", "IMAGE", "VIDEO"]], h)

    @commands.hybrid_command(aliases=["color", "recolor"])
    async def tint(self, ctx, color: discord.Color):
        """
        Tint media to a color.
        This command first makes the image grayscale, then replaces white with your color.
        The resulting image should be nothing but shades of your color.

        :param ctx: discord context
        :param color: The hex or RGB color to tint to.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.tint, [["GIF", "IMAGE", "VIDEO"]], color)

    @commands.hybrid_command(aliases=["round", "circlecrop", "roundcrop", "circle", "roundedcorners"])
    async def roundcorners(self, ctx, radius: int = 10):
        """
        Round corners of media
        see https://developer.mozilla.org/en-US/docs/Web/CSS/border-radius

        :param ctx: discord context
        :param radius: the size of the rounded corners in pixels
        :mediaparam media: A video, gif, or image.
        """
        if not 0 <= radius:
            raise commands.BadArgument(f"Border radius percent must be above 0")
        await process(ctx, processing.ffmpeg.round_corners, [["GIF", "IMAGE", "VIDEO"]], radius)

    @commands.hybrid_command()
    async def volume(self, ctx, volume: commands.Range[float, 0, 32]):
        """
        Changes the volume of media.
        To make 2x as loud, use `$volume 2`.
        This command changes *perceived loudness*, not the raw audio level.
        WARNING: ***VERY*** LOUD AUDIO CAN BE CREATED

        :param ctx: discord context
        :param volume: number to multiply the percieved audio level by. Must be between 0 and 32.
        :mediaparam media: A video or audio file.
        """
        if not 0 <= volume <= 32:
            raise commands.BadArgument(f"{config.emojis['warning']} Volume must be between 0 and 32.")
        await process(ctx, processing.ffmpeg.volume, [["VIDEO", "AUDIO"]], volume)

    @commands.hybrid_command()
    async def mute(self, ctx):
        """
        alias for $volume 0

        :param ctx: discord context
        :mediaparam media: A video or audio file.
        """
        await process(ctx, processing.ffmpeg.volume, [["VIDEO", "AUDIO"]], 0)

    @commands.hybrid_command()
    async def vibrato(self, ctx, frequency: commands.Range[float, 0.1, 20000.0] = 5,
                      depth: commands.Range[float, 0, 1] = 1):
        """
        Applies a "wavy pitch"/vibrato effect to audio.
        officially described as "Sinusoidal phase modulation"
        see https://ffmpeg.org/ffmpeg-filters.html#tremolo

        :param ctx: discord context
        :param frequency: Modulation frequency in Hertz. must be between 0.1 and 20000.
        :param depth: Depth of modulation as a percentage. must be between 0 and 1.
        :mediaparam media: A video or audio file.
        """
        await process(ctx, processing.ffmpeg.vibrato, [["VIDEO", "AUDIO"]], frequency, depth)

    @commands.hybrid_command()
    async def pitch(self, ctx, numofhalfsteps: commands.Range[float, -12, 12] = 12):
        """
        Changes pitch of audio

        :param ctx: discord context
        :param numofhalfsteps: the number of half steps to change the pitch by. `12` raises the pitch an octave and
        `-12` lowers the pitch an octave. must be between -12 and 12.
        :mediaparam media: A video or audio file.
        """
        if not -12 <= numofhalfsteps <= 12:
            raise commands.BadArgument(f"numofhalfsteps must be between -12 and 12.")
        await process(ctx, processing.ffmpeg.pitch, [["VIDEO", "AUDIO"]], numofhalfsteps)

    @commands.hybrid_command(aliases=["concat", "combinev"])
    async def concatv(self, ctx):
        """
        Makes one video file play right after another.
        The output video will take on all of the settings of the FIRST video.
        The second video will be scaled to fit.

        :param ctx: discord context
        :mediaparam video1: A video or gif.
        :mediaparam video2: A video or gif.
        """
        await process(ctx, processing.ffmpeg.concatv, [["VIDEO", "GIF"], ["VIDEO", "GIF"]])

    @commands.hybrid_command()
    async def hstack(self, ctx):
        """
        Stacks 2 videos horizontally

        :param ctx: discord context
        :mediaparam video1: A video, image, or gif.
        :mediaparam video2: A video, image, or gif.
        """
        await process(ctx, processing.ffmpeg.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                      "hstack")

    @commands.hybrid_command()
    async def vstack(self, ctx):
        """
        Stacks 2 videos horizontally

        :param ctx: discord context
        :mediaparam video1: A video, image, or gif.
        :mediaparam video2: A video, image, or gif.
        """
        await process(ctx, processing.ffmpeg.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                      "vstack")

    @commands.hybrid_command(aliases=["blend"])
    async def overlay(self, ctx, alpha: commands.Range[float, 0, 1] = 0.5):
        """
        Overlays the second input over the first

        :param ctx: discord context
        :param alpha: the alpha (transparency) of the top video. must be between 0 and 1.
        :mediaparam video1: A video or gif.
        :mediaparam video2: A video or gif.
        """
        await process(ctx, processing.ffmpeg.overlay, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], alpha,
                      "overlay")

    @commands.hybrid_command(aliases=["overlayadd", "addition"])
    async def add(self, ctx):
        """
        Adds the pixel values of the second video to the first.

        :param ctx: discord context
        :mediaparam video1: A video or gif.
        :mediaparam video2: A video or gif.
        """
        await process(ctx, processing.ffmpeg.overlay, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], 1,
                      "add")

    @commands.hybrid_command(name="speed")
    async def spcommand(self, ctx, speed: commands.Range[float, 0.25, 100.0] = 2):
        """
        Changes the speed of media.
        This command preserves the original FPS, which means speeding up will drop frames. See $fps.

        :param ctx: discord context
        :param speed: Multiplies input video speed by this number. must be between 0.25 and 100.
        :mediaparam media: A video, gif, or audio.
        """
        await process(ctx, processing.ffmpeg.speed, [["VIDEO", "GIF", "AUDIO"]], speed)

    @commands.hybrid_command(aliases=["shuffle", "stutter", "nervous"])
    async def random(self, ctx, frames: commands.Range[int, 2, 512] = 30):
        """
        Shuffles the frames of a video around.
        Currently, this command does NOT apply to audio. This is an FFmpeg limitation.
        see https://ffmpeg.org/ffmpeg-filters.html#random

        :param ctx: discord context
        :param frames: Set size in number of frames of internal cache. must be between 2 and 512. default is 30.
        :mediaparam video: A video or gif.
        """
        await process(ctx, processing.ffmpeg.random, [["VIDEO", "GIF"]], frames)

    @commands.hybrid_command()
    async def reverse(self, ctx):
        """
        Reverses media.

        :param ctx: discord context
        :mediaparam video: A video or gif.
        """
        await process(ctx, processing.ffmpeg.reverse, [["VIDEO", "GIF"]])

    @commands.hybrid_command(aliases=["compress", "quality", "lowerquality", "crf", "qa"])
    async def compressv(self, ctx, crf: commands.Range[float, 28, 51] = 51,
                        qa: commands.Range[float, 10, 112] = 20):
        """
        Makes videos terrible quality.
        The strange ranges on the numbers are because they are quality settings in FFmpeg's encoding.
        CRF info is found at https://trac.ffmpeg.org/wiki/Encode/H.264#crf
        audio quality info is found under https://trac.ffmpeg.org/wiki/Encode/AAC#fdk_cbr

        :param ctx: discord context
        :param crf: Controls video quality. Higher is worse quality. must be between 28 and 51.
        :param qa: Audio bitrate in kbps. Lower is worse quality. Must be between 10 and 112.
        :mediaparam video: A video or gif.
        """
        await process(ctx, processing.ffmpeg.quality, [["VIDEO", "GIF"]], crf, qa)

    @commands.hybrid_command(name="fps")
    async def fpschange(self, ctx, fps: commands.Range[float, 1, 60]):
        """
        Changes the FPS of media.
        This command keeps the speed the same.
        BEWARE: Changing the FPS of gifs can create strange results due to the strange way GIFs store FPS data.
        GIFs are only stable at certain FPS values. These include 50, 30, 15, 10, and others.
        An important reminder that by default tenor "gifs" are interpreted as mp4s,
        which do not suffer this problem.

        :param ctx: discord context
        :param fps: Frames per second of the output. must be between 1 and 60.
        :mediaparam video: A video or gif.
        """
        await process(ctx, processing.ffmpeg.changefps, [["VIDEO", "GIF"]], fps)

    @commands.hybrid_command(aliases=["negate", "opposite"])
    async def invert(self, ctx):
        """
        Inverts colors of media

        :param ctx: discord context
        :mediaparam video: A video or gif.
        """
        await process(ctx, processing.ffmpeg.invert, [["VIDEO", "GIF", "IMAGE"]])

    @commands.hybrid_command()
    async def trim(self, ctx, length: commands.Range[float, 0, None],
                   start: commands.Range[float, 0, None] = 0):
        """
        Trims media.

        :param ctx: discord context
        :param length: Length in seconds to trim the media to.
        :param start: Time in seconds to start the trimmed media at.
        :mediaparam media: A video, gif, or audio file.
        """
        await process(ctx, processing.ffmpeg.trim, [["VIDEO", "GIF", "AUDIO"]], length, start)

    @commands.hybrid_command(aliases=["uncap", "nocaption", "nocap", "rmcap", "removecaption", "delcap", "delcaption",
                                      "deletecaption", "trimcap", "trimcaption"])
    async def uncaption(self, ctx, frame_to_try: int = 0, threshold: commands.Range[float, 0, 255] = 10):
        """
        try to remove esm/default style captions from media
        scans the leftmost column of pixels on one frame to attempt to determine where the caption is.

        :param ctx:
        :param frame_to_try: which frame to run caption detection on. -1 uses the last frame.
        :param threshold: a number 0-255 how similar the caption background must be to white
        :mediaparam media: A video, image, or GIF file
        """
        await process(ctx, processing.vips.other.uncaption, [["VIDEO", "IMAGE", "GIF"]], frame_to_try, threshold)
