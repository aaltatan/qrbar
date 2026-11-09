"""Build the README images: `uv run python docs/make_images.py`.

`images/sheet_preview.png` is not made here: it is page 1 of a rendered sheet
converted to PDF (Word or `qrbar.docx_to_pdf`) and then to PNG.
"""

from pathlib import Path

from PIL import ImageOps

import qrbar
from qrbar.arabic import default_font, rasterize

IMAGES = Path(__file__).parent / "images"

CODES = {
    "qr": "https://example.com/item/42",
    "code128": "SKU-00042",
    "ean13": "400638133393",
    "upca": "03600029145",
    "datamatrix": "SKU-00042",
    "pdf417": "SKU-00042 Lamp 12W",
    "aztec": "https://example.com/item/42",
}

SCALES = {"code128": 2, "ean13": 2, "upca": 2, "pdf417": 2}


if __name__ == "__main__":
    IMAGES.mkdir(exist_ok=True)

    for name, payload in CODES.items():
        png = qrbar.render_code(name, payload, scale=SCALES.get(name, 5))

        (IMAGES / f"{name}.png").write_bytes(png)

    text = rasterize("مصباح LED أبيض 12 واط", default_font(), 48)

    ImageOps.invert(text.convert("L")).save(str(IMAGES / "arabic_text.png"))
