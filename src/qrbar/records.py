"""Records and quantities: validate input data and expand it into identical copies."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from qrbar.exceptions import QuantityError, ValidationError

type Collate = Literal["grouped", "interleaved"]

DEFAULT_QTY_FIELD = "qty"


@dataclass(frozen=True, slots=True)
class Record:
    """One input record and how many identical copies of it to produce."""

    index: int
    data: Mapping[str, Any]
    qty: int


def parse_records(
    data: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    qty_field: str = DEFAULT_QTY_FIELD,
) -> list[Record]:
    """Validate records and read their quantities, dropping records with qty 0.

    A single mapping is treated as a list of one record.
    """
    if isinstance(data, Mapping):
        data = [data]

    elif not isinstance(data, Sequence) or isinstance(data, str | bytes):
        msg = f"Data must be a mapping or a list of mappings, got {type(data).__name__}."

        raise ValidationError(msg)

    records: list[Record] = []

    for index, item in enumerate(data):
        if not isinstance(item, Mapping):
            msg = f"Record {index} must be a mapping, got {type(item).__name__}."

            raise ValidationError(msg)

        qty = parse_quantity(item.get(qty_field), index)

        if qty > 0:
            records.append(Record(index=index, data=item, qty=qty))

    return records


def parse_quantity(value: object, index: int) -> int:
    """Turn a raw quantity into a non-negative int.

    Missing, `None` or blank -> 1. Whole numbers, whole floats (`2.0`) and numeric
    strings (`"3"`, `"2.0"`) are accepted. Bools, fractions, negatives and
    anything else raise `QuantityError`.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return 1

    if isinstance(value, bool):
        raise QuantityError(index, value, "must be a whole number, not a bool")

    number: int | float | None = None

    if isinstance(value, int | float):
        number = value

    elif isinstance(value, str):
        number = _parse_number(value.strip())

    if isinstance(number, float):
        # nan and inf are not integers either
        number = int(number) if number.is_integer() else None

    if number is None:
        raise QuantityError(index, value, "must be a whole number")

    if number < 0:
        raise QuantityError(index, value, "must not be negative")

    return number


def _parse_number(text: str) -> int | float | None:
    try:
        return int(text)

    except ValueError:
        pass

    try:
        return float(text)

    except ValueError:
        return None


def expand(records: Sequence[Record]) -> list[Record]:
    """Repeat each record `qty` times, keeping records together: A, A, B."""
    return [record for record in records for _ in range(record.qty)]


def collate(records: Sequence[Record], mode: Collate = "grouped") -> list[Record]:
    """Expand records into copies in `grouped` (A, A, B) or `interleaved` (A, B, A) order."""
    if mode == "grouped":
        return expand(records)

    if mode == "interleaved":
        rounds = max((record.qty for record in records), default=0)

        return [record for turn in range(rounds) for record in records if record.qty > turn]

    msg = f"Unknown collate mode {mode!r}, expected 'grouped' or 'interleaved'."

    raise ValidationError(msg)
