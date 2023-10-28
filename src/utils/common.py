import datetime
import textwrap
import typing

import aiohttp
import discord
import requests
from discord.ext import commands

import config
from core import database


async def fetch(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}, timeout=60 * 10) as session:
        async with session.get(url) as response:
            if response.status != 200:
                response.raise_for_status()
            return await response.text()


def get_full_class_name(obj):
    module = obj.__class__.__module__
    if module is None or module == str.__class__.__module__:
        return obj.__class__.__name__
    return module + '.' + obj.__class__.__name__


def download_sync(url, filename):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filename, 'wb+') as f:
            for chunk in r.iter_content(chunk_size=8192):
                # If you have chunk encoded response uncomment if
                # and set chunk_size parameter to None.
                # if chunk:
                f.write(chunk)


number = typing.Union[float, int]


def quote(string: str) -> str:
    """
    (tries to) discord quote a string
    :param string: string to quote
    :return: quoted string
    """
    return textwrap.indent(string, "> ")


def now():
    return datetime.datetime.now(tz=datetime.timezone.utc).timestamp()


async def prefix_function(dbot: typing.Union[commands.Bot, commands.AutoShardedBot], message: discord.Message,
                          no_mnts=False):
    mentions = [f'<@{dbot.user.id}> ', f'<@!{dbot.user.id}> ', f'<@{dbot.user.id}>', f'<@!{dbot.user.id}>']
    if not message.guild:
        if no_mnts:
            return config.default_command_prefix
        else:
            # mentions or default or nothing for DMs only
            return mentions + [config.default_command_prefix, ""]
    async with database.db.execute("SELECT prefix from guild_prefixes WHERE guild=?", (message.guild.id,)) as cur:
        pfx = await cur.fetchone()
        if pfx:
            pfx = pfx[0]
        else:
            pfx = config.default_command_prefix
        if no_mnts:
            return pfx
        else:
            return mentions + [pfx]
