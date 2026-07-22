from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import Any

from app.services.bitso import BitsoClient, BitsoError
from app.services.rfq_quotes import RfqQuoteError, RfqQuoteResolver
from app.services.stocks import StockQuoteClient, StockQuoteError
from app.services.signals import momentum_signal


@dataclass(frozen=True)
class AssetDefinition:
    book: str
    symbol: str
    name: str
    asset_type: str
    stock_symbol: str | None = None
    tradeable: bool = True


CURATED_ASSETS = (
    AssetDefinition("btc_mxn", "BTC", "Bitcoin", "crypto"),
    AssetDefinition("eth_mxn", "ETH", "Ether", "crypto"),
    AssetDefinition("sol_mxn", "SOL", "Solana", "crypto"),
    AssetDefinition("atom_mxn", "ATOM", "Cosmos", "crypto"),
    AssetDefinition("mxn_cash", "MXN", "Peso mexicano", "cash", tradeable=False),
    AssetDefinition("usdc_mxn", "USD", "Dólar digital (USDC)", "currency"),
    AssetDefinition("usdt_mxn", "USDT", "Tether", "currency"),
    AssetDefinition("paxg_mxn", "PAXG", "PAX Gold", "crypto"),
    AssetDefinition("xrp_mxn", "XRP", "XRP", "crypto"),
    AssetDefinition("algn_mxn", "ALGN", "Align Technology", "stock", "ALGN"),
    AssetDefinition("pstg_mxn", "PSTG", "Everpure, Inc.", "stock", "PSTG"),
    AssetDefinition("tsla_mxn", "TSLA", "Tesla", "stock", "TSLA"),
    AssetDefinition("aapl_mxn", "AAPL", "Apple", "stock", "AAPL"),
)
ASSET_BY_BOOK = {asset.book: asset for asset in CURATED_ASSETS}
FALLBACK_FEES = {
    "mxn": 0.0078,
    "usdc": 0.0036,
    "usd": 0.0036,
    "usdt": 0.0036,
    "btc": 0.00098,
}


class UnifiedMarketError(RuntimeError):
    pass


class UnifiedMarketService:
    def __init__(
        self,
        bitso: BitsoClient,
        stocks: StockQuoteClient | None = None,
    ) -> None:
        self.bitso = bitso
        self.stocks = stocks or StockQuoteClient()
        self.rfq = RfqQuoteResolver(bitso)
        self._available_books: set[str] = set()
        self._available_until = 0.0
        self._fee_rates: dict[str, float] = {}
        self._fee_source = "public_fallback"
        self._fees_until = 0.0
        self._quote_cache: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}

    async def _available(self) -> set[str]:
        now = time.monotonic()
        if self._available_books and now < self._available_until:
            return self._available_books
        try:
            result = await self.bitso.available_books()
            payload = result.get("payload", result)
            rows = payload.get("books", []) if isinstance(payload, dict) else payload
            self._available_books = {
                str(item.get("book", "")).lower()
                for item in rows
                if isinstance(item, dict) and item.get("book")
            }
        except (BitsoError, TypeError, AttributeError):
            self._available_books = {
                "btc_mxn",
                "eth_mxn",
                "sol_mxn",
                "xrp_mxn",
                "usdc_mxn",
                "usdt_mxn",
            }
        self._available_until = now + 300
        return self._available_books

    async def _fees(self) -> tuple[dict[str, float], str]:
        now = time.monotonic()
        if self._fee_rates and now < self._fees_until:
            return self._fee_rates, self._fee_source
        rates: dict[str, float] = {}
        source = "bitso_account"
        try:
            result = await self.bitso.fees()
            payload = result.get("payload", result)
            for item in payload.get("fees", []):
                book = str(item.get("book", "")).lower()
                raw = item.get("taker_fee_decimal") or item.get("fee_decimal")
                if book and raw is not None:
                    value = float(raw)
                    if 0 <= value < 1:
                        rates[book] = value
        except (BitsoError, TypeError, ValueError, AttributeError):
            source = "public_fallback"
        self._fee_rates = rates
        self._fee_source = source
        self._fees_until = now + 900
        return rates, source

    @staticmethod
    def _fallback_fee(book: str) -> float:
        return FALLBACK_FEES.get(book.rsplit("_", 1)[-1], 0.0078)

    async def _ticker(self, book: str) -> dict[str, Any]:
        result = await self.bitso.ticker(book)
        ticker = result.get("payload", result)
        if float(ticker["last"]) <= 0:
            raise UnifiedMarketError(f"Precio inválido para {book}.")
        return ticker

    async def _alpha_route(self, book: str) -> list[str]:
        available = await self._available()
        major = book.split("_", 1)[0]
        candidates = [
            [f"{major}_usdt", "usdt_mxn"],
            [f"{major}_usdc", "usdc_mxn"],
            [f"{major}_usd", "usdc_mxn"],
            [f"{major}_btc", "btc_mxn"],
        ]
        valid = [
            route for route in candidates if all(leg in available for leg in route)
        ]
        if not valid:
            raise UnifiedMarketError(
                f"Bitso no tiene libro Alpha ni conversión disponible para {major.upper()}."
            )
        rates, _ = await self._fees()

        def cost(route: list[str]) -> float:
            retained = 1.0
            for leg in route:
                retained *= 1 - rates.get(leg, self._fallback_fee(leg))
            return 1 - retained

        return min(valid, key=cost)

    async def _alpha_quote(
        self,
        asset: AssetDefinition,
        route: list[str],
    ) -> dict[str, Any]:
        tickers = await asyncio.gather(*(self._ticker(leg) for leg in route))
        rates, fee_source = await self._fees()
        last = high = low = 1.0
        volume = 0.0
        retained = 1.0
        for leg, ticker in zip(route, tickers, strict=True):
            last *= float(ticker["last"])
            high *= float(ticker.get("high") or ticker["last"])
            low *= float(ticker.get("low") or ticker["last"])
            volume += float(ticker.get("volume") or 0)
            retained *= 1 - rates.get(leg, self._fallback_fee(leg))
        fee_rate = round(1 - retained, 12)
        return {
            "book": asset.book,
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "last": last,
            "high": high,
            "low": low,
            "volume": volume,
            "effective_fee_rate": fee_rate,
            "effective_fee_percent": round(fee_rate * 100, 6),
            "fee_source": fee_source,
            "fee_included_in_quote": False,
            "route": route,
            "route_label": " → ".join(leg.upper() for leg in route),
            "source": "bitso_alpha",
            "tradeable": asset.tradeable,
            "delayed": False,
        }

    async def _crypto_quote(
        self,
        asset: AssetDefinition,
        side: str,
    ) -> dict[str, Any]:
        available = await self._available()
        if asset.book in available:
            return await self._alpha_quote(asset, [asset.book])
        try:
            rfq = await self.rfq.quote(asset.symbol, side)
            return {
                "book": asset.book,
                "symbol": asset.symbol,
                "name": asset.name,
                "asset_type": asset.asset_type,
                "tradeable": asset.tradeable,
                **rfq,
            }
        except (RfqQuoteError, BitsoError, KeyError, TypeError, ValueError):
            return await self._alpha_quote(asset, await self._alpha_route(asset.book))

    async def _mxn_per_usd(self) -> tuple[float, str]:
        available = await self._available()
        for book in ("usdc_mxn", "usd_mxn", "usdt_mxn"):
            if book in available:
                return float((await self._ticker(book))["last"]), book
        raise UnifiedMarketError("No se encontró una referencia USD/MXN en Bitso.")

    async def _stock_quote(self, asset: AssetDefinition) -> dict[str, Any]:
        try:
            stock, (mxn_per_usd, fx_book) = await asyncio.gather(
                self.stocks.quote(str(asset.stock_symbol)),
                self._mxn_per_usd(),
            )
        except (StockQuoteError, BitsoError, UnifiedMarketError) as exc:
            raise UnifiedMarketError(str(exc)) from exc
        return {
            "book": asset.book,
            "symbol": asset.symbol,
            "name": asset.name,
            "asset_type": "stock",
            "last": float(stock["last"]) * mxn_per_usd,
            "high": float(stock.get("high") or stock["last"]) * mxn_per_usd,
            "low": float(stock.get("low") or stock["last"]) * mxn_per_usd,
            "volume": float(stock.get("volume") or 0),
            "effective_fee_rate": 0.0,
            "effective_fee_percent": 0.0,
            "fee_source": "bitso_stock_zero_fee",
            "fee_included_in_quote": False,
            "route": [f"{asset.stock_symbol}_USD", fx_book],
            "route_label": f"{asset.stock_symbol}/USD → {fx_book.upper()}",
            "source": str(stock.get("source") or "external_stock_reference"),
            "tradeable": True,
            "delayed": bool(stock.get("delayed", False)),
        }

    async def quote(
        self,
        book: str,
        *,
        force: bool = False,
        side: str = "buy",
    ) -> dict[str, Any]:
        book = book.lower()
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise UnifiedMarketError("La cotización requiere side=buy o side=sell.")
        asset = ASSET_BY_BOOK.get(book)
        if asset is None:
            raise UnifiedMarketError(f"Activo no autorizado: {book}")
        now = time.monotonic()
        cache_key = (book, side)
        cached = self._quote_cache.get(cache_key)
        if not force and cached and now < cached[0]:
            return cached[1]

        if asset.asset_type == "cash":
            result = {
                "book": asset.book,
                "symbol": asset.symbol,
                "name": asset.name,
                "asset_type": "cash",
                "last": 1.0,
                "high": 1.0,
                "low": 1.0,
                "volume": 0.0,
                "effective_fee_rate": 0.0,
                "effective_fee_percent": 0.0,
                "fee_source": "none",
                "fee_included_in_quote": False,
                "route": [],
                "route_label": "Efectivo disponible",
                "source": "cash",
                "tradeable": False,
                "delayed": False,
            }
        elif asset.asset_type == "stock":
            result = await self._stock_quote(asset)
        else:
            result = await self._crypto_quote(asset, side)
        ttl = 15 if asset.asset_type == "stock" else 5
        self._quote_cache[cache_key] = (now + ttl, result)
        return result

    async def catalog(self, allowed_books: set[str]) -> list[dict[str, Any]]:
        async def build(asset: AssetDefinition) -> dict[str, Any]:
            try:
                quote = await self.quote(asset.book, side="buy")
                if asset.asset_type == "cash":
                    action = "hold"
                    confidence = 100
                    reason = "Efectivo disponible; no tiene movimiento de mercado."
                elif quote["source"] == "bitso_rfq":
                    action = "hold"
                    confidence = 50
                    reason = (
                        "Disponible mediante conversión de Bitso. Sin libro Alpha de 24 h, "
                        "se muestra mantener hasta contar con datos comparables."
                    )
                else:
                    signal = momentum_signal(
                        float(quote["last"]),
                        float(quote["high"]),
                        float(quote["low"]),
                        float(quote.get("volume", 0)),
                    )
                    action = signal.action
                    confidence = signal.confidence
                    reason = signal.reason
                return {
                    **quote,
                    "available": True,
                    "signal": {
                        "action": action,
                        "confidence": confidence,
                        "reason": reason,
                        "reference_price": quote["last"],
                    },
                }
            except (
                UnifiedMarketError,
                BitsoError,
                StockQuoteError,
                RfqQuoteError,
                ValueError,
            ) as exc:
                return {
                    "book": asset.book,
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_type": asset.asset_type,
                    "last": None,
                    "effective_fee_rate": None,
                    "effective_fee_percent": None,
                    "fee_included_in_quote": False,
                    "route": [],
                    "route_label": "Cotización no disponible",
                    "source": "unavailable",
                    "tradeable": False,
                    "available": False,
                    "delayed": False,
                    "signal": {
                        "action": "hold",
                        "confidence": 0,
                        "reason": str(exc),
                        "reference_price": 0,
                    },
                }

        assets = [asset for asset in CURATED_ASSETS if asset.book in allowed_books]
        return list(await asyncio.gather(*(build(asset) for asset in assets)))
