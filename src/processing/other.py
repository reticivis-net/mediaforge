from processing.ffprobe import *


async def freezemotivate(files, *caption):
    """
    ends video with motivate caption
    :param files: media
    :param caption: caption to pass to motivate()
    :return: processed media
    """
    if isinstance(files, list):  # audio specified
        video = files[0]
        audio = files[1]
    else:  # just default to song lol!
        video = files
        audio = "rendering/what.mp3"
    lastframe = await frame_n(video, -1)
    # TODO: update to modern
    # clastframe = await handleanimated(lastframe, captionfunctions.motivate, None, *caption)
    # freezeframe = await imageaudio([clastframe, audio])
    # final = await concatv([video, freezeframe])
    # return final


async def checkwatermark(file):
    # see watermark()
    etdata = await run_command("exiftool", "-artist", "-json", file)
    logger.info(etdata)
    etdata = json.loads(etdata)[0]
    if "Artist" in etdata:
        if etdata["Artist"] == "MediaForge":
            return True
    return False


def ytdownload(vid, form):
    raise NotImplementedError  # TODO: implement

    # while True:
    #     name = f"temp/{get_random_string(12)}"
    #     if len(glob.glob(name + ".*")) == 0:
    #         break
    # opts = {
    #     # "max_filesize": config.file_upload_limit,
    #     "quiet": True,
    #     "outtmpl": f"{name}.%(ext)s",
    #     "default_search": "auto",
    #     "logger": MyLogger(),
    #     "merge_output_format": "mp4",
    #     "format": f'(bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best)'
    #               f'[filesize<?{config.file_upload_limit}]',
    #     "max_filesize": config.file_upload_limit
    #     # "format": "/".join(f"({i})[filesize<{config.file_upload_limit}]" for i in [
    #     #     "bestvideo[ext=mp4]+bestaudio", "best[ext=mp4]", "bestvideo+bestaudio", "best"
    #     # ]),
    # }
    # if form == "audio":
    #     opts['format'] = f"bestaudio[filesize<{config.file_upload_limit}]"
    #     opts['postprocessors'] = [{
    #         'key': 'FFmpegExtractAudio',
    #         'preferredcodec': 'mp3',
    #     }]
    # with youtube_dl.YoutubeDL(opts) as ydl:
    #     # manually exclude livestreams, cant find a better way to do this ¯\_(ツ)_/¯
    #     nfo = ydl.extract_info(vid, download=False)
    #     logger.debug(nfo)
    #     if "is_live" in nfo and nfo["is_live"]:
    #         raise youtube_dl.DownloadError("Livestreams cannot be downloaded.")
    #     ydl.download([vid])
    # filename = glob.glob(name + ".*")
    # if len(filename) > 0:
    #     return filename[0]
    # else:
    #     return None
