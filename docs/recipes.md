# Recipes

Short answers to common jobs. The template files are in the repository's
[`tests/fixtures/`](https://github.com/aaltatan/qrbar/tree/main/tests/fixtures).

## Labels from a CSV file

```python
import csv
from pathlib import Path

import qrbar

with open("items.csv", newline="", encoding="utf-8") as file:
    rows = list(csv.DictReader(file))  # qty values are strings, and that is fine

docx = qrbar.render(Path("label_paged.docx").read_bytes(), rows)
```

An empty `qty` cell means one copy, `0` skips the row. See
[Data and quantities](guide/data.md).

## Reuse a partly used A4 sheet

```python
from qrbar import SheetOptions, SheetSpec

docx = qrbar.render(
    Path("sheet_a4_3x8.docx").read_bytes(),
    rows,
    mode="sheet",
    sheet=SheetSpec(rows=8, cols=3),
    options=SheetOptions(skip=7),  # seven stickers already peeled off
)
```

## One file per record

```python
docs = qrbar.render(Path("label_paged.docx").read_bytes(), rows, mode="per_item")

for row, docx in zip(rows, docs, strict=True):
    Path(f"{row['sku']}.docx").write_bytes(docx)
```

With a ZPL template, `mode="per_item"` gives one `^XA ... ^XZ` block per
record, e.g. to send them to different printers.

## A 300 dpi printer

Put `{% set dpi = 300 %}` at the top of the ZPL template, before the first
code. Sizes in mm stay the same.

## Pick the code type per row

```python
row = {"kind": "datamatrix", "code": "SKU-7", "qty": 1}

zpl = qrbar.render(b"^XA^FO20,20{{ barcode(item.kind, item.code, size_mm=12) }}^XZ", row)
```

## Validate a code in a form

```python
from qrbar import PayloadError, symbologies


def clean_ean(value: str) -> str:
    try:
        symbologies.get("ean13").validate(value)
    except PayloadError as error:
        raise ValueError(str(error)) from None

    return value
```

## Point at the bad row of an upload

```python
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

## PDF for printing

```python
# needs: LibreOffice
pdf = qrbar.docx_to_pdf(docx)
```

## FastAPI

qrbar takes bytes and returns bytes, so templates can come from uploads or a
database and results stream straight back.

```python
# needs: fastapi
import json

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import Response

import qrbar

app = FastAPI()


@app.post("/labels")
async def labels(template: UploadFile, items: str = Form()) -> Response:
    """Multipart form: the template file, and the records as a JSON string."""
    try:
        result = qrbar.render(await template.read(), json.loads(items))
    except qrbar.ValidationError as error:  # bad data, template or arguments
        raise HTTPException(422, str(error)) from error

    is_docx = result.startswith(b"PK")
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if is_docx
        else "text/plain"
    )

    return Response(result, media_type=media)
```

## Django

```python
# needs: django
from django.http import HttpResponse

import qrbar

from .models import LabelTemplate, Product


def sheet(request, template_id):
    template = LabelTemplate.objects.get(pk=template_id)
    products = Product.objects.values("sku", "name", "url", "qty")

    docx = qrbar.render(
        template.file.read(),
        list(products),
        mode="sheet",
        sheet=qrbar.SheetSpec(rows=8, cols=3),
        options=qrbar.SheetOptions(skip=int(request.GET.get("skip", 0))),
    )

    response = HttpResponse(
        docx, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    response["Content-Disposition"] = 'attachment; filename="labels.docx"'

    return response
```
