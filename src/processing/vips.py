import asyncio
import concurrent.futures
import functools
import typing

import pyvips


async def run_parallel(syncfunc: typing.Callable, *args: tuple, **kwargs: dict):
    """
    uses concurrent.futures.ProcessPoolExecutor to run CPU-bound functions in their own process

    :param syncfunc: the blocking function
    :return: the result of the blocking function
    """
    with concurrent.futures.ProcessPoolExecutor(1) as pool:
        return await asyncio.get_running_loop().run_in_executor(pool, functools.partial(syncfunc, *args, **kwargs))


def text():
    out = pyvips.Image.text(".", fontfile="rendering/fonts/slkscr.ttf")
    out = pyvips.Image.text("test😀.", font="Twemoji Color Emoji, Silkscreen 200px", rgba=True,
                            fontfile="rendering/fonts/TwemojiCOLR0.ttf")
    out.pngsave("out.png")


text()
