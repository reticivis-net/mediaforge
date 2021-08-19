import asyncio
from multiprocessing import Process

import aiohttp

import config
from clogs import logger
from improcessing import fetch


async def send_heartbeat():
    try:
        resp = await fetch(config.heartbeaturl)
        logger.debug(f"Successfully sent heartbeat. {resp}")
    except aiohttp.ClientResponseError as e:
        logger.error(e, exc_info=(type(e), e, e.__traceback__))


async def heartbeat():
    while True:
        await asyncio.gather(
            send_heartbeat(),
            asyncio.sleep(config.heartbeatfrequency)
        )


def start_heartbeat():
    logger.debug("starting heartbeat")
    loop = asyncio.get_event_loop()
    task = loop.create_task(heartbeat())
    try:
        loop.run_until_complete(task)
    except asyncio.CancelledError:
        task.cancel()


def init():
    heartbeat_active = hasattr(config, "heartbeaturl") and config.heartbeaturl
    if heartbeat_active:
        logger.debug(f"Heartbeat URL is {config.heartbeaturl}")
        heartbeatprocess = Process(target=start_heartbeat)
        heartbeatprocess.start()
    else:
        logger.debug("No heartbeat url set.")
