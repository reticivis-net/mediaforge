import discord
from discord.ext import commands

from core.clogs import logger
from utils.common import prefix_function


class BotEventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.AutoShardedBot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.log(35, f"Logged in as {self.bot.user.name}!")
        logger.log(25, f"{len(self.bot.guilds)} guild(s)")
        logger.log(25, f"{len(self.bot.shards)} shard(s)")

    @commands.Cog.listener()
    async def on_shard_connect(self, shardid):
        logger.info(f"Shard {shardid} connected")

    @commands.Cog.listener()
    async def on_disconnect(self):
        logger.error("on_disconnect")

    @commands.Cog.listener()
    async def on_shard_disconnect(self, shardid):
        logger.error(f"Shard {shardid} disconnected")

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        if ctx.interaction:
            command = f"/{ctx.command} {ctx.kwargs}"
        else:
            command = ctx.message.content
        if isinstance(ctx.channel, discord.DMChannel):
            logger.log(25,
                       f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.id}) ran "
                       f"'{command}' in DMs")
        else:
            logger.log(25,
                       f"@{ctx.message.author.name}#{ctx.message.author.discriminator}"
                       f" ({ctx.message.author.display_name}) ({ctx.message.author.id}) "
                       f"ran '{command}' in channel "
                       f"#{ctx.channel.name} ({ctx.channel.id}) in server {ctx.guild} ({ctx.guild.id})")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user:
            return
        if message.content.strip() in [f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>"]:
            pfx = await prefix_function(self.bot, message, True)
            await message.reply(f"My command prefix is `{pfx}`, or you can "
                                f"mention me! Run `{pfx}help` for bot help.", delete_after=10,
                                mention_author=False)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.interaction:
            command = f"/{ctx.command} {ctx.kwargs}"
        else:
            command = ctx.message.content
        logger.log(35,
                   f"Command '{command}' by "
                   f"@{ctx.message.author.name}#{ctx.message.author.discriminator} ({ctx.message.author.id}) "
                   f"is complete!")
    # command here


'''
Steps to convert:
@bot.command() -> @commands.hybrid_command()
@bot.listen() -> @commands.Cog.listener()
function(ctx, ...): -> function(self, ctx, ...)
bot -> self.bot
'''
