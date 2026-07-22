# Autonomous Runtime v1

This phase enables continuous paper-trading cycles with live read-only Bitso market data while keeping LIVE_TRADING=false.

Scope:
- Automatic runtime loop while the web service is alive.
- BTC, ETH, SOL, XRP and USDT as the initial autonomous crypto universe.
- Paper broker only.
- Dashboard status translated to user-facing Spanish.
- No real-money orders.

Important limitation:
The current Bitso provider derives short candle sequences from public ticker data. Historical multi-timeframe ingestion, persistent learning and strategy promotion remain separate phases and must not be represented as complete until real historical datasets are connected and validated.
