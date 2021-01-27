# standard libs
import datetime
import glob
import json
import logging
import os
import random
import re
import string
import traceback
# pip libs
import coloredlogs
import discord
from discord.ext import commands
import aiohttp
import aiofiles
import humanize
# project files
import captionfunctions
import improcessing
import sus
import config

# TODO: fix image stacking
# TODO: overlay media command
# https://coloredlogs.readthedocs.io/en/latest/api.html#id28
# configure logging
field_styles = {
    'levelname': {'bold': True, 'color': 'blue'},
    'asctime': {'color': 2},
    'filename': {'color': 6},
    'funcName': {'color': 5},
    'lineno': {'color': 13}
}
level_styles = coloredlogs.DEFAULT_LEVEL_STYLES
level_styles['COMMAND'] = {'color': 4}
logging.addLevelName(25, "NOTICE")
logging.addLevelName(35, "SUCCESS")
logging.addLevelName(21, "COMMAND")
coloredlogs.install(level=config.log_level, fmt='[%(asctime)s] [%(filename)s:%(funcName)s:%(lineno)d] '
                                                '%(levelname)s %(message)s',
                    datefmt='%m/%d/%Y %I:%M:%S %p', field_styles=field_styles, level_styles=level_styles)

if __name__ == "__main__":  # prevents multiprocessing workers from running bot code
    renderpool = improcessing.initializerenderpool()
    if not os.path.exists("temp"):  # cant fucking believe i never had this
        os.mkdir("temp")
    bot = commands.Bot(command_prefix=config.command_prefix, help_command=None)


    @bot.event
    async def on_ready():
        logging.log(35, f"Logged in as {bot.user.name}!")
        game = discord.Activity(name=f"with your media | {config.command_prefix}help",
                                type=discord.ActivityType.playing)
        await bot.change_presence(activity=game)


    def get_random_string(length):
        return ''.join(random.choice(string.ascii_letters) for _ in range(length))


    async def fetch(url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    response.raise_for_status()
                return await response.text()


    async def saveurl(url, extension=None):
        """
        save a url to /temp
        :param url: web url of a file
        :param extension: force a file extension
        :return: local path of saved file
        """
        if extension is None:
            extension = url.split(".")[-1].split("?")[0]
        name = improcessing.temp_file(extension)
        async with aiohttp.ClientSession() as session:
            async with session.head(url) as resp:
                if resp.status == 200:
                    if "Content-Length" not in resp.headers:  # size of file to download
                        raise Exception("Cannot determine filesize!")
                    size = int(resp.headers["Content-Length"])
                    logging.info(f"Url is {humanize.naturalsize(size)}")
                    if 50000000 < size:  # file size to download must be under ~50MB
                        raise Exception(f"File is too big ({humanize.naturalsize(size)})!")
                else:
                    logging.error(f"aiohttp status {resp.status}")
                    logging.error(f"aiohttp status {await resp.read()}")
            async with session.get(url) as resp:
                if resp.status == 200:
                    logging.info(f"Saving url {url} as {name}")
                    f = await aiofiles.open(name, mode='wb')
                    await f.write(await resp.read())
                    await f.close()
                else:
                    logging.error(f"aiohttp status {resp.status}")
                    logging.error(f"aiohttp status {await resp.read()}")

        return name


    async def handlemessagesave(m: discord.Message, ctx: discord.ext.commands.Context):
        """
        handles saving of media from discord messages
        :param m: a discord message
        :param ctx: command context (for sending error messages)
        :return: local file path if saved, None if message has no savable media.
        """
        if len(m.embeds):
            if m.embeds[0].type == "gifv":
                # https://github.com/esmBot/esmBot/blob/master/utils/imagedetect.js#L34
                tenor = await fetch(
                    f"https://api.tenor.com/v1/gifs?ids={m.embeds[0].url.split('-').pop()}&key={config.tenor_key}")
                tenor = json.loads(tenor)
                if 'error' in tenor:
                    await ctx.reply(f"{config.emojis['2exclamation']} Tenor Error! `{tenor['error']}`")
                    logging.error(f"Tenor Error! `{tenor['error']}`")
                    return None
                else:
                    return await saveurl(tenor['results'][0]['media'][0]['mp4']['url'], "mp4")
            elif m.embeds[0].type in ["image", "video", "audio"]:
                return await saveurl(m.embeds[0].url)
        if len(m.attachments):
            return await saveurl(m.attachments[0].url)
        return None


    async def imagesearch(ctx, nargs=1):
        """
        searches the channel for nargs media
        :param ctx: command context
        :param nargs: amount of media to return
        :return: False if none or not enough media found, list of file paths if found
        """
        outfiles = []
        if ctx.message.reference:
            m = ctx.message.reference.resolved
            hm = await handlemessagesave(m, ctx)
            if hm is None:
                return False
            else:
                outfiles.append(hm)
                if len(outfiles) >= nargs:
                    return outfiles[::-1]
        async for m in ctx.channel.history(limit=50):
            hm = await handlemessagesave(m, ctx)
            if hm is not None:
                outfiles.append(hm)
                if len(outfiles) >= nargs:
                    return outfiles[::-1]
        return False


    async def handletenor(m, ctx, gif=False):
        """
        like handlemessagesave() but only for tenor
        :param m: discord message
        :param ctx: command context
        :param gif: return GIF url if true, mp4 url if false
        :return: raw tenor media url
        """
        if len(m.embeds):
            if m.embeds[0].type == "gifv":
                # https://github.com/esmBot/esmBot/blob/master/utils/imagedetect.js#L34
                tenor = await fetch(
                    f"https://api.tenor.com/v1/gifs?ids={m.embeds[0].url.split('-').pop()}&key={config.tenor_key}")
                tenor = json.loads(tenor)
                if 'error' in tenor:
                    logging.error(tenor['error'])
                    await ctx.send(f"{config.emojis['2exclamation']} Tenor Error! `{tenor['error']}`")
                    return False
                else:
                    if gif:
                        return tenor['results'][0]['media'][0]['gif']['url']
                    else:
                        return tenor['results'][0]['media'][0]['mp4']['url']
        return None


    # currently only used for 1 command, might have future uses?
    async def tenorsearch(ctx, gif=False):
        """
        like imagesearch() but for tenor
        :param ctx: discord context
        :param gif: return GIF url if true, mp4 url if false
        :return:
        """
        if ctx.message.reference:
            m = ctx.message.reference.resolved
            hm = await handletenor(m, ctx, gif)
            if hm is None:
                return False
            else:
                return hm
        else:
            async for m in ctx.channel.history(limit=50):
                hm = await handletenor(m, ctx, gif)
                if hm is not None:
                    return hm
        return False


    async def improcess(ctx: discord.ext.commands.Context, func: callable, allowedtypes: list, *args,
                        handleanimated=False):
        """
        The core function of the bot.
        :param ctx: discord context. media is gathered using imagesearch() with this.
        :param func: function to process input media with
        :param allowedtypes: list of lists of strings. each inner list is an argument, the strings it contains are the types that arg must be.
        :param args: any non-media arguments, passed into func()
        :param handleanimated: if func() only works on still images, set to True to process each frame individually.
        :return: nothing, all processing and uploading is done in this function
        """
        async with ctx.channel.typing():
            files = await imagesearch(ctx, len(allowedtypes))
            if files:
                for i, file in enumerate(files):
                    if (imtype := improcessing.mediatype(file)) not in allowedtypes[i]:
                        await ctx.reply(
                            f"{config.emojis['z']} Media #{i + 1} is {imtype}, it must be: {', '.join(allowedtypes[i])}")
                        logging.warning(f"Media {i} type {imtype} is not in {allowedtypes[i]}")
                        for f in files:
                            os.remove(f)
                        break
                else:
                    logging.info("Processing...")
                    msg = await ctx.reply(f"{config.emojis['working']} Processing...", mention_author=False)
                    if len(files) == 1:
                        filesforcommand = files[0]
                    else:
                        filesforcommand = files.copy()
                    if handleanimated:
                        result = await improcessing.handleanimated(filesforcommand, func, ctx, *args)
                    else:
                        result = await func(filesforcommand, *args)
                    result = await improcessing.assurefilesize(result, ctx)
                    logging.info("Uploading...")
                    await msg.edit(content=f"{config.emojis['working']} Uploading...")
                    await ctx.reply(file=discord.File(result))
                    await msg.delete()
                    for f in files:
                        try:
                            os.remove(f)
                        except FileNotFoundError:
                            pass
                    os.remove(result)
            else:
                logging.warning("No media found.")
                await ctx.send(f"{config.emojis['x']} No file found.")


    class Caption(commands.Cog, name="Caption Commands"):
        """
        Commands to caption media.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def motivate(self, ctx, *, caption):
            """
            Captions media in the style of demotivational posters.
            :Usage=$motivate `toptext`|`bottomtext`
            :Param=caption - The caption text. Optionally add a bottom text with a `|` character.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.motivate, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def meme(self, ctx, *, caption):
            """
            Captions media in the style of top text + bottom text memes.

            :Usage=$meme `toptext`|`bottomtext`
            :Param=caption - The caption text. Optionally add a bottom text with a `|` character.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, captionfunctions.meme, [["VIDEO", "GIF", "IMAGE"]], *caption,
                            handleanimated=True)

        @commands.command(name="caption", aliases=["cap"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def captioncommand(self, ctx, *, caption):
            """
            Captions media.

            :Usage=$caption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.caption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def stuff(self, ctx, *, caption):
            """
            Captions media in the style of the "i'm stuff" meme

            :Usage=$stuff `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.stuff, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def stuffstretch(self, ctx, *, caption):
            """
            Alternate version of $stuff
            it's not a bug... its a feature™! (this command exists due to a funny bug i made when trying to make $stuff)


            :Usage=$stuffstretch `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.stuffstretch, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.command(aliases=["bottomcap", "botcap"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def bottomcaption(self, ctx, *, caption):
            """
            Captions underneath media.

            :Usage=$bottomcaption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.bottomcaption, [["VIDEO", "GIF", "IMAGE"]], caption,
                            handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def esmcaption(self, ctx, *, caption):
            """
            Captions media in the style of Essem's esmBot.

            :Usage=$esmcaption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.esmcaption, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def twittercaption(self, ctx, *, caption):
            """
            Captions media in the style of a Twitter screenshot.

            :Usage=$twittercaption `text`
            :Param=caption - The caption text.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, captionfunctions.twittercap, [["VIDEO", "GIF", "IMAGE"]], caption, handleanimated=True)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def freezemotivate(self, ctx, *, caption):
            """
            Ends video with a freeze frame from $motivate.

            :Usage=$freezemotivate `text`
            :Param=caption - The caption text.
            :Param=video - A video or gif. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, improcessing.freezemotivate, [["VIDEO", "GIF"]], *caption)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def freezemotivateaudio(self, ctx, *, caption):
            # TODO: merge this into freezemotivate
            """
            Ends video with a freeze frame from $motivate with custom audio.

            :Usage=$freezemotivateaudio `text`
            :Param=caption - The caption text.
            :Param=video - A video or gif. (automatically found in channel)
            :Param=audio - An audio file. (automatically found in channel)
            """
            caption = caption.split("|")
            if len(caption) == 1:
                caption.append("")
            await improcess(ctx, improcessing.freezemotivate, [["VIDEO", "GIF"], ["AUDIO"]], *caption)


    class Media(commands.Cog, name="Media Processing"):
        """
        Basic media editing/processing commands.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def jpeg(self, ctx, strength: int = 30, stretch: int = 20, quality: int = 10):
            """
            Makes media into a low quality jpeg

            :Usage=$jpeg `[strength]` `[stretch]` `[quality]`
            :Param=strength - amount of times to jpegify image. must be between 1 and 100. defaults to 30.
            :Param=stretch - randomly stretch the image by this number on each jpegification. an cause strange effects on videos. must be between 0 and 40. defaults to 20.
            :Param=quality - quality of JPEG compression. must be between 1 and 95. defaults to 10.
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            if not 0 < strength <= 100:
                await ctx.send(f"{config.emojis['warning']} Strength must be between 0 and 100.")
                return
            if not 0 <= stretch <= 40:
                await ctx.send(f"{config.emojis['warning']} Stretch must be between 0 and 40.")
                return
            if not 1 <= quality <= 95:
                await ctx.send(f"{config.emojis['warning']} Quality must be between 1 and 95.")
                return
            await improcess(ctx, captionfunctions.jpeg, [["VIDEO", "GIF", "IMAGE"]], strength, stretch, quality,
                            handleanimated=True)

        @commands.command(aliases=["pad"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def square(self, ctx):
            """
            Pads media into a square shape.

            :Usage=$square
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, improcessing.pad, [["VIDEO", "GIF", "IMAGE"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def imageaudio(self, ctx):
            """
            Combines an image and audio into a video.

            :Usage=$imageaudio
            :Param=image - An image. (automatically found in channel)
            :Param=audio - An audio file. (automatically found in channel)
            """
            await improcess(ctx, improcessing.imageaudio, [["IMAGE"], ["AUDIO"]])

        @commands.command(aliases=["concat", "combinev"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def concatv(self, ctx):
            """
            Combines 2 video files.
            The output video will take on all of the settings of the FIRST video, and the second
            video will take on those settings.

            :Usage=$concatv
            :Param=video1 - A video or gif. (automatically found in channel)
            :Param=video2 - A video or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.concatv, [["VIDEO", "GIF"], ["VIDEO", "GIF"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def hstack(self, ctx):
            """
            Stacks 2 videos horizontally

            :Usage=$hstack
            :Param=video1 - A video or gif. (automatically found in channel)
            :Param=video2 - A video or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], "hstack")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def vstack(self, ctx):
            """
            Stacks 2 videos horizontally

            :Usage=$vstack
            :Param=video1 - A video or gif. (automatically found in channel)
            :Param=video2 - A video or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.stack, [["VIDEO", "GIF", "IMAGE"], ["VIDEO", "GIF", "IMAGE"]], "vstack")

        @commands.command(name="speed")
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def spcommand(self, ctx, speed: float = 2):
            """
            Changes the speed of media.
            This command preserves the original FPS, which means speeding up will drop frames. See $fps.

            :Usage=$speed `[speed]`
            :Param=speed - Multiplies input video speed by this number. must be between 0.5 and 10. defaults to 2.
            :Param=video - A video or gif. (automatically found in channel)
            """
            # i want this to allow 0.25 but fuckin atempo's minimum is 0.5
            if not 0.5 <= speed <= 10:
                await ctx.send(f"{config.emojis['warning']} Speed must be between 0.5 and 10")
                return
            await improcess(ctx, improcessing.speed, [["VIDEO", "GIF"]], speed)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def reverse(self, ctx):
            """
            Reverses media.

            :Usage=$reverse
            :Param=video - A video or gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.reverse, [["VIDEO", "GIF"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def compressv(self, ctx, crf: float = 51, qa: float = 8000):
            """
            Makes videos terrible quality.
            The strange ranges on the numbers are because they are quality settings in FFmpeg's encoding.
            CRF info is found at https://trac.ffmpeg.org/wiki/Encode/H.264#crf

            :Usage=$compressv `[crf]` `[qa]`
            :Param=crf - Controls video quality. Higher is worse quality. must be between 28 and 51. defaults to 51.
            :Param=qa - Audio sample rate in Hz. lower is worse quality. must be between 8000 and 44100. defaults to 8000
            :Param=video - A video or gif. (automatically found in channel)

            """
            if not 28 <= crf <= 51:
                await ctx.send(f"{config.emojis['warning']} CRF must be between 28 and 51.")
                return
            if not 8000 <= qa <= 44100:
                await ctx.send(f"{config.emojis['warning']} qa must be between 8000 and 44100.")
                return
            await improcess(ctx, improcessing.quality, [["VIDEO", "GIF"]], crf, qa)

        @commands.command(name="fps")
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def fpschange(self, ctx, fps: float = 30):
            """
            Changes the FPS of media.
            This command keeps the speed the same.
            BEWARE: Changing the FPS of gifs can create strange results due to the strange way GIFs store FPS data.
            GIFs are only stable at certain FPS values. These include 50, 30, 15, 10, and others.
            An important reminder that by default tenor "gifs" are interpreted as mp4s, which do not suffer this problem.

            :Usage=$fpschange `[fps]`
            :Param=fps - Frames per second of the output. must be between 1 and 60. defaults to 30.
            :Param=video - A video or gif. (automatically found in channel)
            """
            if not 1 <= fps <= 60:
                await ctx.send(f"{config.emojis['warning']} FPS must be between 1 and 60.")
                return
            await improcess(ctx, improcessing.changefps, [["VIDEO", "GIF"]], fps)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def trim(self, ctx, length: int):
            """
            Trims media.

            :Usage=$trim `[length]`
            :Param=length - Length in seconds to trim the media to.
            :Param=media - A video, gif, or audio file. (automatically found in channel)
            """
            await improcess(ctx, improcessing.trim, [["VIDEO", "GIF", "AUDIO"]], length)


    class Conversion(commands.Cog, name="Media Conversion"):
        """
        Commands to convert one type of media to another
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def togif(self, ctx):
            """
            Converts a video to a GIF.

            :Usage=$togif
            :Param=video - A video. (automatically found in channel)
            """
            await improcess(ctx, improcessing.mp4togif, [["VIDEO"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def tenorgif(self, ctx):
            """
            Sends the GIF url for a tenor gif.
            By default, tenor gifs are interpreted as MP4 files due to their superior quality.
            This command gets the gif straight from tenor, making it faster than $videotogif,
            however, some tenor gifs can be lower fps/quality than the converted video.

            :Usage=$tenorgif
            :Param=gif - any gif sent from tenor. (automatically found in channel)
            """
            logging.info("Getting tenor gif...")
            file = await tenorsearch(ctx, True)
            if file:
                await ctx.send(file)
                logging.info("Complete!")
            else:
                await ctx.send(f"{config.emojis['x']} No tenor gif found.")

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def tovideo(self, ctx):
            """
            Converts a GIF to a video.

            :Usage=$tovideo
            :Param=gif - A gif. (automatically found in channel)
            """
            await improcess(ctx, improcessing.giftomp4, [["GIF"]])

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def topng(self, ctx):
            """
            Converts media to PNG

            :Usage=$topng
            :Param=media - A video, gif, or image. (automatically found in channel)
            """
            await improcess(ctx, improcessing.mediatopng, [["VIDEO", "GIF", "IMAGE"]])


    class Other(commands.Cog, name="Other Commands"):
        """
        Commands that don't fit in the other categories.
        """

        def __init__(self, bot):
            self.bot = bot

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def help(self, ctx, *, arg=None):
            """
            Shows the help message.

            :Usage=$help `[inquiry]`
            :Param=inquiry - the name of a command or command category. If none is provided, all categories are shown.
            """
            if arg is None:
                embed = discord.Embed(title="Help", color=discord.Color(0xB565D9),
                                      description=f"Run `{config.command_prefix}help category` to list commands from "
                                                  f"that category.")
                for c in bot.cogs.values():
                    if c.qualified_name != "Owner Only":
                        embed.add_field(name=c.qualified_name, value=c.description)
                await ctx.reply(embed=embed)
            elif arg.lower() in [c.lower() for c in bot.cogs]:
                cogs_lower = {k.lower(): v for k, v in bot.cogs.items()}
                cog = cogs_lower[arg.lower()]
                embed = discord.Embed(title=cog.qualified_name,
                                      description=cog.description + f"\nRun `{config.command_prefix}help command` for "
                                                                    f"more information on a command.",
                                      color=discord.Color(0xD262BA))
                for cmd in cog.get_commands():
                    embed.add_field(name=f"{config.command_prefix}{cmd.name}", value=cmd.short_doc)
                await ctx.reply(embed=embed)
            elif arg.lower() in [c.name for c in bot.commands]:
                for all_cmd in bot.commands:
                    if all_cmd.name == arg.lower():
                        cmd: discord.ext.commands.Command = all_cmd
                        break
                embed = discord.Embed(title=config.command_prefix + cmd.name, description=cmd.cog_name,
                                      color=discord.Color(0xEE609C))
                fields = {}
                fhelp = []
                for line in cmd.help.split("\n"):
                    if line.startswith(":"):
                        if line.split("=")[0].strip(":") in fields:
                            fields[line.split("=")[0].strip(":")] += "\n" + "=".join(line.split("=")[1:])
                        else:
                            fields[line.split("=")[0].strip(":")] = "=".join(line.split("=")[1:])
                    else:
                        fhelp.append(line)
                fhelp = "\n".join(fhelp)
                embed.add_field(name="Command Information", value=fhelp.replace("$", config.command_prefix),
                                inline=False)
                for k, v in fields.items():
                    if k == "Param":
                        k = "Paramaters"
                    embed.add_field(name=k, value=v.replace("$", config.command_prefix), inline=False)
                if cmd.aliases:
                    embed.add_field(name="Aliases", value=", ".join(cmd.aliases))
                await ctx.reply(embed=embed)
            else:
                await ctx.reply(f"{config.emojis['warning']} `{arg}` is not the name of a command or a command category!")

        @commands.command(aliases=["ffprobe"])
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def info(self, ctx):
            """
            Provides info on a media file.
            Info provided is from ffprobe and libmagic.

            :Usage=$info
            :Param=media - Any media file.
            """
            async with ctx.channel.typing():
                file = await imagesearch(ctx)
                if file:
                    result = await improcessing.ffprobe(file[0])
                    await ctx.reply(f"`{result[1]}` `{result[2]}`\n```{result[0]}```")
                    os.remove(file[0])
                else:
                    await ctx.send(f"{config.emojis['x']} No file found.")

        @commands.command()
        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        async def feedback(self, ctx):
            """
            Give feedback for the bot.
            This sends various links from the github repo for reporting issues or asking questions.

            :Usage=$feedback
            """
            embed = discord.Embed(title="Feedback", description="Feedback is best given via the GitHub repo, various "
                                                                "links are provided below.",
                                  color=discord.Color(0xD262BA))
            embed.add_field(name="Report a bug",
                            value="To report a bug, make an issue at\nhttps://github.com/HexCodeFFF/captionbot/issues",
                            inline=False)
            embed.add_field(name="Ask a question", value="Have a question? Use the Q&A Discussion "
                                                         "page.\nhttps://github.com/HexCodeFFF/captionbot/discussions/c"
                                                         "ategories/q-a", inline=False)
            embed.add_field(name="Give an idea", value="Have an idea or suggestion? Use the Ideas Discussion page.\nhtt"
                                                       "ps://github.com/HexCodeFFF/captionbot/discussions/categories/id"
                                                       "eas", inline=False)
            embed.add_field(name="Something else?", value="Anything is welcome in the discussion page!\nhttps://github."
                                                          "com/HexCodeFFF/captionbot/discussions", inline=False)
            embed.add_field(name="Why GitHub?", value="Using GitHub for feedback makes it much easier to organize any i"
                                                      "ssues and to implement them into the bot's code.")
            await ctx.reply(embed=embed)

        @commands.command(aliases=['sus', 'imposter'])
        async def jermatext(self, ctx, *, text="when the imposter is sus!😳"):
            """
            Cut and slice the popular Jerma sus meme to any message
            For any letter not in the original meme, a random slice of the face is selected.
            Based on https://github.com/aechaechaech/Jerma-Imposter-Message-Generator

            :Usage=$sus `text`
            :Param=text - The text to cut and splice.
            """
            file = sus.sus(text)
            await ctx.reply(file=discord.File(file))
            os.remove(file)

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def attributions(self, ctx):
            """
            Lists most libraries and programs this bot uses.
            :Usage=$attributions
            """
            with open("attributions.txt", "r") as f:
                await ctx.send(f.read())

        @commands.cooldown(1, config.cooldown, commands.BucketType.user)
        @commands.command()
        async def emojiurl(self, ctx, *, msg):
            """
            Extracts the raw file from up to 5 custom emojis.
            Each emoji is sent as a separate message intentionally to allow replying with a media command.

            :Usage=$emojiurl `emojis`
            :Param=emojis - Up to 5 custom emojis to send the URL of.
            """
            urls = []
            emojiregex = "<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>"
            for i, match in enumerate(re.finditer(emojiregex, msg)):
                if i == 5:
                    break
                emojiid = int(match.group(3))
                anim = bool(match.group(1))
                url = str(discord.PartialEmoji(id=emojiid, name="", animated=anim).url)
                urls.append(url)
            if urls:
                for url in urls:
                    await ctx.reply(url)
            else:
                await ctx.reply(f"{config.emojis['warning']} Your message doesn't contain any custom emojis!")


    class Debug(commands.Cog, name="Owner Only"):
        def __init__(self, bot):
            self.bot = bot

        @commands.command(hidden=True)
        @commands.is_owner()
        async def say(self, ctx, *, msg):
            """
            Make the bot say something
            """
            await ctx.message.delete()
            await ctx.channel.send(msg)

        @commands.command(hidden=True)
        @commands.is_owner()
        async def error(self, ctx):
            """
            Raise an error
            """
            raise Exception("Exception raised by $error command")

        @commands.command(hidden=True)
        @commands.is_owner()
        async def errorcmd(self, ctx):
            """
            Raise an error from the commandline
            """
            await improcessing.run_command("ffmpeg", "-hide_banner", "dsfasdfsadfasdfasdf")

        @commands.command(hidden=True)
        @commands.is_owner()
        async def cleartemp(self, ctx):
            """
            Clear the /temp folder
            """
            l = len(glob.glob('temp/*'))
            for f in glob.glob('temp/*'):
                os.remove(f)
            await ctx.send(f"✅ Removed {l} files.")

        @commands.command(hidden=True, aliases=["stop", "close"])
        @commands.is_owner()
        async def shutdown(self, ctx):
            """
            Shut down the bot
            """
            await ctx.send("✅ Shutting Down...")
            logging.log(25, "Shutting Down...")
            renderpool.close()
            await bot.logout()
            await bot.close()


    def logcommand(cmd):
        cmd = cmd.replace("\n", "\\n")
        if len(cmd) > 100:
            cmd = cmd[:100] + "..."
        return cmd


    @bot.listen()
    async def on_command(ctx):
        if isinstance(ctx.channel, discord.DMChannel):
            logging.log(25,
                        f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ran "
                        f"'{logcommand(ctx.message.content)}' in DMs")
        else:
            logging.log(25,
                        f"@{ctx.message.author.name}#{ctx.message.author.discriminator}"
                        f" ({ctx.message.author.display_name}) ran '{logcommand(ctx.message.content)}' in channel "
                        f"#{ctx.channel.name} in server {ctx.guild}")


    @bot.listen()
    async def on_command_completion(ctx):
        logging.log(35,
                    f"Command '{logcommand(ctx.message.content)}' by @{ctx.message.author.name}#{ctx.message.author.discriminator} "
                    f"is complete!")


    @bot.listen()
    async def on_command_error(ctx, commanderror):
        if isinstance(commanderror, discord.ext.commands.errors.CommandNotFound):
            msg = ctx.message.content.replace("@", "\\@")
            err = f"{config.emojis['exclamation_question']} Command `{msg.split(' ')[0]}` does not exist."
            logging.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.NotOwner):
            err = f"{config.emojis['x']} You are not authorized to use this command."
            logging.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.CommandOnCooldown):
            err = f"{config.emojis['clock']} " + str(commanderror).replace("@", "\\@")
            logging.warning(err)
            await ctx.reply(err)
        elif isinstance(commanderror, discord.ext.commands.errors.MissingRequiredArgument):
            err = f"{config.emojis['question']} " + str(commanderror).replace("@", "\\@")
            logging.warning(err)
            await ctx.reply(err)
        else:
            logging.error(commanderror, exc_info=(type(commanderror), commanderror, commanderror.__traceback__))
            tr = improcessing.temp_file("txt")
            trheader = f"DATETIME:{datetime.datetime.now()}\nCOMMAND:{ctx.message.content}\nTRACEBACK:\n"
            with open(tr, "w+") as t:
                t.write(trheader + ''.join(
                    traceback.format_exception(etype=type(commanderror), value=commanderror,
                                               tb=commanderror.__traceback__)))
            await ctx.reply(f"{config.emojis['2exclamation']} `" + str(commanderror).replace("@", "\\@") +
                            "`\nPlease report this error with the attached traceback to the github.",
                            file=discord.File(tr))
            os.remove(tr)


    logging.info(f"discord.py {discord.__version__}")

    # bot.remove_command('help')
    for f in glob.glob('temp/*'):
        os.remove(f)
    bot.add_cog(Caption(bot))
    bot.add_cog(Media(bot))
    bot.add_cog(Conversion(bot))
    bot.add_cog(Other(bot))
    bot.add_cog(Debug(bot))

    bot.run(config.bot_token)
