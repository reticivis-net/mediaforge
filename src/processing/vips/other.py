import random
from statistics import mean

import pyvips

import processing.ffmpeg
import processing.ffprobe
from processing.common import run_parallel, NonBugError
from utils.tempfiles import TempFile


def get_caption_height(file, tolerance: float):
    im = pyvips.Image.new_from_file(file)
    h = im.height  # height of image, fuckin weird name
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


def jpeg(file, strength, stretch, quality):
    im = pyvips.Image.new_from_file(file)
    orig_w = im.width
    orig_h = im.height
    for i in range(strength):
        if stretch > 0:
            # resize to anywhere between (original image width ± stretch, original image height ± stretch)
            w_add = random.randint(-stretch, stretch)
            h_add = random.randint(-stretch, stretch)
            im = im.resize((orig_w + w_add) / im.width, (orig_h + h_add) / im.height)
        # save to jpeg and read back to image
        im = pyvips.Image.new_from_buffer(im.write_to_buffer(".jpg", Q=quality), ".jpg")
    # save
    outfile = TempFile("png", only_delete_in_main_process=True)
    im.pngsave(outfile)
    return outfile
