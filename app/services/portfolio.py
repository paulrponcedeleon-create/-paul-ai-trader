from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.services.money import (
    public_decimal,
    public_money,
    public_price,
    public_quantity,
    quantize_rate,
    to_decimal,
)
from app.services.trade_sources import (
    BOT_SOURCES,
    MANUAL_SOURCE,
    POSITION_SOURCES,
    infer_position_source,
    public_source,
)

PERCENT = Decimal("0.0001")
DEFAULT_TAKER_FEE_RATE = Decimal("0.0078")


def _rate(value: Any | None, fallback: Decimal = DEFAULT_TAKER_FEE_RATE) -> Decimal:
    if value is None:
        return quantize_rate(fallback)
    parsed = to_decimal(value)
    return quantize_rate(parsed if parsed >= 0 else fallback)


def calculate_position(
    order: dict[str, Any],
    current_price: Any,
    *,
    exit_fee_rate: Any | None = None,
) -> dict[str, Any]:
    entry_price = to_decimal(order["reference_price"])
    market_price = to_decimal(current_price)
    amount = to_decimal(order["amount_mxn"])
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
        gross_current_value = current_value + estimated_exit_fee
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
        "entry_price": public_price(entry_price),
        "current_price": public_price(market_price),
        "asset_quantity": public_quantity(asset_quantity),
        "gross_current_value_mxn": public_money(gross_current_value),
        "current_value_mxn": public_money(current_value),
        "unrealized_pnl_mxn": public_money(pnl),
        "return_pct": public_decimal(return_pct, quantum=PERCENT),
        "entry_fee_rate": public_decimal(entry_rate),
        "entry_fee_percent": public_decimal(
            entry_rate * Decimal("100"), quantum=PERCENT
        ),
        "entry_fee_mxn": public_money(entry_fee_mxn),
        "exit_fee_rate": public_decimal(current_exit_rate),
        "exit_fee_percent": public_decimal(
            current_exit_rate * Decimal("100"), quantum=PERCENT
        ),
        "estimated_exit_fee_mxn": public_money(estimated_exit_fee),
        "total_estimated_fees_mxn": public_money(
            entry_fee_mxn + estimated_exit_fee
        ),
        "break_even_price": public_price(break_even_price),
        "break_even_change_pct": public_decimal(
            break_even_change_pct, quantum=PERCENT
        ),
    }


def _summarize_rows(positions: list[dict[str, Any]]) -> dict[str, Any]:
    invested = sum((to_decimal(item["amount_mxn"]) for item in positions), Decimal("0"))
    current_value = sum(
        (to_decimal(item["current_value_mxn"]) for item in positions), Decimal("0")
    )
    fees = sum(
        (to_decimal(item["total_estimated_fees_mxn"]) for item in positions),
        Decimal("0"),
    )
    pnl = current_value - invested
    return_pct = (pnl / invested) * Decimal("100") if invested else Decimal("0")

    return {
        "open_positions": len(positions),
        "invested_mxn": public_money(invested),
        "current_value_mxn": public_money(current_value),
        "unrealized_pnl_mxn": public_money(pnl),
        "estimated_fees_mxn": public_money(fees),
        "return_pct": public_decimal(return_pct, quantum=PERCENT),
    }


def summarize_positions(positions: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in positions:
        grouped[infer_position_source(item)].append(item)

    by_source = [
        {
            **public_source(source),
            **_summarize_rows(grouped.get(source, [])),
        }
        for source in POSITION_SOURCES
    ]
    source_map = {item["source"]: item for item in by_source}
    manual = _summarize_rows(grouped.get(MANUAL_SOURCE, []))
    bot_rows = [
        row
        for source in BOT_SOURCES
        for row in grouped.get(source, [])
    ]
    bot = _summarize_rows(bot_rows)

    return {
        **_summarize_rows(positions),
        "by_source": by_source,
        "comparison": {
            "manual": {"label": "Tus operaciones manuales", **manual},
            "bot": {"label": "Bot + IA", **bot},
        },
        "source_counts": {
            source: int(source_map[source]["open_positions"])
            for source in POSITION_SOURCES
        },
    }
