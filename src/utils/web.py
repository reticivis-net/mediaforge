import aiofiles
import aiohttp
import humanize

import config
import processing.common
import processing.ffmpeg
from core.clogs import logger
from utils.tempfiles import reserve_tempfile


async def saveurl(url: str) -> str:
    """
    save a url

    :param url: web url of a file
    :return: path to file
    """
    tenorgif = url.startswith("https://media.tenor.com") and url.endswith("/mp4")  # tenor >:(
    extension = None
    if tenorgif:
        extension = "mp4"
    if extension is None:
        after_slash = url.split("/")[-1].split("?")[0]
        if "." in after_slash:
            extension = after_slash.split(".")[-1]
        # extension will stay None if no extension detected.
    name = reserve_tempfile(extension)

    # https://github.com/aio-libs/aiohttp/issues/3904#issuecomment-632661245
    async with aiohttp.ClientSession(headers={'Connection': 'keep-alive'},
                                     timeout=aiohttp.ClientTimeout(total=600)) as session:
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
                async with aiofiles.open(name, mode='wb') as f:
                    await f.write(await resp.read())
            else:
                logger.error(f"aiohttp status {resp.status}")
                logger.error(f"aiohttp status {await resp.read()}")
                resp.raise_for_status()
    if tenorgif and name:
        name = await processing.ffmpeg.mp4togif(name)
    return name


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
