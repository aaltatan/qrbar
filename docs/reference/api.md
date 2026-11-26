# API

## Rendering

### `render`

```py
render(
    template: bytes,                     # .docx or ZPL bytes
    data: Mapping | Sequence[Mapping],   # one record or many
    *,
    mode: Mode = "paged",                # "paged" | "sheet" | "per_item"
    kind: TemplateKind | None = None,    # "docx" | "zpl"; None sniffs (zip = docx)
    qty_field: str = "qty",
    sheet: SheetSpec | None = None,      # required for "sheet"
    options: SheetOptions | None = None, # "sheet" only
    collate: Collate | None = None,      # "grouped" | "interleaved"; docx "paged"/"sheet"
    max_copies: int | None = DEFAULT_MAX_COPIES,  # None turns the limit off
    font: bytes | None = None,           # TTF/OTF bytes for Arabic text(), ZPL only
) -> bytes | list[bytes]                 # list[bytes] for "per_item"
```

Render one record or a list with a docx or ZPL template.

| Mode | docx | ZPL |
|------|------|-----|
| `paged` | One document, one label per copy | All blocks joined |
| `sheet` | One document of label sheets | Not available |
| `per_item` | One document per record | One block per record |

`collate` overrides `options.collate` in `sheet` mode. Options that do not
apply raise `ValidationError` instead of being ignored:

- `sheet=` or `options=` with a mode other than `sheet`
- `mode="sheet"` with ZPL, or without `sheet=`
- `collate="interleaved"` with ZPL (copies print with `^PQ`)
- `collate=` with `per_item`
- `font=` with docx

Raises: `ValidationError` (and its subclasses `QuantityError`,
`TemplateError`, `PayloadError`, `RecordError`), `UnknownSymbologyError`.

Guide: [ZPL labels](../guide/zpl.md), [Word templates](../guide/docx.md),
[Label sheets](../guide/sheets.md), [Data and quantities](../guide/data.md).

### `render_code`

```py
render_code(
    name: str,
    payload: str,
    fmt: ImageFormat = "png",
    *,
    scale: int = 4,
) -> bytes
```

One code as PNG or SVG bytes. `scale` is PNG pixels per module.
Raises `UnknownSymbologyError`, `PayloadError`, and `ValidationError` for an
unknown `fmt`.

Guide: [Barcode images](../guide/images.md).

### `docx_to_pdf`

```py
docx_to_pdf(
    docx: bytes,
    *,
    soffice: str | None = None,  # LibreOffice executable; default: PATH, then install folders
    timeout: float = 120.0,
) -> bytes
```

Convert a docx to PDF with headless LibreOffice. Raises `ValidationError` for
input that is not docx bytes or a non-positive `timeout`, and
`ConversionError` when LibreOffice is missing, fails or times out.

Guide: [PDF](../guide/pdf.md).

### `DEFAULT_MAX_COPIES`

```py
DEFAULT_MAX_COPIES = 10_000
```

Total copies one `render` call may produce.

## Sheets

### `SheetSpec`

```py
@dataclass(frozen=True, slots=True)
class SheetSpec:
    rows: int
    cols: int
```

The grid of one label sheet, e.g. `SheetSpec(rows=8, cols=3)` for A4 3x8.
`rows` and `cols` must be integers of at least 1 (`ValidationError`).
`spec.size` is `rows * cols`.

### `SheetOptions`

```py
@dataclass(frozen=True, slots=True)
class SheetOptions:
    skip: int = 0
    fill_last: bool = False
    new_page_per_record: bool = False
    collate: Collate = "grouped"
```

| Field | Meaning |
|-------|---------|
| `skip` | Leading empty cells on the first sheet; at least 0 and less than `SheetSpec.size` |
| `fill_last` | Pad incomplete sheets to their full size with `None` cells |
| `new_page_per_record` | Each record's copies start on a fresh sheet |
| `collate` | Copy order: `grouped` (A, A, B) or `interleaved` (A, B, A) |

`new_page_per_record=True` with `collate="interleaved"` raises `ValidationError`.

## Type aliases

```py
type Mode = Literal["sheet", "paged", "per_item"]
type TemplateKind = Literal["docx", "zpl"]
type Collate = Literal["grouped", "interleaved"]
type ImageFormat = Literal["png", "svg"]
```

## The `symbologies` registry

```py
from qrbar import symbologies
```

| Name | Description |
|------|-------------|
| `register(symbology, *, replace=False)` | Add a handler under its `name`; a taken name raises `SymbologyAlreadyRegisteredError` unless `replace=True` |
| `get(name) -> Symbology` | The handler for `name`; raises `UnknownSymbologyError` |
| `names() -> list[str]` | Registered names, sorted |
| `Symbology` | The handler protocol: `name`, `validate`, `to_png`, `to_svg`, `module_size`, `to_zpl` |
| `DEFAULT_SCALE` | `4`, PNG pixels per module |

Built in: `aztec`, `code128`, `datamatrix`, `ean13`, `pdf417`, `qr`, `upca`.

Guide: [Custom code types](../guide/custom-symbologies.md).

## Lower-level helpers

Used in the [sheet layout example](../guide/sheets.md#what-the-template-receives),
for testing what a template will receive:

| Name | Description |
|------|-------------|
| `qrbar.records.parse_records(data, qty_field="qty") -> list[Record]` | Validate records and read quantities, dropping qty 0 |
| `qrbar.records.Record` | Frozen dataclass: `index`, `data`, `qty` |
| `qrbar.layout.layout_sheet(records, spec, options=None) -> list[Page]` | Expand copies and lay them out as pages of rows of `Record` or `None` |
