import asyncio
import concurrent.futures
import functools
import multiprocessing
import typing

import config
import tempfiles
from clogs import logger


class Pool:
    def __init__(self, nworkers):
        self._executor = concurrent.futures.ProcessPoolExecutor(nworkers)
        self._nworkers = nworkers
        self._submitted = 0

    async def submit(self, fn, *args, **kwargs):
        self._submitted += 1
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(self._executor, functools.partial(fn, args=args, keywords=kwargs))
        try:
            return await fut
        finally:
            self._submitted -= 1

    async def shutdown(self):
        self._executor.shutdown(wait=False, cancel_futures=True)

    def stats(self):
        queued = max(0, self._submitted - self._nworkers)
        executing = min(self._submitted, self._nworkers)
        return queued, executing


renderpool: typing.Optional[Pool] = None


def initializerenderpool():
    """
    Start the worker pool
    :return: the worker pool
    """
    global renderpool
    try:
        # looks like it uses less memory
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass
    logger.info(f"Starting {config.chrome_driver_instances} pool processes...")
    # renderpool = multiprocessing.Pool(config.chrome_driver_instances, initializer=chromiumrender.initdriver)
    renderpool = Pool(config.chrome_driver_instances)
    return renderpool
