import os
import typing

import discord
from discord import AppCommandOptionType
from discord.app_commands.transformers import IdentityTransformer
from discord.ext import commands
from discord.ext.commands import BadArgument

import config
from core.clogs import logger
from processing.ffprobe import mediatype


async def count_emoji(guild: discord.Guild):
    anim = 0
    static = 0
    for emoji in guild.emojis:
        if emoji.animated:
            anim += 1
        else:
            static += 1
    return {"animated": anim, "static": static}


async def add_emoji(file, guild: discord.Guild, name):
    """
    adds emoji to guild
    :param file: emoji to add
    :param guild: guild to add it to
    :param name: emoji name
    :return: result text
    """
    with open(file, "rb") as f:
        data = f.read()
    try:
        emoji = await guild.create_custom_emoji(name=name, image=data, reason="$addemoji command")
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to create an emoji. Make sure I have the Manage Emojis " \
               f"permission. "
    except discord.HTTPException as e:
        logger.error(e, exc_info=(type(e), e, e.__traceback__))
        return f"{config.emojis['2exclamation']} Something went wrong trying to add your emoji! ```{e}```"
    else:
        count = await count_emoji(guild)
        if emoji.animated:
            return f"{config.emojis['check']} Animated emoji successfully added: " \
                   f"{emoji}\n{guild.emoji_limit - count['animated']} slots are left."
        else:
            return f"{config.emojis['check']} Emoji successfully added: " \
                   f"{emoji}\n{guild.emoji_limit - count['static']} slots are left."


async def add_sticker(file, guild: discord.Guild, sticker_emoji, name):
    """
    adds sticker to guild
    :param file: sticker to add
    :param guild: guild to add it to
    :param sticker_emoji "related" emoji of the sticker
    :param name: sticker name
    :return: result text
    """
    size = os.path.getsize(file)
    file = discord.File(file)
    try:
        await guild.create_sticker(name=name, emoji=sticker_emoji, file=file, reason="$addsticker command",
                                   description=" ")
        # description MUST NOT be empty. see https://github.com/nextcord/nextcord/issues/165
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to create a sticker. Make sure I have the Manage " \
               f"Emojis and Stickers permission. "
    except discord.HTTPException as e:
        logger.error(e, exc_info=(type(e), e, e.__traceback__))
        toreturn = f"{config.emojis['2exclamation']} Something went wrong trying to add your sticker! ```{e}```"
        if "Invalid Asset" in str(e):
            toreturn += "\nNote: `Invalid Asset` means Discord does not accept this file format. Stickers are only " \
                        "allowed to be png or apng."
        if "Asset exceeds maximum size" in str(e):
            toreturn += f"\nNote: Stickers must be under ~500kb. Your sticker is {humanize.naturalsize(size)}"
        return toreturn
    else:
        return f"{config.emojis['check']} Sticker successfully added.\n" \
               f"\n{guild.sticker_limit - len(guild.stickers)} slots are left."


async def set_banner(file, guild: discord.Guild):
    """
    sets guild banner
    :param file: banner file
    :param guild: guild to add it to
    :return:
    """
    with open(file, "rb") as f:
        data = f.read()
    try:
        await guild.edit(banner=bytes(data))
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to set your banner. Make sure I have the Manage Server " \
               f"permission. "
    except discord.HTTPException as e:
        return f"{config.emojis['2exclamation']} Something went wrong trying to set your banner! ```{e}```"
    else:
        return f"{config.emojis['check']} Successfully changed guild banner."


async def set_icon(file, guild: discord.Guild):
    """
    sets guild icon
    :param file: icon file
    :param guild: guild to add it to
    :return:
    """
    if (await mediatype(file)) == "GIF" and "ANIMATED_ICON" not in guild.features:
        return f"{config.emojis['x']} This guild does not support animated icons."
    with open(file, "rb") as f:
        data = f.read()
    try:
        await guild.edit(icon=bytes(data))
    except discord.Forbidden:
        return f"{config.emojis['x']} I don't have permission to set your icon. Make sure I have the Manage Server " \
               f"permission. "
    except discord.HTTPException as e:
        return f"{config.emojis['2exclamation']} Something went wrong trying to set your icon! ```{e}```"
    else:
        return "Successfully changed guild icon."


async def iconfromsnowflakeid(snowflake: int, bot, ctx):
    try:
        user = await bot.fetch_user(snowflake)
        return str(user.avatar.url)
    except (discord.NotFound, discord.Forbidden):
        pass
    try:
        guild = await bot.fetch_guild(snowflake)
        return str(guild.icon.url)
    except (discord.NotFound, discord.Forbidden):
        pass
    try:  # get the icon through a message author to support webhook/pk icons
        msg = await ctx.channel.fetch_message(snowflake)
        return str(msg.author.avatar.url)
    except (discord.NotFound, discord.Forbidden):
        pass
    return None


class HybridRangeTransformer(IdentityTransformer):
    # SEE https://github.com/Rapptz/discord.py/pull/9075
    def __init__(
            self,
            opt_type: AppCommandOptionType,
            *,
            min: typing.Optional[typing.Union[int, float]] = None,
            max: typing.Optional[typing.Union[int, float]] = None,
    ) -> None:
        if min and max and min > max:
            raise TypeError('minimum cannot be larger than maximum')

        self._min: typing.Optional[typing.Union[int, float]] = min
        self._max: typing.Optional[typing.Union[int, float]] = max
        self._opt_type: AppCommandOptionType = opt_type
        super().__init__(opt_type)

    @property
    def min_value(self) -> typing.Optional[typing.Union[int, float]]:
        return self._min

    @property
    def max_value(self) -> typing.Optional[typing.Union[int, float]]:
        return self._max

    async def convert(self, ctx: commands.Context, argument):
        # compatability with classic converters for hybrid command usage
        if self._opt_type == AppCommandOptionType.string:
            if self._min and len(argument) < self._min:
                raise BadArgument(
                    f'Parameter "{ctx.current_parameter.name}" must be longer than {self._min} character{"s" if self._min == 1 else ""}.'
                )
            if self._max and len(argument) > self._max:
                raise BadArgument(
                    f'Parameter "{ctx.current_parameter.name}" must be shorter than {self._min} character{"s" if self._min == 1 else ""}.'
                )
        else:
            converterfunc = int if self._opt_type == AppCommandOptionType.integer else float
            try:
                argument = converterfunc(argument)
            except ValueError:
                raise BadArgument(
                    f'Converting to "{converterfunc.annotation.__name__}" failed for parameter "{ctx.current_parameter.name}".'
                )
            if self._min and argument < self._min:
                raise BadArgument(
                    f'Parameter "{ctx.current_parameter.name}" must be greater than {self._min}.'
                )
            if self._max and argument > self._max:
                raise BadArgument(
                    f'Parameter "{ctx.current_parameter.name}" must be less than {self._max}.'
                )
        return argument


class HybridRange:
    # SEE https://github.com/Rapptz/discord.py/pull/9047
    def __class_getitem__(cls, obj):
        if not isinstance(obj, tuple):
            raise TypeError(f'expected tuple for arguments, received {obj.__class__.__name__} instead')

        if len(obj) == 2:
            obj = (*obj, None)
        elif len(obj) != 3:
            raise TypeError('Range accepts either two or three arguments with the first being the type of range.')

        obj_type, min, max = obj

        if min is None and max is None:
            raise TypeError('Range must not be empty')

        if obj_type is int:
            opt_type = AppCommandOptionType.integer
        elif obj_type is float:
            opt_type = AppCommandOptionType.number
        elif obj_type is str:
            opt_type = AppCommandOptionType.string
        else:
            raise TypeError(f'expected int, float, or str as range type, received {obj_type!r} instead')

        # ensure min and max types are correct
        if obj_type is int or obj_type is str:
            if min is not None and type(min) != int:
                raise TypeError(f'expected min to be int, got {type(min)}')
            if max is not None and type(max) != int:
                raise TypeError(f'expected max to be int, got {type(min)}')
        else:
            if min is not None and type(min) not in (int, float):
                raise TypeError(f'expected min to be int or float, got {type(min)}')
            if max is not None and type(max) not in (int, float):
                raise TypeError(f'expected max to be int or float, got {type(min)}')

        # string ranges must have both values ≥ 1 (or unspecified)
        if obj_type is str and ((max is None or max < 1) or (min is None or min < 1)):
            raise TypeError(f'max and min must be greater than or equal to 1 for str range type.')

        transformer = HybridRangeTransformer(
            opt_type,
            min=min if min is not None else None,
            max=max if max is not None else None,
        )
        return transformer
