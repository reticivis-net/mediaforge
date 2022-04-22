import typing

import nextcord as discord
from nextcord.ext import commands


class V2test(commands.Cog):
    def __init__(self, bot):
        self.bot: commands.Bot = bot

    @commands.command()
    async def v2rot(self, ctx, rottype: typing.Literal["90", "90ccw", "180", "vflip", "hflip"]):
        """
        Rotates and/or flips media

        :param ctx: discord context
        :param rottype: 90: 90° clockwise, 90ccw: 90° counter clockwise, 180: 180°, vflip: vertical flip, hflip:
        horizontal flip
        :mediaparam media: A video, gif, or image.
        """
        await improcess(ctx, improcessing.rotate, [["GIF", "IMAGE", "VIDEO"]], rottype)
    # command here


'''
Steps to convert:
@bot.command() -> @commands.command()
@bot.listen() -> @commands.Cog.listener()
function(ctx, ...): -> function(self, ctx, ...)
bot -> self.bot
'''
