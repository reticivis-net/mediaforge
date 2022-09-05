import aiohttp
import humanize

import config
import processing.ffmpeg
import processing.common
from src.clogs import logger


async def saveurl(url) -> bytes | None:
    """
    save a url

    :param url: web url of a file
    :return: bytes of file
    """
    tenorgif = url.startswith("https://media.tenor.com") and url.endswith("/mp4")  # tenor >:(
    # https://github.com/aio-libs/aiohttp/issues/3904#issuecomment-632661245
    result = None
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        # i used to make a head request to check size first, but for some reason head requests can be super slow
        async with session.get(url) as resp:
            if resp.status == 200:
                if "Content-Length" not in resp.headers:  # size of file to download
                    raise Exception("Cannot determine filesize!")
                size = int(resp.headers["Content-Length"])
                logger.info(f"Url is {humanize.naturalsize(size)}")
                if config.max_file_size < size:  # file size to download must be under max configured size.
                    raise processing.common.NonBugError(f"Your file is too big ({humanize.naturalsize(size)}). "
                                                       f"I'm configured to only download files up to "
                                                        f"{humanize.naturalsize(config.max_file_size)}.")
                logger.info(f"Saving url {url}")
                result = await resp.read()
            else:
                logger.error(f"aiohttp status {resp.status}")
                logger.error(f"aiohttp status {await resp.read()}")
                resp.raise_for_status()
    if tenorgif and result:
        result = await processing.ffmpeg.mp4togif(result)
    # if lottie:
    #     name = await renderpool.submit(lottiestickers.lottiestickertogif, name)
    return result


async def saveurls(urls: list):
    """
    saves list of URLs and returns it
    :param urls: list of urls
    :return: list of files
    """
    if not urls:
        return False
    files = []
    for url in urls:
        files.append(await saveurl(url))
    return files


async def contentlength(url):
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'}) as session:
        # i used to make a head request to check size first, but for some reason head requests can be super slow
        async with session.get(url) as resp:
            if resp.status == 200:
                if "Content-Length" not in resp.headers:  # size of file to download
                    return False
                else:
                    return int(resp.headers["Content-Length"])
