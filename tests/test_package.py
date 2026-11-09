import qrbar
from qrbar import QrbarError, ValidationError


def test_public_names_are_exported() -> None:
    assert set(qrbar.__all__) == {
        "DEFAULT_MAX_COPIES",
        "Collate",
        "ConversionError",
        "docx_to_pdf",
        "ImageFormat",
        "Mode",
        "SheetOptions",
        "SheetSpec",
        "TemplateKind",
        "render",
        "render_code",
        "PayloadError",
        "QrbarError",
        "QuantityError",
        "RecordError",
        "SymbologyAlreadyRegisteredError",
        "TemplateError",
        "UnknownSymbologyError",
        "ValidationError",
    }


def test_validation_error_is_caught_as_qrbar_and_value_error() -> None:
    assert issubclass(ValidationError, QrbarError)

    assert issubclass(ValidationError, ValueError)
