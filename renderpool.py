import asyncio
import concurrent.futures
import multiprocessing
import typing

import chromiumrender
import config
import tempfiles
from clogs import logger


def pass_temp_session(fn, args, kwargs, sessionlist):
    """used in Pool to pass the current TempFileSession into the process"""
    tempfiles.globallist = sessionlist
    result = fn(*args, **kwargs)
    tempfiles.globallist = None
    return result


class MyProcess(multiprocessing.Process):
    def start(self):
        super(MyProcess, self).start()


# https://stackoverflow.com/a/65966787/9044183
class Pool:
    def __init__(self, nworkers):
        self._executor = concurrent.futures.ProcessPoolExecutor(nworkers, initializer=chromiumrender.initdriver)
        self._nworkers = nworkers
        self._submitted = 0
        # loop = asyncio.get_event_loop()
        # loop.run_until_complete(self.init())

    async def init(self):
        await asyncio.gather(*([self.submit(chromiumrender.initdriver)] * self._nworkers))

    async def submit(self, fn, *args, ses=None, **kwargs):
        self._submitted += 1
        if ses is None:
            ses = tempfiles.get_session_list()
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(self._executor, pass_temp_session, fn, args, kwargs, ses)
        try:
            return await fut
        finally:
            self._submitted -= 1

    async def shutdown(self):
        await asyncio.wait([self.submit(chromiumrender.closedriver)] * self._nworkers)
        self._executor.shutdown(wait=True)

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
