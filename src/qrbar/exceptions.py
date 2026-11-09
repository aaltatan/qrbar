"""Exceptions raised by qrbar.

Every exception derives from `QrbarError`, so callers can catch the whole
family at once. Validation errors also derive from `ValueError`, to stay
compatible with code that expects the built-in exception type.
"""


class QrbarError(Exception):
    """Base class for every exception raised by qrbar."""


class ValidationError(QrbarError, ValueError):
    """Raised when input data, a payload, or an option is invalid."""


class QuantityError(ValidationError):
    """Raised when a record's quantity is negative, fractional, or not a number."""

    def __init__(self, index: int, value: object, reason: str) -> None:
        self.index = index

        self.value = value

        super().__init__(f"Record {index}: invalid quantity {value!r}, {reason}.")


class PayloadError(ValidationError):
    """Raised when a payload cannot be encoded by a symbology."""

    def __init__(self, symbology: str, payload: object, reason: str) -> None:
        self.symbology = symbology

        self.payload = payload

        super().__init__(f"{symbology}: invalid payload {payload!r}, {reason}.")


class ConversionError(QrbarError):
    """Raised when an external converter (LibreOffice) is missing or fails; not a data problem."""


class TemplateError(ValidationError):
    """Raised when a template cannot be read, parsed, or produces an invalid document."""


class RecordError(ValidationError):
    """Raised when rendering one record fails; the original error is `error` (and the cause)."""

    def __init__(self, index: int, error: Exception) -> None:
        self.index = index

        self.error = error

        super().__init__(f"Record {index}: {error}")


class UnknownSymbologyError(QrbarError, LookupError):
    """Raised when no symbology is registered under a name."""

    def __init__(self, name: str, available: list[str]) -> None:
        super().__init__(f"Unknown symbology {name!r}. Available: {', '.join(available)}.")


class SymbologyAlreadyRegisteredError(QrbarError):
    """Raised when a symbology name is registered twice without `replace=True`."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Symbology {name!r} is already registered.")
