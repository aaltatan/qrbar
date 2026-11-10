"""ZPL renderer for `.zpl` / `.prn` templates: one label block per record.

A template is one label, `^XA ... ^XZ`, with Jinja in it. Each record renders
the template once with `item` set to the record's data. qrbar then inserts
`^CI28` (UTF-8) after the first `^XA` and `^PQ{qty}` before the last `^XZ`, so
a record with qty 3 is one block printed three times.

Codes are native ZPL fields placed after the template's own `^FO`:

    {% set dpi = 300 %}
    ^XA
    ^FO50,50{{ qr(item.url, size_mm=25) }}
    ^FO50,300{{ code128(item.sku, width_mm=40, height_mm=10) }}
    ^XZ

`dpi` (default 203) converts mm to dots; set it before the first code.

`{{ text(item.name, size_mm=3) }}` prints text `size_mm` tall: Latin as a native
`^A0` field, text with Arabic as a `^GF` graphic, since printers cannot shape
Arabic (needs `qrbar[arabic]`).
"""

import re
from collections.abc import Callable, Sequence

import jinja2
from jinja2.runtime import Context
from jinja2.sandbox import ImmutableSandboxedEnvironment

from qrbar import symbologies
from qrbar._checks import require_int, require_positive
from qrbar.arabic import check_font, default_font, has_arabic, rasterize, to_gf
from qrbar.exceptions import PayloadError, QrbarError, RecordError, TemplateError, ValidationError
from qrbar.records import Record
from qrbar.symbologies.base import payload_text, zpl_field

DEFAULT_DPI = 203

MAX_MODULE_DOTS = 10  # the limit of ^BY and ^BQ

DEFAULT_TEXT_MM = 3.0

_MM_PER_INCH = 25.4

_XA = re.compile(r"\^XA", re.IGNORECASE)

_XZ = re.compile(r"\^XZ", re.IGNORECASE)

_PQ = re.compile(r"\^PQ", re.IGNORECASE)

_COMMAND_CHARS = "^~"


class Zpl(str):
    """ZPL produced by qrbar, which the output check lets through unchanged."""

    __slots__ = ()


def render_zpl(
    template: bytes,
    records: Sequence[Record],
    *,
    font: bytes | None = None,
) -> list[bytes]:
    """Render one UTF-8 `^XA ... ^XZ` block per record.

    `font` (TrueType/OpenType bytes) draws Arabic text; default: the bundled font.
    """
    if font is not None:
        check_font(font)

    try:
        compiled = _environment(font).from_string(_decode(template))

    except jinja2.TemplateSyntaxError as error:
        msg = f"ZPL template line {error.lineno}: {error.message}"

        raise TemplateError(msg) from error

    labels: list[bytes] = []

    for record in records:
        try:
            text = compiled.render(item=record.data)

        except (QrbarError, jinja2.TemplateError) as error:
            raise RecordError(record.index, error) from error

        labels.append(_finish_label(text, record.qty).encode())

    return labels


def _decode(template: bytes) -> str:
    try:
        return template.decode("utf-8-sig")

    except UnicodeDecodeError as error:
        msg = f"ZPL template must be UTF-8 text: {error}."

        raise TemplateError(msg) from None


def _environment(font: bytes | None) -> jinja2.Environment:
    # sandboxed: templates may come from uploads, so they must not reach Python internals;
    # no autoescape: output is ZPL, not HTML, see _finalize
    environment = ImmutableSandboxedEnvironment(
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
        trim_blocks=True,
        finalize=_finalize,
    )

    environment.globals["barcode"] = _code

    environment.globals["text"] = _text_function(font)

    for name in symbologies.names():
        environment.globals[name] = _named_code(name)

    return environment


def _finish_label(text: str, qty: int) -> str:
    start = _XA.search(text)

    ends = list(_XZ.finditer(text))

    if start is None or not ends or ends[-1].start() < start.end():
        msg = "ZPL template must contain a label: ^XA ... ^XZ."

        raise TemplateError(msg)

    if _PQ.search(text):
        msg = "ZPL template must not set ^PQ; quantities come from the data."

        raise TemplateError(msg)

    end = ends[-1].start()

    return f"{text[: start.end()]}^CI28{text[start.end() : end]}^PQ{qty}{text[end:]}"


def _finalize(value: object) -> object:
    """Reject plain values that would be read as ZPL commands."""
    if isinstance(value, Zpl):
        return value

    for char in _COMMAND_CHARS:
        if char in str(value):
            msg = f"Value {value!r} contains {char!r}, which ZPL reads as a command."

            raise ValidationError(msg)

    return value


def _named_code(name: str) -> Callable[..., Zpl]:
    @jinja2.pass_context
    def code(
        context: Context,
        data: object,
        *,
        size_mm: float | None = None,
        width_mm: float | None = None,
        height_mm: float | None = None,
    ) -> Zpl:
        return _code(context, name, data, size_mm=size_mm, width_mm=width_mm, height_mm=height_mm)

    return code


@jinja2.pass_context
def _code(  # noqa: PLR0913 - the template-facing keyword options
    context: Context,
    name: str,
    data: object,
    *,
    size_mm: float | None = None,
    width_mm: float | None = None,
    height_mm: float | None = None,
) -> Zpl:
    """Return a native ZPL code field.

    `size_mm` sets width and height (QR codes are square and use the width).
    Without a width the module is about 0.25 mm, the printer default.
    """
    symbology = symbologies.get(name)

    if isinstance(data, jinja2.Undefined):
        str(data)  # StrictUndefined raises here, naming the missing field

    payload = payload_text(name, data)

    dpi = _dpi(context)

    width_mm = size_mm if width_mm is None else width_mm

    height_mm = size_mm if height_mm is None else height_mm

    if width_mm is None:
        module = max(1, round(dpi / 100))

    else:
        modules, _ = symbology.module_size(payload)

        module = _dots("width_mm", width_mm, dpi) // modules

        if module < 1:
            reason = f"{width_mm} mm at {dpi} dpi is too narrow for its {modules} modules"

            raise PayloadError(name, payload, reason)

        module = min(module, MAX_MODULE_DOTS)

    if height_mm is None:
        height = module * symbology.module_size(payload)[1]

    else:
        height = _dots("height_mm", height_mm, dpi)

    return Zpl(symbology.to_zpl(payload, module=module, height=height))


def _text_function(font: bytes | None) -> Callable[..., Zpl]:
    @jinja2.pass_context
    def text(context: Context, value: object, *, size_mm: float = DEFAULT_TEXT_MM) -> Zpl:
        """Return a text field `size_mm` tall: `^A0` for Latin, a `^GF` graphic for Arabic."""
        if isinstance(value, jinja2.Undefined):
            str(value)  # StrictUndefined raises here, naming the missing field

        content = str(value)

        height = _dots("size_mm", size_mm, _dpi(context))

        if has_arabic(content):
            image = rasterize(content, default_font() if font is None else font, height)

            return Zpl(to_gf(image))

        return Zpl(f"^A0N,{height},{height}{zpl_field(content)}")

    return text


def _dpi(context: Context) -> int:
    dpi = context.get("dpi", DEFAULT_DPI)

    require_int("dpi", dpi, 1)

    return int(dpi)


def _dots(name: str, mm: object, dpi: int) -> int:
    return round(require_positive(name, mm) * dpi / _MM_PER_INCH)
