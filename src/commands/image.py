import typing

from discord.ext import commands

import processing.common
import processing.ffmpeg
import processing.vips
import processing.vips.creation
from core.process import process
from processing import sus


class Image(commands.Cog, name="Creation"):
    """
    Generate images from a template.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="1984", aliases=["nineteeneightyfour", "georgeorwell"])
    async def f1984(self, ctx, *, caption):
        """
        Creates a custom meme based off of the "living in 1984" comic.

        :param ctx: discord context
        :param caption: The text that the lady checking her phone is saying. Optionally change what is on the
            calendar by writing something after a `|` character.
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("JANUARY 1984")
        await process(ctx, processing.vips.creation.f1984, [], caption, run_parallel=True)

    @commands.hybrid_command(aliases=["ltg", "now", "lowtiergod", "youshould"])
    async def yskysn(self, ctx, *, caption):
        """
        Creates a custom meme based off of the popular Low Tier God "You Should... NOW!" edit.

        :param ctx: discord context
        :param caption: The text that will be placed next to LTG. Optionally change the "NOW!" text by writing
            something after a `|` character (or remove it by typing a `|` followed by nothing else).
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("NOW!")
        await process(ctx, processing.vips.creation.yskysn, [], caption, run_parallel=True)

    @commands.hybrid_command(aliases=["troll"])
    async def trollface(self, ctx):
        """
        Colors a trollface with an image.

        :param ctx: discord context
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.trollface, [["VIDEO", "GIF", "IMAGE"]])

    @commands.hybrid_command(aliases=["emsay"])
    async def eminemsay(self, ctx, *, text):
        """
        Eminem says something.

        :param ctx: discord context
        :param text: The text to put next to eminem.
        """
        await process(ctx, processing.vips.caption.generic_image_caption, [],
                      "rendering/images/eminem.png",
                      [text],
                      processing.vips.vipsutils.ImageSize(1000, 1000),
                      run_parallel=True)

    @commands.hybrid_command(aliases=["customsay"])
    async def imagesay(self, ctx, *, text):
        """
        An image of your choice says something.
        Like `$eminemsay` but for a custom image.

        :param ctx: discord context
        :param text: The text to put next to your image.
        :mediaparam media: An image, video, or gif
        """
        await process(ctx, processing.vips.caption.generic_image_caption, [["IMAGE"]],
                      [text],
                      processing.vips.vipsutils.ImageSize(1000, 1000), run_parallel=True)

    @commands.hybrid_command(aliases=["handitover", "takeit", "giveme", "gmyp"])
    async def givemeyourphone(self, ctx):
        """
        Overlays an image over the hand of the boy in the "give me your phone" meme.
        https://knowyourmeme.com/memes/give-me-your-phone

        :param ctx: discord context
        :mediaparam media: The media to be overlayed over his hand.
        """
        await process(ctx, processing.ffmpeg.give_me_your_phone_now, [["IMAGE", "VIDEO", "GIF"]])

    @commands.hybrid_command(aliases=["texttospeak", "speak", "talk", "speech", "espeak"])
    async def tts(self, ctx: commands.Context,
                  voice: typing.Optional[typing.Literal["male", "female", "retro"]] = "male", *, text):
        """
        make an mp3 text-to-speech of a given input
        for modern voices: uses espeak+mbrola on linux, or native tts on windows (OS of the host server)
        for retro TTS: uses commodore sam

        :param ctx: discord ctx
        :param voice: choose what voice you want it to be spoken in. modern TTS voices are "male" or "female", or
            you can use "retro" for a 1980s TTS, just for fun :p
        :param text: the text to speak
        :return: audio file of the spoken text
        """
        # shouldnt happen but sanity check
        if not voice:
            voice = "male"
        await process(ctx, processing.common.tts, [], text, voice)

    # WIP
    @commands.hybrid_command()
    async def epicbirthday(self, ctx: commands.Context, *, text):
        """
        let mediaforge wish someone a very epic birthday!!!
        all credit for song goes to https://epichappybirthdaysongs.com/

        :param ctx:
        :param text: who you want to wish an epic birthday to
        :return: a custom made song just for you!
        """
        await process(ctx, processing.ffmpeg.epicbirthday, [], text)

    @commands.hybrid_command(aliases=['sus', 'imposter'])
    async def jermatext(self, ctx, *, text="when the imposter is sus!😳"):
        """
        Cut and slice the popular Jerma sus meme to any message
        For any letter not in the original meme, a random slice of the face is selected.
        Based on https://github.com/aechaechaech/Jerma-Imposter-Message-Generator
        :param ctx: discord context
        :param text: The text to cut and splice.
        """
        await process(ctx, sus.sus, [], text, run_parallel=True)
