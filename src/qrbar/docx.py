"""Docx renderer: docxtpl templates with codes as inline images sized in mm.

The template functions match the ZPL ones, `{{ qr(item.url, size_mm=25) }}`,
and sizes mean the same: the code itself, without its white margin (quiet
zone), so the template must leave space around a code.

What the template loops over depends on the mode:

- sheet: `pages -> rows -> cells`, a cell is an item or `None` (empty position),
  every row is as wide as the sheet.
- paged: `items`, every copy in order; the template starts a page per item.
- per item: one document per record, with `item` and `items` (its copies).

Data values are XML-escaped (autoescape), so `&` or `<` cannot break the file.
"""

import io
import math
import zipfile
from collections.abc import Sequence
from functools import partial
from typing import Any

import jinja2
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage

from qrbar import symbologies
from qrbar._checks import require_positive
from qrbar.exceptions import QrbarError, RecordError, TemplateError
from qrbar.layout import SheetOptions, SheetSpec, layout_sheet
from qrbar.records import Collate, Record, collate
from qrbar.symbologies.base import payload_text

DEFAULT_MODULE_MM = 0.25
"""Module width without a size, matching ZPL's default of about 2 dots at 203 dpi."""

IMAGE_DPI = 600
"""Minimum PNG resolution at the printed size, so Word scaling keeps edges sharp."""

_MM_PER_INCH = 25.4


def render_docx_sheet(
    template: bytes,
    records: Sequence[Record],
    spec: SheetSpec,
    options: SheetOptions | None = None,
) -> bytes:
    """Render one document of label sheets; the template loops over `pages`."""
    pages = [
        [[cell.data if cell else None for cell in row] for row in page]
        for page in layout_sheet(records, spec, options)
    ]

    return _render(template, {"pages": pages})


def render_docx_paged(
    template: bytes,
    records: Sequence[Record],
    order: Collate = "grouped",
) -> bytes:
    """Render one document; the template loops over `items`, one page each."""
    return _render(template, {"items": [record.data for record in collate(records, order)]})


def render_docx_per_item(template: bytes, records: Sequence[Record]) -> list[bytes]:
    """Render one document per record, with `item` and `items` (its qty copies)."""
    return [
        _render(template, {"item": record.data, "items": [record.data] * record.qty}, record)
        for record in records
    ]


def _render(template: bytes, context: dict[str, Any], record: Record | None = None) -> bytes:
    """Render a fresh copy of the template; errors name `record` when there is one."""
    document = _open(template)

    try:
        document.render(context, jinja_env=_environment(document), autoescape=True)

    except jinja2.TemplateSyntaxError as error:
        msg = f"Docx template: {error.message}"

        raise TemplateError(msg) from error

    except (QrbarError, jinja2.TemplateError) as error:
        if record is not None:
            raise RecordError(record.index, error) from error

        if isinstance(error, QrbarError):
            raise

        raise TemplateError(str(error)) from error

    buffer = io.BytesIO()

    document.save(buffer)

    return buffer.getvalue()


def _open(template: bytes) -> DocxTemplate:
    document = DocxTemplate(io.BytesIO(template))

    try:
        document.init_docx()

    except (zipfile.BadZipFile, KeyError, ValueError) as error:
        msg = f"Docx template is not a valid .docx file: {error}"

        raise TemplateError(msg) from None

    return document


def _environment(document: DocxTemplate) -> jinja2.Environment:
    environment = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=True)

    environment.globals["barcode"] = partial(_code, document)

    for name in symbologies.names():
        environment.globals[name] = partial(_code, document, name)

    return environment


def _code(  # noqa: PLR0913 - the template-facing keyword options
    document: DocxTemplate,
    name: str,
    data: object,
    *,
    size_mm: float | None = None,
    width_mm: float | None = None,
    height_mm: float | None = None,
) -> InlineImage:
    """Return the code as an image; `size_mm` sets width and height.

    Without a height the image keeps the code's own ratio (linear codes are 50
    modules tall).
    """
    symbology = symbologies.get(name)

    if isinstance(data, jinja2.Undefined):
        str(data)  # StrictUndefined raises here, naming the missing field

    payload = payload_text(name, data)

    width_mm = size_mm if width_mm is None else width_mm

    height_mm = size_mm if height_mm is None else height_mm

    modules, _ = symbology.module_size(payload)

    if width_mm is None:
        width = modules * DEFAULT_MODULE_MM

    else:
        width = require_positive("width_mm", width_mm)

    scale = max(1, math.ceil(width / modules * IMAGE_DPI / _MM_PER_INCH))

    png = symbology.to_png(payload, scale=scale, quiet_zone=False)

    height = None if height_mm is None else Mm(require_positive("height_mm", height_mm))

    return InlineImage(document, io.BytesIO(png), width=Mm(width), height=height)
