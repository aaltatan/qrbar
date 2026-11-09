"""Linear (1D) barcodes encoded with python-barcode: Code 128, EAN-13 and UPC-A.

PNGs are drawn here from python-barcode's module pattern, because its own
image writer positions bars with float mm and makes them a pixel too wide or
narrow. Both PNG and SVG show bars only; templates print any text themselves.
ZPL uses the printer's native commands (`^BC`, `^BE`, `^BU`), also without text.
"""

import io
from typing import Any

from barcode import EAN13, UPCA, Code128
from barcode.writer import SVGWriter
from PIL import Image

from qrbar._checks import require_int
from qrbar.exceptions import PayloadError
from qrbar.symbologies.base import DEFAULT_SCALE, require_text, zpl_field

BAR_HEIGHT_MODULES = 50
"""PNG bar height in modules; renderers that size the image in mm override the ratio."""

_SVG_MODULE_MM = 0.2  # python-barcode's default module width

_WHITE = 255

_BLACK = 0


class _Linear:
    name: str
    barcode_class: Any
    quiet_modules: int  # minimum quiet zone on each side, in modules
    zpl_command: str  # ZPL barcode command with a `{height}` placeholder

    def validate(self, payload: str) -> None:
        self._prepare(payload)

    def modules(self, payload: str) -> str:
        """Return the bar pattern, one `1` (bar) or `0` (space) per module."""
        pattern: str = self.barcode_class(self._prepare(payload)).build()[0]

        return pattern

    def to_png(self, payload: str, *, scale: int = DEFAULT_SCALE, quiet_zone: bool = True) -> bytes:
        require_int("scale", scale, 1)

        quiet = [_WHITE] * (self.quiet_modules if quiet_zone else 0)

        row = [*quiet, *(_BLACK if m == "1" else _WHITE for m in self.modules(payload)), *quiet]

        image = Image.new("1", (len(row), 1))

        image.putdata(row)

        size = (len(row) * scale, BAR_HEIGHT_MODULES * scale)

        buffer = io.BytesIO()

        image.resize(size, Image.Resampling.NEAREST).save(buffer, "PNG")

        return buffer.getvalue()

    def to_svg(self, payload: str) -> bytes:
        code = self.barcode_class(self._prepare(payload), writer=SVGWriter())

        options = {"quiet_zone": self.quiet_modules * _SVG_MODULE_MM, "write_text": False}

        buffer = io.BytesIO()

        code.write(buffer, options)

        return buffer.getvalue()

    def module_size(self, payload: str) -> tuple[int, int]:
        return len(self.modules(payload)), BAR_HEIGHT_MODULES

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:
        command = self.zpl_command.format(height=height)

        return f"^BY{module}{command}" + zpl_field(self._prepare(payload))

    def _prepare(self, payload: str) -> str:
        """Validate `payload` and return the text to hand to python-barcode."""
        raise NotImplementedError


class Code128Symbology(_Linear):
    name = "code128"
    barcode_class = Code128
    quiet_modules = 10
    zpl_command = "^BCN,{height},N,N,N,A"  # no text line, automatic subset switching

    def _prepare(self, payload: str) -> str:
        text = require_text(self.name, payload)

        if not text.isascii():
            raise PayloadError(self.name, payload, "only ASCII characters are allowed")

        return text


class _Ean(_Linear):
    digits: int  # data digits, without the check digit

    def _prepare(self, payload: str) -> str:
        """Return the data digits; one more digit must be the correct check digit.

        python-barcode silently replaces a wrong check digit, so it is checked here.
        """
        text = require_text(self.name, payload)

        if not (text.isascii() and text.isdigit()) or len(text) - self.digits not in {0, 1}:
            reason = f"must be {self.digits} or {self.digits + 1} digits"

            raise PayloadError(self.name, payload, reason)

        data = text[: self.digits]

        expected = ean13_check_digit(data.zfill(12))  # UPC-A is EAN-13 with a leading 0

        if text[self.digits :] not in {"", str(expected)}:
            raise PayloadError(self.name, payload, f"wrong check digit, expected {expected}")

        return data


class Ean13Symbology(_Ean):
    name = "ean13"
    barcode_class = EAN13
    quiet_modules = 11
    digits = 12
    zpl_command = "^BEN,{height},N,N"  # the printer adds the check digit


class UpcaSymbology(_Ean):
    name = "upca"
    barcode_class = UPCA
    quiet_modules = 9
    digits = 11
    zpl_command = "^BUN,{height},N,N,N"  # the printer adds the check digit


def ean13_check_digit(data: str) -> int:
    """Return the EAN-13 check digit for 12 data digits (weights 1, 3, 1, 3, ...)."""
    total = sum(int(digit) * (3 if i % 2 else 1) for i, digit in enumerate(data))

    return -total % 10
