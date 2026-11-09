"""QR Code, rendered with segno; native `^BQ` in ZPL. Error correction level M."""

import io

import segno

from qrbar._checks import require_int
from qrbar.exceptions import PayloadError
from qrbar.symbologies.base import DEFAULT_SCALE, require_text, zpl_field


class QrSymbology:
    name = "qr"

    def validate(self, payload: str) -> None:
        self._make(payload)

    def to_png(self, payload: str, *, scale: int = DEFAULT_SCALE, quiet_zone: bool = True) -> bytes:
        require_int("scale", scale, 1)

        return self._save(payload, kind="png", scale=scale, border=None if quiet_zone else 0)

    def to_svg(self, payload: str) -> bytes:
        return self._save(payload, kind="svg")

    def module_size(self, payload: str) -> tuple[int, int]:
        width, height = self._make(payload, boost_error=False).symbol_size(border=0)

        return int(width), int(height)

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:  # noqa: ARG002 - square
        text = require_text(self.name, payload)

        self._make(text)

        # ^BQ: normal orientation, model 2, magnification; data "MA,": level M, automatic mode
        return f"^BQN,2,{module}" + zpl_field(f"MA,{text}")

    def _make(self, payload: str, *, boost_error: bool = True) -> segno.QRCode:
        """Build the code; ZPL cannot boost the error level, so sizing for it does not."""
        text = require_text(self.name, payload)

        try:
            return segno.make_qr(text, error="m", boost_error=boost_error, encoding="utf-8")

        except segno.DataOverflowError:
            raise PayloadError(self.name, payload, "too long for a QR code") from None

    def _save(self, payload: str, *, kind: str, scale: int = 1, border: int | None = None) -> bytes:
        buffer = io.BytesIO()

        self._make(payload).save(buffer, kind=kind, scale=scale, border=border)

        return buffer.getvalue()
