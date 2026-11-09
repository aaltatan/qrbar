"""Build the Arabic text fixture: `uv run python tests/fixtures/make_text_fixture.py`.

Regenerate only after checking by eye that the new image reads correctly; a
Pillow, FreeType or font update can move pixels.
"""

from pathlib import Path

from PIL import ImageOps

from qrbar.arabic import default_font, rasterize

HERE = Path(__file__).parent

TEXT = "مصباح LED أبيض 12 واط"

HEIGHT = 40  # dots: size_mm=5 at 203 dpi


if __name__ == "__main__":
    image = rasterize(TEXT, default_font(), HEIGHT)

    ImageOps.invert(image.convert("L")).convert("1").save(str(HERE / "arabic_text.png"))
