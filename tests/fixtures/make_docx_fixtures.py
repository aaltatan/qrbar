"""Build the docx template fixtures: `uv run python tests/fixtures/make_docx_fixtures.py`.

The generated files are committed; they double as example templates to open in Word.
"""

from pathlib import Path

from docx import Document
from docx.document import Document as DocumentObject
from docx.enum.table import WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_BREAK, WD_LINE_SPACING
from docx.shared import Mm, Pt
from docx.text.paragraph import Paragraph

HERE = Path(__file__).parent


def page_setup(document: DocumentObject, width: float, height: float, margin: float) -> None:
    section = document.sections[0]

    section.page_width, section.page_height = Mm(width), Mm(height)

    section.top_margin = section.bottom_margin = Mm(margin)

    section.left_margin = section.right_margin = Mm(margin)


def tiny(paragraph: Paragraph) -> Paragraph:
    """Make a paragraph 1 pt tall, so it fits below a sheet that fills the page."""
    paragraph.paragraph_format.space_before = paragraph.paragraph_format.space_after = Pt(0)

    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY

    paragraph.paragraph_format.line_spacing = Pt(1)

    for run in paragraph.runs:
        run.font.size = Pt(1)

    return paragraph


def page_break_between(document: DocumentObject) -> None:
    """Add a page break after every loop pass except the last."""
    document.add_paragraph("{%p if not loop.last %}")

    tiny(document.add_paragraph()).add_run().add_break(WD_BREAK.PAGE)

    document.add_paragraph("{%p endif %}")


def sheet_a4_3x8() -> DocumentObject:
    """A4 sheet of 3 x 8 stickers, 70 x 37 mm, a QR code and a name in each."""
    document = Document()

    page_setup(document, 210, 297, 0)

    document.add_paragraph("{%p for page in pages %}")

    table = document.add_table(rows=3, cols=3)

    table.rows[0].cells[0].text = "{%tr for row in page %}"

    table.rows[2].cells[0].text = "{%tr endfor %}"

    sticker = table.rows[1]

    sticker.height, sticker.height_rule = Mm(37), WD_ROW_HEIGHT_RULE.EXACTLY

    for i, cell in enumerate(sticker.cells):
        cell.width = Mm(70)

        code = f"{{{{ qr(row[{i}].url, size_mm=20) }}}}"

        cell.paragraphs[0].text = f"{{% if row[{i}] %}}{code}{{% endif %}}"

        cell.add_paragraph(f"{{% if row[{i}] %}}{{{{ row[{i}].name }}}}{{% endif %}}")

    page_break_between(document)

    document.add_paragraph("{%p endfor %}")

    tiny(document.add_paragraph())  # Word needs a paragraph after the last table

    return document


def label_paged() -> DocumentObject:
    """One 60 x 40 mm label per page: a Code 128 and a name."""
    document = Document()

    page_setup(document, 60, 40, 3)

    document.add_paragraph("{%p for item in items %}")

    document.add_paragraph("{{ code128(item.sku, width_mm=50, height_mm=12) }}")

    document.add_paragraph("{{ item.name }}")

    page_break_between(document)

    document.add_paragraph("{%p endfor %}")

    return document


if __name__ == "__main__":
    sheet_a4_3x8().save(str(HERE / "sheet_a4_3x8.docx"))

    label_paged().save(str(HERE / "label_paged.docx"))
