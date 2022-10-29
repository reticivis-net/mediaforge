import aiosqlite

import config
from core.clogs import logger

db: aiosqlite.Connection


async def init_database():
    global db
    logger.debug("database connecting")
    db = await aiosqlite.connect(config.db_filename)


async def close_database():
    logger.debug("database disconnecting")
    await db.close()
