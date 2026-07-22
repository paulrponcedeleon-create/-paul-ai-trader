from __future__ import annotations

import csv
from io import StringIO
from typing import Any

import httpx


class StockQuoteError(RuntimeError):
    pass


class StockQuoteClient:
    YAHOO_BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"
    STOOQ_BASE_URL = "https://stooq.com/q/l/"

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.timeout = timeout
        self.transport = transport

    async def quote(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not symbol:
            raise StockQuoteError("Símbolo de acción vacío.")
        yahoo_error: Exception | None = None
        try:
            return await self._quote_yahoo(symbol)
        except (
            StockQuoteError,
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            IndexError,
        ) as exc:
            yahoo_error = exc
        try:
            return await self._quote_stooq(symbol)
        except (
            StockQuoteError,
            httpx.TimeoutException,
            httpx.HTTPStatusError,
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            IndexError,
        ) as exc:
            raise StockQuoteError(
                f"No se encontró cotización para {symbol}; Yahoo={type(yahoo_error).__name__}, Stooq={type(exc).__name__}."
            ) from exc

    async def _quote_yahoo(self, symbol: str) -> dict[str, Any]:
        url = f"{self.YAHOO_BASE_URL}/{symbol}"
        params = {
            "range": "1d",
            "interval": "5m",
            "includePrePost": "true",
        }
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 Paul-AI-Trader-Simulation",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout, transport=self.transport
        ) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        chart = data.get("chart", {})
        if chart.get("error"):
            raise StockQuoteError(f"Yahoo sin datos para {symbol}.")
        results = chart.get("result") or []
        if not results:
            raise StockQuoteError(f"Yahoo sin resultados para {symbol}.")
        result = results[0]
        meta = result.get("meta") or {}
        quote_rows = result.get("indicators", {}).get("quote", [{}])[0]
        highs = [
            float(value) for value in quote_rows.get("high", []) if value is not None
        ]
        lows = [
            float(value) for value in quote_rows.get("low", []) if value is not None
        ]
        volumes = [
            float(value) for value in quote_rows.get("volume", []) if value is not None
        ]
        raw_last = meta.get("regularMarketPrice") or meta.get("previousClose")
        if raw_last in {None, "", "N/D"}:
            raise StockQuoteError(f"Yahoo sin precio para {symbol}.")
        last = float(raw_last)
        high = float(
            meta.get("regularMarketDayHigh") or (max(highs) if highs else last)
        )
        low = float(meta.get("regularMarketDayLow") or (min(lows) if lows else last))
        previous_close = float(
            meta.get("chartPreviousClose") or meta.get("previousClose") or last
        )
        return {
            "symbol": symbol,
            "last": last,
            "high": high,
            "low": low,
            "volume": sum(volumes),
            "previous_close": previous_close,
            "currency": str(meta.get("currency") or "USD"),
            "exchange": str(meta.get("exchangeName") or "US"),
            "source": "yahoo_reference",
            "delayed": False,
        }

    async def _quote_stooq(self, symbol: str) -> dict[str, Any]:
        params = {
            "s": f"{symbol.lower()}.us",
            "f": "sd2t2ohlcv",
            "h": "",
            "e": "csv",
        }
        async with httpx.AsyncClient(
            timeout=self.timeout, transport=self.transport
        ) as client:
            response = await client.get(self.STOOQ_BASE_URL, params=params)
            if response.status_code == 404:
                raise StockQuoteError(f"Stooq respondió 404 para {symbol}.")
            response.raise_for_status()

        if not response.text.strip():
            raise StockQuoteError(f"Stooq devolvió CSV vacío para {symbol}.")
        rows = list(csv.DictReader(StringIO(response.text)))
        if not rows:
            raise StockQuoteError(f"Stooq devolvió CSV sin filas para {symbol}.")
        row = rows[0]
        if row.get("Close") in {None, "N/D", ""}:
            raise StockQuoteError(f"No se encontró cotización para {symbol}.")
        last = float(row["Close"])
        return {
            "symbol": symbol,
            "last": last,
            "high": float(row.get("High") or last),
            "low": float(row.get("Low") or last),
            "volume": float(row.get("Volume") or 0),
            "previous_close": float(row.get("Open") or last),
            "currency": "USD",
            "exchange": "US",
            "source": "stooq_delayed",
            "delayed": True,
        }
