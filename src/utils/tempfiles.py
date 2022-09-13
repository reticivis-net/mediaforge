import os
import random
import string
import tempfile

import config
from core.clogs import logger

if config.override_temp_dir is not None:
    temp_dir = config.override_temp_dir
else:
    if os.path.isdir("/dev/shm"):  # in-memory fs
        temp_dir = "/dev/shm/mediaforge"
    else:
        temp_dir = os.path.join(tempfile.gettempdir(), "mediaforge")

if os.path.isdir(temp_dir):
    os.rmdir(temp_dir)
os.makedirs(temp_dir)

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

    # literally just a path but it removes itself on garbage collection
    def __new__(cls, arg: str | None):
        if arg is None:  # default
            return str.__new__(cls, temp_file_name())
        elif "." not in arg:  # just extension
            return str.__new__(cls, temp_file_name(arg))
        else:  # full filename
            return str.__new__(cls, arg)

    def __del__(self):
        if self.todelete:
            logger.debug(f"Removing tempfile {self}")
            try:
                os.remove(self)
            except Exception as e:
                logger.debug(e, exc_info=1)
        else:
            logger.debug(f"{self} was garbage collected but was requested to not be deleted.")
