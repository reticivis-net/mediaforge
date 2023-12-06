# MediaForge Privacy Policy

See the [Terms of Service](terms_of_service.md).

## Text and Commands

Through [discord.py](https://github.com/Rapptz/discord.py), MediaForge internally scans every message in the channels it
has access to. It ignores all commands
except the ones containing the server's command prefix. All attempted command invocations, via classic chat commands or
new slash commands, are logged to the console for debugging and monitoring purposes. The logged data includes the
command, command arguments, the user, channel, and server. This data may be occasionally saved to be analyzed for
debugging but is never publicly released nor permanently stored.

## Media

When requested by a command, MediaForge scans the channel of command invocation for media. Anything that isn't media is
ignored. One or more medias are downloaded for the command and, depending on if the command is successful, a media may
be sent back. Media is stored in a temporary directory in memory and is designed to be deleted as soon as it's not
needed. MediaForge makes no guarantee that this deletion is always successful, but it will never be shared publicly or
permanently stored.

## Self-Hosted Instances

The ID of the official MediaForge bot is `780570413767983122`. MediaForge
is [open-source](https://github.com/reticivis-net/mediaforge) and designed to be flexible for
others to host their own copy of MediaForge. MediaForge makes no guarantee that any self-hosted copy of MediaForge
follows the official privacy policy.

## Remember the Human

I am only human, and although I will try my best to uphold these practices, the chance of a mistake, hack, or other
attack is non-zero, and I am not liable for any damages caused.