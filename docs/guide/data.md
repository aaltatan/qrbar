# Data and quantities

`data` is one dict or a list of dicts (any mappings). A single mapping is a
list of one record. Records are numbered from 0, and errors name that index.

## The quantity field

| Value | Copies |
|-------|--------|
| missing, `None`, `""` | 1 |
| `0` | none, the record is skipped |
| `3`, `3.0`, `"3"`, `" 3 "` | 3 |
| `-1`, `2.5`, `"abc"`, `True` | `QuantityError` naming the record |

Copies are always identical. In docx they become separate labels; in ZPL
each record stays one block with `^PQ{qty}`.

## From a CSV file

```csv
sku,name,url,qty
SKU-1,Lamp,https://example.com/1,3
SKU-2,Desk lamp,https://example.com/2,
SKU-3,Discontinued,https://example.com/3,0
```

```python
import csv
from pathlib import Path

import qrbar

with open("items.csv", newline="", encoding="utf-8") as file:
    rows = list(csv.DictReader(file))  # qty values are strings, and that is fine

docx = qrbar.render(Path("label_paged.docx").read_bytes(), rows)  # 3 + 1 + 0 labels
```

## Another quantity field

```python
orders = [{"sku": "SKU-1", "name": "Lamp", "copies": 4}]

docx = qrbar.render(Path("label_paged.docx").read_bytes(), orders, qty_field="copies")
```

## A copy limit

`max_copies` (default `qrbar.DEFAULT_MAX_COPIES`, 10,000 per call) rejects a
huge quantity, e.g. a typo in a web form, before anything is rendered. Raise
it or pass `max_copies=None` for big trusted jobs:

```python
try:
    qrbar.render(Path("label_paged.docx").read_bytes(), {"sku": "X", "name": "X", "qty": 50_000})
except qrbar.ValidationError as error:
    print(error)  # 50000 copies requested, more than max_copies=10000.
```

## Missing fields

Templates use strict undefined values: `{{ item.typo }}` raises instead of
printing an empty field. In ZPL and `per_item` docx the error is a
`RecordError` with the record's `.index`; see [Exceptions](../reference/exceptions.md).
