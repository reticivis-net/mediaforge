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
    todelete: bool = True
    only_delete_in_main_process: bool = False

    # literally just a path but it removes itself on garbage collection
    def __new__(cls, arg: str | None, *, todelete=True, only_delete_in_main_process=False):
        if arg is None:  # default
            arg = temp_file_name()
        elif "." not in arg:  # just extension
            arg = temp_file_name(arg)
        # full filename otherwise
        logger.debug(f"Reserved new tempfile {arg}")
        return str.__new__(cls, arg)

    def __init__(self, arg: str | None, todelete=True, only_delete_in_main_process=False):
        self.todelete = todelete
        self.only_delete_in_main_process = only_delete_in_main_process

    def __del__(self):
        if self.todelete:
            logger.debug(f"Removing tempfile {self}")
            # https://stackoverflow.com/a/67577364/9044183
            # deletes without blocking loop
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self.delete())
                    else:
                        loop.run_until_complete(self.delete())
                except RuntimeError:  # no loop
                    os.remove(self)
            except Exception as e:
                logger.debug(e, exc_info=1)
        else:
            logger.debug(f"{self} was garbage collected but was requested to not be deleted.")

    async def delete(self):
        try:
            if multiprocessing.current_process().name != "MainProcess" and self.only_delete_in_main_process:
                logger.debug(f"deletion of {self} was requested by {multiprocessing.current_process().name}, "
                             f"but specified to only be deleted in the main process, ignoring.")
            else:
                await aiofiles.os.remove(self)
        except FileNotFoundError:
            logger.debug(f"Tried to delete {self} but it does not exist")
