"""Generate barcodes and QR codes and render sticker and label documents from templates."""

from qrbar.api import DEFAULT_MAX_COPIES, Mode, TemplateKind, render
from qrbar.exceptions import (
    ConversionError,
    PayloadError,
    QrbarError,
    QuantityError,
    RecordError,
    SymbologyAlreadyRegisteredError,
    TemplateError,
    UnknownSymbologyError,
    ValidationError,
)
from qrbar.image import ImageFormat, render_code
from qrbar.layout import SheetOptions, SheetSpec
from qrbar.pdf import docx_to_pdf
from qrbar.records import Collate

__all__ = [
    "DEFAULT_MAX_COPIES",
    "Collate",
    "ConversionError",
    "ImageFormat",
    "Mode",
    "PayloadError",
    "QrbarError",
    "QuantityError",
    "RecordError",
    "SheetOptions",
    "SheetSpec",
    "SymbologyAlreadyRegisteredError",
    "TemplateError",
    "TemplateKind",
    "UnknownSymbologyError",
    "ValidationError",
    "docx_to_pdf",
    "render",
    "render_code",
]
