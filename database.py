import asyncio

import aiosqlite
from discord.ext import commands

import config

db: aiosqlite.Connection


async def create_db():
    global db
    db = await aiosqlite.connect(config.db_filename)


class CreateDB(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        asyncio.get_event_loop().run_until_complete(create_db())
