# Markets and Bitso Audit

## Market inventory

`app/services/unified_markets.py` defines curated assets including crypto, cash/currency and stock-like synthetic MXN books. Current tests and dashboard focus on verified visible assets: BTC, ETH, SOL, USDT, XRP, ALGN, TSLA and AAPL.

## Providers

- `MockMarketDataProvider` offers deterministic read-only data and events.
- `BitsoMarketDataProvider` extends mock behavior, uses `BitsoClient.ticker()` for public read-only ticker data, synthesizes orderbook/candles/trades, and reports `live_trading_enabled=False`.
- `ProviderFactory` selects `mock` or `bitso`.
- `MarketDataCache` stores tickers, orderbooks, candle deques, trade deques and bounded events.

## Bitso client and live safety

- `BitsoClient` signs private requests with HMAC only when private endpoints are called.
- `BitsoClient.place_market_order()` only permits real market buys and rejects sells in the current v1 live implementation.
- `BitsoBroker` is guarded by live-trading controls and tests assert simulation does not call real Bitso orders.
- `LIVE_TRADING=false` is the default in configuration.

## Findings

1. Market-data Bitso provider is read-only and does not place orders.
2. Runtime books are filtered to verified crypto books in `app/api/routes/runtime.py`.
3. The market catalog includes stock-style assets resolved through stock quote/RFQ services, but availability depends on providers and settings.
4. Candle data quality is a known limitation because candles are derived from ticker snapshots.
5. Caching exists but is split between provider cache and higher-level market service cache; v3 should define one explicit cache policy per data class.

## Evidence commands

- `sed -n '1,220p' app/services/unified_markets.py`
- `sed -n '1,220p' app/market_data/bitso.py app/market_data/cache.py app/market_data/factory.py`
- `sed -n '1,260p' app/services/bitso.py app/brokers/bitso.py`
- `rg -n "CURATED_ASSETS|VERIFIED_RUNTIME_BOOKS|place_market_order|live_trading_enabled|read_only" app tests -S`
