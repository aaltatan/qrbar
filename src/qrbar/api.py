"""The entry point: template bytes and data in, rendered bytes out."""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any, Literal, overload

from qrbar._checks import require_int
from qrbar.docx import render_docx_paged, render_docx_per_item, render_docx_sheet
from qrbar.exceptions import ValidationError
from qrbar.layout import SheetOptions, SheetSpec
from qrbar.records import DEFAULT_QTY_FIELD, Collate, Record, parse_records
from qrbar.zpl import render_zpl

type Mode = Literal["sheet", "paged", "per_item"]

type TemplateKind = Literal["docx", "zpl"]

type Data = Mapping[str, Any] | Sequence[Mapping[str, Any]]

DEFAULT_MAX_COPIES = 10_000
"""Total copies one call may produce, so untrusted quantities cannot build huge documents."""

_ZIP_MAGIC = b"PK\x03\x04"


@overload
def render(
    template: bytes,
    data: Data,
    *,
    mode: Literal["per_item"],
    kind: TemplateKind | None = None,
    qty_field: str = DEFAULT_QTY_FIELD,
    sheet: None = None,
    options: None = None,
    collate: Collate | None = None,
    max_copies: int | None = DEFAULT_MAX_COPIES,
    font: bytes | None = None,
) -> list[bytes]: ...


@overload
def render(
    template: bytes,
    data: Data,
    *,
    mode: Literal["sheet", "paged"] = "paged",
    kind: TemplateKind | None = None,
    qty_field: str = DEFAULT_QTY_FIELD,
    sheet: SheetSpec | None = None,
    options: SheetOptions | None = None,
    collate: Collate | None = None,
    max_copies: int | None = DEFAULT_MAX_COPIES,
    font: bytes | None = None,
) -> bytes: ...


def render(  # noqa: PLR0913 - the keyword options of the one entry point
    template: bytes,
    data: Data,
    *,
    mode: Mode = "paged",
    kind: TemplateKind | None = None,
    qty_field: str = DEFAULT_QTY_FIELD,
    sheet: SheetSpec | None = None,
    options: SheetOptions | None = None,
    collate: Collate | None = None,
    max_copies: int | None = DEFAULT_MAX_COPIES,
    font: bytes | None = None,
) -> bytes | list[bytes]:
    """Render `data` (one record or a list) with a docx or ZPL template.

    - `paged`: one document, one label per copy (ZPL: the blocks joined).
    - `sheet`: one docx of label sheets; needs `sheet=SheetSpec(rows, cols)`.
    - `per_item`: one output per record, as a list.

    `kind` is sniffed when omitted: a zip is docx, anything else ZPL. `collate`
    orders copies in `paged` and `sheet` (it overrides `options.collate`).
    `font` (TrueType/OpenType bytes) draws Arabic `text()` in ZPL; default: bundled.
    Raises `ValidationError` for bad arguments or data, before rendering.
    """
    kind = _template_kind(template) if kind is None else kind

    _check_arguments(kind, mode, sheet, options, collate)

    if kind == "docx" and font is not None:
        msg = "font only applies to ZPL templates; a docx uses its own fonts."

        raise ValidationError(msg)

    records = parse_records(data, qty_field)

    _check_copies(records, max_copies)

    if kind == "zpl":
        labels = render_zpl(template, records, font=font)

        return labels if mode == "per_item" else b"".join(labels)

    if mode == "per_item":
        return render_docx_per_item(template, records)

    if mode == "paged":
        return render_docx_paged(template, records, collate or "grouped")

    if sheet is None:
        msg = "mode='sheet' needs sheet=SheetSpec(rows, cols)."

        raise ValidationError(msg)

    if collate is not None:
        options = replace(options or SheetOptions(), collate=collate)

    return render_docx_sheet(template, records, sheet, options)


def _template_kind(template: bytes) -> TemplateKind:
    return "docx" if template.startswith(_ZIP_MAGIC) else "zpl"


def _check_arguments(
    kind: str,
    mode: str,
    sheet: SheetSpec | None,
    options: SheetOptions | None,
    collate: Collate | None,
) -> None:
    if kind not in {"docx", "zpl"}:
        msg = f"Unknown template kind {kind!r}, expected 'docx' or 'zpl'."

        raise ValidationError(msg)

    if mode not in {"sheet", "paged", "per_item"}:
        msg = f"Unknown mode {mode!r}, expected 'sheet', 'paged' or 'per_item'."

        raise ValidationError(msg)

    if mode != "sheet" and (sheet is not None or options is not None):
        msg = f"sheet and options only apply to mode='sheet', not {mode!r}."

        raise ValidationError(msg)

    if kind == "zpl" and mode == "sheet":
        msg = "ZPL templates have no sheets; use mode='paged' or 'per_item'."

        raise ValidationError(msg)

    if kind == "zpl" and collate not in {None, "grouped"}:
        msg = "ZPL prints copies with ^PQ, so they cannot be interleaved."

        raise ValidationError(msg)

    if collate is not None and mode == "per_item":
        msg = "collate does not apply to mode='per_item'."

        raise ValidationError(msg)


def _check_copies(records: Sequence[Record], max_copies: int | None) -> None:
    if max_copies is None:
        return

    require_int("max_copies", max_copies, 1)

    total = sum(record.qty for record in records)

    if total > max_copies:
        msg = f"{total} copies requested, more than max_copies={max_copies}."

        raise ValidationError(msg)
