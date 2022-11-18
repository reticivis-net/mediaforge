from discord.ext import commands

import processing.ffmpeg
import processing.vips.caption

import processing.vips.vipsutils
from core.process import process


class Caption(commands.Cog, name="Captioning"):
    """
    Commands to caption media.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(aliases=["demotivate", "motivational", "demotivational", "inspire", "uninspire"])
    async def motivate(self, ctx, *, caption):
        """
        Captions media in the style of demotivational posters.

        :param ctx: discord context
        :param caption: The caption text. Optionally add a bottom text with a `|` character.
        :mediaparam media: A video, gif, or image.
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("")
        await process(ctx, processing.ffmpeg.motivate, [["VIDEO", "GIF", "IMAGE"]], caption)

    @commands.hybrid_command(aliases=["toptextbottomtext", "impact", "adviceanimal"])
    async def meme(self, ctx, *, caption):
        """
        Captions media in the style of top text + bottom text memes.

        :param ctx: discord context
        :param caption: The caption text. Optionally add a bottom text with a `|` character.
        :mediaparam media: A video, gif, or image.
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("")
        await process(ctx, processing.vips.vipsutils.generic_caption_overlay, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.meme, caption)

    @commands.hybrid_command(aliases=["snapchat", "snap", "snapcap", "snapcaption", "snapchatcap", "classiccaption"])
    async def snapchatcaption(self, ctx, *, caption):
        """
        Captions media in the style of the classic Snapchat caption.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_overlay, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.snapchat, [caption])

    @commands.hybrid_command(aliases=["whisper", "wcap", "wcaption"])
    async def whispercaption(self, ctx, *, caption):
        """
        Captions media in the style of the confession website Whisper.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_overlay, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.whisper, [caption])

    @commands.hybrid_command(aliases=["news"])
    async def breakingnews(self, ctx, *, caption):
        """
        Create a fake "Breaking News" screencap.
        This command is a clone of https://breakyourownnews.com/
        To quote them: This app is intended for fun, humour and parody - be careful what you make and how it may be
        shared. You should avoid making things which are unlawful, defamatory or likely to cause distress. Have fun
        and be kind!

        :param ctx: discord context
        :param caption: The headline text. Optionally add a bottom "ticker" text with a `|` character.
        :mediaparam media: A video, gif, or image.
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("")
        raise NotImplementedError  # TODO: implement
        # await process(ctx, captionfunctions.breakingnews, [["VIDEO", "GIF", "IMAGE"]], *caption,
        #                 handleanimated=True)

    @commands.hybrid_command(aliases=["tenor"])
    async def tenorcap(self, ctx, *, caption):
        """
        Captions media in the style of tenor.

        :param ctx: discord context
        :param caption: The caption text. Optionally add a bottom text with a `|` character.
        :mediaparam media: A video, gif, or image.
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("")
        await process(ctx, processing.vips.vipsutils.generic_caption_overlay, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.tenor, caption)

    @commands.hybrid_command(name="caption", aliases=["cap"])
    async def captioncommand(self, ctx, *, caption):
        """
        Captions media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_stack, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.mediaforge_caption, [caption])

    @commands.hybrid_command(aliases=["imstuff"])
    async def stuff(self, ctx, *, caption):
        """
        Captions media in the style of the "i'm stuff" meme

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_stack, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.generic_image_caption, [caption], "rendering/images/Stuff.PNG", reverse=True)

    @commands.hybrid_command(aliases=["eminemcaption", "eminemcap"])
    async def eminem(self, ctx, *, caption):
        """
        Eminem says something below your media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_stack, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.generic_image_caption, [caption], "rendering/images/eminem.png", reverse=True)

    @commands.hybrid_command(aliases=["peter", "peterexplain", "petersay", "petergriffinexplain", "petergriffinsay"])
    async def petergriffin(self, ctx, *, caption):
        """
        Peter Griffin says something below your media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_stack, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.generic_image_caption, [caption], "rendering/images/Peter_Griffin.png", reverse=True)

    @commands.hybrid_command(aliases=["bottomcap", "botcap"])
    async def bottomcaption(self, ctx, *, caption):
        """
        Captions underneath media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_stack, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.mediaforge_caption, [caption], reverse=True)

    @commands.hybrid_command(aliases=["esm", "&caption", "essemcaption", "esmbotcaption", "esmcap"])
    async def esmcaption(self, ctx, *, caption):
        """
        Captions media in the style of Essem's esmBot.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.vips.vipsutils.generic_caption_stack, [["VIDEO", "GIF", "IMAGE"]],
                      processing.vips.caption.esmcaption, [caption])

    @commands.hybrid_command(aliases=["twitter", "twitcap", "twittercap"])
    async def twittercaption(self, ctx, *, caption):
        """
        Captions media in the style of a Twitter screenshot.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.twitter_caption, [["VIDEO", "GIF", "IMAGE"]], caption, False)

    @commands.hybrid_command(aliases=["twitterdark", "twitcapdark", "twittercapdark"])
    async def twittercaptiondark(self, ctx, *, caption):
        """
        Captions media in the style of a dark mode Twitter screenshot.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.twitter_caption, [["VIDEO", "GIF", "IMAGE"]], caption, True)

    @commands.hybrid_command()
    async def freezemotivate(self, ctx, *, caption):
        """
        Ends video with a freeze frame from $motivate.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam video: A video or gif.
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("")
        await process(ctx, processing.ffmpeg.freezemotivate, [["VIDEO", "GIF"]], *caption)

    @commands.hybrid_command()
    async def freezemotivateaudio(self, ctx, *, caption):
        # TODO: merge this into freezemotivate
        """
        Ends video with a freeze frame from $motivate with custom audio.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam video: A video or gif.
        :mediaparam audio: An audio file.
        """
        caption = caption.split("|")
        if len(caption) == 1:
            caption.append("")
        await process(ctx, processing.ffmpeg.freezemotivate, [["VIDEO", "GIF"], ["AUDIO"]], *caption)
