import pronouncing
import regex as re
from nextcord.ext import commands

import captionfunctions
from mainutils import improcess


class Slashscript(commands.Cog, name="Slashscript"):
    """
    Commands that don't fit in the other categories.
    """

    def __init__(self, bot):
        self.bot = bot
        self.slashnemes = {"AA": "a", "AE": "a", "AH": "E", "AO": "o", "AW": "ao", "AY": "ai", "B": "b", "CH": "tS",
                           "D": "d", "DH": "D", "EH": "e", "ER": "er", "EY": "ei", "F": "f", "G": "g", "HH": "h",
                           "IH": "i", "IY": "i", "JH": "dZ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "N",
                           "OW": "o", "OY": "oi", "P": "p", "R": "r", "S": "s", "SH": "S", "T": "t", "TH": "T",
                           "UH": "u", "UW": "u", "V": "v", "W": "w", "Y": "y", "Z": "z", "ZH": "Z"}

    # @commands.command()
    # async def slashscript(self, ctx, *, text):
    #     """
    #     Eminem says something.
    #
    #
    #     :param text: The text to put next to eminem.
    #     """
    #     await improcess(ctx, captionfunctions.slashscript, [], [text])

    @commands.command(hidden=True, aliases=["slashscript", "slashscriptconvert", "ssconvert"])
    async def sconvert(self, ctx, *, text):
        """
        Converts text into a custom writing system known as SlashScript.
        """
        out = []
        for word in re.finditer("([a-zA-Z0-9!@#$%)>]+|[,.])", text.strip()):
            word = word.group(0)
            word_phonemes = pronouncing.phones_for_word(word.lower())
            if word_phonemes and not word.startswith(">"):  # pronunication known
                ph_list = (''.join(i for i in word_phonemes[0] if not i.isdigit())).split(" ")
                out.append(''.join(self.slashnemes[ph] for ph in ph_list if ph in self.slashnemes))
            elif word.startswith(">") or word in [".", ","]:
                out.append(word.replace(">", ""))
            else:
                await ctx.reply(f"No pronunciation found for `{word}`. To render literal slashnemes, begin the "
                                f"word with `>`.")
                return
        out = " ".join(out)
        # clear out any whitespace touching punctuation
        out = re.sub(r"(\s(?=[,.])|(?<=[,.])\s)", "", out)
        await improcess(ctx, captionfunctions.slashscript, [], [out])
