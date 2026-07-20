from decimal import Decimal, ROUND_HALF_UP
from typing import Any

MONEY = Decimal("0.01")
PERCENT = Decimal("0.0001")
QUANTITY = Decimal("0.000000000001")


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> float:
    return float(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def calculate_position(order: dict[str, Any], current_price: float) -> dict[str, Any]:
    entry_price = _decimal(order["reference_price"])
    market_price = _decimal(current_price)
    amount = _decimal(order["amount_mxn"])

    if entry_price <= 0 or market_price <= 0:
        raise ValueError("Los precios deben ser mayores que cero.")

    asset_quantity = amount / entry_price
    direction = Decimal("1") if order["side"] == "buy" else Decimal("-1")
    pnl = asset_quantity * (market_price - entry_price) * direction
    current_value = amount + pnl
    return_pct = (pnl / amount) * Decimal("100") if amount else Decimal("0")

    return {
        **order,
        "entry_price": float(entry_price),
        "current_price": float(market_price),
        "asset_quantity": float(asset_quantity.quantize(QUANTITY, rounding=ROUND_HALF_UP)),
        "current_value_mxn": _money(current_value),
        "unrealized_pnl_mxn": _money(pnl),
        "return_pct": float(return_pct.quantize(PERCENT, rounding=ROUND_HALF_UP)),
    }


def summarize_positions(positions: list[dict[str, Any]]) -> dict[str, Any]:
    invested = sum((_decimal(item["amount_mxn"]) for item in positions), Decimal("0"))
    current_value = sum(
        (_decimal(item["current_value_mxn"]) for item in positions), Decimal("0")
    )
    pnl = current_value - invested
    return_pct = (pnl / invested) * Decimal("100") if invested else Decimal("0")

    return {
        "open_positions": len(positions),
        "invested_mxn": _money(invested),
        "current_value_mxn": _money(current_value),
        "unrealized_pnl_mxn": _money(pnl),
        "return_pct": float(return_pct.quantize(PERCENT, rounding=ROUND_HALF_UP)),
    }
