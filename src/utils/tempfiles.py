import asyncio
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


class TempFile(str):
    _deleted = False

    def __new__(cls, arg: str | None):
        if arg is None:  # default
            arg = temp_file_name()
        elif "." not in arg:  # just extension
            arg = temp_file_name(arg)
        # full filename otherwise
        logger.debug(f"Reserved new tempfile {arg}")
        return str.__new__(cls, arg)

    def __del__(self):
        if not self._deleted and multiprocessing.current_process().name == 'MainProcess':
            logger.debug(f"{self} was garbage collected... deleting")
            self.deletesoon()

    def deletesoon(self):
        try:
            asyncio.create_task(self.delete())
        except RuntimeError as e:
            logger.debug(e)
            logger.debug(f"async deleting {self} failed due to {e}, trying sync delete")
            os.remove(self)

    async def delete(self):
        try:
            logger.debug(f"deleting {self}")
            await aiofiles.os.remove(self)
            self._deleted = True
        except FileNotFoundError:
            logger.debug(f"Tried to delete {self} but it does not exist")
            self._deleted = True
