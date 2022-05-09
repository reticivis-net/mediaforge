"""
The entrypoint of MediaForge, containing the majority of the discord API interactions.
"""

# standard libs
import os
import sqlite3
import sys
import traceback

from cog_botevents import BotEventsCog
from cog_botlist import DiscordListsPost
from cog_commandchecks import CommandChecksCog
from cog_errorhandler import ErrorHandlerCog
from cog_status import StatusCog

try:
    # pip libs
    import aiofiles
    import aiohttp
    from aiohttp import client_exceptions as aiohttp_client_exceptions
    import aiosqlite
    import discordlists
    import docstring_parser
    import emojis
    import humanize
    import discord
    import pronouncing
    import psutil
    import regex as re
    import requests
    import selenium.common.exceptions
    import yt_dlp as youtube_dl

    from discord.ext import commands, tasks

    # project files
    import captionfunctions
    import chromiumrender
    import config
    import heartbeat
    import improcessing
    from mainutils import *
    import renderpool as renderpoolmodule
    import sus
    import tempfiles
    from clogs import logger
    from tempfiles import TempFileSession, get_random_string, temp_file

    # cogs
    from cog_caption import Caption
    from cog_conversion import Conversion
    from cog_debug import Debug
    from cog_image import Image
    from cog_media import Media
    from cog_other import Other
    from cog_slashscript import Slashscript
except ModuleNotFoundError as e:
    print("".join(traceback.format_exception(type(e), e, tb=e.__traceback__)), file=sys.stderr)
    sys.exit("MediaForge was unable to import the required libraries and files. Did you follow the self-hosting guide "
             "on the GitHub? https://github.com/HexCodeFFF/mediaforge#to-self-host")
docker = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
if not hasattr(config, "bot_token") or config.bot_token == "EXAMPLE_TOKEN":
    sys.exit("The bot token could not be found or hasn't been properly set. Be sure to follow the self-hosting "
             "guide on GitHub. https://github.com/HexCodeFFF/mediaforge#to-self-host")

# make copy of .reply() function
discord.Message.orig_reply = discord.Message.reply


async def safe_reply(self: discord.Message, *args, **kwargs) -> discord.Message:
    # replies to original message if it exists, just sends in channel if it doesnt
    try:
        # retrieve this message, will throw NotFound if its not found and go to the fallback option.
        # turns out trying to send a message will close any file objects which causes problems
        await self.channel.fetch_message(self.id)
        # reference copy of .reply() since this func will override .reply()
        return await self.orig_reply(*args, **kwargs)
    # for some reason doesnt throw specific error
    # if its unrelated httpexception itll just throw again and fall to the
    # error handler hopefully
    except (discord.errors.NotFound, discord.errors.HTTPException) as e:
        logger.debug(f"abandoning reply to {self.id} due to {get_full_class_name(e)}, "
                     f"sending message in {self.channel.id}.")
        # mention author
        author = self.author.mention
        if len(args):
            content = author + (args[0] or "")[:2000 - len(author)]
        else:
            content = author
        return await self.channel.send(content, **kwargs, allowed_mentions=discord.AllowedMentions(
            everyone=False, users=True, roles=False, replied_user=True))


# override .reply()
discord.Message.reply = safe_reply


def setselfpriority():
    # (try to) set self to high priority
    # https://stackoverflow.com/questions/1023038/change-process-priority-in-python-cross-platform
    try:
        if sys.platform == 'win32':
            # Based on:
            #   "Recipe 496767: Set Process Priority In Windows" on ActiveState
            #   http://code.activestate.com/recipes/496767/
            import win32api
            import win32process
            import win32con

            pid = win32api.GetCurrentProcessId()
            handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
            win32process.SetPriorityClass(handle, win32process.HIGH_PRIORITY_CLASS if docker
            else win32process.ABOVE_NORMAL_PRIORITY_CLASS)
        else:
            os.nice(-19 if docker else -10)
    except Exception as commanderror:
        if docker:
            logger.log(25, f"Failed to set main process priority. I've detected you're running me within a docker "
                           f"container. To fix this, add `--cap-add SYS_NICE` to the run arguments.")
        else:
            logger.debug(f"Failed to set own priority.")
        logger.debug(commanderror, exc_info=(type(commanderror), commanderror, commanderror.__traceback__))


def downloadttsvoices():
    # other misc init code (really need to organize this :p)
    if sys.platform != 'win32':
        if not os.path.isfile("tts/mycroft_voice_4.0.flitevox"):
            logger.log(25, "Downloading male TTS voice...")
            download_sync("https://github.com/MycroftAI/mimic1/raw/development/voices/mycroft_voice_4.0.flitevox",
                          "tts/mycroft_voice_4.0.flitevox")
            logger.log(35, "Male TTS voice downloaded!")
        if not os.path.isfile("tts/cmu_us_slt.flitevox"):
            logger.log(25, "Downloading female TTS voice...")
            download_sync("https://github.com/MycroftAI/mimic1/raw/development/voices/cmu_us_slt.flitevox",
                          "tts/cmu_us_slt.flitevox")
            logger.log(35, "Female TTS voice downloaded!")
        # chmod +x (mark executable)
        os.chmod('tts/mimic', os.stat('tts/mimic').st_mode | 0o111)


def cleartempdir():
    if not os.path.exists(config.temp_dir.rstrip("/")):
        os.mkdir(config.temp_dir.rstrip("/"))
    for f in glob.glob(f'{config.temp_dir}*'):
        os.remove(f)


def initdbsync():
    # create table if it doesnt exist
    # this isnt done with aiosqlite because its easier to just not do things asyncly during startup.
    syncdb = sqlite3.connect(config.db_filename)
    # setup db tables
    with syncdb:
        cur = syncdb.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_prefixes'")
        if not cur.fetchall():
            syncdb.execute(
                "create table guild_prefixes ( guild int not null constraint table_name_pk primary key, "
                "prefix text not null ); "
            )
        cur = syncdb.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bans'")
        if not cur.fetchall():
            syncdb.execute("create table bans ( user int not null constraint bans_pk primary key, banreason text );  ")
    syncdb.close()


def init():
    global renderpool
    setselfpriority()
    initdbsync()
    downloadttsvoices()
    cleartempdir()
    chromiumrender.updatechromedriver()
    renderpool = renderpoolmodule.initializerenderpool()
    heartbeat.init()


class MyBot(commands.AutoShardedBot):
    async def setup_hook(self):
        logger.debug(f"initializing cogs")
        await database.create_db()
        if config.bot_list_data:
            logger.info("bot list data found. botblock will start when bot is ready.")
            await bot.add_cog(DiscordListsPost(bot))
        else:
            logger.debug("no bot list data found")
        await asyncio.gather(
            bot.add_cog(Caption(bot)),
            bot.add_cog(Media(bot)),
            bot.add_cog(Conversion(bot)),
            bot.add_cog(Image(bot)),
            bot.add_cog(Other(bot)),
            bot.add_cog(Debug(bot)),
            bot.add_cog(Slashscript(bot)),
            bot.add_cog(StatusCog(bot)),
            bot.add_cog(ErrorHandlerCog(bot)),
            bot.add_cog(CommandChecksCog(bot)),
            bot.add_cog(BotEventsCog(bot))
        )


if __name__ == "__main__":
    logger.log(25, "Hello World!")
    logger.info(f"discord.py {discord.__version__}")
    init()
    if hasattr(config, "shard_count") and config.shard_count is not None:
        shard_count = config.shard_count
    else:
        shard_count = None
    # if on_ready is firing before guild count is collected, increase guild_ready_timeout
    intents = discord.Intents.all()
    intents.presences = False
    intents.members = False
    bot = MyBot(command_prefix=prefix_function,
                help_command=None,
                case_insensitive=True,
                shard_count=shard_count,
                guild_ready_timeout=30,
                allowed_mentions=discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=True),
                intents=intents)

    logger.debug("running bot")
    bot.run(config.bot_token)
