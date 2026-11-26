# Exceptions

Every error derives from `QrbarError`; data and template problems are also
`ValueError`s. All are importable from `qrbar`.

```text
QrbarError
├── ValidationError (ValueError)    bad data or arguments
│   ├── QuantityError               a record's qty is invalid
│   ├── PayloadError                a code cannot encode its data
│   ├── TemplateError               the template cannot be read or parsed
│   └── RecordError                 rendering one record failed (.index, .error)
├── UnknownSymbologyError (LookupError)
├── SymbologyAlreadyRegisteredError
└── ConversionError                 LibreOffice is missing or failed
```

| Exception | Attributes | Message |
|-----------|------------|---------|
| `QuantityError` | `index`, `value` | `Record 0: invalid quantity -1, ...` |
| `PayloadError` | `symbology`, `payload` | `ean13: invalid payload '12345', must be 12 or 13 digits.` |
| `RecordError` | `index`, `error` (also the `__cause__`) | `Record 1: <the original error>` |
| `UnknownSymbologyError` | | `Unknown symbology 'x'. Available: aztec, code128, ...` |
| `SymbologyAlreadyRegisteredError` | | `Symbology 'qr' is already registered.` |

## Which record broke

`RecordError` tells you which record broke and why, e.g. to point at a row in
an uploaded spreadsheet:

```python
from pathlib import Path

import qrbar

bad = [
    {"url": "u", "sku": "SKU-1", "ean": "400638133393", "name": "Lamp"},
    {"url": "u", "sku": "SKU-2", "ean": "12345", "name": "Shade"},
]

try:
    qrbar.render(Path("label.zpl").read_bytes(), bad)
except qrbar.RecordError as error:
    print(error.index)  # 1
    print(error)  # Record 1: ean13: invalid payload '12345', must be 12 or 13 digits.
```

In docx `sheet` and `paged` modes all records render together, so errors there
do not carry a record index; `per_item` and ZPL do.

## In a web app

Catch `ValidationError` for a 4xx answer (bad upload, data or arguments) and
let `ConversionError` surface as a server problem.
