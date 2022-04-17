import difflib
import io
import time
import typing

import docstring_parser
import nextcord as discord
import regex as re
from nextcord.ext import commands

import config
import database
import improcessing
# from main import database.db, renderpool, bot, prefix_function
import renderpool
from cog_conversion import UnicodeEmojiConverter
from mainutils import improcess, imagesearch, saveurls, prefix_function
from tempfiles import TempFileSession


def showcog(cog):
    show_cog = False
    # check if there are any non-hidden commands in the cog, if not, dont show it in the help menu.
    for com in cog.get_commands():
        if not com.hidden:
            show_cog = True
            break
    return show_cog


def add_long_field(embed: discord.Embed, name: str, value: str) -> discord.Embed:
    """
    add fields every 1024 characters to a discord embed
    :param embed: embed
    :param name: title of embed
    :param value: long value
    :return: updated embed
    """
    if len(value) <= 1024:
        return embed.add_field(name=name, value=value, inline=False)
    else:
        for i, section in enumerate(re.finditer('.{1,1024}', value, flags=re.S)):
            embed.add_field(name=name + f" {i + 1}", value=section[0], inline=False)
    if len(embed) > 6000:
        raise Exception(f"Generated embed exceeds maximum size. ({len(embed)} > 6000)")
    return embed


class Other(commands.Cog, name="Other"):
    """
    Commands that don't fit in the other categories.
    """

    def __init__(self, bot):
        self.bot: commands.Bot = bot

    @commands.cooldown(60, config.cooldown, commands.BucketType.guild)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.command(aliases=["pfx", "setprefix", "changeprefix", "botprefix", "commandprefix"])
    async def prefix(self, ctx, prefix=None):
        """
        Changes the bot's prefix for this guild.

        :param ctx: discord context
        :param prefix: The new prefix for the bot to use.
        """
        if prefix is None or prefix == config.default_command_prefix:
            await database.db.execute("DELETE FROM guild_prefixes WHERE guild=?", (ctx.guild.id,))
            await database.db.commit()
            await ctx.reply(f"{config.emojis['check']} Set guild prefix back to global default "
                            f"(`{config.default_command_prefix}`).")

        else:
            if not 50 >= len(prefix) > 0:
                raise commands.BadArgument(f"prefix must be between 1 and 50 characters.")
            # check for invalid characters by returning all invalid characters
            invalids = re.findall(r"[^a-zA-Z0-9!$%^&()_\-=+,<.>\/?;'[{\]}|]", prefix)
            if invalids:
                raise commands.BadArgument(f"{config.emojis['x']} Found invalid characters: "
                                           f"{', '.join([discord.utils.escape_markdown(i) for i in invalids])}")
            else:
                await database.db.execute("REPLACE INTO guild_prefixes(guild, prefix) VALUES (?,?)",
                                          (ctx.guild.id, prefix))
                await database.db.commit()
                await ctx.reply(f"{config.emojis['check']} Set guild prefix to `{prefix}`")
                if prefix.isalpha():  # only alphabetic characters
                    await ctx.reply(f"{config.emojis['warning']} Your prefix only contains alphabetic characters. "
                                    f"This could cause normal sentences/words to be interpreted as commands. "
                                    f"This could annoy users.")

    @commands.guild_only()
    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_guild_permissions(manage_emojis=True)
    @commands.command(aliases=["createemoji"])
    async def addemoji(self, ctx, name):
        """
        Adds a file as an emoji to a server.

        Both MediaForge and the command caller must have the Manage Emojis permission.

        :param ctx: discord context
        :param name: The emoji name. Must be at least 2 characters.
        :mediaparam media: A gif or image.
        """
        await improcess(ctx, improcessing.add_emoji, [["GIF", "IMAGE"]], ctx.guild, name, expectresult=False,
                        resize=False)

    # TODO: fix?
    @commands.guild_only()
    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_guild_permissions(manage_emojis=True)
    @commands.command(aliases=["createsticker"])
    async def addsticker(self, ctx, stickeremoji: UnicodeEmojiConverter, *, name: str):
        """
        Adds a file as a sticker to a server. Both MediaForge and the command caller must have the Manage Emojis
        and Stickers permission.

        :param ctx: discord context
        :param stickeremoji: The related emoji. Must be a single default emoji.
        :param name: The sticker name. Must be at least 2 characters.
        :mediaparam media: A gif or image.
        """
        await improcess(ctx, improcessing.add_sticker, [["GIF", "IMAGE"]], ctx.guild, stickeremoji, name,
                        expectresult=False, resize=False)

    @commands.command()
    async def bpm(self, ctx):
        """
        Detects bpm of media.

        :param ctx: discord context
        :mediaparam media: Video or audio.
        """
        await improcess(ctx, improcessing.tempo, [["VIDEO", "AUDIO"]], expectresult=False, resize=False)

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_guild=True)
    @commands.command(aliases=["guildatabase.dbanner", "serverbanner", "banner"])
    async def setbanner(self, ctx):
        """
        Sets a file as the server banner.
        Server must support banners.

        :param ctx: discord context
        :mediaparam media: An image.
        """
        if "BANNER" not in ctx.guild.features:
            await ctx.reply(f"{config.emojis['x']} This guild does not support banners.")
            return
        await improcess(ctx, improcessing.set_banner, [["IMAGE"]], ctx.guild, expectresult=False,
                        resize=False)

    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_guild=True)
    @commands.command(aliases=["setguildicon", "guildicon", "servericon", "seticon"])
    async def setservericon(self, ctx):
        """
        Sets a file as the server icon.
        If setting a gif, server must support animated icons.

        :param ctx: discord context
        :mediaparam media: An image or gif.
        """
        await improcess(ctx, improcessing.set_icon, [["IMAGE", "GIF"]], ctx.guild, expectresult=False,
                        resize=False)

    @commands.command(aliases=["statistics"])
    async def stats(self, ctx):
        """
        Displays some stats about what the bot is currently doing.

        :param ctx: discord context
        """
        stats = renderpool.renderpool.stats()
        embed = discord.Embed(color=discord.Color(0xD262BA), title="Statistics",
                              description="A 'task' is typically processing a single image/frame of a video. Not "
                                          "all commands will use tasks.")
        embed.add_field(name="Queued Tasks", value=f"{stats[0]}")
        embed.add_field(name="Currently Executing Tasks", value=f"{stats[1]}")
        embed.add_field(name="Available Workers", value=f"{config.chrome_driver_instances - stats[1]}")
        embed.add_field(name="Total Workers", value=f"{config.chrome_driver_instances}")
        if isinstance(self.bot, discord.AutoShardedClient):
            embed.add_field(name="Total Bot Shards", value=f"{len(self.bot.shards)}")
        await ctx.reply(embed=embed)

    @commands.command(aliases=["shard", "shardstats", "shardinfo"])
    async def shards(self, ctx):
        """
        Displays info about bot shards

        :param ctx: discord context
        """
        embed = discord.Embed(color=discord.Color(0xD262BA), title="Shards",
                              description="Each shard is a separate connection to Discord that handles a fraction "
                                          "of all servers MediaForge is in.")
        for i, shard in self.bot.shards.items():
            shard: discord.ShardInfo
            embed.add_field(name=f"Shard #{shard.id}", value=f"{round(shard.latency * 1000)}ms latency")
        await ctx.reply(embed=embed)

    @commands.command(aliases=["discord", "invite", "botinfo"])
    async def about(self, ctx):
        """
        Lists important links related to MediaForge such as the official server.

        :param ctx: discord context
        """
        embed = discord.Embed(color=discord.Color(0xD262BA), title="MediaForge")
        embed.add_field(name="Official MediaForge Discord Server", value=f"https://discord.gg/xwWjgyVqBz")
        embed.add_field(name="top.gg link", value=f"https://top.gg/bot/780570413767983122")
        embed.add_field(name="Vote for MediaForge on top.gg", value=f"https://top.gg/bot/780570413767983122/vote")
        embed.add_field(name="Add MediaForge to your server",
                        value=f"https://discord.com/api/oauth2/authorize?client_id=780570413767983122&permissions=3"
                              f"79968&scope=bot")
        embed.add_field(name="MediaForge GitHub", value=f"https://github.com/HexCodeFFF/mediaforge")
        await ctx.reply(embed=embed)

    @commands.command(aliases=["privacypolicy"])
    async def privacy(self, ctx):
        """
        Shows MediaForge's privacy policy

        :param ctx: discord context
        """
        embed = discord.Embed(color=discord.Color(0xD262BA), title="Privacy Policy")
        embed.add_field(name="What MediaForge Collects",
                        value=f"MediaForge has a sqlite database with the **sole purpose** of storing "
                              f"guild-specific command prefixes. **All** other data is *always* deleted when it is "
                              f"done with. MediaForge displays limited info "
                              f"about commands being run to the console of the host machine for debugging purposes."
                              f" This data is not stored either.")
        embed.add_field(name="Contact about data", value=f"There really isn't anything to contact me about since "
                                                         f"MediaForge doesn't have any form of long term data "
                                                         f"storage, but you can join the MediaForge discord "
                                                         f"server (https://discord.gg/QhMyz3n4V7) or raise an "
                                                         f"issue on the GitHub ("
                                                         f"https://github.com/HexCodeFFF/mediaforge).")
        await ctx.reply(embed=embed)

    @commands.command(aliases=["github", "git"])
    async def version(self, ctx):
        """
        Shows information on how this copy of MediaForge compares to the latest code on github.
        https://github.com/HexCodeFFF/mediaforge
        This command returns the output of `git status`.

        :param ctx: discord context
        """
        await improcessing.run_command("git", "fetch")
        status = await improcessing.run_command("git", "status")
        with io.StringIO() as buf:
            buf.write(status)
            buf.seek(0)
            await ctx.reply("Output of `git status` (the differences between this copy of MediaForge and the latest"
                            " code on GitHub)", file=discord.File(buf, filename="gitstatus.txt"))

    @commands.command(aliases=["ffmpeginfo"])
    async def ffmpegversion(self, ctx):
        """
        Shows version information of FFmpeg running on this copy.
        This command returns the output of `ffmpeg -version`.

        :param ctx: discord context
        """
        status = await improcessing.run_command("ffmpeg", "-version")
        with io.StringIO() as buf:
            buf.write(status)
            buf.seek(0)
            await ctx.reply("Output of `ffmpeg -version`", file=discord.File(buf, filename="ffmpegversion.txt"))

    def showcog(self, cog):
        showcog = False
        # check if there are any non-hidden commands in the cog, if not, dont show it in the help menu.
        for com in cog.get_commands():
            if not com.hidden:
                showcog = True
                break
        return showcog

    @commands.command()
    async def help(self, ctx, *, inquiry: typing.Optional[str] = None):
        """
        Shows help on bot commands.

        :param ctx: discord context
        :param inquiry: the name of a command or command category. If none is provided, all categories are shown.
        :return: the help text if found
        """
        prefix = await prefix_function(self.bot, ctx.message, True)
        # unspecified inquiry
        if inquiry is None:
            embed = discord.Embed(title="Help", color=discord.Color(0xB565D9),
                                  description=f"Run `{prefix}help category` to list commands from "
                                              f"that category.")
            # for every cog
            for c in self.bot.cogs.values():
                # if there is 1 or more non-hidden command
                if self.showcog(c):
                    # add field for every cog
                    if not c.description:
                        c.description = "No Description."
                    embed.add_field(name=c.qualified_name, value=c.description)
            await ctx.reply(embed=embed)
        # if the command argument matches the name of any of the cogs that contain any not hidden commands
        elif inquiry.lower() in (coglist := {k.lower(): v for k, v in self.bot.cogs.items() if self.showcog(v)}):
            # get the cog found
            cog = coglist[inquiry.lower()]
            embed = discord.Embed(title=cog.qualified_name,
                                  description=cog.description + f"\nRun `{prefix}help command` for "
                                                                f"more information on a command.",
                                  color=discord.Color(0xD262BA))
            # add field with description for every command in the cog
            for cmd in sorted(cog.get_commands(), key=lambda x: x.name):
                if not cmd.hidden:
                    desc = cmd.short_doc if cmd.short_doc else "No Description."
                    embed.add_field(name=f"{prefix}{cmd.name}", value=desc)
            await ctx.reply(embed=embed)
        else:
            # for every bot command
            for bot_cmd in self.bot.commands:
                # if the name matches inquiry or alias and is not hidden
                if (bot_cmd.name == inquiry.lower() or inquiry.lower() in bot_cmd.aliases) and not bot_cmd.hidden:
                    # set cmd and continue
                    cmd: discord.ext.commands.Command = bot_cmd
                    break
            else:
                # inquiry doesnt match cog or command, not found

                # get all cogs n commands n aliases
                allcmds = []
                for c in self.bot.cogs.values():
                    if self.showcog(c):
                        allcmds.append(c.qualified_name.lower())
                for cmd in self.bot.commands:
                    if not cmd.hidden:
                        allcmds.append(cmd.qualified_name)
                        allcmds += cmd.aliases
                match = difflib.get_close_matches(inquiry, allcmds, n=1, cutoff=0)[0]
                raise commands.BadArgument(
                    f"`{inquiry}` is not the name of a command or a command category. "
                    f"Did you mean `{match}`?")
                # past this assume cmd is defined
            embed = discord.Embed(title=prefix + cmd.name, description=cmd.cog_name,
                                  color=discord.Color(0xEE609C))
            # if command func has docstring
            if cmd.help:
                # parse it
                docstring = docstring_parser.parse(cmd.help, style=docstring_parser.DocstringStyle.REST)
                # format short/long descriptions or say if there is none.
                if docstring.short_description or docstring.long_description:
                    command_information = \
                        f"{f'**{docstring.short_description}**' if docstring.short_description else ''}" \
                        f"\n{docstring.long_description if docstring.long_description else ''}"
                else:
                    command_information = "This command has no information."
                embed = add_long_field(embed, "Command Information", command_information)

                paramtext = []
                # for every "clean paramater" (no self or ctx)
                for param in list(cmd.clean_params.values()):
                    # get command description from docstring
                    paramhelp = discord.utils.get(docstring.params, arg_name=param.name)
                    # not found in docstring
                    if paramhelp is None:
                        paramtext.append(f"**{param.name}** - No description")
                        continue
                    # optional argument (param has a default value)
                    if param.default != param.empty:  # param.empty != None
                        pend = f" (optional, defaults to `{param.default}`)"
                    else:
                        pend = ""
                    # format and add to paramtext list
                    paramhelp.description = paramhelp.description.replace('\n', ' ')
                    paramtext.append(f"**{param.name}** - "
                                     f"{paramhelp.description if paramhelp.description else 'No description'}"
                                     f"{pend}")
                mediaparamtext = []
                for mediaparam in re.finditer(re.compile(":mediaparam ([^ :]+): ([^\n]+)"), cmd.help):
                    argname = mediaparam[1]
                    argdesc = mediaparam[2]
                    mediaparamtext.append(f"**{argname}** - {argdesc}")
                # if there are params found
                if len(paramtext):
                    # join list and add to help
                    embed = add_long_field(embed, "Parameters", "\n".join(paramtext))
                if len(mediaparamtext):
                    mval = "*Media parameters are automatically collected from the channel.*\n" + \
                           "\n".join(mediaparamtext)
                    embed = add_long_field(embed, "Media Parameters", mval)
                if docstring.returns:
                    embed.add_field(name="Returns", value=docstring.returns.description, inline=False)
            else:
                # if no docstring
                embed.add_field(name="Command Information", value="This command has no information.", inline=False)
            # cmd.signature is a human readable list of args formatted like the manual usage
            embed.add_field(name="Usage", value=prefix + cmd.name + " " + cmd.signature)
            # if aliases, add
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join([prefix + a for a in cmd.aliases]))

            await ctx.reply(embed=embed)

    @commands.command(aliases=["ffprobe"])
    async def info(self, ctx):
        """
        Provides info on a media file.
        Info provided is from ffprobe and libmagic.

        :param ctx: discord context
        :mediaparam media: Any media file.
        """
        with TempFileSession() as tempfilesession:
            file = await imagesearch(ctx, 1)
            if file:
                file = await saveurls(file)
                result = await improcessing.ffprobe(file[0])
                await ctx.reply(f"`{result[1]}` `{result[2]}`\n```{result[0]}```")
                # os.remove(file[0])
            else:
                await ctx.send(f"{config.emojis['x']} No file found.")

    @commands.command()
    async def feedback(self, ctx):
        """
        Give feedatabase.dback for the bot.
        This sends various links from the github repo for reporting issues or asking questions.

        :param ctx: discord context
        """
        embed = discord.Embed(title="Feedatabase.dback",
                              description="Feedatabase.dback is best given via the GitHub repo, various "
                                          "links are provided below.",
                              color=discord.Color(0xD262BA))
        embed.add_field(name="Report a bug",
                        value="To report a bug, make an issue at\nhttps://github.com/HexCodeFFF/mediaforge/issues",
                        inline=False)
        embed.add_field(name="Ask a question", value="Have a question? Use the Q&A Discussion "
                                                     "page.\nhttps://github.com/HexCodeFFF/mediaforge/discussions/c"
                                                     "ategories/q-a", inline=False)
        embed.add_field(name="Give an idea",
                        value="Have an idea or suggestion? Use the Ideas Discussion page.\nhtt"
                              "ps://github.com/HexCodeFFF/mediaforge/discussions/categories/id"
                              "eas", inline=False)
        embed.add_field(name="Something else?",
                        value="Anything is welcome in the discussion page!\nhttps://github."
                              "com/HexCodeFFF/mediaforge/discussions", inline=False)
        embed.add_field(name="Why GitHub?",
                        value="Using GitHub for feedatabase.dback makes it much easier to organize any i"
                              "ssues and to implement them into the bot's code.")
        await ctx.reply(embed=embed)

    @commands.command()
    async def attributions(self, ctx):
        """
        Lists most libraries and programs this bot uses.

        :param ctx: discord context
        """
        with open("media/attributions.txt", "r") as f:
            await ctx.send(f.read())

    @commands.command(aliases=["pong"])
    async def ping(self, ctx):
        """
        Pong!

        :param ctx: discord context
        :return: API and websocket latency
        """
        start = time.perf_counter()
        message = await ctx.send("Ping...")
        end = time.perf_counter()
        duration = (end - start) * 1000
        await message.edit(content=f'🏓 Pong!\n'
                                   f'API Latency: `{round(duration)}ms`\n'
                                   f'Websocket Latency: `{round(self.bot.latency * 1000)}ms`')
