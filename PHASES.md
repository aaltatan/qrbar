# qrbar build phases

Each phase ends in a working, tested, type-checked state. Do them in order;
a phase only depends on the ones before it. Track status in
[PROGRESS.md](PROGRESS.md). Design rules live in [CLAUDE.md](CLAUDE.md).

Every phase is done only when:

```
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy --strict src tests
```

all pass.

---

## Phase 0 - Project setup

**Goal:** a clean library skeleton with the tooling wired up.

- Remove `[project.scripts]` and `main()` (qrbar has no CLI).
- Fill in `description` in `pyproject.toml`.
- Add dev deps: `pytest`. Keep `ruff` and `mypy` (already present).
- Configure ruff (rules, line length) and `mypy --strict` in `pyproject.toml`.
- Add `src/qrbar/py.typed`.
- Add `src/qrbar/exceptions.py`: `QrbarError` base, `ValidationError(QrbarError, ValueError)`.
- Create `tests/` and `tests/fixtures/`, one smoke test (`import qrbar`).

**Done when:** the three commands above pass on an empty package.

---

## Phase 1 - Domain model

**Goal:** turn raw input into validated, expanded items. Pure Python, no deps.

- `Record` dataclass: `index: int`, `data: dict[str, Any]`, `qty: int`.
- `parse_records(data: dict | list[dict], qty_field: str = "qty") -> list[Record]`
  - single `dict` is treated as a list of one.
  - qty missing -> 1, `0` -> record dropped.
  - negative, non-integer, non-numeric -> `QuantityError(ValidationError)`
    carrying `index` and `value`, with a message naming both.
- `expand(records) -> list[Record]` (identical copies).
- `collate(records, mode: Collate) -> list[Record]`, `Collate` = `grouped` |
  `interleaved` (enum or `Literal`).

**Decide:** is `True` a valid qty (Python `bool` is an `int`)? Are numeric
strings like `"3"` accepted (common from CSV/forms)? Is `2.0` an integer?

**Done when:** unit tests cover every qty rule, both collation orders, and the
error message contents.

---

## Phase 2 - Layout

**Goal:** arrange items for output modes. Pure, no rendering.

- `SheetSpec(rows: int, cols: int)` and `SheetOptions(skip, fill_last,
  new_page_per_record, collate)`.
- `layout_sheet(records, spec, options) -> list[Page]` where
  `Page = list[Row]`, `Row = list[Cell]`, `Cell = Record | None`.
  - `skip=N`: N leading `None` cells on the first page.
  - `fill_last`: pad the last page with `None`.
  - `new_page_per_record`: each source record's copies start on a new page.
- Validate options (`skip` within page size, positive rows/cols).

**Done when:** tests cover skip, fill_last, new_page_per_record, collate, and
their combinations (e.g. skip + new_page_per_record).

---

## Phase 3 - Symbology registry

**Goal:** a swappable registry of barcode handlers, rendering to PNG/SVG.

- `Symbology` protocol: `name`, `validate(payload) -> None`,
  `to_png(payload, **opts) -> bytes`, `to_svg(payload, **opts) -> bytes`,
  (`to_zpl` is added in phase 4).
- `PayloadError(ValidationError)` carries `symbology` and `payload`.
- Registry: `register()`, `get(name)`, `UnknownSymbologyError`.
- Handlers: `qr` (segno), `code128` and `ean13` (python-barcode encodes, qrbar draws
  the PNG so bars are exact pixels).
  - EAN-13: accept 12 digits (compute check) or 13 (verify check).
  - Payloads are UTF-8 (test an Arabic QR payload).
- `ImageRenderer`: `render_code(name, payload, fmt="png"|"svg", ...) -> bytes`.
- Test dep: `zxing-cpp` (+ Pillow) to decode generated images.

**Done when:** each handler round-trips through the decoder, and invalid
payloads raise `ValidationError` with a clear message.

---

## Phase 4 - ZPL renderer

**Goal:** `.zpl` / `.prn` templates rendered with native ZPL codes.

- Each renderer builds its own Jinja environment with its own code globals, so
  globals know their target without a shared `RenderContext` or file extensions.
- Add `to_zpl(payload, ...) -> str` to the `Symbology` protocol.
- Jinja globals/filters: `qr(...)`, `code128(...)`, `ean13(...)`,
  `barcode(name, ...)`; they call the symbology's `to_zpl`.
- One `^XA ... ^XZ` block per record with `^PQ{qty}`; `^CI28` for UTF-8.
- mm -> dots conversion from dpi.
- `render_zpl(template, records) -> list[bytes]`, one block per record; phase 6
  joins them (or not, for `per_item`).

**Decide:** does the template contain `^XA`/`^XZ` itself, with the renderer
injecting `^PQ` and `^CI28`, or does the renderer wrap the template body?
Where does `dpi` come from (template global vs render argument)?

**Done when:** tests assert exact ZPL text for single, bulk and qty cases.

---

## Phase 5 - Docx renderer

**Goal:** `.docx` templates via docxtpl, codes as `InlineImage` in mm.

- Same Jinja globals as Phase 4, returning `InlineImage(tpl, png, width=Mm(..))`.
  Sizes are the code without its quiet zone, as in ZPL.
- `render_docx_sheet` / `render_docx_paged` / `render_docx_per_item`, context:
  - `sheet`: `pages -> rows -> cells` from Phase 2 (cells are item dicts or `None`).
  - `paged`: `items`, every copy; one document, the template breaks pages.
  - `per_item`: one document per record with `item` and `items` (its copies).
- Fixtures: an A4 3x8 sheet template and a 60x40 mm paged label, built by
  `tests/fixtures/make_docx_fixtures.py`.

**Done when:** tests open the output docx and assert on `word/document.xml`
(cell count, text, image count), and an embedded code decodes.

---

## Phase 6 - Public API

**Goal:** one entry point consumers (CLI, Django, FastAPI) call.

- `Mode` = `sheet` | `per_item` | `paged` (moved here from phase 2).
- `render(template: bytes, data, *, mode="paged", kind=None, qty_field="qty",
  sheet=None, options=None, collate=None, max_copies=10_000) -> bytes | list[bytes]`
  (built: default mode changed from `sheet`, plus `collate` and `max_copies`;
  see the phase 6 decisions in PROGRESS.md).
- ZPL: join `render_zpl` blocks unless `per_item`.
- Docx: dispatch `mode` to the three `render_docx_*` functions.
- Template kind from `kind` or sniffed (`PK\x03\x04` zip -> docx, else text ->
  zpl).
- Export the public names from `qrbar/__init__.py`; everything else private.

**Done when:** end-to-end tests run the full pipeline from bytes in to bytes
out for both template kinds.

---

## Phase 7 - Arabic text in ZPL

**Goal:** Arabic text prints correctly on printers that cannot shape it.

- `text(value, ...)` filter: Latin -> native `^FD`; contains Arabic ->
  shaped (arabic-reshaper), RTL-ordered (python-bidi), drawn with Pillow,
  emitted as `^GF` graphic.
- Optional extra: `qrbar[arabic]`.

**Decide:** font source. The core cannot read paths, so either the caller
passes font bytes, or a bundled OFL font (e.g. Noto Naskh Arabic) ships as
package data. *Decided:* both; IBM Plex Sans Arabic is bundled (it covers
Latin too) and `render(font=...)` overrides it.

**Done when:** tests assert `^GF` output for Arabic, `^FD` for Latin, and the
rasterized image matches a fixture.

---

## Phase 8 - More symbologies

**Goal:** cover the common types.

- `upca`, `datamatrix`, `pdf417`, `aztec`, then others as needed.
- Native ZPL where it exists (`^BU`, `^BX`, `^B7`, `^BO`); `^GF` raster
  fallback otherwise.
- Heavy backends (e.g. `treepoem`, needs Ghostscript) behind an extra.
  *Built:* zxing-cpp in core covers all four natively; no `^GF` fallback or
  heavy extra was needed yet.

**Done when:** each new handler has validation tests and a decode round-trip.

---

## Phase 9 - PDF extra

**Goal:** `qrbar[pdf]` converts rendered docx to PDF.

- LibreOffice headless; the only module allowed to use temp files.
- Clear error when LibreOffice is not installed.
- Tests skipped when LibreOffice is missing.

**Done when:** a rendered sheet docx converts to a PDF with the right page
count.

---

## Phase 10 - Release

- README with install, extras, and template examples for docx and ZPL.
- CI (GitHub Actions): tests, ruff, mypy on 3.12+.
- Build with `uv build`, publish to PyPI.
