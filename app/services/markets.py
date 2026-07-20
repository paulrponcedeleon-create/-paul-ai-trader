from __future__ import annotations

from typing import Any

PRIMARY_BOOKS = {"btc_mxn", "eth_mxn", "sol_mxn", "xrp_mxn"}

DISPLAY_NAMES = {
    "btc_mxn": "Bitcoin",
    "eth_mxn": "Ether",
    "sol_mxn": "Solana",
    "xrp_mxn": "XRP",
    "doge_mxn": "Dogecoin",
    "ada_mxn": "Cardano",
    "ltc_mxn": "Litecoin",
    "link_mxn": "Chainlink",
    "shib_mxn": "Shiba Inu",
    "pepe_mxn": "Pepe",
    "sui_mxn": "Sui",
    "hbar_mxn": "Hedera",
    "avax_mxn": "Avalanche",
    "dot_mxn": "Polkadot",
    "atom_mxn": "Cosmos",
    "uni_mxn": "Uniswap",
    "aave_mxn": "Aave",
    "mana_mxn": "Decentraland",
    "gala_mxn": "Gala",
    "sand_mxn": "The Sandbox",
    "bch_mxn": "Bitcoin Cash",
    "bat_mxn": "Basic Attention Token",
    "comp_mxn": "Compound",
    "mkr_mxn": "Maker",
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_market_catalog(
    books: list[str],
    tickers: dict[str, dict[str, Any]],
    fee_rates: dict[str, float],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for book in books:
        ticker = tickers.get(book)
        if not ticker:
            continue

        last = _number(ticker.get("last"))
        high = _number(ticker.get("high"), last)
        low = _number(ticker.get("low"), last)
        if last <= 0:
            continue

        range_24_pct = max(0.0, ((high - low) / last) * 100)
        change_24 = _number(ticker.get("change_24"))
        previous = last - change_24
        change_24_pct = (change_24 / previous * 100) if previous > 0 else 0.0
        fee_rate = max(0.0, fee_rates.get(book, 0.0))

        items.append(
            {
                "book": book,
                "symbol": book.split("_", 1)[0].upper(),
                "name": DISPLAY_NAMES.get(book, book.split("_", 1)[0].upper()),
                "last": last,
                "range_24_pct": round(range_24_pct, 2),
                "change_24_pct": round(change_24_pct, 2),
                "taker_fee_rate": fee_rate,
                "taker_fee_percent": round(fee_rate * 100, 4),
                "is_primary": book in PRIMARY_BOOKS,
                "tags": [],
            }
        )

    items.sort(key=lambda item: (-item["range_24_pct"], item["taker_fee_rate"], item["book"]))
    if not items:
        return items

    minimum_fee = min(item["taker_fee_rate"] for item in items)
    maximum_fee = max(item["taker_fee_rate"] for item in items)
    fees_differ = (maximum_fee - minimum_fee) > 1e-12
    volatile_books = {item["book"] for item in items[: min(5, len(items))]}
    for item in items:
        tags: list[str] = []
        if item["is_primary"]:
            tags.append("Principal")
        if item["book"] in volatile_books or item["range_24_pct"] >= 5:
            tags.append("Alta volatilidad")
        if fees_differ and abs(item["taker_fee_rate"] - minimum_fee) < 1e-12:
            tags.append("Comisión menor")
        item["tags"] = tags

    return items
