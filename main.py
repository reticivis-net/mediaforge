import glob
import json
import logging
import os
import random
import string
import sys
import traceback
import discord
from discord.ext import commands
import captionfunctions
import improcessing
import aiohttp
import aiofiles

logging.basicConfig(format='%(levelname)s:[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.INFO)
if __name__ == '__main__':
    logging.info(f"Discord Version {discord.__version__}")
    logging.info("Initalizing")
    bot = commands.Bot(command_prefix='$', description='captionbot')
    bot.remove_command('help')
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
                    await ctx.send(f":bangbang: Tenor Error! {tenor['error']}")
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


    @bot.event
    async def on_ready():
        logging.info(f"Logged in as {bot.user.name}!")
        game = discord.Activity(name=f"with your files",
                                type=discord.ActivityType.watching)


    @bot.command()
    async def videotogif(ctx):
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
                await ctx.send("Detected file is not a valid video.")
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def giftovideo(ctx):
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
                await ctx.send("Detected file is not a valid gif.")
            logging.info("Complete!")
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    async def esmcaption(ctx, *, cap):
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.handleanimated(file, cap, captionfunctions.imcaption)
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
    async def motivate(ctx, *, cap):
        cap = cap.split(",")
        if len(cap) == 1:
            cap.append("")
        logging.info("Getting image...")
        file = await imagesearch(ctx)
        if file:
            logging.info("Processing image...")
            msg = await ctx.send("⚙ Processing...")
            await ctx.channel.trigger_typing()
            result = await improcessing.handleanimated(file, cap, captionfunctions.motivate)
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
        file = await imagesearch(ctx)
        if file:
            await ctx.channel.trigger_typing()
            result = await improcessing.ffprobe(file)
            await ctx.reply(f"```{result}```")
            # os.remove(file)
        else:
            await ctx.send("❌ No file found.")


    @bot.command()
    @commands.is_owner()
    async def say(ctx, *, msg):
        await ctx.message.delete()
        await ctx.channel.send(msg)


    @bot.command()
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
            err = f"⁉ Command `{ctx.message.content}` does not exist."
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
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
            await ctx.send("‼ `" + str(error).replace("@", "\\@") + "`")


    with open('token.txt') as f:  # not on github for obvious reasons
        token = f.read()
    bot.run(token)
