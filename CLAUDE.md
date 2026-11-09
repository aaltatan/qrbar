# qrbar

Domain-only Python package that generates barcodes / QR codes and renders
sticker/label documents from templates (`.docx`, `.zpl`, `.prn`), for single
items and bulk jobs. It is a library: no CLI, no printing, no filesystem I/O
in the core. A separate `qrbar-cli` package (later, not in this repo) and web
projects (Django/FastAPI) will consume it.

## Principles

- **I/O-free core.** Public functions take `bytes` / `dict` / `list[dict]` and
  return `bytes` or `list[bytes]`. Never read or write paths inside `qrbar`.
  Web apps must be able to call it with uploaded bytes and stream the result.
- **The template decides.** Barcode type, size and options are set in the
  template via Jinja filters/globals, not in Python config or in the data.
- **Same template syntax, renderer-aware output.** `{{ qr(item.url, size_mm=25) }}`
  produces an image in docx and a native ZPL command in `.zpl`/`.prn`.
- **Style: follow the author's libraries** pyspecification and pyflowstep
  (github.com/aaltatan): full type hints, dataclasses for domain objects,
  small composable units, explicit errors. Read those repos for conventions
  before introducing new patterns.
- Pure domain logic (validation, quantity expansion, layout) must be testable
  without rendering anything.

## Pipeline

```
data (dict | list[dict]) + template bytes
  -> validate records + quantities
  -> expand quantities (identical copies)
  -> layout (mode + sheet options)
  -> render (renderer chosen by template type)
  -> bytes | list[bytes]
```

## Quantities

- Each record may carry a quantity field. Default field name `qty`,
  configurable.
- Missing -> 1. `0` -> record skipped. Negative, non-integer, or non-numeric
  -> raise a validation error naming the record index and value.
- Copies are always identical (no per-copy serials).
- ZPL/PRN: do NOT duplicate blocks. Emit one `^XA ... ^XZ` block per record
  with `^PQ{qty}`.
- docx/PDF/PNG: expand records into copies before layout.

## Output modes

| Mode | Result |
|------|--------|
| `sheet` | Many stickers per page (label sheets, e.g. A4 3x8) |
| `per_item` | One output per record -> `list[bytes]` |
| `paged` | One document, one sticker per page |

Sheet options (docx/PDF):
- `skip`: start at position N to reuse a partly used sheet (leading empty cells).
- `fill_last`: pad the last sheet with empty cells (`None`).
- `new_page_per_record`: each record's copies start on a fresh sheet.
- `collate`: `grouped` (A,A,A,B,B) or `interleaved` (A,B,A,B,A).

For docx sheets the core pre-chunks items and passes a nested context the
template loops over, e.g. `pages -> rows -> cells`, where a cell is a record
or `None`. Word has no "repeat cell in grid", so chunking lives in Python.

## Symbologies

- Registry of symbology handlers keyed by name (`qr`, `code128`, `ean13`,
  `upca`, `datamatrix`, `pdf417`, `aztec`, ... aim to cover all common types).
- Each handler: validates payload (length, charset, check digit), renders to
  PNG/SVG, and (where supported) emits native ZPL.
- Candidate backends: `segno` (QR/Micro QR), `python-barcode`, `treepoem`
  (BWIPP, broadest coverage, needs Ghostscript). Keep backends behind the
  registry so they are swappable; heavy ones go in extras.
- Arabic / any Unicode payloads are encoded as UTF-8.

## Renderers

- `DocxRenderer`: docxtpl. Code filters return `InlineImage` sized in mm.
- `ZplRenderer` (also `.prn`): plain Jinja text rendering.
  - Codes as native commands (`^BQ`, `^BC`, `^BE`, `^BX`, `^B7`, ...).
  - `^CI28` for UTF-8.
  - Text containing Arabic is rasterized to a `^GF` graphic (shaping + RTL
    done in Python, e.g. arabic-reshaper + python-bidi + Pillow), since
    printers often cannot shape Arabic natively. Latin text stays native `^FD`.
- `ImageRenderer`: standalone PNG/SVG codes, no template.
- PDF: optional extra, converts rendered docx (LibreOffice headless). Keep it
  isolated; it is the only part allowed to touch temp files.

Filters must know which renderer they run in (pass a render context into the
Jinja environment) rather than branching on file extensions inside filters.

## Out of scope (v1)

- `.lbl` / `.nlbl` (NiceLabel / BarTender) files.
- Sending jobs to printers.
- The CLI (`qrbar-cli`, separate package later).
- Per-copy serial numbers.

## Suggested build order

1. Domain model: record, quantity parsing/validation, expansion, collation.
2. Layout: chunking into pages/rows/cells with skip, fill_last,
   new_page_per_record.
3. Symbology registry + 2-3 handlers (QR, Code128, EAN-13) to PNG/SVG.
4. ZPL renderer with native codes and `^PQ`.
5. Docx renderer with InlineImage filters and sheet context.
6. Arabic `^GF` rasterization.
7. Remaining symbologies, PDF extra.

## Tooling

- Python >= 3.12, `uv` for env and builds, `src/` layout (`src/qrbar/`).
- `pytest` for tests, `ruff` for lint/format, a strict type checker
  (`pyright` or `mypy --strict`).
- Tests: unit tests for all pure logic; renderer tests assert on output
  (ZPL text, docx XML, decoded images via a barcode reader where practical).
- Keep fixtures (sample templates, data) under `tests/fixtures/`.

Commands (adjust once the project exists):

```
uv sync
uv run pytest
uv run ruff check . && uv run ruff format .
uv run pyright
```