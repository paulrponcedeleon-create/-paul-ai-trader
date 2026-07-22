from __future__ import annotations

import asyncio

import pytest

httpx = pytest.importorskip("httpx")

from app.services.stocks import StockQuoteClient, StockQuoteError

pytestmark = pytest.mark.unit


def _client(handler):
    return StockQuoteClient(timeout=0.1, transport=httpx.MockTransport(handler))


def test_stock_quote_falls_back_from_yahoo_to_stooq_csv():
    def handler(request: httpx.Request) -> httpx.Response:
        if "finance/chart" in str(request.url):
            return httpx.Response(
                200, json={"chart": {"result": None, "error": {"code": "Not Found"}}}
            )
        return httpx.Response(
            200,
            text="Symbol,Date,Time,Open,High,Low,Close,Volume\nAAPL.US,2026-07-22,12:00:00,10,12,9,11,100\n",
        )

    quote = asyncio.run(_client(handler).quote("aapl"))

    assert quote["symbol"] == "AAPL"
    assert quote["last"] == 11.0
    assert quote["source"] == "stooq_delayed"


def test_stock_quote_wraps_stooq_404_without_httpx_traceback():
    def handler(request: httpx.Request) -> httpx.Response:
        if "finance/chart" in str(request.url):
            return httpx.Response(200, json={"chart": {"result": [], "error": None}})
        return httpx.Response(404, text="Not Found")

    with pytest.raises(StockQuoteError) as excinfo:
        asyncio.run(_client(handler).quote("pstg"))

    assert "No se encontró cotización para PSTG" in str(excinfo.value)
    assert "Stooq=StockQuoteError" in str(excinfo.value)


def test_stock_quote_wraps_empty_csv_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if "finance/chart" in str(request.url):
            return httpx.Response(404)
        return httpx.Response(200, text="")

    with pytest.raises(StockQuoteError) as excinfo:
        asyncio.run(_client(handler).quote("missing"))

    assert "No se encontró cotización para MISSING" in str(excinfo.value)


def test_stock_quote_wraps_timeout_as_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(StockQuoteError) as excinfo:
        asyncio.run(_client(handler).quote("aapl"))

    assert "No se encontró cotización para AAPL" in str(excinfo.value)
