import asyncio
import os
import typing

import config

workers = config.workers or os.cpu_count() or 1
sem = asyncio.Semaphore(workers)
queued = 0


async def enqueue(task: typing.Coroutine):
    global queued
    queued += 1
    # only allows a certian amount of tasks inside the context at once
    # quick tests show that its roughly FIFO but there are libraries if needed
    async with sem:
        try:
            res = await task
        except Exception as e:
            queued -= 1
            raise e
        else:
            queued -= 1
            return res
