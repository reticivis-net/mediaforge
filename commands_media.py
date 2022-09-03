import typing

import discord
from discord.ext import commands

import config
import processing_ffmpeg
from mainutils import improcess, number_range, prefix_function


class Media(commands.Cog, name="Editing"):
    """
    Basic media editing/processing commands.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["copy", "nothing", "noop"])
    async def repost(self, ctx):
        """
        Reposts media as-is.

        :param ctx: discord context
        :mediaparam media: Any valid media.
        """
        await improcess(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]])

    @commands.command(aliases=["clean", "remake"])
    async def reencode(self, ctx):
        """
        Re-encodes media.
        Videos become libx264 mp4s, audio files become libmp3lame mp3s, images become pngs.

        :param ctx: discord context
        :mediaparam media: A video, image, or audio file.
        """
        await improcess(ctx, processing_ffmpeg.allreencode, [["VIDEO", "IMAGE", "AUDIO"]])

    @commands.command(aliases=["audioadd", "dub"])
    async def addaudio(self, ctx, loops: number_range(-1, 100, num_type='int') = -1):
        """
        Adds audio to media.

        :param ctx: discord context
        :param loops: Amount of times to loop a gif. -1 loops infinitely, 0 only once. Must be between -1 and 100.
        :mediaparam media: Any valid media file.
        :mediaparam audio: An audio file.
        """
        await improcess(ctx, processing_ffmpeg.addaudio, [["IMAGE", "GIF", "VIDEO", "AUDIO"], ["AUDIO"]], loops)

    @commands.command()
    async def jpeg(self, ctx, strength: number_range(0, 100, False, True, 'int') = 30,
                   stretch: number_range(0, 40, num_type='int') = 20,
                   quality: number_range(1, 95, num_type='int') = 10):
        """
        Makes media into a low quality jpeg

        :param ctx: discord context
        :param strength: amount of times to jpegify image. must be between 1 and 100.
        :param stretch: randomly stretch the image by this number on each jpegification. can cause strange effects
        on videos. must be between 0 and 40.
        :param quality: quality of JPEG compression. must be between 1 and 95.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.jpeg, [["VIDEO", "GIF", "IMAGE"]], strength, stretch, quality, handleanimated=True)

    @commands.command()
    async def deepfry(self, ctx, brightness: number_range(0, 5) = 1.5,
                      contrast: number_range(0, 5) = 1.5,
                      sharpness: number_range(0, 5) = 1.5,
                      saturation: number_range(0, 5) = 1.5,
                      noise: number_range(0, 255) = 40,
                      jpegstrength: number_range(0, 100, False, True, 'int') = 20):
        """
        Applies several filters to the input media to make it appear "deep fried" in the style of deep fried memes.
        See https://pillow.readthedocs.io/en/3.0.x/reference/ImageEnhance.html


        :param ctx: discord context
        :param brightness: value of 1 makes no change to the image. must be between 0 and 5.
        :param contrast: value of 1 makes no change to the image. must be between 0 and 5.
        :param sharpness: value of 1 makes no change to the image. must be between 0 and 5.
        :param saturation: value of 1 makes no change to the image. must be between 0 and 5.
        :param noise: value of 0 makes no change to the image. must be between 0 and 255.
        :param jpegstrength: value of 0 makes no change to the image. must be between 0 and 100.
        :mediaparam media: A video, gif, or image.
        """
        if not 0 <= brightness <= 5:
            raise commands.BadArgument(f"Brightness must be between 0 and 5.")
        if not 0 <= contrast <= 5:
            raise commands.BadArgument(f"Contrast must be between 0 and 5.")
        if not 0 <= sharpness <= 5:
            raise commands.BadArgument(f"Sharpness must be between 0 and 5.")
        if not 0 <= saturation <= 5:
            raise commands.BadArgument(f"Saturation must be between 0 and 5.")
        if not 0 <= noise <= 255:
            raise commands.BadArgument(f"Noise must be between 0 and 255.")
        if not 0 < jpegstrength <= 100:
            raise commands.BadArgument(f"JPEG strength must be between 0 and 100.")
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.deepfry, [["VIDEO", "GIF", "IMAGE"]], brightness, contrast, sharpness,
        #                 saturation, noise, jpegstrength, handleanimated=True)

    @commands.command()
    async def corrupt(self, ctx, strength: number_range(0, 0.5) = 0.05):
        """
        Intentionally glitches media
        Effect is achieved through randomly changing a % of bytes in a jpeg image.

        :param ctx: discord context
        :param strength: % chance to randomly change a byte of the input image.
        :mediaparam media: A video, gif, or image.
        """
        if not 0 <= strength <= 0.5:
            raise commands.BadArgument(f"Strength must be between 0% and 0.5%.")
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.jpegcorrupt, [["VIDEO", "GIF", "IMAGE"]], strength,
        #                 handleanimated=True)

    @commands.command(aliases=["pad"])
    async def square(self, ctx):
        """
        Pads media into a square shape.

        :param ctx: discord context
        :mediaparam media: A video, gif, or image.
        """
        await improcess(ctx, processing_ffmpeg.pad, [["VIDEO", "GIF", "IMAGE"]])

    @commands.command(aliases=["size"])
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
        await improcess(ctx, processing_ffmpeg.resize, [["VIDEO", "GIF", "IMAGE"]], width, height, resize=False)

    @commands.command(aliases=["short", "kyle"])
    async def wide(self, ctx):
        """
        makes media twice as wide

        :param ctx: discord context
        :mediaparam media: A video, gif, or image.
        """
        await improcess(ctx, processing_ffmpeg.resize, [["VIDEO", "GIF", "IMAGE"]], "iw*2", "ih")

    @commands.command(aliases=["tall", "long", "antikyle"])
    async def squish(self, ctx):
        """
        makes media twice as tall


        """
        await improcess(ctx, processing_ffmpeg.resize, [["VIDEO", "GIF", "IMAGE"]], "iw", "ih*2")

    @commands.command(aliases=["magic", "magik", "contentawarescale", "liquidrescale"])
    async def magick(self, ctx, strength: number_range(1, 99, num_type='int') = 50):
        """
        Apply imagemagick's liquid/content aware scale to an image.
        This command is a bit slow.
        https://legacy.imagemagick.org/Usage/resize/#liquid-rescale

        :param ctx: discord context
        :param strength: how strongly to compress the image. smaller is stronger. output image will be strength% of
        the original size. must be between 1 and 99.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.magick, [["VIDEO", "GIF", "IMAGE"]], strength, handleanimated=True)

    @commands.command(aliases=["repeat"], hidden=True)
    async def loop(self, ctx):
        await ctx.reply("MediaForge has 2 loop commands.\nUse `$gifloop` to change/limit the amount of times a GIF "
                        "loops. This ONLY works on GIFs.\nUse `$videoloop` to loop a video. This command "
                        "duplicates the video contents."
                        .replace("$", await prefix_function(self.bot, ctx.message, True)))

    @commands.command(aliases=["gloop"])
    async def gifloop(self, ctx, loop: number_range(-1, lower_incl=True, num_type='int') = 0):
        """
        Changes the amount of times a gif loops
        See $videoloop for videos.

        :param ctx: discord context
        :param loop: number of times to loop. -1 for no loop, 0 for infinite loop.
        :mediaparam media: A gif.
        """
        if not -1 <= loop:
            raise commands.BadArgument(f"Loop must be -1 or more.")
        await improcess(ctx, processing_ffmpeg.gifloop, [["GIF"]], loop)

    @commands.command(aliases=["vloop"])
    async def videoloop(self, ctx, loop: number_range(1, 15, num_type='int') = 1):
        """
        Loops a video
        This command technically works on GIFs but its better to use `$gifloop` which takes advantage of GIFs'
        loop metadata.
        See $gifloop for gifs.

        :param ctx: discord context
        :param loop: number of times to loop.
        :mediaparam media: A video or GIF.
        """
        if not 1 <= loop <= 15:
            raise commands.BadArgument(f"Loop must be between 1 and 15.")
        await improcess(ctx, processing_ffmpeg.videoloop, [["VIDEO", "GIF"]], loop)

    @commands.command(aliases=["flip", "rot"])
    async def rotate(self, ctx, rottype: typing.Literal["90", "90ccw", "180", "vflip", "hflip"]):
        """
        Rotates and/or flips media

        :param ctx: discord context
        :param rottype: 90: 90° clockwise, 90ccw: 90° counter clockwise, 180: 180°, vflip: vertical flip, hflip:
        horizontal flip
        :mediaparam media: A video, gif, or image.
        """
        await improcess(ctx, processing_ffmpeg.rotate, [["GIF", "IMAGE", "VIDEO"]], rottype)

    @commands.command()
    async def hue(self, ctx, h: float):
        """
        Change the hue of media.
        see https://ffmpeg.org/ffmpeg-filters.html#hue

        :param ctx: discord context
        :param h: The hue angle as a number of degrees.
        :mediaparam media: A video, gif, or image.
        """
        await improcess(ctx, processing_ffmpeg.hue, [["GIF", "IMAGE", "VIDEO"]], h)

    @commands.command(aliases=["color", "recolor"])
    async def tint(self, ctx, color: discord.Color):
        """
        Tint media to a color.
        This command first makes the image grayscale, then replaces white with your color.
        The resulting image should be nothing but shades of your color.

        :param ctx: discord context
        :param color: The hex or RGB color to tint to.
        :mediaparam media: A video, gif, or image.
        """
        await improcess(ctx, processing_ffmpeg.tint, [["GIF", "IMAGE", "VIDEO"]], color)

    @commands.command(aliases=["round", "circlecrop", "roundcrop", "circle", "roundedcorners"])
    async def roundcorners(self, ctx, radiuspercent: number_range(0, 50) = 50.0):
        """
        Round corners of media
        see https://developer.mozilla.org/en-US/docs/Web/CSS/border-radius

        :param ctx: discord context
        :param radiuspercent: How rounded the corners will be. 0 is rectangle, 50 is ellipse.
        :mediaparam media: A video, gif, or image.
        """
        if not 0 <= radiuspercent <= 50:
            raise commands.BadArgument(f"Border radius percent must be between 0 and 50.")
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.roundcorners, [["GIF", "IMAGE", "VIDEO"]], str(radiuspercent),
        #                 handleanimated=True)

    @commands.command()
    async def volume(self, ctx, volume: number_range(0, 32)):
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
        await improcess(ctx, processing_ffmpeg.volume, [["VIDEO", "AUDIO"]], volume)

    @commands.command()
    async def mute(self, ctx):
        """
        alias for $volume 0

        :param ctx: discord context
        :mediaparam media: A video or audio file.
        """
        await improcess(ctx, processing_ffmpeg.volume, [["VIDEO", "AUDIO"]], 0)

    @commands.command()
    async def vibrato(self, ctx, frequency: number_range(0.1, 20000) = 5,
                      depth: number_range(0, 1) = 1):
        """
        Applies a "wavy pitch"/vibrato effect to audio.
        officially described as "Sinusoidal phase modulation"
        see https://ffmpeg.org/ffmpeg-filters.html#tremolo

        :param ctx: discord context
        :param frequency: Modulation frequency in Hertz. must be between 0.1 and 20000.
        :param depth: Depth of modulation as a percentage. must be between 0 and 1.
        :mediaparam media: A video or audio file.
        """
        await improcess(ctx, processing_ffmpeg.vibrato, [["VIDEO", "AUDIO"]], frequency, depth)

    @commands.command()
    async def pitch(self, ctx, numofhalfsteps: number_range(-12, 12) = 12):
        """
        Changes pitch of audio

        :param ctx: discord context
        :param numofhalfsteps: the number of half steps to change the pitch by. `12` raises the pitch an octave and
        `-12` lowers the pitch an octave. must be between -12 and 12.
        :mediaparam media: A video or audio file.
        """
        if not -12 <= numofhalfsteps <= 12:
            raise commands.BadArgument(f"numofhalfsteps must be between -12 and 12.")
        await improcess(ctx, processing_ffmpeg.pitch, [["VIDEO", "AUDIO"]], numofhalfsteps)

    @commands.command(aliases=["concat", "combinev"])
    async def concatv(self, ctx):
        """
        Makes one video file play right after another.
        The output video will take on all of the settings of the FIRST video.
        The second video will be scaled to fit.

        :param ctx: discord context
        :mediaparam video1: A video or gif.
        :mediaparam video2: A video or gif.
        """
        await improcess(ctx, processing_ffmpeg.concatv, [["VIDEO", "GIF"], ["VIDEO", "GIF"]])

    @commands.command()
    async def hstack(self, ctx):
        """
        Stacks 2 videos horizontally

        :param ctx: discord context
        :mediaparam video1: A video, image, or gif.
        :mediaparam video2: A video, image, or gif.
        """
        await improcess(ctx, processing_ffmpeg.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                        "hstack")

    @commands.command()
    async def vstack(self, ctx):
        """
        Stacks 2 videos horizontally

        :param ctx: discord context
        :mediaparam video1: A video, image, or gif.
        :mediaparam video2: A video, image, or gif.
        """
        await improcess(ctx, processing_ffmpeg.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]],
                        "vstack")

    @commands.command(aliases=["blend"])
    async def overlay(self, ctx, alpha: number_range(0, 1) = 0.5):
        """
        Overlays the second input over the first

        :param ctx: discord context
        :param alpha: the alpha (transparency) of the top video. must be between 0 and 1.
        :mediaparam video1: A video or gif.
        :mediaparam video2: A video or gif.
        """
        await improcess(ctx, processing_ffmpeg.overlay, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], alpha,
                        "overlay")

    @commands.command(aliases=["overlayadd", "addition"])
    async def add(self, ctx):
        """
        Adds the pixel values of the second video to the first.

        :param ctx: discord context
        :mediaparam video1: A video or gif.
        :mediaparam video2: A video or gif.
        """
        await improcess(ctx, processing_ffmpeg.overlay, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], 1,
                        "add")

    @commands.command(name="speed")
    async def spcommand(self, ctx, speed: number_range(0.25, 100) = 2):
        """
        Changes the speed of media.
        This command preserves the original FPS, which means speeding up will drop frames. See $fps.

        :param ctx: discord context
        :param speed: Multiplies input video speed by this number. must be between 0.25 and 100.
        :mediaparam media: A video, gif, or audio.
        """
        if not 0.25 <= speed <= 100:
            raise commands.BadArgument(f"Speed must be between 0.25 and 100")
        await improcess(ctx, processing_ffmpeg.speed, [["VIDEO", "GIF", "AUDIO"]], speed)

    @commands.command(aliases=["shuffle", "stutter", "nervous"])
    async def random(self, ctx, frames: number_range(2, 512, num_type='int') = 30):
        """
        Shuffles the frames of a video around.
        Currently, this command does NOT apply to audio. This is an FFmpeg limitation.
        see https://ffmpeg.org/ffmpeg-filters.html#random

        :param ctx: discord context
        :param frames: Set size in number of frames of internal cache. must be between 2 and 512. default is 30.
        :mediaparam video: A video or gif.
        """
        if not 2 <= frames <= 512:
            raise commands.BadArgument(f"Frames must be between 2 and 512")
        await improcess(ctx, processing_ffmpeg.random, [["VIDEO", "GIF"]], frames)

    @commands.command()
    async def reverse(self, ctx):
        """
        Reverses media.

        :param ctx: discord context
        :mediaparam video: A video or gif.
        """
        await improcess(ctx, processing_ffmpeg.reverse, [["VIDEO", "GIF"]])

    @commands.command(aliases=["compress", "quality", "lowerquality", "crf", "qa"])
    async def compressv(self, ctx, crf: number_range(28, 51) = 51, qa: number_range(10, 112) = 20):
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
        await improcess(ctx, processing_ffmpeg.quality, [["VIDEO", "GIF"]], crf, qa)

    @commands.command(name="fps")
    async def fpschange(self, ctx, fps: number_range(1, 60)):
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
        await improcess(ctx, processing_ffmpeg.changefps, [["VIDEO", "GIF"]], fps)

    @commands.command(aliases=["negate", "opposite"])
    async def invert(self, ctx):
        """
        Inverts colors of media

        :param ctx: discord context
        :mediaparam video: A video or gif.
        """
        await improcess(ctx, processing_ffmpeg.invert, [["VIDEO", "GIF", "IMAGE"]])

    @commands.command()
    async def trim(self, ctx, length: number_range(0, lower_incl=False), start: number_range(0) = 0):
        """
        Trims media.

        :param ctx: discord context
        :param length: Length in seconds to trim the media to.
        :param start: Time in seconds to start the trimmed media at.
        :mediaparam media: A video, gif, or audio file.
        """
        if not 0 < length:
            raise commands.BadArgument(f"Length must be more than 0.")
        if not 0 <= start:
            raise commands.BadArgument(f"Start must be equal to or more than 0.")
        await improcess(ctx, processing_ffmpeg.trim, [["VIDEO", "GIF", "AUDIO"]], length, start)

    @commands.command()
    async def autotune(self, ctx, CONCERT_A: float = 440, FIXED_PITCH: float = 0.0,
                       FIXED_PULL: float = 0.1, KEY: str = "c", CORR_STR: float = 1.0, CORR_SMOOTH: float = 0.0,
                       PITCH_SHIFT: float = 0.0, SCALE_ROTATE: int = 0, LFO_DEPTH: float = 0.0,
                       LFO_RATE: float = 1.0, LFO_SHAPE: float = 0.0, LFO_SYMM: float = 0.0, LFO_QUANT: int = 0,
                       FORM_CORR: int = 0, FORM_WARP: float = 0.0, MIX: float = 1.0):
        """
        Autotunes media.
        :param ctx: discord context
        :param CONCERT_A: CONCERT A: Value in Hz of middle A, used to tune the entire algorithm.
        :param FIXED_PITCH: FIXED PITCH: Pitch (semitones) toward which pitch is pulled when PULL TO FIXED PITCH is
         engaged. FIXED PITCH = O: middle A. FIXED PITCH = MIDI pitch - 69.
        :param FIXED_PULL: PULL TO FIXED PITCH: Degree to which pitch Is pulled toward FIXED PITCH. O: use original
         pitch. 1: use FIXED PITCH.
        :param KEY: the key it is tuned to. can be any letter a-g, A-G, or X (chromatic scale).
        :param CORR_STR: CORRECTION STRENGTH: Strength of pitch correction. O: no correction. 1: full correction.
        :param CORR_SMOOTH: CORRECTION SMOOTHNESS: Smoothness of transitions between notes when pitch correction is
        used. O: abrupt transitions. 1: smooth transitions.
        :param PITCH_SHIFT: PITCH SHIFT: Number of notes in scale by which output pitch Is shifted.
        :param SCALE_ROTATE: OUTPUT SCALE ROTATE: Number of notes by which the output scale Is rotated In the
        conversion back to semitones from scale notes. Can be used to change the scale between major and minor or
        to change the musical mode.
        :param LFO_DEPTH: LFO DEPTH: Degree to which low frequency oscillator (LFO) Is applied.
        :param LFO_RATE: LFO RATE: Rate (In Hz) of LFO.
        :param LFO_SHAPE: LFO SHAPE: Shape of LFO waveform. -1: square. 0: sine. 1: triangle.
        :param LFO_SYMM: LFO SYMMETRY: Adjusts the rise/fall characteristic of the LFO waveform.
        :param LFO_QUANT: LFO QUANTIZATION: Quantizes the LFO waveform, resulting in chiptune-like effects.
        :param FORM_CORR: FORMANT CORRECTION: Enables formant correction, reducing the "chipmunk effect"
        in pitch shifting.
        :param FORM_WARP: FORMANT WARP: Warps the formant frequencies. Can be used to change gender/age.
        :param MIX: Blends between the modified signal and the delay-compensated Input signal. 1: wet. O: dry.
        :mediaparam media: A video or audio file.
        """
        # TODO: flag command thing

        await improcess(ctx, processing_ffmpeg.handleautotune, [["VIDEO", "AUDIO"]],
                        CONCERT_A, FIXED_PITCH, FIXED_PULL, KEY, CORR_STR, CORR_SMOOTH, PITCH_SHIFT, SCALE_ROTATE,
                        LFO_DEPTH, LFO_RATE, LFO_SHAPE, LFO_SYMM, LFO_QUANT, FORM_CORR, FORM_WARP, MIX)

    @commands.command(aliases=["uncap", "nocaption", "nocap", "rmcap", "removecaption", "delcap", "delcaption",
                               "deletecaption", "trimcap", "trimcaption"])
    async def uncaption(self, ctx, frame_to_try: int = 0, tolerance: number_range(0, 100, False) = 95):
        """
        try to remove esm/default style captions from media
        scans the leftmost column of pixels on one frame to attempt to determine where the caption is.

        :param ctx:
        :param frame_to_try: which frame to run caption detection on. -1 uses the last frame.
        :param tolerance: in % how close to white the color must be to count as caption
        :mediaparam media: A video, image, or GIF file
        """
        await improcess(ctx, processing_ffmpeg.uncaption, [["VIDEO", "IMAGE", "GIF"]], frame_to_try, tolerance)
