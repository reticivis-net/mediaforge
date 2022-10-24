import aiosqlite

import config
from core.clogs import logger

db: aiosqlite.Connection


async def setup(_):
    global db
    logger.debug("database connecting")
    db = await aiosqlite.connect(config.db_filename)


async def teardown(_):
    logger.debug("database disconnecting")
    await db.close()
