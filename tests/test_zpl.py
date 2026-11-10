from pathlib import Path
from typing import Any

import pytest

from qrbar.exceptions import PayloadError, RecordError, TemplateError, ValidationError
from qrbar.records import parse_records
from qrbar.zpl import render_zpl

LABEL = (Path(__file__).parent / "fixtures" / "label_203dpi.zpl").read_bytes()

LAMP = {
    "url": "https://example.com/1",
    "sku": "SKU-1",
    "ean": "400638133393",
    "name": "Lamp",
}


def render(template: str | bytes, data: Any) -> list[str]:
    raw = template.encode() if isinstance(template, str) else template

    return [label.decode() for label in render_zpl(raw, parse_records(data))]


def test_label_fixture_renders_native_codes() -> None:
    expected = (
        "^XA^CI28\n"
        "^FO50,50^BQN,2,8^FH_^FDMA,https://example.com/1^FS\n"  # 200 dots / 25 modules
        "^FO50,300^BY3^BCN,80,N,N,N,A^FH_^FDSKU-1^FS\n"  # 320 dots / 90 modules
        "^FO50,450^BY2^BEN,100,N,N^FH_^FD400638133393^FS\n"  # default module, 50 tall
        "^FO50,600^A0N,30,30^FDLamp^FS\n"
        "^PQ3^XZ\n"
    )

    assert render(LABEL, {**LAMP, "qty": 3}) == [expected]


def test_one_block_per_record_with_its_qty_and_zero_skipped() -> None:
    template = "^XA^FO0,0^FD{{ item.name }}^FS^XZ"

    data = [{"name": "A", "qty": 2}, {"name": "B", "qty": 0}, {"name": "C"}]

    assert render(template, data) == [
        "^XA^CI28^FO0,0^FDA^FS^PQ2^XZ",
        "^XA^CI28^FO0,0^FDC^FS^PQ1^XZ",
    ]


def test_dpi_from_template_converts_mm() -> None:
    template = "{% set dpi = 300 %}^XA{{ qr('hi', size_mm=10) }}{{ code128('A') }}^XZ"

    # 10 mm at 300 dpi = 118 dots over 21 modules -> 5; default module round(300 / 100) = 3
    assert render(template, {}) == [
        "^XA^CI28^BQN,2,5^FH_^FDMA,hi^FS^BY3^BCN,150,N,N,N,A^FH_^FDA^FS^PQ1^XZ"
    ]


def test_module_is_capped_at_10_dots() -> None:
    assert render("^XA{{ qr('hi', size_mm=100) }}^XZ", {}) == [
        "^XA^CI28^BQN,2,10^FH_^FDMA,hi^FS^PQ1^XZ"
    ]


def test_generic_barcode_global_and_int_payloads() -> None:
    template = "^XA{{ barcode('code128', item.id, height_mm=5) }}{{ qr(item.id) }}^XZ"

    assert render(template, {"id": 42}) == [
        "^XA^CI28^BY2^BCN,40,N,N,N,A^FH_^FD42^FS^BQN,2,2^FH_^FDMA,42^FS^PQ1^XZ"
    ]


def test_code_payloads_escape_zpl_command_characters() -> None:
    assert render("^XA{{ code128(item.sku) }}^XZ", {"sku": "A_^~B"}) == [
        "^XA^CI28^BY2^BCN,100,N,N,N,A^FH_^FDA_5F_5E_7EB^FS^PQ1^XZ"
    ]


def test_utf8_output_for_arabic_payloads() -> None:
    [label] = render_zpl(b"^XA{{ qr(item.name) }}^XZ", parse_records({"name": "مصباح"}))

    assert "MA,مصباح".encode() in label


def test_lowercase_commands_are_recognised() -> None:
    assert render("^xa^FDx^FS^xz", {}) == ["^xa^CI28^FDx^FS^PQ1^xz"]


@pytest.mark.parametrize("value", ["A^XZ^XA^PQ9999", "~JR"])
def test_plain_values_with_command_characters_are_rejected(value: str) -> None:
    with pytest.raises(
        RecordError, match=r"^Record 1: Value .* which ZPL reads as a command"
    ) as info:
        render("^XA^FD{{ item.name }}^FS^XZ", [{"name": "ok"}, {"name": value}])

    assert info.value.index == 1

    assert isinstance(info.value.error, ValidationError)


def test_missing_field_names_the_record() -> None:
    with pytest.raises(RecordError, match=r"^Record 0: 'dict object' has no attribute 'url'"):
        render("^XA{{ qr(item.url) }}^XZ", {})


@pytest.mark.parametrize(
    ("call", "error_type", "message"),
    [
        ("qr(item.flag)", PayloadError, "must be a string, not bool"),
        ("ean13('123')", PayloadError, "must be 12 or 13 digits"),
        ("code128('A' * 40, width_mm=5)", PayloadError, "5 mm at 203 dpi is too narrow"),
        ("qr('x', size_mm=0)", ValidationError, "width_mm must be a number > 0"),
        ("qr('x', size_mm='big')", ValidationError, "width_mm must be a number > 0"),
        ("barcode('nope', 'x')", Exception, "Unknown symbology 'nope'"),
    ],
)
def test_code_errors_are_wrapped_with_the_record(
    call: str, error_type: type[Exception], message: str
) -> None:
    with pytest.raises(RecordError, match=message) as info:
        render(f"^XA{{{{ {call} }}}}^XZ", {"flag": True})

    assert isinstance(info.value.error, error_type)


def test_bad_dpi_is_rejected() -> None:
    with pytest.raises(RecordError, match="dpi must be an integer >= 1"):
        render("{% set dpi = '300' %}^XA{{ qr('x') }}^XZ", {})


@pytest.mark.parametrize(
    ("template", "message"),
    [
        ("^FDx^FS", r"must contain a label: \^XA \.\.\. \^XZ"),
        ("^XZ^XA", r"must contain a label"),
        ("^XA^PQ2^XZ", r"must not set \^PQ"),
        ("^XA{{ item.name ^XZ", "line 1:"),
    ],
)
def test_invalid_templates_raise_template_error(template: str, message: str) -> None:
    with pytest.raises(TemplateError, match=message):
        render(template, {"name": "x"})


def test_non_utf8_template_is_rejected() -> None:
    with pytest.raises(TemplateError, match="must be UTF-8 text"):
        render_zpl(b"^XA\xff^XZ", parse_records({}))


@pytest.mark.parametrize(
    ("call", "field"),
    [
        ("upca(item.upc)", "^BY2^BUN,100,N,N,N^FH_^FD03600029145^FS"),
        # ^BX reads `~` as an escape, so a literal one is sent as ~d126 (hex-escaped by ^FH)
        ("datamatrix(item.text)", "^BXN,2,200^FH_^FDA_7Ed126B_5F_5E^FS"),
        ("datamatrix(item.text, size_mm=10)", "^BXN,6,200^FH_^FDA_7Ed126B_5F_5E^FS"),
        ("aztec(item.text)", "^BON,2,N,0^FH_^FDA_7EB_5F_5E^FS"),
        # 'hello world' is 2 columns x 8 rows at security level 2: 103 x 24 modules
        ("pdf417(item.words)", "^BY2^B7N,6,2,2,8^FH_^FDhello world^FS"),
        ("pdf417(item.words, width_mm=40, height_mm=10)", "^BY3^B7N,10,2,2,8^FH_^FDhello world^FS"),
    ],
)
def test_more_symbologies_render_native_commands(call: str, field: str) -> None:
    data = {"upc": "03600029145", "text": "A~B_^", "words": "hello world"}

    assert render(f"^XA{{{{ {call} }}}}^XZ", data) == [f"^XA^CI28{field}^PQ1^XZ"]


@pytest.mark.parametrize(
    "expression", ["cycler.__init__.__globals__", "item.__class__.__mro__", "qr.__globals__"]
)
def test_templates_cannot_reach_python_internals(expression: str) -> None:
    with pytest.raises(RecordError, match="unsafe"):
        render(f"^XA{{{{ {expression} }}}}^XZ", {"name": "x"})
