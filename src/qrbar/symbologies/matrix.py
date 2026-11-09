"""2D codes encoded with zxing-cpp: Data Matrix, PDF417 and Aztec.

Text is encoded as UTF-8. ZPL uses the printer's native commands (`^BX`, `^B7`,
`^BO`); the printer encodes the data again, so the symbol layout is pinned
where ZPL allows it (PDF417 rows, columns and security level) to keep the
printed size equal to the PNG.
"""

import io
import math

import zxingcpp
from PIL import Image

from qrbar._checks import require_int
from qrbar.exceptions import PayloadError
from qrbar.symbologies.base import DEFAULT_SCALE, require_text, zpl_field

_PDF417_ROW_MODULES = 3  # zxing-cpp's row height, in modules

_PDF417_FIXED_MODULES = 69  # start + stop patterns and the two row indicators

_PDF417_COLUMN_MODULES = 17


class _Matrix:
    name: str
    barcode_format: zxingcpp.BarcodeFormat

    def validate(self, payload: str) -> None:
        self._make(payload)

    def to_png(self, payload: str, *, scale: int = DEFAULT_SCALE, quiet_zone: bool = True) -> bytes:
        require_int("scale", scale, 1)

        image = _to_pil(self._make(payload).to_image(scale=scale, add_quiet_zones=quiet_zone))

        buffer = io.BytesIO()

        image.convert("1").save(buffer, "PNG")

        return buffer.getvalue()

    def to_svg(self, payload: str) -> bytes:
        return self._make(payload).to_svg(add_quiet_zones=True).encode()

    def module_size(self, payload: str) -> tuple[int, int]:
        return self._module_size(self._make(payload))

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:
        raise NotImplementedError

    def _make(self, payload: str) -> zxingcpp.Barcode:
        text = require_text(self.name, payload)

        try:
            return zxingcpp.create_barcode(text, self.barcode_format, **self._options())

        except ValueError as error:
            raise PayloadError(self.name, payload, str(error)) from None

    def _options(self) -> dict[str, object]:
        return {}

    @staticmethod
    def _module_size(barcode: zxingcpp.Barcode) -> tuple[int, int]:
        height, width = memoryview(barcode.to_image(add_quiet_zones=False)).shape or (0, 0)

        return width, height


class DataMatrixSymbology(_Matrix):
    name = "datamatrix"
    barcode_format = zxingcpp.BarcodeFormat.DataMatrix

    def _options(self) -> dict[str, object]:
        return {"force_square": True}  # ZPL ^BX draws square symbols by default

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:  # noqa: ARG002 - square
        text = require_text(self.name, payload)

        self._make(text)

        # ^BX: module height, ECC 200, size chosen by the printer; `~` is ^BX's escape
        # character, so a literal one is written as its decimal code
        return f"^BXN,{module},200" + zpl_field(text.replace("~", "~d126"))


class Pdf417Symbology(_Matrix):
    name = "pdf417"
    barcode_format = zxingcpp.BarcodeFormat.PDF417

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:
        """Return `^B7` with zxing-cpp's rows, columns and security level; `height` is total."""
        text = require_text(self.name, payload)

        barcode = self._make(text)

        width_modules, height_modules = self._module_size(barcode)

        rows = height_modules // _PDF417_ROW_MODULES

        columns = (width_modules - _PDF417_FIXED_MODULES) // _PDF417_COLUMN_MODULES

        level = _pdf417_level(barcode, rows * columns)

        row_height = max(1, height // rows)

        return f"^BY{module}^B7N,{row_height},{level},{columns},{rows}" + zpl_field(text)


class AztecSymbology(_Matrix):
    name = "aztec"
    barcode_format = zxingcpp.BarcodeFormat.Aztec

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:  # noqa: ARG002 - square
        text = require_text(self.name, payload)

        self._make(text)

        # ^BO: magnification, no ECI, default error correction and size
        return f"^BON,{module},N,0" + zpl_field(text)


def _pdf417_level(barcode: zxingcpp.Barcode, codewords: int) -> int:
    """Return the security level zxing-cpp chose: 2^(level+1) error codewords.

    zxing-cpp reports it as a share of all codewords, e.g. `"50%"`.
    """
    share = float(barcode.ec_level.rstrip("%")) / 100

    return round(math.log2(share * codewords)) - 1


def _to_pil(image: zxingcpp.Image) -> Image.Image:
    view = memoryview(image)

    height, width = view.shape or (0, 0)

    return Image.frombytes("L", (width, height), view.tobytes())
