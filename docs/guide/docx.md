# Word (docx) templates

Write the template in Word with the same functions; codes become inline
images sized in mm. The template sees your data with
[docxtpl](https://docxtpl.readthedocs.io) syntax (`{%p ... %}` for whole
paragraphs, `{%tr ... %}` for table rows).

Sizes are the **code itself**, without its white margin: leave a few mm of
space around each code. Values from your data are XML-escaped, so `&` and `<`
are safe. Templates run in a sandboxed Jinja environment.

## One label per page (`paged`, the default)

[`tests/fixtures/label_paged.docx`](https://github.com/aaltatan/qrbar/blob/main/tests/fixtures/label_paged.docx)
is a 60 x 40 mm page containing:

```text
{%p for item in items %}
{{ code128(item.sku, width_mm=50, height_mm=12) }}
{{ item.name }}
{%p if not loop.last %}
<page break>
{%p endif %}
{%p endfor %}
```

The template receives `items`: one entry per copy.

```python
from pathlib import Path

import qrbar

labels = [
    {"sku": "SKU-1", "name": "Lamp", "qty": 2},
    {"sku": "SKU-2", "name": "Desk lamp & shade"},
]

docx = qrbar.render(Path("label_paged.docx").read_bytes(), labels)  # 3 pages: SKU-1, SKU-1, SKU-2

Path("labels.docx").write_bytes(docx)
```

Copies come grouped (A, A, B). `collate="interleaved"` gives A, B, A, e.g.
to hand out one of each first:

```python
docx = qrbar.render(Path("label_paged.docx").read_bytes(), labels, collate="interleaved")
```

## One document per record (`per_item`)

```python
docs = qrbar.render(Path("label_paged.docx").read_bytes(), labels, mode="per_item")

for record, docx in zip(labels, docs, strict=True):
    Path(f"{record['sku']}.docx").write_bytes(docx)
```

Each document sees `item` (the record) and `items` (its copies), so the same
template works in both modes. `collate=` does not apply to `per_item` and
raises `ValidationError`.

## Sizes in docx

| Call | Size |
|------|------|
| `{{ qr(item.url) }}` | 0.25 mm per module (a 25-module QR is 6.25 mm) |
| `{{ qr(item.url, size_mm=20) }}` | 20 x 20 mm |
| `{{ code128(item.sku, width_mm=50) }}` | 50 mm wide, keeps its ratio |
| `{{ code128(item.sku, width_mm=50, height_mm=12) }}` | 50 x 12 mm |

Images are drawn at 600 dpi or more for their printed size, so they stay
sharp when Word prints them.

`barcode(name, data, ...)` works here too. `text()` is ZPL only; in Word,
just write `{{ item.name }}` and pick the font in Word.

For many labels on one page, see [Label sheets](sheets.md).
