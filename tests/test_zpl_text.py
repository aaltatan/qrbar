"""`text()` in ZPL templates: Latin as native `^A0`, Arabic as a `^GF` graphic."""

import re
import sys
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageOps

import qrbar
from qrbar import RecordError, ValidationError
from qrbar.arabic import default_font, has_arabic

FIXTURES = Path(__file__).parent / "fixtures"

ARABIC = "مصباح LED أبيض 12 واط"

GF = re.compile(r"\^GFA,(\d+),(\d+),(\d+),([0-9A-F]+)\^FS")


def label(field: str, data: object, **kwargs: Any) -> str:
    """Render a one-field label and return the field, between `^CI28` and `^PQ`."""
    template = f"^XA{field}^XZ".encode()

    [zpl] = qrbar.render(template, {"v": data}, mode="per_item", **kwargs)

    return zpl.decode().removeprefix("^XA^CI28").removesuffix("^PQ1^XZ")


def test_latin_text_is_a_native_field_with_escaping() -> None:
    assert label("{{ text(item.v) }}", "SKU_1^x~") == "^A0N,24,24^FH_^FDSKU_5F1_5Ex_7E^FS"


def test_size_and_dpi_set_the_height_in_dots() -> None:
    field = "{% set dpi = 300 %}{{ text(item.v, size_mm=5) }}"

    assert label(field, 42).startswith("^A0N,59,59^")


def test_arabic_text_is_a_graphic_matching_the_fixture() -> None:
    field = label("{{ text(item.v, size_mm=5) }}", ARABIC)

    match = GF.fullmatch(field)

    assert match is not None

    total, _, row_bytes, data = match.groups()

    expected = Image.open(FIXTURES / "arabic_text.png")

    assert int(row_bytes) == (expected.width + 7) // 8

    assert int(total) == int(row_bytes) * expected.height == len(data) // 2

    ink = ImageOps.invert(expected.convert("L")).convert("1")

    assert bytes.fromhex(data) == ink.tobytes()


def test_a_custom_font_is_used() -> None:
    bundled = label("{{ text(item.v) }}", ARABIC)

    assert label("{{ text(item.v) }}", ARABIC, font=default_font()) == bundled


def test_bad_font_bytes_are_rejected_up_front() -> None:
    with pytest.raises(ValidationError, match="font must be TrueType or OpenType"):
        label("{{ text(item.v) }}", "x", font=b"not a font")


def test_font_does_not_apply_to_docx() -> None:
    docx = (FIXTURES / "label_paged.docx").read_bytes()

    with pytest.raises(ValidationError, match="font only applies to ZPL"):
        qrbar.render(docx, {}, font=default_font())


def test_missing_extra_names_the_install_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "bidi", None)

    with pytest.raises(RecordError, match=r"pip install qrbar\[arabic\]"):
        label("{{ text(item.v) }}", ARABIC)


def test_latin_text_does_not_need_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "bidi", None)

    assert label("{{ text(item.v) }}", "Lamp").endswith("^FDLamp^FS")


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("{{ text(item.missing) }}", "has no attribute 'missing'"),
        ("{{ text(item.v, size_mm=0) }}", "size_mm must be a number > 0"),
    ],
)
def test_errors_name_the_record(field: str, message: str) -> None:
    with pytest.raises(RecordError, match=message):
        label(field, "x")


@pytest.mark.parametrize(
    ("text", "expected"),
    [("Lamp", False), ("مصباح", True), ("Lamp ٣", True), ("ﻻ", True), ("Ünïcode", False)],
)
def test_has_arabic(text: str, expected: bool) -> None:
    assert has_arabic(text) is expected


def test_the_font_licence_ships_with_the_font() -> None:
    fonts = resources.files("qrbar") / "fonts"

    assert "SIL Open Font License" in (fonts / "OFL.txt").read_text(encoding="utf-8")
