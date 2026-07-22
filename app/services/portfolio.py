from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MONEY = Decimal("0.01")
PERCENT = Decimal("0.0001")
QUANTITY = Decimal("0.000000000001")
DEFAULT_TAKER_FEE_RATE = Decimal("0.0078")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def _rate(value: Any | None, fallback: Decimal = DEFAULT_TAKER_FEE_RATE) -> Decimal:
    if value is None:
        return fallback
    parsed = _decimal(value)
    return parsed if parsed >= 0 else fallback


def calculate_position(
    order: dict[str, Any],
    current_price: float,
    *,
    exit_fee_rate: float | None = None,
) -> dict[str, Any]:
    entry_price = _decimal(order["reference_price"])
    market_price = _decimal(current_price)
    amount = _decimal(order["amount_mxn"])
    entry_rate = _rate(order.get("entry_fee_rate"))
    current_exit_rate = _rate(exit_fee_rate, entry_rate)

    if entry_price <= 0 or market_price <= 0:
        raise ValueError("Los precios deben ser mayores que cero.")

    gross_quantity = amount / entry_price
    entry_fee_mxn = amount * entry_rate

    if order["side"] == "buy":
        asset_quantity = gross_quantity * (Decimal("1") - entry_rate)
        gross_current_value = asset_quantity * market_price
        estimated_exit_fee = gross_current_value * current_exit_rate
        current_value = gross_current_value - estimated_exit_fee
        break_even_price = entry_price / (
            (Decimal("1") - entry_rate) * (Decimal("1") - current_exit_rate)
        )
    else:
        asset_quantity = gross_quantity
        gross_pnl = asset_quantity * (entry_price - market_price)
        estimated_exit_fee = asset_quantity * market_price * current_exit_rate
        current_value = amount + gross_pnl - entry_fee_mxn - estimated_exit_fee
        break_even_price = (
            entry_price
            * (Decimal("1") - entry_rate)
            / (Decimal("1") + current_exit_rate)
        )

    pnl = current_value - amount
    return_pct = (pnl / amount) * Decimal("100") if amount else Decimal("0")
    break_even_change_pct = (
        ((break_even_price / entry_price) - Decimal("1")) * Decimal("100")
        if entry_price
        else Decimal("0")
    )

    return {
        **order,
        "entry_price": float(entry_price),
        "current_price": float(market_price),
        "asset_quantity": float(
            asset_quantity.quantize(QUANTITY, rounding=ROUND_HALF_UP)
        ),
        "gross_current_value_mxn": _money(
            gross_current_value
            if order["side"] == "buy"
            else current_value + estimated_exit_fee
        ),
        "current_value_mxn": _money(current_value),
        "unrealized_pnl_mxn": _money(pnl),
        "return_pct": float(return_pct.quantize(PERCENT, rounding=ROUND_HALF_UP)),
        "entry_fee_rate": float(entry_rate),
        "entry_fee_percent": float(
            (entry_rate * Decimal("100")).quantize(PERCENT, rounding=ROUND_HALF_UP)
        ),
        "entry_fee_mxn": _money(entry_fee_mxn),
        "exit_fee_rate": float(current_exit_rate),
        "exit_fee_percent": float(
            (current_exit_rate * Decimal("100")).quantize(
                PERCENT, rounding=ROUND_HALF_UP
            )
        ),
        "estimated_exit_fee_mxn": _money(estimated_exit_fee),
        "total_estimated_fees_mxn": _money(entry_fee_mxn + estimated_exit_fee),
        "break_even_price": float(break_even_price),
        "break_even_change_pct": float(
            break_even_change_pct.quantize(PERCENT, rounding=ROUND_HALF_UP)
        ),
    }


def summarize_positions(positions: list[dict[str, Any]]) -> dict[str, Any]:
    invested = sum((_decimal(item["amount_mxn"]) for item in positions), Decimal("0"))
    current_value = sum(
        (_decimal(item["current_value_mxn"]) for item in positions), Decimal("0")
    )
    fees = sum(
        (_decimal(item["total_estimated_fees_mxn"]) for item in positions), Decimal("0")
    )
    pnl = current_value - invested
    return_pct = (pnl / invested) * Decimal("100") if invested else Decimal("0")

    return {
        "open_positions": len(positions),
        "invested_mxn": _money(invested),
        "current_value_mxn": _money(current_value),
        "unrealized_pnl_mxn": _money(pnl),
        "estimated_fees_mxn": _money(fees),
        "return_pct": float(return_pct.quantize(PERCENT, rounding=ROUND_HALF_UP)),
    }
