import io
import xml.etree.ElementTree as ET

import pytest
import zxingcpp
from PIL import Image

from qrbar import symbologies
from qrbar.exceptions import (
    PayloadError,
    SymbologyAlreadyRegisteredError,
    UnknownSymbologyError,
    ValidationError,
)
from qrbar.image import render_code
from qrbar.symbologies.linear import ean13_check_digit
from qrbar.symbologies.qr import QrSymbology


def decode(png: bytes) -> list[tuple[str, str]]:
    """Return (format, text) for every barcode found in a PNG."""
    image = Image.open(io.BytesIO(png))

    return [(result.format.name, result.text) for result in zxingcpp.read_barcodes(image)]


@pytest.mark.parametrize(
    ("name", "payload", "expected"),
    [
        ("qr", "https://example.com/item/42", ("QRCode", "https://example.com/item/42")),
        ("qr", "12345", ("QRCode", "12345")),
        ("qr", "مصباح LED 12W", ("QRCode", "مصباح LED 12W")),
        ("code128", "SKU-00042/a", ("Code128", "SKU-00042/a")),
        ("code128", "0123456789", ("Code128", "0123456789")),
        ("ean13", "400638133393", ("EAN13", "4006381333931")),
        ("ean13", "4006381333931", ("EAN13", "4006381333931")),
        # UPC-A bars are EAN-13 with a leading 0, and zxing-cpp reports them as such
        ("upca", "03600029145", ("EAN13", "0036000291452")),
        ("upca", "036000291452", ("EAN13", "0036000291452")),
        ("datamatrix", "SKU-42 ~_^", ("DataMatrix", "SKU-42 ~_^")),
        ("datamatrix", "مصباح LED 12W", ("DataMatrix", "مصباح LED 12W")),
        ("pdf417", "https://example.com/item/42", ("PDF417", "https://example.com/item/42")),
        ("pdf417", "مصباح LED 12W", ("PDF417", "مصباح LED 12W")),
        ("aztec", "https://example.com/item/42", ("Aztec", "https://example.com/item/42")),
        ("aztec", "مصباح LED 12W", ("Aztec", "مصباح LED 12W")),
    ],
)
def test_png_round_trips_through_a_decoder(
    name: str, payload: str, expected: tuple[str, str]
) -> None:
    assert decode(render_code(name, payload)) == [expected]


@pytest.mark.parametrize("scale", range(1, 9))
def test_qr_scale_sets_pixels_per_module(scale: int) -> None:
    qr = Image.open(io.BytesIO(render_code("qr", "hi", scale=scale)))

    assert qr.size == ((21 + 2 * 4) * scale,) * 2  # version 1 QR + 4-module border


@pytest.mark.parametrize("scale", range(1, 9))
@pytest.mark.parametrize(
    ("name", "payload"), [("code128", "SKU-1"), ("ean13", "400638133393"), ("upca", "03600029145")]
)
def test_linear_bars_are_exactly_scale_pixels_per_module(
    name: str, payload: str, scale: int
) -> None:
    symbology = symbologies.get(name)

    image = Image.open(io.BytesIO(symbology.to_png(payload, scale=scale))).convert("L")

    row = "".join("1" if image.getpixel((x, 0)) == 0 else "0" for x in range(image.width))

    quiet = "0" * (symbology.quiet_modules * scale)  # type: ignore[attr-defined]

    pattern = symbology.modules(payload)  # type: ignore[attr-defined]

    assert row == quiet + "".join(m * scale for m in pattern) + quiet

    assert payload in decode(symbology.to_png(payload, scale=scale))[0][1]


@pytest.mark.parametrize(
    "name", ["qr", "code128", "ean13", "upca", "datamatrix", "pdf417", "aztec"]
)
def test_svg_is_an_svg_document(name: str) -> None:
    payload = {"ean13": "400638133393", "upca": "03600029145"}.get(name, "hello")

    root = ET.fromstring(render_code(name, payload, "svg"))  # noqa: S314 - our own output

    assert root.tag == "{http://www.w3.org/2000/svg}svg"


@pytest.mark.parametrize(
    ("name", "payload", "reason"),
    [
        ("qr", "", "must not be empty"),
        ("qr", 42, "must be a string, not int"),
        ("qr", "x" * 3000, "too long for a QR code"),
        ("code128", "مصباح", "only ASCII"),
        ("ean13", "12345", "must be 12 or 13 digits"),
        ("ean13", "40063813339A", "must be 12 or 13 digits"),
        ("ean13", "٤٠٠٦٣٨١٣٣٣٩٣", "must be 12 or 13 digits"),  # Arabic-Indic digits
        ("ean13", "4006381333932", "wrong check digit, expected 1"),
        ("upca", "0360002914", "must be 11 or 12 digits"),
        ("upca", "036000291453", "wrong check digit, expected 2"),
        ("datamatrix", "", "must not be empty"),
        ("datamatrix", "x" * 3200, "too long"),
        ("pdf417", "x" * 3000, "too long"),
        ("aztec", "x" * 4000, "too long"),
    ],
)
def test_invalid_payloads_raise_payload_error(name: str, payload: object, reason: str) -> None:
    symbology = symbologies.get(name)

    with pytest.raises(PayloadError, match=reason) as exc_info:
        symbology.validate(payload)  # type: ignore[arg-type]

    assert exc_info.value.symbology == name

    assert exc_info.value.payload == payload

    with pytest.raises(PayloadError):
        symbology.to_png(payload)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("data", "check"), [("400638133393", 1), ("590123412345", 7), ("000000000000", 0)]
)
def test_ean13_check_digit(data: str, check: int) -> None:
    assert ean13_check_digit(data) == check


@pytest.mark.parametrize("scale", [0, -1, True, 1.5])
def test_bad_scale_is_rejected(scale: object) -> None:
    with pytest.raises(ValidationError, match="scale must be an integer >= 1"):
        render_code("qr", "hi", scale=scale)  # type: ignore[arg-type]


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Unknown image format 'gif'"):
        render_code("qr", "hi", "gif")  # type: ignore[arg-type]


def test_registry_lists_built_in_names() -> None:
    assert symbologies.names() == [
        "aztec",
        "code128",
        "datamatrix",
        "ean13",
        "pdf417",
        "qr",
        "upca",
    ]


def test_unknown_symbology_lists_available_names() -> None:
    with pytest.raises(
        UnknownSymbologyError,
        match=r"Unknown symbology 'qrr'. Available: aztec, code128, datamatrix, ean13, pdf417, qr, upca",
    ):
        symbologies.get("qrr")


def test_register_refuses_duplicates_unless_replacing() -> None:
    original = symbologies.get("qr")

    with pytest.raises(SymbologyAlreadyRegisteredError, match="'qr' is already registered"):
        symbologies.register(QrSymbology())

    replacement = QrSymbology()

    try:
        symbologies.register(replacement, replace=True)

        assert symbologies.get("qr") is replacement

    finally:
        symbologies.register(original, replace=True)


@pytest.mark.parametrize(
    ("name", "scale"), [(n, s) for n in ["datamatrix", "pdf417", "aztec"] for s in (1, 3)]
)
def test_matrix_png_is_scale_pixels_per_module(name: str, scale: int) -> None:
    symbology = symbologies.get(name)

    width, height = symbology.module_size("hello world")

    cropped = Image.open(io.BytesIO(symbology.to_png("hello world", scale=scale, quiet_zone=False)))

    assert cropped.size == (width * scale, height * scale)

    padded = Image.open(io.BytesIO(symbology.to_png("hello world", scale=scale)))

    assert padded.width >= cropped.width  # Aztec needs no quiet zone, so gets none


def test_datamatrix_is_square() -> None:
    width, height = symbologies.get("datamatrix").module_size("a longer payload, 32 characters")

    assert width == height
