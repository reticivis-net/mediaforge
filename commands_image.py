import typing

from discord.ext import commands

import processing_common
import processing_ffmpeg
import processing_other
from mainutils import improcess


class Image(commands.Cog, name="Creation"):
    """
    Generate images from a template.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="1984", aliases=["nineteeneightyfour", "georgeorwell"])
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
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.f1984, [], caption)

    @commands.command(aliases=["ltg", "now", "lowtiergod", "youshould"])
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
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.yskysn, [], caption)

    @commands.command(aliases=["shes12"])
    async def zamn(self, ctx, *, caption):
        """
        Creates a custom meme based off of the popular "ZAMN😍 SHE'S 12?" meme.

        :param ctx: discord context
        :param caption: The text above your custom image. Optionally change the "ZAMN😍" text by writing
            something after a `|` character (or remove it by typing a `|` followed by nothing else).
        :mediaparam media: An image, video, or gif that Damien will "ZAMN" at
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("ZAMN😍")
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.zamn, [["IMAGE", "VIDEO", "GIF"]], *caption, handleanimated=True)

    @commands.command(aliases=["troll"])
    async def trollface(self, ctx):
        """
        Colors a trollface with an image.

        :param ctx: discord context
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.trollface, [["VIDEO", "GIF", "IMAGE"]], handleanimated=True)

    @commands.command(aliases=["emsay"])
    async def eminemsay(self, ctx, *, text):
        """
        Eminem says something.

        :param ctx: discord context
        :param text: The text to put next to eminem.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.eminem, [], [text])

    @commands.command(aliases=["customsay"])
    async def imagesay(self, ctx, *, text):
        """
        An image of your choice says something.
        Like `$eminemsay` but for a custom image.

        :param ctx: discord context
        :param text: The text to put next to your image.
        :mediaparam media: An image, video, or gif
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.imagesay, [["IMAGE", "VIDEO", "GIF"]], text, handleanimated=True)

    @commands.command(aliases=["customcap", "imagesaycap", "imagesaycaption", "imagecap", "customsaycap",
                               "imagecaptionright"])
    async def imagecaption(self, ctx, *, text):
        """
        An image of your choice says something below another image.
        Like `$stuff`, `$eminem` or `$petergriffin` but for a custom image.

        :param ctx: discord context
        :param text: The text to put next to your image.
        :mediaparam media: An image, video, or gif to caption
        :mediaparam image: An image to sit next to the caption text
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.imagesaycap, [["IMAGE", "VIDEO", "GIF"], ["IMAGE"]], text,
        #                 handleanimated=True)

    @commands.command(aliases=["customcapleft", "imagesaycapleft", "imagesaycaptionleft", "imagecapleft",
                               "customsaycapleft"])
    async def imagecaptionleft(self, ctx, *, text):
        """
        like $imagecaption but the image is on the left.

        :param ctx: discord context
        :param text: The text to put next to your image.
        :mediaparam media: An image, video, or gif to caption
        :mediaparam image: An image to sit next to the caption text
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.imagesaycapleft, [["IMAGE", "VIDEO", "GIF"], ["IMAGE"]], text,
        #                 handleanimated=True)

    @commands.command(aliases=["handitover", "takeit", "giveme"])
    async def givemeyourphone(self, ctx):
        """
        Overlays an image over the hand of the boy in the "give me your phone" meme.
        https://knowyourmeme.com/memes/give-me-your-phone

        :param ctx: discord context
        :mediaparam media: The media to be overlayed over his hand.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.givemeyourphone, [["IMAGE", "VIDEO", "GIF"]], handleanimated=True)

    @commands.command(aliases=["donald", "donalttrump", "trump", "trumptweet", "donaldtrumptweet", "dontweet",
                               "donal", "donaltweet"])
    async def donaldtweet(self, ctx, *, text):
        """
        Makes a fake Donald Trump tweet.

        :param ctx: discord context
        :param text: The text to put in the fake tweet.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.dontweet, [], [text])

    @commands.command(aliases=["texttospeak", "speak", "talk", "speech", "espeak"])
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
        await improcess(ctx, processing_common.tts, [], text, voice)

    # WIP
    @commands.command()
    async def epicbirthday(self, ctx: commands.Context, *, text):
        """
        let mediaforge wish someone a very epic birthday!!!
        all credit for song goes to https://epichappybirthdaysongs.com/

        :param ctx:
        :param text: who you want to wish an epic birthday to
        :return: a custom made song just for you!
        """
        await improcess(ctx, processing_ffmpeg.epicbirthday, [], text)
