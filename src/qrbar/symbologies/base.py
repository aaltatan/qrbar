"""The symbology protocol and the registry of handlers, keyed by name."""

from typing import Protocol

from qrbar.exceptions import PayloadError, SymbologyAlreadyRegisteredError, UnknownSymbologyError

DEFAULT_SCALE = 4
"""PNG pixels per module (the narrowest bar, or one QR square)."""


class Symbology(Protocol):
    """A barcode type: validates payloads and renders them.

    Every method raises `PayloadError` for a payload it cannot encode.
    """

    @property
    def name(self) -> str: ...

    def validate(self, payload: str) -> None: ...

    def to_png(self, payload: str, *, scale: int = DEFAULT_SCALE, quiet_zone: bool = True) -> bytes:
        """Return a PNG, `scale` px per module; `quiet_zone=False` crops the white margin."""
        ...

    def to_svg(self, payload: str) -> bytes: ...

    def module_size(self, payload: str) -> tuple[int, int]:
        """Return (width, height) in modules, without the quiet zone.

        Linear codes report their default bar height, `BAR_HEIGHT_MODULES`.
        """
        ...

    def to_zpl(self, payload: str, *, module: int, height: int) -> str:
        """Return native ZPL for one field (without `^FO`).

        `module` is the module width and `height` the symbol height, both in dots;
        square codes ignore `height`.
        """
        ...


_registry: dict[str, Symbology] = {}


def register(symbology: Symbology, *, replace: bool = False) -> None:
    """Add a handler under its name; `replace=True` swaps out an existing one."""
    if symbology.name in _registry and not replace:
        raise SymbologyAlreadyRegisteredError(symbology.name)

    _registry[symbology.name] = symbology


def get(name: str) -> Symbology:
    """Return the handler registered under `name`."""
    try:
        return _registry[name]

    except KeyError:
        raise UnknownSymbologyError(name, sorted(_registry)) from None


def names() -> list[str]:
    """Return the registered symbology names, sorted."""
    return sorted(_registry)


def payload_text(symbology: str, value: object) -> str:
    """Turn a template value into a payload: ints become strings, other non-strings raise."""
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)

    return require_text(symbology, value)


_ZPL_HEX_ESCAPED = "_^~"  # `_` is the ^FH hex indicator, `^` and `~` start ZPL commands


def zpl_field(data: str) -> str:
    """Return `^FH_^FD{data}^FS`, hex-escaping characters ZPL would read as commands."""
    escaped = "".join(f"_{ord(c):02X}" if c in _ZPL_HEX_ESCAPED else c for c in data)

    return f"^FH_^FD{escaped}^FS"


def require_text(symbology: str, payload: object) -> str:
    """Return `payload` if it is a non-empty string, else raise `PayloadError`."""
    if not isinstance(payload, str):
        raise PayloadError(symbology, payload, f"must be a string, not {type(payload).__name__}")

    if not payload:
        raise PayloadError(symbology, payload, "must not be empty")

    return payload
