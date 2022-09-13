import asyncio
import os
import typing

import discord
import emojis
import regex as re
import yt_dlp as youtube_dl
from discord.ext import commands

import config
import processing.ffmpeg
import processing.ffprobe
import utils.discordmisc
from core.clogs import logger
from core.process import process
from utils.common import prefix_function
from utils.dpy import UnicodeEmojiConverter
from utils.scandiscord import tenorsearch


class Conversion(commands.Cog, name="Conversion"):
    """
    Commands to convert media types and download internet-hosted media.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["filename", "name", "setname"])
    async def rename(self, ctx, filename: str):
        """
        Renames media.
        Note: Discord's spoiler feature is dependent on filenames starting with "SPOILER_". renaming files may
        unspoiler them.

        :param ctx: discord context
        :param filename: the new name of the file
        :mediaparam media: Any valid media.
        """
        file = await process(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]])
        await ctx.reply(file=discord.File(file, filename=filename))

    @commands.command(aliases=["spoil", "censor", "cw", "tw"])
    async def spoiler(self, ctx):
        """
        Spoilers media.

        :param ctx: discord context
        :mediaparam media: Any valid media.
        """
        file = await process(ctx, lambda x: x, [["VIDEO", "GIF", "IMAGE", "AUDIO"]])
        await ctx.reply(file=discord.File(file, spoiler=True))

    @commands.command(aliases=["avatar", "pfp", "profilepicture", "profilepic", "ayowhothismf", "av"])
    async def icon(self, ctx, *, body=None):
        """
        Grabs the icon url of a Discord user or server.

        This command works off IDs. user mentions contain the ID
        internally so mentioning a user will work. To get the icon of a guild, copy the guild id and use that as
        the parameter. To get the icon of a webhook message, copy the message ID and ***in the same channel as
        the message*** use the message ID as the parameter. This will also work for normal users though i have no
        idea why you'd do it that way.


        :param ctx: discord context
        :param body: must contain a user, guild, or message ID. if left blank, the author's avatar will be sent.
        """
        if body is None:
            result = [await utils.discordmisc.iconfromsnowflakeid(ctx.author.id, self.bot, ctx)]
        else:
            id_regex = re.compile(r'([0-9]{15,20})')
            tasks = []
            for m in re.finditer(id_regex, body):
                tasks.append(utils.discordmisc.iconfromsnowflakeid(int(m.group(0)), self.bot, ctx))
            result = await asyncio.gather(*tasks)
            result = list(filter(None, result))  # remove Nones
        if result:
            await ctx.reply("\n".join(result)[0:2000])
        else:
            await ctx.send(f"{config.emojis['warning']} No valid user, guild, or message ID found.")

    @commands.command(aliases=["youtube", "youtubedownload", "youtubedl", "ytdownload", "download", "dl", "ytdl"])
    async def videodl(self, ctx, videourl, videoformat: typing.Literal["video", "audio"] = "video"):
        """
        Downloads a web hosted video from sites like youtube.
        Any site here works: https://ytdl-org.github.io/youtube-dl/supportedsites.html

        :param ctx: discord context
        :param videourl: the URL of a video or the title of a youtube video.
        :param videoformat: download audio or video.
        """
        raise NotImplementedError  # TODO: implement
        # await processing.ytdl(url, form)
        # logger.info(url)
        msg = await ctx.reply(f"{config.emojis['working']} Downloading from site...", mention_author=False)
        try:

            # r = await processing.run_in_exec(ytdownload, videourl, videoformat)
            if r:
                [TempFile(f) for f in r]
                r = await processing.ffmpeg.assurefilesize(r, re_encode=False)
                if not r:
                    return
                txt = ""
                vcodec = await processing.ffprobe.get_vcodec(r)
                acodec = await processing.ffprobe.get_acodec(r)
                # sometimes returns av1 codec
                if vcodec and vcodec["codec_name"] not in ["h264", "gif", "webp", "png", "jpeg"]:
                    txt += f"The returned video is in the `{vcodec['codec_name']}` " \
                           f"({vcodec['codec_long_name']}) codec. Discord might not be able embed this " \
                           f"format. You can use " \
                           f"`{await prefix_function(self.bot, ctx.message, True)}reencode` to change the codec, " \
                           f"though this may increase the filesize or decrease the quality.\n"
                if acodec and acodec["codec_name"] not in ["aac", "mp3"]:
                    txt += f"The returned video's audio is in the `{vcodec['codec_name']}` " \
                           f"({vcodec['codec_long_name']}) codec. Some devices cannot play this. " \
                           f"You can use `{await prefix_function(self.bot, ctx.message, True)}reencode` " \
                           f"to change the codec, " \
                           f"though this may increase the filesize or decrease the quality."
                await msg.edit(content=f"{config.emojis['working']} Uploading to Discord...")
                await ctx.reply(txt, file=discord.File(r))
            else:
                await ctx.reply(f"{config.emojis['warning']} No available downloads found within Discord's "
                                f"file upload limit.")
            # os.remove(r)
            await msg.delete()
        except youtube_dl.DownloadError as e:
            await ctx.reply(f"{config.emojis['2exclamation']} {e}")

    @commands.command(aliases=["gif", "videotogif"])
    async def togif(self, ctx):
        """
        Converts a video to a GIF.

        :param ctx: discord context
        :mediaparam video: A video.
        """
        await process(ctx, processing.ffmpeg.mp4togif, [["VIDEO"]])

    @commands.command(aliases=["apng", "videotoapng", "giftoapng"])
    async def toapng(self, ctx):
        """
        Converts a video or gif to an animated png.

        :param ctx: discord context
        :mediaparam video: A video or gif.
        """
        await process(ctx, processing.ffmpeg.toapng, [["VIDEO", "GIF"]], resize=False)

    @commands.command(aliases=["audio", "mp3", "tomp3", "aac", "toaac"])
    async def toaudio(self, ctx):
        """
        Converts a video to only audio.

        :param ctx: discord context
        :mediaparam video: A video.
        """
        await process(ctx, processing.ffmpeg.toaudio, [["VIDEO", "AUDIO"]])

    @commands.command()
    async def tenorgif(self, ctx):
        """
        Sends the GIF url for a tenor gif.
        By default, tenor gifs are interpreted as MP4 files due to their superior quality.
        This command gets the gif straight from tenor, making it faster than $videotogif,
        however, some tenor gifs can be lower fps/quality than the converted video.

        :param ctx: discord context
        :mediaparam gif: any gif sent from tenor.
        """
        logger.info("Getting tenor gif...")
        file = await tenorsearch(ctx, True)
        if file:
            await ctx.send(file)
            logger.info("Complete!")
        else:
            await ctx.send(f"{config.emojis['x']} No tenor gif found.")

    @commands.command(aliases=["video", "giftovideo", "tomp4"])
    async def tovideo(self, ctx):
        """
        Converts a GIF to a video.

        :param ctx: discord context
        :mediaparam gif: A gif.
        """
        await process(ctx, processing.ffmpeg.giftomp4, [["GIF"]])

    @commands.command(aliases=["png", "mediatopng"])
    async def topng(self, ctx):
        """
        Converts media to PNG

        :param ctx: discord context
        :mediaparam media: A video, gif, or image.
        """
        await process(ctx, processing.ffmpeg.mediatopng, [["VIDEO", "GIF", "IMAGE"]])

    @commands.command(aliases=["emoji", "emojiimage", "emote", "emoteurl"])
    async def emojiurl(self, ctx, *custom_emojis: discord.PartialEmoji):
        """
        Sends the raw image for a custom Discord emoji.
        Each emoji is sent as a separate message intentionally to allow replying with a media command.

        :param ctx: discord context
        :param custom_emojis: Custom emojis to send the URL of. Be sure to put a space between them.
        """
        if emojis:
            out = []
            for emoji in custom_emojis[:5]:
                if emoji.is_custom_emoji():
                    out.append(str(emoji.url))
            await ctx.send("\n".join(out))
        else:
            raise commands.BadArgument(f"Your message doesn't contain any custom emojis!")

    @commands.command()
    async def twemoji(self, ctx, *twemojis: UnicodeEmojiConverter):
        """
        Sends the twemoji image for an emoji.
        Twemoji is the open source emoji set that discord desktop and twitter use. https://twemoji.twitter.com/

        :param ctx: discord context
        :param twemojis: Up to 5 default discord/unicode emojis
        """
        if ctx.message.reference:
            msg = ctx.message.reference.resolved.content
        if twemojis:
            for e in twemojis[:5]:
                chars = []
                for char in e:
                    chars.append(f"{ord(char):x}")  # get hex code of char
                chars = "-".join(chars).replace("/", "")
                fpath = f"rendering/twemoji/72x72/{chars}.png"
                logger.debug(f"trying twemoji {fpath}")
                if os.path.exists(fpath):
                    await ctx.reply(file=discord.File(fpath))
        else:
            raise commands.BadArgument(f"No default emojis found!")
