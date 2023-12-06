from discord.ext import commands

import config
from core import database
from core.clogs import logger
from utils.common import quote


class CommandChecksCog(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot
        # from ?tag cooldown mapping
        self._cd = commands.CooldownMapping.from_cooldown(1.0, config.cooldown, commands.BucketType.member)

    # @commands.check
    async def banned_users(self, ctx: commands.Context):
        if await self.bot.is_owner(ctx.author):
            return True
        async with database.db.execute("SELECT banreason from bans WHERE user=?", (ctx.author.id,)) as cur:
            ban = await cur.fetchone()
        if ban:
            outtext = "You are banned from this bot"
            if ban[0]:
                outtext += f" for the following reason:\n{quote(ban[0])}\n"
            else:
                outtext += f".\n"
            outtext += f"To appeal this, "
            if self.bot.owner_id == 214511018204725248:  # my ID; public bot
                outtext += "raise an issue at https://github.com/reticivis-net/mediaforge/issues/new?assignees=" \
                           "&labels=unban+request&template=unban_request.yaml&title=Unban+request+for" \
                           "+%3CYOUR+NAME+HERE%3E"
            else:
                outtext += "contact the bot owner."
            raise commands.CheckFailure(outtext)
        else:
            return True

    # @commands.Cog.bot_check
    def block_filter(self, ctx: commands.Context):
        # TODO: implement advanced regex-based filter to prevent filter bypass
        # this command is exempt because it only works on URLs and there have been issues with r/okbr
        if ctx.command.name == "videodl":
            return True
        for block in config.blocked_words:
            if block.lower() in ctx.message.content.lower():
                raise commands.CheckFailure("Your command contains one or more blocked words.")
        return True

    # @commands.check
    async def cooldown_check(self, ctx):
        # no cooldown for help
        if ctx.command.name == "help":
            return True
        # owner(s) are exempt from cooldown
        if await self.bot.is_owner(ctx.message.author):
            logger.debug("Owner ran command, exempt from cooldown.")
            return True
        # Then apply a bot check that will run before every command
        # Very similar to ?tag cooldown mapping but in Bot scope instead of Cog scope
        bucket = self._cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after, commands.BucketType.user)
        return True

    async def bot_check(self, ctx: commands.Context):
        results = [
            self.block_filter(ctx),
            await self.cooldown_check(ctx),
            await self.banned_users(ctx)
        ]
        return all(results)
