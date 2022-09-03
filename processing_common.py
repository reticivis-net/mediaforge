import asyncio
import os
import subprocess
import sys
import typing

from clogs import logger
from v2tempfiles import TempFile


class NonBugError(Exception):
    """When this is raised instead of a normal Exception, on_command_error() will not attach a traceback or github
    link. """
    pass


class CMDError(Exception):
    """raised by run_command"""
    pass


class ReturnedNothing(Exception):
    """raised by improcess()"""
    pass


# https://fredrikaverpil.github.io/2017/06/20/async-and-await-with-subprocesses/
async def run_command(*args):
    """
    run a cli command

    :param args: the args of the command, what would normally be seperated by a space
    :return: the result of the command
    """
    # https://stackoverflow.com/a/56884806/9044183
    # set proccess priority low
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.BELOW_NORMAL_PRIORITY_CLASS
        nicekwargs = {"startupinfo": startupinfo}
    else:
        nicekwargs = {"preexec_fn": lambda: os.nice(10)}

    # Create subprocess
    process = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        **nicekwargs
    )

    # Status
    logger.info(f"'{args[0]}' started with PID {process.pid}")
    logger.log(11, f"PID {process.pid}: {args}")

    # Wait for the subprocess to finish
    stdout, stderr = await process.communicate()

    try:
        result = stdout.decode().strip() + stderr.decode().strip()
    except UnicodeDecodeError:
        result = stdout.decode("ascii", 'ignore').strip() + stderr.decode("ascii", 'ignore').strip()
    # Progress
    if process.returncode == 0:
        logger.debug(f"PID {process.pid} Done.")
        logger.debug(f"Results: {result}")
    else:

        logger.error(
            f"PID {process.pid} Failed: {args} result: {result}",
        )
        # adds command output to traceback
        raise CMDError(f"Command {args} failed.") from CMDError(result)
    # Result

    # Return stdout
    return result


async def compresspng(png):
    """
    compress a png file with pngquant
    :param png: file
    :return: filename of compressed png
    """
    # return png
    outname = TempFile("png")
    await run_command("pngquant", "--output", outname, png)  # "--quality=0-80",
    return outname


async def tts(text: str, model: typing.Literal["male", "female", "retro"] = "male"):
    ttswav = TempFile("wav")
    outname = TempFile("mp3")
    if model == "retro":
        await run_command("node", "tts/sam.js", "--moderncmu", "--wav", ttswav, text)
    else:
        # espeak is a fucking nightmare on windows and windows has good native tts anyways sooooo
        if sys.platform == "win32":
            # https://docs.microsoft.com/en-us/dotnet/api/system.speech.synthesis.voicegender?view=netframework-4.8
            voice = str({"male": 1, "female": 2}[model])
            await run_command("powershell", "-File", "tts.ps1", ttswav, text, voice)
        else:
            await run_command("./tts/mimic", "-voice",
                              "tts/mycroft_voice_4.0.flitevox" if model == "male" else "tts/cmu_us_slt.flitevox",
                              "-o", ttswav, "-t", text)
    await run_command("ffmpeg", "-hide_banner", "-i", ttswav, "-c:a", "libmp3lame", outname)
    return outname
