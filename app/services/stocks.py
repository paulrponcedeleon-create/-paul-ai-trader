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

    async def quote(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        try:
            return await self._quote_yahoo(symbol)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, IndexError):
            return await self._quote_stooq(symbol)

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
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

        result = data["chart"]["result"][0]
        meta = result["meta"]
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
        last = float(meta.get("regularMarketPrice") or meta.get("previousClose"))
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
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(self.STOOQ_BASE_URL, params=params)
            response.raise_for_status()

        rows = list(csv.DictReader(StringIO(response.text)))
        if not rows or rows[0].get("Close") in {None, "N/D", ""}:
            raise StockQuoteError(f"No se encontró cotización para {symbol}.")
        row = rows[0]
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
