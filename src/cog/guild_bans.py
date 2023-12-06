import discord
from discord.ext import commands

import config
from core import database
from core.clogs import logger
from utils.common import quote


class GuildBansCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    # @commands.check
    async def bot_check(self, ctx: commands.Context):
        # if await self.bot.is_owner(ctx.author):
        #     return True
        if not ctx.guild:
            return True
        async with database.db.execute("SELECT banreason from server_bans WHERE server_id=?", (ctx.guild.id,)) as cur:
            ban = await cur.fetchone()
        if ban:
            await self.send_ban_message_in_guild(ctx.guild, ban[0])
            await ctx.guild.leave()
            raise commands.CheckFailure("Server is banned from bot.")
        else:
            return True

    async def send_ban_message_in_guild(self, guild: discord.Guild, reason):
        logger.error(self.bot.owner_id)
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                outtext = "This server is banned from this bot"
                if reason:
                    outtext += f" for the following reason:\n{quote(reason)}\n"
                else:
                    outtext += f".\n"
                outtext += f"To appeal this, "
                if self.bot.owner_id == 214511018204725248:  # my ID; public bot
                    outtext += "raise an issue at https://github.com/reticivis-net/mediaforge/issues/new?assignees=" \
                               "&labels=unban+request&template=unban_request_server.yaml&title=Unban+request+for" \
                               "+%3CYOUR+SERVER+HERE%3E"
                else:
                    outtext += "contact the bot owner."
                await channel.send(outtext)
                logger.log(25,
                           f"Sent ban message for {guild.name} (ID {guild.id}) to {channel.name} (ID {channel.id})")
                return True
        try:
            outtext = f"Your server {guild.name} (ID {guild.id}) is banned from this bot"
            if reason:
                outtext += f" for the following reason:\n{quote(reason)}\n"
            else:
                outtext += f".\n"
            outtext += f"To appeal this, "
            if self.bot.owner_id == 214511018204725248:  # my ID; public bot
                outtext += "raise an issue at https://github.com/reticivis-net/mediaforge/issues/new?assignees=" \
                           "&labels=unban+request&template=unban_request_server.yaml&title=Unban+request+for" \
                           "+%3CYOUR+SERVER+HERE%3E"
            else:
                outtext += "contact the bot owner."
            await guild.owner.send(outtext)
            logger.log(25,
                       f"Sent ban message for {guild.name} (ID {guild.id}) to owner {guild.owner} (ID {guild.owner.id})")
            return True
        except discord.DiscordException:
            logger.error(f"Tried to send ban message in {guild.name} (ID {guild.id}), but it failed")
            return False

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        async with database.db.execute("SELECT banreason from server_bans WHERE server_id=?", (guild.id,)) as cur:
            ban = await cur.fetchone()
        if ban:
            await self.send_ban_message_in_guild(guild, ban[0])
            await guild.leave()

    @commands.command()
    @commands.is_owner()
    async def banserver(self, ctx, server: discord.Object, *, reason: str = ""):
        async with database.db.execute("SELECT count(*) from server_bans WHERE server_id=?", (server.id,)) as cur:
            if (await cur.fetchone())[0] > 0:  # check if ban exists
                await ctx.reply(f"{config.emojis['x']} {server.id} is already banned.")
            else:
                await database.db.execute("INSERT INTO server_bans(server_id, banreason) values (?, ?)",
                                          (server.id, reason))
                await database.db.commit()
                guild = discord.utils.get(self.bot.guilds, id=server.id)
                if guild is not None:
                    message_success = await self.send_ban_message_in_guild(guild, reason)
                    await guild.leave()
                    if message_success:
                        await ctx.reply(f"{config.emojis['check']} Sent ban message in, banned, and left {guild.name}.")
                    else:
                        await ctx.reply(
                            f"{config.emojis['check']} Banned and left {guild.name}, but failed to send ban message.")
                else:
                    await ctx.reply(f"{config.emojis['check']} Banned {server.id}, bot was not in server..")

    @commands.command()
    @commands.is_owner()
    async def unbanserver(self, ctx, server: discord.Object):
        cur = await database.db.execute("DELETE FROM server_bans WHERE server_id=?",
                                        (server.id,))
        await database.db.commit()
        if cur.rowcount > 0:
            await ctx.reply(f"{config.emojis['check']} Unbanned {server.id}.")
        else:
            await ctx.reply(f"{config.emojis['x']} {server.id} is not banned.")
