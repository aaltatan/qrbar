"""Docx to PDF with LibreOffice headless.

The only part of qrbar that writes temp files and runs a process; the rest of
the package stays I/O-free. Needs LibreOffice installed (`soffice` on PATH or
in its default install folder); no Python packages.
"""

import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from qrbar._checks import require_positive
from qrbar.exceptions import ConversionError, ValidationError

DEFAULT_TIMEOUT = 120.0
"""Seconds to wait for LibreOffice; a cold start can take a while."""

_NAMES = ("soffice", "libreoffice")

_DEFAULT_PATHS = (
    Path("C:/Program Files/LibreOffice/program/soffice.exe"),
    Path.home() / "scoop/apps/libreoffice/current/LibreOffice/program/soffice.exe",  # no PATH shim
    Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
)

_ZIP_MAGIC = b"PK\x03\x04"


def docx_to_pdf(
    docx: bytes,
    *,
    soffice: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> bytes:
    """Convert a docx (e.g. from `render`) to PDF bytes.

    `soffice` is the LibreOffice executable; by default it is looked up on PATH
    and in the default install folders. Raises `ConversionError` when
    LibreOffice is missing, fails or times out.
    """
    if not isinstance(docx, bytes) or not docx.startswith(_ZIP_MAGIC):
        msg = "docx_to_pdf needs the bytes of a .docx file."

        raise ValidationError(msg)

    require_positive("timeout", timeout)

    executable = find_soffice() if soffice is None else soffice

    # a killed LibreOffice can keep files open on Windows for a moment
    with tempfile.TemporaryDirectory(prefix="qrbar-", ignore_cleanup_errors=True) as folder:
        work = Path(folder)

        source = work / "document.docx"

        source.write_bytes(docx)

        command = [
            executable,
            # a private profile per call, so parallel conversions do not share a lock
            f"-env:UserInstallation={(work / 'profile').as_uri()}",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(work),
            str(source),
        ]

        log = work / "soffice.log"

        code = _run(command, executable, log, timeout)

        target = work / "document.pdf"

        if code != 0 or not target.is_file():
            output = log.read_text(errors="replace").strip()

            msg = f"LibreOffice could not convert the document (exit {code}): {output}"

            raise ConversionError(msg)

        return target.read_bytes()


def find_soffice() -> str:
    """Return the LibreOffice executable, or raise `ConversionError` naming what to install."""
    for name in _NAMES:
        found = shutil.which(name)

        if found:
            return found

    for path in _DEFAULT_PATHS:
        if path.is_file():
            return str(path)

    msg = (
        "LibreOffice is needed for PDF output but was not found: install it "
        "(https://www.libreoffice.org) or pass soffice='/path/to/soffice'."
    )

    raise ConversionError(msg)


def _run(command: list[str], executable: str, log: Path, timeout: float) -> int:
    """Run `command` with its output in `log`; return the exit code.

    Output goes to a file, not a pipe: soffice starts a child (soffice.bin) that
    would hold a pipe open after a timeout. On timeout the whole tree is killed.
    """
    with log.open("wb") as output:
        try:
            process = subprocess.Popen(  # noqa: S603 - fixed arguments, no shell
                command,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        except FileNotFoundError:
            msg = f"LibreOffice was not found at {executable!r}."

            raise ConversionError(msg) from None

        try:
            return process.wait(timeout)

        except subprocess.TimeoutExpired:
            _kill_tree(process)

            msg = f"LibreOffice did not finish within {timeout} s."

            raise ConversionError(msg) from None


def _kill_tree(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603 - fixed arguments, no shell
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],  # noqa: S607 - a Windows system tool
            capture_output=True,
            check=False,
        )

    else:
        os.killpg(process.pid, signal.SIGKILL)

    process.wait()
