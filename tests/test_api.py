"""End to end: template bytes and data in, rendered bytes out, through `qrbar.render` only."""

import io
from pathlib import Path
from typing import Any

import pytest
from docx import Document

import qrbar
from qrbar import SheetOptions, SheetSpec, ValidationError

FIXTURES = Path(__file__).parent / "fixtures"

SHEET = (FIXTURES / "sheet_a4_3x8.docx").read_bytes()

PAGED = (FIXTURES / "label_paged.docx").read_bytes()

ZPL = (FIXTURES / "label_203dpi.zpl").read_bytes()

DATA: list[dict[str, Any]] = [
    {"url": "https://example.com/a", "sku": "SKU-A", "ean": "400638133393", "name": "A", "qty": 2},
    {"url": "https://example.com/b", "sku": "SKU-B", "ean": "400638133393", "name": "B"},
]


def names(docx: bytes) -> list[str]:
    """Non-empty paragraph and cell texts of a document, in order."""
    document = Document(io.BytesIO(docx))

    cells = [cell.text.strip() for t in document.tables for r in t.rows for cell in r.cells]

    return [p.text for p in document.paragraphs if p.text] + [c for c in cells if c]


def test_paged_docx_is_the_default() -> None:
    assert names(qrbar.render(PAGED, DATA)) == ["A", "A", "B"]


def test_paged_docx_can_interleave() -> None:
    assert names(qrbar.render(PAGED, DATA, collate="interleaved")) == ["A", "B", "A"]


def test_sheet_docx() -> None:
    options = SheetOptions(skip=1, collate="grouped")

    docx = qrbar.render(
        SHEET, DATA, mode="sheet", sheet=SheetSpec(8, 3), options=options, collate="interleaved"
    )

    assert Document(io.BytesIO(docx)).tables[0].rows[0].cells[1].text.strip() == "A"

    assert names(docx) == ["A", "B", "A"]


def test_per_item_docx() -> None:
    docs = qrbar.render(PAGED, DATA, mode="per_item")

    assert [names(doc) for doc in docs] == [["A", "A"], ["B"]]


def test_zpl_paged_joins_one_block_per_record() -> None:
    zpl = qrbar.render(ZPL, DATA).decode()

    assert zpl.count("^XA") == 2

    assert zpl.index("^PQ2^XZ") < zpl.index("^PQ1^XZ")


def test_zpl_per_item_is_one_block_each() -> None:
    labels = qrbar.render(ZPL, DATA, mode="per_item", kind="zpl")

    assert [label.count(b"^XA") for label in labels] == [1, 1]

    assert qrbar.render(ZPL, DATA) == b"".join(labels)


def test_records_with_qty_zero_are_skipped() -> None:
    assert qrbar.render(ZPL, [{**DATA[0], "qty": 0}], mode="per_item") == []


def test_kind_overrides_sniffing() -> None:
    with pytest.raises(qrbar.TemplateError):
        qrbar.render(PAGED, DATA, kind="zpl")


def test_too_many_copies_are_rejected_before_rendering() -> None:
    with pytest.raises(ValidationError, match=r"10001 copies requested, more than max_copies"):
        qrbar.render(b"not rendered", {"qty": 10_001})

    assert qrbar.render(ZPL, {**DATA[0], "qty": 10_001}, max_copies=None).count(b"^XA") == 1


@pytest.mark.parametrize(
    ("template", "kwargs", "message"),
    [
        (PAGED, {"kind": "pdf"}, "Unknown template kind 'pdf'"),
        (PAGED, {"mode": "grid"}, "Unknown mode 'grid'"),
        (PAGED, {"mode": "sheet"}, r"needs sheet=SheetSpec"),
        (PAGED, {"sheet": SheetSpec(8, 3)}, "only apply to mode='sheet'"),
        (PAGED, {"options": SheetOptions()}, "only apply to mode='sheet'"),
        (PAGED, {"mode": "per_item", "collate": "grouped"}, "does not apply to mode='per_item'"),
        (ZPL, {"mode": "sheet", "sheet": SheetSpec(8, 3)}, "ZPL templates have no sheets"),
        (ZPL, {"collate": "interleaved"}, "cannot be interleaved"),
        (ZPL, {"max_copies": 0}, "max_copies must be an integer >= 1"),
    ],
)
def test_bad_arguments(template: bytes, kwargs: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        qrbar.render(template, DATA, **kwargs)
