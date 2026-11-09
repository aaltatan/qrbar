from qrbar.exceptions import ValidationError


def require_int(name: str, value: object, minimum: int) -> None:
    """Raise `ValidationError` unless `value` is an int (not a bool) >= `minimum`."""
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        msg = f"{name} must be an integer >= {minimum}, got {value!r}."

        raise ValidationError(msg)


def require_positive(name: str, value: object) -> float:
    """Return `value` if it is a number (not a bool) > 0, else raise `ValidationError`."""
    if isinstance(value, bool) or not isinstance(value, int | float) or not value > 0:
        msg = f"{name} must be a number > 0, got {value!r}."

        raise ValidationError(msg)

    return value
