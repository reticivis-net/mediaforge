import typing

import discord
import emojis
import regex as re
from discord import AppCommandOptionType
from discord.app_commands.transformers import IdentityTransformer
from discord.ext import commands
from discord.ext.commands import BadArgument


def add_long_field(embed: discord.Embed, name: str, value: str) -> discord.Embed:
    """
    add fields every 1024 characters to a discord embed
    :param embed: embed
    :param name: title of embed
    :param value: long value
    :return: updated embed
    """
    if len(value) <= 1024:
        return embed.add_field(name=name, value=value, inline=False)
    else:
        for i, section in enumerate(re.finditer('.{1,1024}', value, flags=re.S)):
            embed.add_field(name=name + f" {i + 1}", value=section[0], inline=False)
    if len(embed) > 6000:
        raise Exception(f"Generated embed exceeds maximum size. ({len(embed)} > 6000)")
    return embed


def showcog(cog):
    show_cog = False
    # check if there are any non-hidden commands in the cog, if not, dont show it in the help menu.
    for com in cog.get_commands():
        if not com.hidden:
            show_cog = True
            break
    return show_cog


class UnicodeEmojiConverter(commands.Converter):
    async def convert(self, ctx, argument):
        emoji = emojis.get(argument)
        if not emoji:
            raise UnicodeEmojiNotFound(argument)
        return list(emoji)[0]

class UnicodeEmojisConverter(commands.Converter):
    async def convert(self, ctx, argument):
        emoji = emojis.get(argument)
        if not emoji:
            raise UnicodeEmojiNotFound(argument)
        return list(emoji)


class UnicodeEmojiNotFound(commands.BadArgument):
    def __init__(self, argument):
        self.argument = argument
        super().__init__(f'Unicode emoji `{argument}` not found.')


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
