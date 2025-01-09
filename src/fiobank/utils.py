from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable


def coerce_amount(value: int | float) -> Decimal:
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    raise ValueError(value)


def coerce_date(value: datetime | date | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def sanitize_value(value: Any, convert: Callable | None = None) -> Any:
    if isinstance(value, str):
        value = value.strip() or None
    if convert and value is not None:
        return convert(value)
    return value
