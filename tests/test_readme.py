"""Run the README's Python examples, in order, and check every `print(x)  # expected`."""

import re
import shutil
from pathlib import Path

import pytest

from qrbar import ConversionError, symbologies
from qrbar.pdf import find_soffice
from qrbar.symbologies import base

ROOT = Path(__file__).parents[1]

FIXTURES = ROOT / "tests" / "fixtures"

BLOCK = re.compile(r"^```(\w+)\n(.*?)^```", re.MULTILINE | re.DOTALL)

PRINT = re.compile(r"^(\s*)print\((.*)\)\s+# (.*)$", re.MULTILINE)

NEEDS = re.compile(r"^# needs: (.+)$", re.MULTILINE)


def blocks(language: str) -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    return [code for lang, code in BLOCK.findall(readme) if lang == language]


def expect(value: object, expected: str) -> None:
    """Compare what the README prints with its comment; `...` ends a prefix."""
    if expected.endswith("..."):
        assert str(value).startswith(expected.removesuffix("..."))

    else:
        assert str(value) == expected


def with_checks(code: str) -> str:
    return PRINT.sub(lambda m: f"{m[1]}_expect({m[2]}, {m[3]!r})", code)


def runnable(code: str) -> bool:
    needs = NEEDS.search(code)

    if needs is None:
        return True

    if needs[1] == "LibreOffice":
        try:
            find_soffice()

        except ConversionError:
            return False

        return True

    return False  # web frameworks, the reader's own font file


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ["label_paged.docx", "sheet_a4_3x8.docx"]:
        shutil.copy(FIXTURES / name, tmp_path / name)

    shutil.copy(FIXTURES / "label_203dpi.zpl", tmp_path / "label.zpl")

    [csv] = blocks("csv")

    (tmp_path / "items.csv").write_text(csv, encoding="utf-8")

    monkeypatch.chdir(tmp_path)

    return tmp_path


def test_readme_has_examples() -> None:
    assert len(blocks("python")) > 20

    assert len(PRINT.findall("\n".join(blocks("python")))) > 10


def test_readme_examples_run(workdir: Path) -> None:
    namespace: dict[str, object] = {"__name__": "readme", "_expect": expect}

    try:
        for code in filter(runnable, blocks("python")):
            exec(compile(with_checks(code), "README.md", "exec"), namespace)  # noqa: S102 - our README

    finally:
        base._registry.pop("code39", None)  # noqa: SLF001 - undo the README's register()

    assert (workdir / "sheet.docx").exists()

    assert "code39" not in symbologies.names()
