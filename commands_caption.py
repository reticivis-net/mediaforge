from discord.ext import commands
from mainutils import improcess


class Caption(commands.Cog, name="Captioning"):
    """
    Commands to caption media.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["demotivate", "motivational", "demotivational", "inspire", "uninspire"])
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
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.motivate, [["VIDEO", "GIF", "IMAGE"]], *caption,
        #                 handleanimated=True)

    @commands.command(aliases=["toptextbottomtext", "impact", "adviceanimal"])
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
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.meme, [["VIDEO", "GIF", "IMAGE"]], *caption,
        #                 handleanimated=True)

    @commands.command(aliases=["snapchat", "snap", "snapcap", "snapcaption", "snapchatcap", "classiccaption"])
    async def snapchatcaption(self, ctx, *, caption):
        """
        Captions media in the style of the classic Snapchat caption.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.snapchat, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

    @commands.command(aliases=["whisper", "wcap", "wcaption"])
    async def whispercaption(self, ctx, *, caption):
        """
        Captions media in the style of the confession website Whisper.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.whisper, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

    @commands.command(aliases=["news"])
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
        # await improcess(ctx, captionfunctions.breakingnews, [["VIDEO", "GIF", "IMAGE"]], *caption,
        #                 handleanimated=True)

    @commands.command(aliases=["tenor"])
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
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.tenorcap, [["VIDEO", "GIF", "IMAGE"]], *caption,
        #                 handleanimated=True)

    @commands.command(name="caption", aliases=["cap"])
    async def captioncommand(self, ctx, *, caption):
        """
        Captions media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.caption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

    @commands.command(aliases=["imstuff"])
    async def stuff(self, ctx, *, caption):
        """
        Captions media in the style of the "i'm stuff" meme

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.stuff, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

    @commands.command(aliases=["eminemcaption", "eminemcap"])
    async def eminem(self, ctx, *, caption):
        """
        Eminem says something below your media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.eminemcap, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

    @commands.command(aliases=["peter", "peterexplain", "petersay", "petergriffinexplain", "petergriffinsay"])
    async def petergriffin(self, ctx, *, caption):
        """
        Peter Griffin says something below your media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.petergriffincap, [["VIDEO", "GIF", "IMAGE"]], caption,
        #                 handleanimated=True)

    @commands.command(aliases=["stretchstuff"])
    async def stuffstretch(self, ctx, *, caption):
        """
        Alternate version of $stuff where RDJ stretches
        in this version, RDJ stretches vertically to the size of whatever text he says
        it's not a bug... its a feature™! (this command exists due to a former bug in $stuff)


        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.stuffstretch, [["VIDEO", "GIF", "IMAGE"]], caption,
        #                 handleanimated=True)

    @commands.command(aliases=["bottomcap", "botcap"])
    async def bottomcaption(self, ctx, *, caption):
        """
        Captions underneath media.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.bottomcaption, [["VIDEO", "GIF", "IMAGE"]], caption,
        #                 handleanimated=True)

    @commands.command(aliases=["esm", "&caption", "essemcaption", "esmbotcaption", "esmcap"])
    async def esmcaption(self, ctx, *, caption):
        """
        Captions media in the style of Essem's esmBot.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.esmcaption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

    @commands.command(aliases=["twitter", "twitcap", "twittercap"])
    async def twittercaption(self, ctx, *, caption):
        """
        Captions media in the style of a Twitter screenshot.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.twittercap, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

    @commands.command(aliases=["twitterdark", "twitcapdark", "twittercapdark"])
    async def twittercaptiondark(self, ctx, *, caption):
        """
        Captions media in the style of a dark mode Twitter screenshot.

        :param ctx: discord context
        :param caption: The caption text.
        :mediaparam media: A video, gif, or image.
        """
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, captionfunctions.twittercapdark, [["VIDEO", "GIF", "IMAGE"]], caption,
        #                 handleanimated=True)

    @commands.command()
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
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, improcessing.freezemotivate, [["VIDEO", "GIF"]], *caption)

    @commands.command()
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
        raise NotImplementedError  # TODO: implement
        # await improcess(ctx, improcessing.freezemotivate, [["VIDEO", "GIF"], ["AUDIO"]], *caption)
