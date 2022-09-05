import aiosqlite

import config

db: aiosqlite.Connection


async def create_db():
    global db
    db = await aiosqlite.connect(config.db_filename)
