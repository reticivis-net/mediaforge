import datetime
import typing

import aiohttp
import discord
import regex as re
import requests
from discord.ext import commands

import config
from core import database


async def fetch(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
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


def number_range(lower_bound: typing.Optional[number] = None, upper_bound: typing.Optional[number] = None,
                 lower_incl: bool = True, upper_incl: bool = True,
                 num_type: typing.Literal['float', 'int'] = 'float') -> object:
    """
    type hint a discord.py parameter to be within a specific number range.
    :param lower_bound: lower bound of arg
    :param upper_bound: upper bound of arg
    :param lower_incl: should the lower bound be included
    :param upper_incl: should the upper bound be included
    :param num_type: float or int
    :return: callable that converts string to num within range or raises commands.BadArgument if not
    """
    numfunc = float if num_type == "float" else int

    def inner(argument):
        try:
            argument = numfunc(argument)
        except ValueError:
            raise commands.BadArgument(
                f"`{argument}` is not a valid number."
                f"{' This argument only accepts whole numbers. ' if numfunc == int else ''}"
            )

        def error():
            raise commands.BadArgument(f"`{argument}` is not between `{lower_bound}` "
                                       f"({'included' if lower_incl else 'excluded'}) "
                                       f"and `{upper_bound}` "
                                       f"({'included' if upper_incl else 'excluded'}).")

        if lower_bound is not None:
            if lower_incl:
                if not lower_bound <= argument:
                    error()
            else:
                if not lower_bound < argument:
                    error()
        if upper_bound is not None:
            if upper_incl:
                if not argument <= upper_bound:
                    error()
            else:
                if not argument < upper_bound:
                    error()
        return argument

    return inner


def quote(string: str) -> str:
    """
    (tries to) discord quote a string
    :param string: string to quote
    :return: quoted string
    """
    return re.sub("([\n\r]|^) *>* *", "\n> ", string)


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
