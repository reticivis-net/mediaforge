import logging
import os
import random
import string
import sys
import traceback
import discord
from discord.ext import commands
import improcessing

logging.basicConfig(format='%(levelname)s:[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.INFO)
logging.info(f"Discord Version {discord.__version__}")
logging.info("Initalizing")
bot = commands.Bot(command_prefix='$', description='captionbot')
bot.remove_command('help')


def get_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))


async def saveattachment(attachment: discord.Attachment):
    extension = attachment.filename.split(".")[-1]
    while True:
        name = f"temp/{get_random_string(8)}.{extension}"
        if not os.path.exists(name):
            await attachment.save(name)
            return name


async def attachmentsearch(ctx):
    async for m in ctx.channel.history(limit=20):
        if len(m.attachments):
            return await saveattachment(m.attachments[0])
    return False


@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user.name}!")
    game = discord.Activity(name=f"with your files",
                            type=discord.ActivityType.watching)


@bot.command()
async def caption(ctx, *, cap):
    if len(ctx.message.attachments):
        file = await saveattachment(ctx.message.attachments[0])
        result = await improcessing.imcaption(file, cap)
        await ctx.send(file=discord.File(result))
    else:
        file = await attachmentsearch(ctx)
        if file:
            result = await improcessing.imcaption(file, cap)
            await ctx.send(file=discord.File(result))
        else:
            await ctx.send("❌ Message has no attachment.")


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
    logging.info(f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.display_name}) "
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
