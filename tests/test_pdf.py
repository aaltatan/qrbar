"""Docx to PDF: error paths with a fake soffice, a real conversion when LibreOffice is installed."""

import io
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

import qrbar
from qrbar import ConversionError, SheetSpec, ValidationError
from qrbar.pdf import find_soffice

FIXTURES = Path(__file__).parent / "fixtures"

SHEET = (FIXTURES / "sheet_a4_3x8.docx").read_bytes()

FAKE = """
import os, sys, time
from pathlib import Path

args = sys.argv[1:]
outdir, source = Path(args[args.index("--outdir") + 1]), Path(args[-1])
mode = os.environ.get("FAKE_SOFFICE", "ok")

if mode == "fail":
    sys.stderr.write("source file could not be loaded")
    sys.exit(1)

if mode == "slow":
    time.sleep(10)

if mode != "silent":
    (outdir / (source.stem + ".pdf")).write_bytes(b"%PDF-fake " + str(len(source.read_bytes())).encode())
"""


@pytest.fixture
def fake_soffice(tmp_path: Path) -> str:
    """Write a stand-in for soffice that follows the FAKE_SOFFICE environment variable."""
    script = tmp_path / "fake_soffice.py"

    script.write_text(FAKE, encoding="utf-8")

    if sys.platform == "win32":
        launcher = tmp_path / "soffice.cmd"

        launcher.write_text(f'@"{sys.executable}" "{script}" %*\n', encoding="utf-8")

    else:
        launcher = tmp_path / "soffice"

        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')

        launcher.chmod(0o755)

    return str(launcher)


def test_converts_through_soffice(fake_soffice: str) -> None:
    assert qrbar.docx_to_pdf(SHEET, soffice=fake_soffice) == f"%PDF-fake {len(SHEET)}".encode()


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("fail", r"could not convert the document \(exit 1\): source file could not be loaded"),
        ("silent", r"could not convert the document \(exit 0\)"),
    ],
)
def test_failures_raise_conversion_error(
    fake_soffice: str, monkeypatch: pytest.MonkeyPatch, mode: str, message: str
) -> None:
    monkeypatch.setenv("FAKE_SOFFICE", mode)

    with pytest.raises(ConversionError, match=message):
        qrbar.docx_to_pdf(SHEET, soffice=fake_soffice)


def test_timeout_raises_conversion_error(
    fake_soffice: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_SOFFICE", "slow")

    with pytest.raises(ConversionError, match=r"did not finish within 0.5 s"):
        qrbar.docx_to_pdf(SHEET, soffice=fake_soffice, timeout=0.5)


def test_missing_executable_raises_conversion_error(tmp_path: Path) -> None:
    with pytest.raises(ConversionError, match="LibreOffice was not found at"):
        qrbar.docx_to_pdf(SHEET, soffice=str(tmp_path / "nope"))


def test_missing_libreoffice_names_what_to_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("qrbar.pdf.shutil.which", lambda _: None)

    monkeypatch.setattr("qrbar.pdf._DEFAULT_PATHS", ())

    with pytest.raises(ConversionError, match="install it"):
        find_soffice()


@pytest.mark.parametrize("data", [b"not a docx", "text"])
def test_non_docx_input_is_rejected(data: object) -> None:
    with pytest.raises(ValidationError, match=r"needs the bytes of a .docx"):
        qrbar.docx_to_pdf(data)  # type: ignore[arg-type]


def test_bad_timeout_is_rejected() -> None:
    with pytest.raises(ValidationError, match="timeout must be a number > 0"):
        qrbar.docx_to_pdf(SHEET, soffice="unused", timeout=0)


def test_conversion_error_is_not_a_validation_error() -> None:
    assert not issubclass(ConversionError, ValidationError)


def _libreoffice() -> str | None:
    try:
        return find_soffice()

    except ConversionError:
        return None


@pytest.mark.skipif(_libreoffice() is None, reason="LibreOffice is not installed")
def test_rendered_sheet_converts_with_one_page_per_sheet() -> None:
    docx = qrbar.render(
        SHEET, {"url": "u", "name": "N", "qty": 25}, mode="sheet", sheet=SheetSpec(8, 3)
    )

    pdf = qrbar.docx_to_pdf(docx)

    assert len(PdfReader(io.BytesIO(pdf)).pages) == 2
