import asyncio
import concurrent.futures
import os
import random
import time
import typing

import config

sem = asyncio.Semaphore(config.workers or os.cpu_count() or 1)
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


async def hehe(i):
    for _ in range(16):
        await asyncio.sleep(random.uniform(0, 1))


def blocking():
    time.sleep(1)


async def test():
    for i in range(16):
        asyncio.create_task(enqueue(hehe(i)))
    for _ in range(20):
        begin = time.time()
        with concurrent.futures.ProcessPoolExecutor(1) as pool:
            result = await asyncio.get_running_loop().run_in_executor(
                pool, blocking)
        end = time.time()
        print(f"pool overhead was {(end - begin)-1}s")


if __name__ == "__main__":
    asyncio.run(test())
