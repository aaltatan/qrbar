# Installation

qrbar needs Python 3.12 or newer.

=== "pip"

    ```bash
    pip install qrbar
    ```

=== "uv"

    ```bash
    uv add qrbar
    ```

Everything else (Pillow, segno, python-barcode, zxing-cpp, docxtpl, Jinja)
installs as prebuilt wheels; no system libraries.

## Optional parts

| Need | Install |
|------|---------|
| Arabic text in ZPL | `pip install "qrbar[arabic]"` (adds arabic-reshaper and python-bidi) |
| PDF output | [LibreOffice](https://www.libreoffice.org) on the machine (`soffice`); no extra package |

The Arabic font, IBM Plex Sans Arabic, is bundled with qrbar under the SIL
Open Font License 1.1.

## Check it works

```python
import qrbar
from qrbar import symbologies

print(symbologies.names())  # ['aztec', 'code128', 'datamatrix', 'ean13', 'pdf417', 'qr', 'upca']
print(qrbar.render_code("qr", "hello")[:4])  # b'\x89PNG'
```

Next: the [user guide](guide/index.md).
