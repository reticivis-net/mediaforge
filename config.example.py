# COPY THIS FILE INTO A FILE CALLED config.py AND THEN CHANGE THE VALUES AS NEEDED.
# discord API bot token https://discord.com/developers/applications
bot_token = "EXAMPLE_TOKEN"
# tenor API key https://tenor.com/developer/keyregistration
tenor_key = "EXAMPLE_KEY"
# windows executable for chromedriver https://chromedriver.chromium.org/
chrome_driver_windows = "chromedriver87.exe"
# linux binary for chromedriver https://chromedriver.chromium.org/
chrome_driver_linux = "chromedriver87"
# the number of instances of chromedriver to run for caption processing.
# more means faster processing of videos and better under heavy load but also uses more PC resources!
chrome_driver_instances = 20
# maximum number of frames for an input file.
max_frames = 1024
# amount of seconds cooldown per user commands have. set to 0 to disable cooldown
cooldown = 1
# NOTICE is recommended, INFO prints more information about what bot is doing, WARNING only prints errors.
log_level = "NOTICE"
# prefix for commands
command_prefix = "$"
