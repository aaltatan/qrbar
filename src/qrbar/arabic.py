"""Arabic text for printers that cannot shape it: shaped, ordered and drawn as a ZPL graphic.

Shaping and ordering need the `arabic` extra (`pip install qrbar[arabic]`). The
default font, IBM Plex Sans Arabic (SIL OFL 1.1, see `fonts/OFL.txt`), ships
with the package and covers Latin too, so mixed text draws in one font.
"""

import io
import math
import re
from functools import cache, lru_cache
from importlib import resources

from PIL import Image, ImageDraw, ImageFont

from qrbar.exceptions import ValidationError

_ARABIC = re.compile("[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")


def has_arabic(text: str) -> bool:
    return _ARABIC.search(text) is not None


@cache
def default_font() -> bytes:
    """Return the bundled font (package data, not a caller path)."""
    return (resources.files("qrbar") / "fonts" / "IBMPlexSansArabic-Regular.ttf").read_bytes()


def check_font(font: bytes) -> None:
    """Raise `ValidationError` unless `font` is a TrueType or OpenType font."""
    _load_font(font, 10)


def rasterize(text: str, font: bytes, height: int) -> Image.Image:
    """Draw `text` in display order, `height` px font size, 1-bit, ink white (bit 1).

    The image is the font's full line height, so labels line up whatever the
    letters; it is as wide as the ink.
    """
    try:
        from arabic_reshaper import reshape  # noqa: PLC0415 - optional extra
        from bidi import get_display  # noqa: PLC0415 - optional extra

    except ImportError:
        msg = "Arabic text in ZPL needs the arabic extra: pip install qrbar[arabic]."

        raise ValidationError(msg) from None

    line = get_display(reshape(text))

    face = _load_font(font, height)

    ascent, descent = face.getmetrics()

    left, _, right, _ = face.getbbox(line, anchor="la")

    image = Image.new("1", (max(1, math.ceil(right - left)), ascent + descent), 0)

    ImageDraw.Draw(image).text((-left, 0), line, font=face, fill=255, anchor="la")

    return image


def to_gf(image: Image.Image) -> str:
    """Return a `^GF` field for a 1-bit image whose ink is white (bit 1 prints black)."""
    data = image.tobytes()  # rows packed MSB first, padded to a byte

    row_bytes = (image.width + 7) // 8

    # shortcut: uncompressed ASCII hex, fine for a few lines of text; use ZPL
    # compression (or Z64) if labels carry large images
    return f"^GFA,{len(data)},{len(data)},{row_bytes},{data.hex().upper()}^FS"


@lru_cache(maxsize=16)
def _load_font(font: bytes, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(io.BytesIO(font), size)

    except OSError as error:
        msg = f"font must be TrueType or OpenType bytes: {error}."

        raise ValidationError(msg) from None
