import io
import zipfile
from pathlib import Path
from typing import Any

import pytest
import zxingcpp
from docx import Document
from docx.shared import Mm
from PIL import Image, ImageOps

from qrbar.docx import IMAGE_DPI, render_docx_paged, render_docx_per_item, render_docx_sheet
from qrbar.exceptions import PayloadError, RecordError, TemplateError, ValidationError
from qrbar.layout import SheetOptions, SheetSpec
from qrbar.records import parse_records

FIXTURES = Path(__file__).parent / "fixtures"

SHEET = (FIXTURES / "sheet_a4_3x8.docx").read_bytes()

PAGED = (FIXTURES / "label_paged.docx").read_bytes()

A4_3X8 = SheetSpec(rows=8, cols=3)

DATA: list[dict[str, Any]] = [
    {"url": "https://example.com/a", "name": "A & B <x>", "sku": "SKU-A", "qty": 2},
    {"url": "https://example.com/b", "name": "Lamp", "sku": "SKU-B"},
]


def template(*paragraphs: str) -> bytes:
    """Build a one-off docx template with one paragraph per string."""
    document = Document()

    for text in paragraphs:
        document.add_paragraph(text)

    buffer = io.BytesIO()

    document.save(buffer)

    return buffer.getvalue()


def one(docx_template: bytes, data: dict[str, Any]) -> bytes:
    """Render a single-record template, which sees `item`."""
    [docx] = render_docx_per_item(docx_template, parse_records(data))

    return docx


def xml(docx: bytes) -> str:
    return zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode()


def cell_texts(docx: bytes) -> list[list[list[str]]]:
    """Text of every cell, per table, per row."""
    tables = Document(io.BytesIO(docx)).tables

    return [[[cell.text.strip() for cell in row.cells] for row in table.rows] for table in tables]


def paragraph_texts(docx: bytes) -> list[str]:
    return [p.text for p in Document(io.BytesIO(docx)).paragraphs if p.text]


def extents(docx: bytes) -> list[tuple[int, int]]:
    """(width, height) in EMU of every inline image, in order."""
    shapes = Document(io.BytesIO(docx)).inline_shapes

    return [(shape.width, shape.height) for shape in shapes]


def decode_images(docx: bytes) -> set[str]:
    """Decode every embedded image, after adding the white margin a cell would give."""
    archive = zipfile.ZipFile(io.BytesIO(docx))

    texts: set[str] = set()

    for name in archive.namelist():
        if name.startswith("word/media/"):
            image = Image.open(io.BytesIO(archive.read(name))).convert("L")

            padded = ImageOps.expand(image, border=image.width // 4, fill=255)

            texts.update(result.text for result in zxingcpp.read_barcodes(padded))

    return texts


def test_sheet_fills_cells_with_codes_and_escaped_text() -> None:
    docx = render_docx_sheet(SHEET, parse_records(DATA), A4_3X8)

    assert cell_texts(docx) == [[["A & B <x>", "A & B <x>", "Lamp"]]]

    assert extents(docx) == [(Mm(20), Mm(20))] * 3

    assert decode_images(docx) == {"https://example.com/a", "https://example.com/b"}


def test_sheet_starts_a_new_table_per_page() -> None:
    docx = render_docx_sheet(SHEET, parse_records({"url": "u", "name": "N", "qty": 25}), A4_3X8)

    tables = cell_texts(docx)

    assert [len(table) for table in tables] == [8, 1]

    assert tables[1] == [["N", "", ""]]

    assert xml(docx).count('w:type="page"') == 1


def test_sheet_options_are_applied() -> None:
    options = SheetOptions(skip=2, new_page_per_record=True)

    docx = render_docx_sheet(SHEET, parse_records(DATA), A4_3X8, options)

    assert cell_texts(docx) == [[["", "", "A & B <x>"], ["A & B <x>", "", ""]], [["Lamp", "", ""]]]


def test_paged_has_one_label_per_copy() -> None:
    docx = render_docx_paged(PAGED, parse_records(DATA), "interleaved")

    assert paragraph_texts(docx) == ["A & B <x>", "Lamp", "A & B <x>"]

    assert xml(docx).count('w:type="page"') == 2

    assert extents(docx) == [(Mm(50), Mm(12))] * 3

    assert decode_images(docx) == {"SKU-A", "SKU-B"}


def test_per_item_is_one_document_per_record_with_its_copies() -> None:
    first, second = render_docx_per_item(PAGED, parse_records(DATA))

    assert paragraph_texts(first) == ["A & B <x>", "A & B <x>"]

    assert paragraph_texts(second) == ["Lamp"]


def test_per_item_template_can_use_item_directly() -> None:
    docs = render_docx_per_item(
        template("{{ item.name }} x{{ items | length }}"), parse_records(DATA)
    )

    assert [paragraph_texts(doc) for doc in docs] == [["A & B <x> x2"], ["Lamp x1"]]


def test_default_size_is_a_quarter_mm_per_module() -> None:
    docx = one(template("{{ qr(item.url) }}{{ code128(item.sku) }}"), DATA[1])

    # QR: 25 modules; Code 128 "SKU-B": 90 modules wide, 50 tall
    assert extents(docx) == [(Mm(6.25), Mm(6.25)), (Mm(22.5), Mm(12.5))]


def test_images_have_print_resolution_and_no_quiet_zone() -> None:
    docx = one(template("{{ qr(item.url, size_mm=20) }}"), DATA[1])

    archive = zipfile.ZipFile(io.BytesIO(docx))

    [name] = [n for n in archive.namelist() if n.startswith("word/media/")]

    image = Image.open(io.BytesIO(archive.read(name))).convert("L")

    assert image.width / (20 / 25.4) >= IMAGE_DPI

    assert image.getpixel((0, 0)) == 0  # a finder pattern corner, not a white margin


def test_2d_codes_default_to_a_quarter_mm_per_module() -> None:
    docx = one(template("{{ pdf417(item.v) }}{{ datamatrix(item.v) }}"), {"v": "hello world"})

    # PDF417: 103 x 24 modules; Data Matrix: 16 x 16
    assert extents(docx) == [(Mm(25.75), Mm(6)), (Mm(4), Mm(4))]

    assert decode_images(docx) == {"hello world"}


def test_generic_barcode_and_int_payloads() -> None:
    docx = one(template("{{ barcode('ean13', item.ean, size_mm=30) }}"), {"ean": 400638133393})

    assert extents(docx) == [(Mm(30), Mm(30))]

    assert decode_images(docx) == {"4006381333931"}


LOOP = "{{% for item in items %}}{{{{ {} }}}}{{% endfor %}}"


def test_sheet_errors_raise_without_a_record() -> None:
    with pytest.raises(TemplateError, match="has no attribute 'url'"):
        render_docx_paged(template(LOOP.format("qr(item.url)")), parse_records({}))

    with pytest.raises(PayloadError, match="must be 12 or 13 digits"):
        render_docx_paged(template(LOOP.format("ean13(item.sku)")), parse_records(DATA))


def test_per_item_errors_name_the_record() -> None:
    data: list[dict[str, Any]] = [{"ean": "400638133393"}, {"ean": "123"}]

    with pytest.raises(RecordError, match=r"^Record 1: ean13: invalid payload '123'") as info:
        render_docx_per_item(template("{{ ean13(item.ean) }}"), parse_records(data))

    assert isinstance(info.value.error, PayloadError)


@pytest.mark.parametrize(
    ("call", "message"),
    [
        ("qr('x', size_mm=0)", "width_mm must be a number > 0"),
        ("code128('x', height_mm=-1)", "height_mm must be a number > 0"),
    ],
)
def test_bad_sizes_are_rejected(call: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        render_docx_paged(template(f"{{{{ {call} }}}}"), parse_records({}))


def test_syntax_error_is_a_template_error() -> None:
    with pytest.raises(TemplateError, match=r"^Docx template:"):
        render_docx_paged(template("{{ item.name "), parse_records({}))


@pytest.mark.parametrize("data", [b"not a zip", b"PK\x05\x06" + b"\x00" * 18])
def test_invalid_docx_is_a_template_error(data: bytes) -> None:
    with pytest.raises(TemplateError, match=r"not a valid .docx file"):
        render_docx_paged(data, parse_records({}))


@pytest.mark.parametrize(
    "expression", ["cycler.__init__.__globals__", "items.__class__.__mro__", "qr.func.__globals__"]
)
def test_templates_cannot_reach_python_internals(expression: str) -> None:
    with pytest.raises(TemplateError, match="unsafe"):
        render_docx_paged(template(f"{{{{ {expression} }}}}"), parse_records({}))
