"""Standalone barcode images, without a template."""

from typing import Literal

from qrbar.exceptions import ValidationError
from qrbar.symbologies import DEFAULT_SCALE, get

type ImageFormat = Literal["png", "svg"]


def render_code(
    name: str,
    payload: str,
    fmt: ImageFormat = "png",
    *,
    scale: int = DEFAULT_SCALE,
) -> bytes:
    """Render one barcode as PNG or SVG bytes. `scale` is PNG pixels per module."""
    symbology = get(name)

    if fmt == "png":
        return symbology.to_png(payload, scale=scale)

    if fmt == "svg":
        return symbology.to_svg(payload)

    msg = f"Unknown image format {fmt!r}, expected 'png' or 'svg'."

    raise ValidationError(msg)
