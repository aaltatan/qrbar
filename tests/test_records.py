from typing import Any

import pytest

from qrbar.exceptions import QuantityError, ValidationError
from qrbar.records import Record, collate, expand, parse_quantity, parse_records


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 1),
        ("", 1),
        ("  ", 1),
        (0, 0),
        (3, 3),
        (2.0, 2),
        ("3", 3),
        (" 3 ", 3),
        ("2.0", 2),
        ("٣", 3),  # Arabic-Indic digit
    ],
)
def test_parse_quantity_accepts(value: object, expected: int) -> None:
    assert parse_quantity(value, 0) == expected


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        (True, "not a bool"),
        (False, "not a bool"),
        (2.5, "whole number"),
        ("2.5", "whole number"),
        ("abc", "whole number"),
        (float("nan"), "whole number"),
        (float("inf"), "whole number"),
        ([3], "whole number"),
        (-1, "negative"),
        ("-2", "negative"),
    ],
)
def test_parse_quantity_rejects(value: object, reason: str) -> None:
    with pytest.raises(QuantityError, match=reason) as exc_info:
        parse_quantity(value, 4)

    assert exc_info.value.index == 4

    assert exc_info.value.value is value

    assert str(exc_info.value).startswith(f"Record 4: invalid quantity {value!r}")


def test_parse_records_reads_qty_and_drops_zero() -> None:
    data: list[dict[str, Any]] = [{"sku": "A"}, {"sku": "B", "qty": 0}, {"sku": "C", "qty": "2"}]

    assert parse_records(data) == [
        Record(index=0, data={"sku": "A"}, qty=1),
        Record(index=2, data={"sku": "C", "qty": "2"}, qty=2),
    ]


def test_parse_records_accepts_single_mapping() -> None:
    assert parse_records({"sku": "A", "qty": 3}) == [
        Record(index=0, data={"sku": "A", "qty": 3}, qty=3)
    ]


def test_parse_records_custom_qty_field() -> None:
    records = parse_records([{"sku": "A", "qty": 9, "copies": 2}], qty_field="copies")

    assert records[0].qty == 2


def test_parse_records_error_names_record_index() -> None:
    with pytest.raises(QuantityError, match=r"^Record 1: invalid quantity -3"):
        parse_records([{"qty": 1}, {"qty": -3}])


@pytest.mark.parametrize("data", ["abc", b"abc", 5, None])
def test_parse_records_rejects_non_list_data(data: Any) -> None:
    with pytest.raises(ValidationError, match="mapping or a list of mappings"):
        parse_records(data)


def test_parse_records_rejects_non_mapping_item() -> None:
    with pytest.raises(ValidationError, match="Record 1 must be a mapping, got str"):
        parse_records([{"sku": "A"}, "B"])  # type: ignore[list-item]


A = Record(index=0, data={"sku": "A"}, qty=3)
B = Record(index=1, data={"sku": "B"}, qty=2)


def test_expand_repeats_identical_copies() -> None:
    assert expand([A, B]) == [A, A, A, B, B]


def test_collate_grouped() -> None:
    assert collate([A, B], "grouped") == [A, A, A, B, B]


def test_collate_interleaved() -> None:
    assert collate([A, B], "interleaved") == [A, B, A, B, A]


def test_collate_empty() -> None:
    assert collate([], "interleaved") == []


def test_collate_rejects_unknown_mode() -> None:
    with pytest.raises(ValidationError, match="Unknown collate mode 'zigzag'"):
        collate([A], "zigzag")  # type: ignore[arg-type]
