import glob
import json
import logging
import os
import random
import re
import string
import coloredlogs
import discord
from discord.ext import commands
import captionfunctions
import improcessing
import aiohttp
import aiofiles
import humanize

# TODO: twitter style caption
# TODO: custom style caption
# TODO: better help command
# TODO: stitch media command
# TODO: concat media command
# TODO: end video with motivate freeze frame command
# TODO: attach audio to video command
# TODO: credits command
# TODO: enforce image types better lol!
if __name__ == '__main__':  # if i don't have this multiprocessing breaks idfk
    coloredlogs.install(level='INFO', fmt='[%(asctime)s] %(levelname)s %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p')
    logging.info(f"discord.py {discord.__version__}")
    bot = commands.Bot(command_prefix='$', description='CaptionX')
    # bot.remove_command('help')
    for f in glob.glob('temp/*'):
        os.remove(f)
    with open('tenorkey.txt') as f:  # not on github for obvious reasons
        tenorkey = f.read()


    def get_random_string(length):
        return ''.join(random.choice(string.ascii_letters) for i in range(length))


    async def fetch(url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    response.raise_for_status()
                return await response.text()


    async def saveurl(url, extension=None):
        if extension is None:
            extension = url.split(".")[-1].split("?")[0]
        while True:
            name = f"temp/{get_random_string(8)}.{extension}"
            if not os.path.exists(name):
                async with aiohttp.ClientSession() as session:
                    async with session.head(url) as resp:
                        if resp.status == 200:
                            if "Content-Length" not in resp.headers:
                                raise Exception("Cannot determine filesize!")
                            size = int(resp.headers["Content-Length"])
                            logging.info(f"Url {url} is {humanize.naturalsize(size)}")
                            if 50000000 < size:
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


    async def handlemessagesave(m, ctx: discord.ext.commands.Context):
        if len(m.embeds):
            if m.embeds[0].type == "gifv":
                # https://github.com/esmBot/esmBot/blob/master/utils/imagedetect.js#L34
                tenor = await fetch(
                    f"https://api.tenor.com/v1/gifs?ids={m.embeds[0].url.split('-').pop()}&key={tenorkey}")
                tenor = json.loads(tenor)
                if 'error' in tenor:
                    print(tenor['error'])
                    await ctx.send(f":bangbang: Tenor Error! `{tenor['error']}`")
                    return False
                else:
                    return await saveurl(tenor['results'][0]['media'][0]['mp4']['url'], "mp4")
            elif m.embeds[0].type == "image" or m.embeds[0].type == "video":
                return await saveurl(m.embeds[0].url)
        elif len(m.attachments):
            if m.attachments[0].width:
                return await saveurl(m.attachments[0].url)
        return None


    async def imagesearch(ctx):
        if ctx.message.reference:
            m = ctx.message.reference.resolved
            hm = await handlemessagesave(m, ctx)
            if hm is None:
                return False
            else:
                return hm
        else:
            async for m in ctx.channel.history(limit=50):
                hm = await handlemessagesave(m, ctx)
                if hm is not None:
                    return hm
        return False


    async def handletenor(m, ctx, gif=False):
        if len(m.embeds):
            if m.embeds[0].type == "gifv":
                # https://github.com/esmBot/esmBot/blob/master/utils/imagedetect.js#L34
                tenor = await fetch(
                    f"https://api.tenor.com/v1/gifs?ids={m.embeds[0].url.split('-').pop()}&key={tenorkey}")
                tenor = json.loads(tenor)
                if 'error' in tenor:
                    print(tenor['error'])
                    await ctx.send(f":bangbang: Tenor Error! `{tenor['error']}`")
                    return False
                else:
                    if gif:
                        return tenor['results'][0]['media'][0]['gif']['url']
                    else:
                        return tenor['results'][0]['media'][0]['mp4']['url']
        return None


    async def tenorsearch(ctx, gif=False):
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


    @bot.event
    async def on_ready():
        logging.info(f"Logged in as {bot.user.name}!")
        game = discord.Activity(name=f"with your files",
                                type=discord.ActivityType.playing)
        await bot.change_presence(activity=game)


    @bot.command()
    async def emojiurl(ctx, *, msg):
        """
        Extracts the raw file from up to 5 custom emojis.
        Each emoji is sent as a separate message intentionally to allow replying with a media command.

        Parameters:
            msg - any text that contains at least one custom emoji.
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
                await ctx.send(url)
        else:
            await ctx.send("⚠ Your message doesn't contain any custom emojis!")


    @bot.command()
    async def tenorgif(ctx, *, gif=""):
        """
        Sends the GIF url for a tenor gif.
        By default, tenor gifs are interpreted as MP4 files due to their superior quality.
        This command gets the gif straight from tenor, making it faster than $videotogif.

        Parameters:
            gif - a valid tenor URL
        """
        logging.info("Getting tenor gif...")
        file = await tenorsearch(ctx, True)
        if file:
            await ctx.send(file)
            logging.info("Complete!")
        else:
            await ctx.send("❌ No tenor gif found.")


    @bot.command()
    async def videotogif(ctx):
        """
        Converts a video to a GIF.

        Parameters:
            video - any video format FFMPEG supports.
        """
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.mp4togif(file)
            if result:
                result = await improcessing.assurefilesize(result, ctx)
                await ctx.channel.trigger_typing()
                logging.info("Uploading image...")
                await ctx.reply(file=discord.File(result))
                await msg.delete()
                os.remove(file)
                os.remove(result)
            else:
                await ctx.send("❌ Detected file is not a valid video.")
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def giftovideo(ctx):
        """
        Converts a GIF to a video.

        Parameters:
            gif - a gif file
        """
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.giftomp4(file)
            if result:
                result = await improcessing.assurefilesize(result, ctx)
                await ctx.channel.trigger_typing()
                logging.info("Uploading image...")
                await ctx.reply(file=discord.File(result))
                await msg.delete()
                os.remove(file)
                os.remove(result)
            else:
                await ctx.send("⚠ Detected file is not a valid gif.")
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def mediatopng(ctx):
        """
        Converts media to PNG

        Parameters:
            media - any valid media file.
        """
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.mediatopng(file)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
        else:
            await ctx.send("❌ No file found.")


    @bot.command(name="speed")
    async def spcommand(ctx, speed: float = 2):
        """
        Changes the speed of media.
        This command preserves the original FPS.

        Parameters:
            media - any valid media file.
            speed - speed to multiply the video by. must be between 0.25 and 10. defaults to 2.
        """
        # raise NotImplementedError("i fucking hate ffmpeg")
        if not 0.25 <= speed <= 10:
            await ctx.send("⚠ Speed must be between 0.25 and 10")
            return
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.speed(file, speed)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def compressv(ctx, crf: float = 51, qa: float = 0.2):
        """
        Makes videos terrible quality.
        The strange ranges on the numbers are because they are quality settings in FFmpeg's encoding.
        CRF info is found at https://trac.ffmpeg.org/wiki/Encode/H.264#crf
        q:a info is found at https://trac.ffmpeg.org/wiki/Encode/AAC#NativeFFmpegAACEncoder

        Parameters:
            media - any valid media file.
            crf - Controls video quality. Higher is worse quality. must be between 28 and 51. defaults to 51.
            qa - Controls audio quality. Lower is worse quality. must be between 0.1 and 2. defaults to 0.2.

        """
        if not 28 <= crf <= 51:
            await ctx.send("⚠ CRF must be between 28 and 51.")
            return
        if not 0.1 <= qa <= 2:
            await ctx.send("⚠ qa must be between 0.1 and 2.")
            return
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.quality(file, crf, qa)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
        else:
            await ctx.send("❌ No file found.")


    @bot.command(name="fps")
    async def fpschange(ctx, fps: float = 30):
        """
        Changes the FPS of media.
        This command keeps the speed the same.
        BEWARE: Changing the FPS of gifs can create strange results due to the strange way GIFs store FPS data.
        GIFs are only stable at certain FPS values. These include 50, 30, 15, 10, and others.
        An important reminder that by default tenor "gifs" are interpreted as mp4s, which do not suffer this problem.

        Parameters:
            media - any valid media file.
            fps - FPS to change the video to. must be between 1 and 60. defaults to 30.
        """
        if not 1 <= fps <= 60:
            await ctx.send("⚠ FPS must be between 1 and 60.")
            return
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.changefps(file, fps)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def esmcaption(ctx, *, caption):
        """
        Captions media in the style of Essem's esmBot.

        Parameters:
            media - any valid media file
            caption - the caption text
        """
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.handleanimated(file, caption, captionfunctions.imcaption)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def jpeg(ctx, strength: int = 30, stretch: int = 20, quality: int = 10):
        """
        Makes media into a low quality jpeg

        Parameters:
            media - any valid media file
            strength - amount of times to jpegify image. must be between 1 and 100. defaults to 30.
            stretch - randomly stretch the image by this number on each jpegification. can cause strange effects on videos. must be between 0 and 40. defaults to 20.
            quality - quality of JPEG compression. must be between 1 and 95. defaults to 10.
        """
        if not 0 < strength <= 100:
            await ctx.send("⚠ Strength must be between 0 and 100.")
            return
        if not 0 <= stretch <= 40:
            await ctx.send("⚠ Stretch must be between 0 and 40.")
            return
        if not 1 <= quality <= 95:
            await ctx.send("⚠ Quality must be between 1 and 95.")
            return
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.handleanimated(file, [strength, stretch, quality], captionfunctions.jpeg)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def motivate(ctx, *, caption):
        """
        Captions media in the style of demotivational posters.

        Parameters:
            media - any valid media file
            caption - the caption texts. divide the top text from the bottom text with a comma.
        """
        caption = caption.split(",")
        if len(caption) == 1:
            caption.append("")
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.handleanimated(file, caption, captionfunctions.motivate)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def meme(ctx, *, cap):
        """
        Captions media in the style of top text + bottom text memes.

        Parameters:
            media - any valid media file
            caption - the caption texts. divide the top text from the bottom text with a comma.
        """
        cap = cap.split(",")
        if len(cap) == 1:
            cap.append("")
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.handleanimated(file, cap, captionfunctions.meme)
            result = await improcessing.assurefilesize(result, ctx)
            await ctx.channel.trigger_typing()
            logging.info("Uploading image...")
            await ctx.reply(file=discord.File(result))
            await msg.delete()
            os.remove(file)
            os.remove(result)
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def info(ctx):
        """
        Provides info on a media file.
        Info provided is from ffprobe and libmagic.

        Parameters:
            media - any valid media file
        """
        file = await imagesearch(ctx)
        if file:
            await ctx.channel.trigger_typing()
            result = await improcessing.ffprobe(file)
            await ctx.reply(f"`{result[1]}` `{result[2]}`\n```{result[0]}```")
            os.remove(file)
        else:
            await ctx.send("❌ No file found.")


    @bot.command(hidden=True)
    @commands.is_owner()
    async def say(ctx, *, msg):
        await ctx.message.delete()
        await ctx.channel.send(msg)


    @bot.command(hidden=True)
    @commands.is_owner()
    async def error(ctx, *, msg):
        await ctx.send("run comand with no args to make error lol!")


    @bot.command(hidden=True)
    @commands.is_owner()
    async def shutdown(ctx):
        await ctx.send("✅ Shutting Down...")
        await bot.close()


    @bot.listen()
    async def on_command(ctx):
        logging.info(
            f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.display_name}) "
            f"ran '{ctx.message.content}' in channel #{ctx.channel.name} in server {ctx.guild}")


    @bot.listen()
    async def on_command_error(ctx, error):
        if isinstance(error, discord.ext.commands.errors.CommandNotFound):
            msg = ctx.message.content.replace("@", "\\@")
            err = f"⁉ Command `{msg}` does not exist."
            logging.warning(err)
            await ctx.send(err)
        elif isinstance(error, discord.ext.commands.errors.NotOwner):
            err = "❌ You are not authorized to use this command."
            logging.warning(err)
            await ctx.send(err)
        elif isinstance(error, discord.ext.commands.errors.CommandOnCooldown):
            err = "⏱ " + str(error).replace("@", "\\@")
            logging.warning(err)
            await ctx.send(err)
        else:
            logging.error(error, exc_info=(type(error), error, error.__traceback__))
            await ctx.send("‼ `" + str(error).replace("@", "\\@") + "`")


    with open('token.txt') as f:  # not on github for obvious reasons
        token = f.read()
    bot.run(token)
