import os

import discord
import humanize

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


