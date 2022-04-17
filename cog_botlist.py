import discordlists
from nextcord.ext import commands

import config


class DiscordListsPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = discordlists.Client(self.bot)  # Create a Client instance
        if config.bot_list_data:
            for k, v in config.bot_list_data.items():
                if "token" in v and v["token"]:
                    self.api.set_auth(k, v["token"])
        self.api.start_loop()  # Posts the server count automatically every 30 minutes

    @commands.command(hidden=True)
    @commands.is_owner()
    async def post(self, ctx: commands.Context):
        """
        Manually posts guild count using discordlists.py (BotBlock)
        """
        try:
            result = await self.api.post_count()
        except Exception as e:
            await ctx.send(f"Request failed: `{e}`")
            return

        await ctx.send("Successfully manually posted server count ({:,}) to {:,} lists."
                       "\nFailed to post server count to {:,} lists.".format(self.api.server_count,
                                                                             len(result["success"].keys()),
                                                                             len(result["failure"].keys())))
