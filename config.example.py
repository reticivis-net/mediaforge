# COPY THIS FILE INTO A FILE CALLED config.py AND CHANGE THE VALUES AS NEEDED.
# discord API bot token https://discord.com/developers/applications
bot_token = "EXAMPLE_TOKEN"
# tenor API key https://tenor.com/developer/keyregistration
tenor_key = "EXAMPLE_KEY"
# top.gg token. set to None to disable. https://docs.top.gg/
topgg_token = None
# windows executable for chromedriver https://chromedriver.chromium.org/
chrome_driver_windows = "chromedriver87.exe"
# linux binary for chromedriver https://chromedriver.chromium.org/
chrome_driver_linux = "./chromedriver87"
# the number of instances of chromedriver to run for caption processing.
# more means faster processing of videos and better under heavy load but also uses more PC resources!
chrome_driver_instances = 20
# NOTICE is recommended, INFO prints more information about what bot is doing, WARNING only prints errors.
log_level = "NOTICE"
# maximum number of frames for an input file.
max_frames = 1024
# amount of seconds cooldown per user commands have. set to 0 to disable cooldown
cooldown = 3
# minimum height/width that media will be sized up to if below
min_size = 100
# maximum height/width that media will be downsized to if above
max_size = 2000
# maximum size, in bytes, to download. see https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Length
max_file_size = 25000000
# the text to use for different messages, can be custom emojis or just unicode
emojis = {
    "x": "<:xmark:803792052932444180>",
    "warning": "<:wmark:803791399782580284>",
    "question": "<:qmark:803791399615070249>",
    "exclamation_question": "<:eqmark:803791399501168641>",
    "2exclamation": "<:eemark:803791399710883871>",
    "working": "<a:working:803801825605320754>",
    "clock": "<:clockmark:803803703169515541>"
}
# up to 25 tips that can show when using $help tips. type \n for a newline
tips = {
    "Media Searching": "MediaForge automatically searches for any media in a channel. Reply to a message with the command to search that message first.",
    "File Formats": "MediaForge supports static image formats like PNG, animated image formats like GIF, and video formats like MP4.",
    "Self-Hosting": "MediaForge is completely open source and anyone can host a clone themself!\nhttps://github.com/HexCodeFFF/captionbot"
}
# the directory to store temporary files in. must end with a slash.
temp_dir = "temp/"
# prefix for commands
command_prefix = "$"
