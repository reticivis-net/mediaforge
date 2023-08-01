# COPY THIS FILE INTO A FILE CALLED config.py AND CHANGE THE VALUES AS NEEDED.
# discord API bot token https://discord.com/developers/applications
bot_token = "EXAMPLE_TOKEN"
# tenor API key https://developers.google.com/tenor/guides/quickstart#setup
tenor_key = "EXAMPLE_KEY"
# BotBlock tokens. see https://pypi.org/project/discordlists.py/
bot_list_data = None
# bot_list_data = {
#         "examplebotlist.com": {
#             "token": "exampletoken"
#         },
# }
# number of commands that can be processed at once. set to None to automatically use OS cpu core count.
# set to -1 to remove limit.
workers = None
# manually specify tempdir rather than using OS's default
# temp dir defaults to /dev/shm (in-memory) if available and this var is None
override_temp_dir = None
# NOTICE is recommended, INFO prints more information about what bot is doing, WARNING only prints errors.
log_level = "NOTICE"
# amount of seconds cooldown per user commands have. set to 0 to disable cooldown
cooldown = 3
# minimum height/width that media will be sized up to if below
min_size = 100
# maximum height/width that media will be downsized to if above
max_size = 2000
# maximum size, in bytes, to download. see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Length
max_file_size = 25_000_000
# maximum file size, in bytes, that a file can be. if resulting file is bigger than this, mediaforge instantly gives
# up and does not try to upload nor resize the file.
way_too_big_size = 100_000_000
# the text to use for different messages, can be custom emojis or just any text
emojis = {
    "x": "<:xmark:803792052932444180>",
    "warning": "<:wmark:803791399782580284>",
    "question": "<:qmark:803791399615070249>",
    "exclamation_question": "<:eqmark:803791399501168641>",
    "2exclamation": "<:eemark:803791399710883871>",
    "working": "<a:working:803801825605320754>",
    "clock": "<:clockmark:803803703169515541>",
    "one": "<:one:826643438555758622>",
    "two": "<:two:826643438421671987>",
    "three": "<:three:826643438723923968>",
    "resize": "<:resize:826643438354694165>",
    "check": "<:check:826643438652489778>"
}
# up to 25 tips that can show when using $help tips. type \n for a newline
tips = {
    "Media Searching": "MediaForge automatically searches for any media in a channel. Reply to a message with the "
                       "command to search that message first.",
    "File Formats": "MediaForge supports static image formats like PNG, animated image formats like GIF, and video "
                    "formats like MP4.",
    "Self-Hosting": "MediaForge is completely open source and anyone can host a clone "
                    "themself!\nhttps://github.com/HexCodeFFF/mediaforge "
}
# https://www.reddit.com/r/discordapp/comments/aflp3p/the_truth_about_discord_file_upload_limits/
# configured upload limit, in bytes, for files.
# dont change this unless you have a really good reason to. i dont have error handling for overly large files
file_upload_limit = 8_388_119
# this applies to every command. if any string arguments contain any of these words, the command will instantly
# fail. this is intended to block hateful language like slurs. not case sensitive.
# its in the config so i dont have to upload slurs to github...
blocked_words = []
# filename of the sqlite3 database. currently only used for storing server-specific prefixes.
db_filename = "database.db"
# default prefix for commands
default_command_prefix = "$"
# this url will be sent a periodic request. this is designed to be used with an uptime monitoring service
heartbeaturl = None
# how often (in seconds) to request the heartbeat url
heartbeatfrequency = 60
# number of shards
# set to None or remove and "the library will use the Bot Gateway endpoint call to figure out how many shards to use."
shard_count = None
# maximum number of frames an input video can have, will be trimmed if it's too long
max_frames = 1024
# maximum temp file size from FFmpeg. reduce if ffmpeg eats into your disk/memory too much, increase if youre able
max_temp_file_size = "1G"
# cap FPS for sanity
max_fps = 100
