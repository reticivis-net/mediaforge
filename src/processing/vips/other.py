from statistics import mean

import pyvips

import processing.ffmpeg
import processing.ffprobe
from processing.common import run_parallel, NonBugError


def get_caption_height(file, tolerance: float):
    im = pyvips.Image.new_from_file(file)
    h = im.get_page_height()  # height of image, fuckin weird name
    # based on old esmbot approach, the new one looks weird
    target = 255
    for row in range(h):
        px = im.getpoint(0, row)
        if mean([abs(target - bandval) for bandval in px]) > tolerance:
            return row + 1
    raise NonBugError("Unable to detect caption. Try to adjust `frame_to_try`. Run `$help uncaption` for help.")


async def uncaption(file, frame_to_try: int, tolerance: float):
    frame_to_try = await processing.ffmpeg.frame_n(file, frame_to_try)
    w, h = await processing.ffprobe.get_resolution(file)
    cap_height = await run_parallel(get_caption_height, frame_to_try, tolerance)

    return await processing.ffmpeg.trim_top(file, cap_height)
