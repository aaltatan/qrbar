# ZPL labels

A ZPL template is **one label**, `^XA ... ^XZ`, with Jinja in it. Each record
renders it once as `item`. Positions (`^FO`) and fonts stay in your template;
qrbar fills in the codes. This is
[`tests/fixtures/label_203dpi.zpl`](https://github.com/aaltatan/qrbar/blob/main/tests/fixtures/label_203dpi.zpl):

```text
{% set dpi = 203 %}
^XA
^FO50,50{{ qr(item.url, size_mm=25) }}
^FO50,300{{ code128(item.sku, width_mm=40, height_mm=10) }}
^FO50,450{{ ean13(item.ean) }}
^FO50,600^A0N,30,30^FD{{ item.name }}^FS
^XZ
```

```python
from pathlib import Path

import qrbar

template = Path("label.zpl").read_bytes()

items = [
    {
        "url": "https://example.com/1",
        "sku": "SKU-1",
        "ean": "400638133393",
        "name": "Lamp",
        "qty": 3,
    },
    {"url": "https://example.com/2", "sku": "SKU-2", "ean": "590123412345", "name": "Desk lamp"},
]

zpl = qrbar.render(template, items)

Path("labels.zpl").write_bytes(zpl)
print(zpl.decode().splitlines()[0:3])
# ['^XA^CI28', '^FO50,50^BQN,2,8^FH_^FDMA,https://example.com/1^FS', '^FO50,300^BY3^BCN,80,N,N,N,A^FH_^FDSKU-1^FS']
```

`.prn` files are the same thing: pass their bytes, or `kind="zpl"` to skip
sniffing.

## What qrbar adds and checks

- `^CI28` after `^XA` (UTF-8) and `^PQ{qty}` before `^XZ`: the first record
  above is **one block printed 3 times**, not three blocks. Do not put `^PQ`
  in the template.
- Sizes in mm become dots using `dpi` (set it before the first code;
  default 203). For a 300 dpi printer: `{% set dpi = 300 %}`.
- Code payloads are hex-escaped (`^FH`), so `^`, `~` and `_` in data are safe.
- A plain `{{ item.name }}` containing `^` or `~` is rejected
  (`ValidationError`), so data cannot inject ZPL commands. Use
  `{{ text(item.name) }}` for text that may contain them.
- A missing field (`item.typo`) raises an error naming the record, instead
  of printing an empty field.
- Templates run in a sandboxed Jinja environment, so an uploaded template
  cannot reach Python internals.

## Code sizes

Code functions take `size_mm` (width and height), `width_mm` and `height_mm`.
Square codes (`qr`, `datamatrix`, `aztec`) use the width.

- Without a width, a module is about 0.25 mm (`dpi / 100` dots, at least 1).
- With a width, the module is whole dots (1 to 10, the limit of `^BY` and
  `^BQ`), so the printed width is the largest that fits. A width too narrow
  for one dot per module raises `PayloadError`.
- Without a height, linear codes are 50 modules tall.

## One block per record

`mode="per_item"` returns a list, e.g. to send records to different printers
or store them separately:

```python
blocks = qrbar.render(template, items, mode="per_item")

for index, block in enumerate(blocks):
    Path(f"label-{index}.zpl").write_bytes(block)
```

`mode="sheet"` does not apply to ZPL and raises `ValidationError`, as do
`collate=` and `sheet=`.

## Any code by name

`barcode(name, data, ...)` picks the type from data or a variable:

```python
row = {"kind": "datamatrix", "code": "SKU-7", "qty": 1}

zpl = qrbar.render(b"^XA^FO20,20{{ barcode(item.kind, item.code, size_mm=12) }}^XZ", row)
print(zpl.decode())  # ^XA^CI28^FO20,20^BXN,8,200^FH_^FDSKU-7^FS^PQ1^XZ
```

Integers work as payloads too: `{{ ean13(item.ean) }}` with `"ean": 400638133393`.

## Native commands

| Function | ZPL |
|----------|-----|
| `qr` | `^BQ` |
| `code128` | `^BC` |
| `ean13` | `^BE` |
| `upca` | `^BU` |
| `datamatrix` | `^BX` |
| `pdf417` | `^B7` |
| `aztec` | `^BO` |
| `text` | `^A0`, or `^GF` for Arabic ([next page](arabic.md)) |
