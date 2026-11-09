from typing import Any

import pytest

from qrbar.exceptions import ValidationError
from qrbar.layout import Page, SheetOptions, SheetSpec, layout_sheet
from qrbar.records import Record

A = Record(index=0, data={"sku": "A"}, qty=3)
B = Record(index=1, data={"sku": "B"}, qty=2)

GRID_2X2 = SheetSpec(rows=2, cols=2)


def names(pages: list[Page]) -> list[list[list[str | None]]]:
    """Show each cell as its sku, or None, for readable assertions."""
    return [
        [[cell.data["sku"] if cell else None for cell in row] for row in page] for page in pages
    ]


def test_fills_pages_in_order_and_completes_last_row() -> None:
    assert names(layout_sheet([A, B], GRID_2X2)) == [
        [["A", "A"], ["A", "B"]],
        [["B", None]],
    ]


def test_skip_leaves_leading_empty_cells_on_first_page_only() -> None:
    pages = layout_sheet([A, B], GRID_2X2, SheetOptions(skip=3))

    assert names(pages) == [
        [[None, None], [None, "A"]],
        [["A", "A"], ["B", "B"]],
    ]


def test_fill_last_pads_last_page() -> None:
    pages = layout_sheet([A], GRID_2X2, SheetOptions(fill_last=True))

    assert names(pages) == [[["A", "A"], ["A", None]]]

    pages = layout_sheet(
        [Record(index=0, data={"sku": "A"}, qty=1)], GRID_2X2, SheetOptions(fill_last=True)
    )

    assert names(pages) == [[["A", None], [None, None]]]


def test_new_page_per_record() -> None:
    pages = layout_sheet([A, B], GRID_2X2, SheetOptions(new_page_per_record=True))

    assert names(pages) == [
        [["A", "A"], ["A", None]],
        [["B", "B"]],
    ]


def test_new_page_per_record_with_fill_last_pads_every_record_end() -> None:
    options = SheetOptions(new_page_per_record=True, fill_last=True)

    assert names(layout_sheet([A, B], GRID_2X2, options)) == [
        [["A", "A"], ["A", None]],
        [["B", "B"], [None, None]],
    ]


def test_skip_with_new_page_per_record_applies_to_first_record_only() -> None:
    options = SheetOptions(skip=2, new_page_per_record=True)

    assert names(layout_sheet([A, B], GRID_2X2, options)) == [
        [[None, None], ["A", "A"]],
        [["A", None]],
        [["B", "B"]],
    ]


def test_interleaved_collate() -> None:
    pages = layout_sheet([A, B], SheetSpec(rows=1, cols=5), SheetOptions(collate="interleaved"))

    assert names(pages) == [[["A", "B", "A", "B", "A"]]]


def test_no_records_gives_no_pages() -> None:
    assert layout_sheet([], GRID_2X2, SheetOptions(skip=1, fill_last=True)) == []


def test_skip_must_fit_on_a_sheet() -> None:
    with pytest.raises(ValidationError, match="less than the 4 cells"):
        layout_sheet([A], GRID_2X2, SheetOptions(skip=4))


@pytest.mark.parametrize(("rows", "cols"), [(0, 3), (3, 0), (-1, 3), (True, 3), (2.0, 3)])
def test_sheet_spec_rejects_bad_grid(rows: Any, cols: Any) -> None:
    with pytest.raises(ValidationError, match="must be an integer >= 1"):
        SheetSpec(rows=rows, cols=cols)


@pytest.mark.parametrize("skip", [-1, True, 1.5])
def test_options_reject_bad_skip(skip: Any) -> None:
    with pytest.raises(ValidationError, match="skip must be an integer >= 0"):
        SheetOptions(skip=skip)


def test_options_reject_unknown_collate() -> None:
    with pytest.raises(ValidationError, match="Unknown collate mode 'zigzag'"):
        SheetOptions(collate="zigzag")  # type: ignore[arg-type]


def test_options_reject_interleaved_new_page_per_record() -> None:
    with pytest.raises(ValidationError, match="cannot be interleaved"):
        SheetOptions(new_page_per_record=True, collate="interleaved")
