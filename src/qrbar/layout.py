"""Sheet layout: chunk record copies into pages of rows of cells.

A cell is a `Record` or `None` (an empty position). Docx templates loop over
`pages -> rows -> cells`, since Word cannot repeat a cell across a grid.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import get_args

from qrbar._checks import require_int
from qrbar.exceptions import ValidationError
from qrbar.records import Collate, Record, collate, expand

type Cell = Record | None
type Row = list[Cell]
type Page = list[Row]


@dataclass(frozen=True, slots=True)
class SheetSpec:
    """Grid of one label sheet, e.g. `SheetSpec(rows=8, cols=3)` for A4 3x8."""

    rows: int
    cols: int

    def __post_init__(self) -> None:
        require_int("rows", self.rows, 1)

        require_int("cols", self.cols, 1)

    @property
    def size(self) -> int:
        return self.rows * self.cols


@dataclass(frozen=True, slots=True)
class SheetOptions:
    """How copies are placed on sheets.

    - `skip`: leading empty cells on the first sheet, to reuse a partly used one.
    - `fill_last`: pad every incomplete sheet to its full size with empty cells.
    - `new_page_per_record`: each record's copies start on a fresh sheet.
    - `collate`: copy order, `grouped` (A, A, B) or `interleaved` (A, B, A).
    """

    skip: int = 0
    fill_last: bool = False
    new_page_per_record: bool = False
    collate: Collate = "grouped"

    def __post_init__(self) -> None:
        require_int("skip", self.skip, 0)

        if self.collate not in get_args(Collate.__value__):
            msg = f"Unknown collate mode {self.collate!r}, expected 'grouped' or 'interleaved'."

            raise ValidationError(msg)

        if self.new_page_per_record and self.collate == "interleaved":
            msg = "new_page_per_record keeps a record's copies together, it cannot be interleaved."

            raise ValidationError(msg)


def layout_sheet(
    records: Sequence[Record],
    spec: SheetSpec,
    options: SheetOptions | None = None,
) -> list[Page]:
    """Expand records into copies and lay them out on sheets.

    Rows are always `spec.cols` cells wide; the last row of a sheet is padded
    with `None`. No records gives no pages.
    """
    options = options or SheetOptions()

    if options.skip >= spec.size:
        msg = f"skip must be less than the {spec.size} cells on a sheet, got {options.skip}."

        raise ValidationError(msg)

    if not records:
        return []

    if options.new_page_per_record:
        groups = [expand([record]) for record in records]

    else:
        groups = [collate(records, options.collate)]

    pages: list[Page] = []

    for number, group in enumerate(groups):
        lead: list[Cell] = [None] * options.skip if number == 0 else []

        pages.extend(_paginate([*lead, *group], spec, fill=options.fill_last))

    return pages


def _paginate(cells: list[Cell], spec: SheetSpec, *, fill: bool) -> list[Page]:
    pages: list[Page] = []

    for start in range(0, len(cells), spec.size):
        chunk = cells[start : start + spec.size]

        missing = spec.size - len(chunk) if fill else -len(chunk) % spec.cols

        chunk.extend([None] * missing)

        pages.append([chunk[i : i + spec.cols] for i in range(0, len(chunk), spec.cols)])

    return pages
