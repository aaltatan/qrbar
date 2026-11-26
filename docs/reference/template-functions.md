# Template functions

Every template, docx or ZPL, can call these. Templates run in a sandboxed
Jinja environment with strict undefined values: a missing field raises.

| Function | docx | ZPL |
|----------|------|-----|
| `qr(data, ...)` | Image | `^BQ` |
| `code128(data, ...)` | Image | `^BC` |
| `ean13(data, ...)` | Image | `^BE` |
| `upca(data, ...)` | Image | `^BU` |
| `datamatrix(data, ...)` | Image | `^BX` |
| `pdf417(data, ...)` | Image | `^B7` |
| `aztec(data, ...)` | Image | `^BO` |
| `barcode(name, data, ...)` | Any of the above by name | Any of the above by name |
| `text(value, size_mm=3)` | Not available | `^A0`, or `^GF` for Arabic |

A [registered custom code type](../guide/custom-symbologies.md) adds a
function of its own name.

## Code options

```text
code(data, *, size_mm=None, width_mm=None, height_mm=None)
```

- `data`: a non-empty string, or an integer (turned into a string).
- `size_mm` sets width and height; `width_mm` / `height_mm` override it.
- Square codes (`qr`, `datamatrix`, `aztec`) use the width.
- Without a width, a module is about 0.25 mm.
- Without a height, linear codes are 50 modules tall (docx keeps the image
  ratio).
- In ZPL the module is whole dots (1 to 10), so the printed width is the
  largest that fits.

## `text`

```text
text(value, *, size_mm=3)
```

ZPL only. `size_mm` is the font height. Text with Arabic letters is shaped
and drawn as a `^GF` graphic (needs `qrbar[arabic]`); other text is an `^A0`
field with `^`, `~` and `_` escaped. See [Arabic text in ZPL](../guide/arabic.md).

## `dpi` (ZPL)

```text
{% set dpi = 300 %}
```

Printer resolution used to turn mm into dots; default 203. Set it before the
first code.

## Template variables

| Mode | docx | ZPL |
|------|------|-----|
| `paged` | `items`: one entry per copy | `item`, once per record |
| `per_item` | `item` (the record) and `items` (its copies) | `item`, once per record |
| `sheet` | `pages`: pages of rows of cells, a cell is a record or `None` | Not available |
