import asyncio
import contextvars
import multiprocessing
import os
import random
import shutil
import string
import tempfile

import aiofiles.os

import config
from core.clogs import logger


def init():
    global temp_dir
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)


if config.override_temp_dir is not None:
    temp_dir = config.override_temp_dir
else:
    if os.path.isdir("/dev/shm"):  # in-memory fs
        temp_dir = "/dev/shm/mediaforge"
    else:
        temp_dir = os.path.join(tempfile.gettempdir(), "mediaforge")

logger.debug(f"temp dir is {temp_dir}")


def get_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))


def is_named_used(name):
    return os.path.exists(name)


def temp_file_name(extension=None):
    while True:
        name = os.path.join(temp_dir, get_random_string(8))
        if extension:
            name += f".{extension}"
        if not is_named_used(name):
            return name


def reserve_tempfile(arg):
    if arg is None:  # default
        arg = temp_file_name()
    elif "." not in arg:  # just extension
        arg = temp_file_name(arg)
    # full filename otherwise

    tfs = session.get()
    tfs.append(arg)
    session.set(tfs)
    logger.debug(f"Reserved new tempfile {arg}")
    return arg


class TempFileSession:
    def __init__(self):
        pass

    async def __aenter__(self):
        try:
            session.get()
            raise Exception("Cannot create new TempFileSession, one already exists in this context.")
        except LookupError:
            pass
        logger.debug("Created new TempFileSession")
        session.set([])

    async def __aexit__(self, *_):
        files = session.get()
        logger.debug(f"TempFileSession exiting with {len(files)} files: {files}")
        await asyncio.gather(*[aiofiles.os.remove(file) for file in files], return_exceptions=True)
        logger.debug(f"TempFileSession exited!")


session: contextvars.ContextVar[list[str]] = contextvars.ContextVar("session")
