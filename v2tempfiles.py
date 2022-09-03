import os
import random
import string

import config
from clogs import logger


def get_random_string(length):
    return ''.join(random.choice(string.ascii_letters) for _ in range(length))


def is_named_used(name):
    return os.path.exists(name)


def temp_file_name(extension):
    while True:
        if extension is not None:
            name = f"{config.temp_dir}{get_random_string(8)}.{extension}"
        else:
            name = f"{config.temp_dir}{get_random_string(8)}"
        if not is_named_used(name):
            return name


class TempFile(str):
    todelete: bool = True

    # literally just a path but it removes itself on garbage collection
    def __init__(self, arg: str | None):
        if arg is None:  # default
            super().__init__(temp_file_name())
        elif "." not in arg:  # just extension
            super().__init__(temp_file_name(arg))
        else:  # full filename
            super().__init__(arg)

    def __del__(self):
        if self.todelete:
            logger.debug(f"Removing {self}")
            try:
                os.remove(self)
            except Exception as e:
                logger.debug(e, exc_info=1)
        else:
            logger.debug(f"{self} was garbage collected but was requested to not be deleted.")
