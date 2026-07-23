from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MONEY_QUANTUM = Decimal("0.01")
PRICE_QUANTUM = Decimal("0.000000000001")
RATE_QUANTUM = Decimal("0.000000000001")
QUANTITY_QUANTUM = Decimal("0.000000000001")
ZERO = Decimal("0")


def to_decimal(value: Any) -> Decimal:
    """Convert external numeric input without inheriting binary-float artifacts."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def optional_decimal(value: Any | None) -> Decimal | None:
    return None if value is None else to_decimal(value)


def quantize_money(value: Any) -> Decimal:
    return to_decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_price(value: Any) -> Decimal:
    return to_decimal(value).quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_rate(value: Any) -> Decimal:
    return to_decimal(value).quantize(RATE_QUANTUM, rounding=ROUND_HALF_UP)


def quantize_quantity(value: Any) -> Decimal:
    return to_decimal(value).quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_UP)


def public_decimal(value: Decimal | None, *, quantum: Decimal | None = None) -> float | None:
    """Serialize Decimal at the HTTP boundary while calculations remain exact internally."""
    if value is None:
        return None
    normalized = value.quantize(quantum, rounding=ROUND_HALF_UP) if quantum else value
    return float(normalized)


def public_money(value: Decimal | None) -> float | None:
    return public_decimal(value, quantum=MONEY_QUANTUM)


def public_price(value: Decimal | None) -> float | None:
    return public_decimal(value, quantum=PRICE_QUANTUM)


def public_rate(value: Decimal | None) -> float | None:
    return public_decimal(value, quantum=RATE_QUANTUM)


def public_quantity(value: Decimal | None) -> float | None:
    return public_decimal(value, quantum=QUANTITY_QUANTUM)
