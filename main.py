import discord
from discord.ext import commands
import asyncio
import logging
import datetime
import re

logging.basicConfig(format='%(levelname)s:[%(asctime)s] %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p',
                    level=logging.INFO)
logging.info(f"Discord Version {discord.__version__}")
logging.info("Initalizing")
bot = commands.Bot(command_prefix='$', description='captionbot')
bot.remove_command('help')


@bot.event
async def on_ready():
    global awatingmonday
    # await database.firsttime()
    logging.info(f"Logged in as {bot.user.name}!")
    game = discord.Activity(name=f"with your files",
                            type=discord.ActivityType.watching)


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


with open('token.txt') as f:  # not on github for obvious reasons
    token = f.read()
bot.run(token)
