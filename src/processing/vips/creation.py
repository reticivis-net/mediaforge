import typing

import pyvips

from processing.vips.caption import twemoji
from processing.vips.vipsutils import escape
from processing.vips.vipsutils import normalize
from utils.tempfiles import reserve_tempfile


def yskysn(captions: typing.Sequence[str]):
    captions = escape(captions)
    # load stuff
    im = normalize(pyvips.Image.new_from_file("rendering/images/yskysn.png"))
    # here for my sanity, dimensions of text area
    w = 500
    h = 582
    # technically redundant but adds twemoji font
    text_prerender = pyvips.Image.text(".", fontfile=twemoji)
    # generate text
    text_prerender, autofit_dict = pyvips.Image.text(
        f"<span foreground='white'>"
        f"{captions[0]}\n<span size='150%'>{captions[1]}</span>"
        f"</span>",
        font=f"Twemoji Color Emoji,Tahoma Bold 56",
        rgba=True,
        fontfile="rendering/fonts/TAHOMABD.TTF",
        align=pyvips.Align.CENTRE,
        width=w,
        height=h,
        autofit_dpi=True
    )
    autofit_dpi = autofit_dict["autofit_dpi"]
    if autofit_dpi <= 72:
        text = text_prerender
    else:
        # technically redundant but adds twemoji font
        text = pyvips.Image.text(".", fontfile=twemoji)
        # generate text
        text = pyvips.Image.text(
            f"<span foreground='white'>"
            f"{captions[0].upper()}\n<span size='150%'>{captions[1].upper()}</span>"
            f"</span>",
            font=f"Twemoji Color Emoji,Tahoma Bold 56",
            rgba=True,
            fontfile="rendering/fonts/TAHOMABD.TTF",
            align=pyvips.Align.CENTRE,
            width=w,
            height=h,
            dpi=72
        )
    # pad to expected size, 48 is margin
    text = text.gravity(pyvips.CompassDirection.CENTRE, w + 48, h + 48, extend=pyvips.Extend.BLACK)
    # add glow, similar technique to shadow
    mask = pyvips.Image.gaussmat(5 / 2, 0.0001, separable=True)
    glow = text[3].convsep(mask).cast(pyvips.BandFormat.UCHAR)
    glow = glow.new_from_image((255, 255, 255)) \
        .bandjoin(glow) \
        .copy(interpretation=pyvips.Interpretation.SRGB)

    text = glow.composite2(text, pyvips.BlendMode.OVER)

    out = im.composite2(text, pyvips.BlendMode.OVER)
    # save and return
    outfile = reserve_tempfile("png")
    out.pngsave(outfile)
    return outfile


def f1984(captions: typing.Sequence[str]):
    captions = escape(captions)

    originaldate = captions[1].lower() == "january 1984"

    if originaldate:
        im = normalize(pyvips.Image.new_from_file("rendering/images/1984/1984originaldate.png"))
    else:
        im = normalize(pyvips.Image.new_from_file("rendering/images/1984/1984.png"))

    # technically redundant but adds twemoji font
    speech_bubble = pyvips.Image.text(".", fontfile=twemoji)
    # generate text
    speech_bubble = pyvips.Image.text(
        captions[0],
        font=f"Twemoji Color Emoji,Atkinson Hyperlegible Bold",
        rgba=True,
        fontfile="rendering/fonts/AtkinsonHyperlegible-Bold.ttf",
        align=pyvips.Align.CENTRE,
        width=290,
        height=90
    )
    # pad to expected size
    speech_bubble = speech_bubble.gravity(pyvips.CompassDirection.CENTRE, 290, 90, extend=pyvips.Extend.BLACK)
    # add speech bubble
    im = im.composite2(speech_bubble, pyvips.BlendMode.OVER, x=60, y=20)

    if not originaldate:
        # technically redundant but adds twemoji font
        date = pyvips.Image.text(".", fontfile=twemoji)
        # generate text
        date = pyvips.Image.text(
            captions[1].upper(),
            font=f"Twemoji Color Emoji,ImpactMix",
            rgba=True,
            fontfile="rendering/fonts/ImpactMix.ttf",
            align=pyvips.Align.CENTRE,
            width=124,
            height=34
        )
        # pad to expected size
        date = date.gravity(pyvips.CompassDirection.CENTRE, 124, 34, extend=pyvips.Extend.BLACK)
        # equivelant to skewY(10deg)
        date = date.affine([1, 0, 0.176327, 1])
        # add date
        im = im.composite2(date, pyvips.BlendMode.OVER, x=454, y=138)
        # add cover
        im = im.composite2(normalize(pyvips.Image.new_from_file("rendering/images/1984/1984cover.png")),
                           pyvips.BlendMode.OVER)

    outfile = reserve_tempfile("png")
    im.pngsave(outfile)
    return outfile


def epicbirthdaytext(caption: str):
    # technically redundant but adds twemoji font
    text = pyvips.Image.text(".", fontfile=twemoji)
    # generate text
    text = pyvips.Image.text(
        f"<span foreground=\"white\">{caption.upper()}</span>",
        font=f"Twemoji Color Emoji,MarkerFeltWide",
        rgba=True,
        fontfile="rendering/fonts/MarkerFeltWide Regular.ttf",
        align=pyvips.Align.CENTRE,
        width=540,
        height=260
    )
    outfile = reserve_tempfile("png")
    text.pngsave(outfile)
    return outfile
