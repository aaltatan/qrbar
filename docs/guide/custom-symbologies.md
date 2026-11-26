# Custom code types

A code type is any object with the `qrbar.symbologies.Symbology` protocol:

| Member | Does |
|--------|------|
| `name` | The name used in `render_code` and as the template function |
| `validate(payload)` | Raise `PayloadError` for a payload it cannot encode |
| `to_png(payload, *, scale=4, quiet_zone=True)` | PNG bytes, `scale` px per module; `quiet_zone=False` crops the white margin |
| `to_svg(payload)` | SVG bytes |
| `module_size(payload)` | `(width, height)` in modules, without the quiet zone; linear codes report their default bar height |
| `to_zpl(payload, *, module, height)` | One native ZPL field without `^FO`; `module` and `height` are in dots |

Register it and it works in `render_code` and in every template. Templates
created after registering see it as a function of the same name. A Code 39
built on zxing-cpp (installed with qrbar):

```python
import io
from pathlib import Path

import zxingcpp
from PIL import Image

import qrbar
from qrbar import PayloadError, symbologies


class Code39:
    name = "code39"

    def _make(self, payload: str) -> zxingcpp.Barcode:
        try:
            return zxingcpp.create_barcode(payload, zxingcpp.BarcodeFormat.Code39)
        except ValueError as error:
            raise PayloadError(self.name, payload, str(error)) from None

    def validate(self, payload: str) -> None:
        self._make(payload)

    def to_png(self, payload: str, *, scale: int = 4, quiet_zone: bool = True) -> bytes:
        view = memoryview(self._make(payload).to_image(scale=scale, add_quiet_zones=quiet_zone))
        height, width = view.shape or (0, 0)
        buffer = io.BytesIO()
        Image.frombytes("L", (width, height), view.tobytes()).save(buffer, "PNG")
        return buffer.getvalue()

    def to_svg(self, payload: str) -> bytes:
        return self._make(payload).to_svg().encode()

    def module_size(self, payload: str) -> tuple[int, int]:
        height, width = memoryview(self._make(payload).to_image(add_quiet_zones=False)).shape or (
            0,
            0,
        )
        return width, height

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:
        self.validate(payload)
        return f"^BY{module}^B3N,N,{height},N,N^FD{payload}^FS"


symbologies.register(Code39())

Path("code39.png").write_bytes(qrbar.render_code("code39", "LAMP-12W"))

zpl = qrbar.render(b"^XA^FO20,20{{ code39(item.sku, height_mm=10) }}^XZ", {"sku": "LAMP-12W"})
print(zpl.decode())  # ^XA^CI28^FO20,20^BY2^B3N,N,80,N,N^FDLAMP-12W^FS^PQ1^XZ
```

## Replacing a built-in

Registering a name twice raises `SymbologyAlreadyRegisteredError`.
`register(..., replace=True)` swaps out a built-in handler, e.g. to change
the QR error correction level.

!!! note
    The registry is process-wide: a handler registered once is used by every
    later `render` and `render_code` call.
