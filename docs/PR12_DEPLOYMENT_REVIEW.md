# PR #12 Deployment Review

## Render quote failure root cause

`app.services.stocks.StockQuoteClient` queried Yahoo first and then Stooq for every stock
symbol. `PSTG` is no longer a valid public quote symbol in the providers used by the
application. Yahoo can return an empty chart result / no price for that symbol, and the
fallback URL `https://stooq.com/q/l/?s=pstg.us&f=sd2t2ohlcv&h=&e=csv` can return 404.
The previous client did not wrap the Stooq `HTTPStatusError`, so Render logged an
uncontrolled traceback even though the FastAPI process continued serving other routes.

Everpure is not remapped to another ticker in this codebase. `pstg_mxn` is retained only
as an unavailable legacy asset definition and is removed from the default public/trading
allow-list.

## Implemented only

These modules contain core/domain functionality and do not run by themselves:

- `app.ai`
- `app.analytics`
- `app.optimization`
- `app.experiments`
- `app.research`
- `app.adaptive`
- `app.validation`
- `app.system`
- `app.market_data`
- `app.live`
- `app.burnin`

## Connected to endpoints

These modules are exposed through FastAPI routers registered in `app.main`:

- AI: `/ai/*`
- Analytics: `/analytics/*`
- Optimization: `/optimization/*`
- Paper trading: `/paper/*` and `/paper-trading/status`
- Broker abstraction: `/broker/*`
- Market data: `/market/live/*`
- Runtime: `/runtime/*`
- Burn-in: `/burnin/*`
- Experiments: `/experiments/*`
- Research: `/research/*`
- Adaptive selection: `/adaptive/*`
- Validation pipeline: `/validation/*`
- System services: `/system/*`
- Readiness: `/ready` and `/readiness`

## Executing automatically

The web application automatically serves HTTP requests, performs health/readiness checks
on demand, and builds market catalog quotes when requested by API/UI clients.

## Pending continuous scheduler

The bot does not currently open or close simulated trades without user/API interaction.
Continuous unattended paper trading still needs a scheduler or background worker that
starts `RuntimeEngine`, invokes it on a configured interval, supervises it, and persists
state across process restarts. This was intentionally not enabled during this fix.

## Safety

`LIVE_TRADING` remains false by default. This review did not enable live trading, did not
add private credentials, and did not send real orders.
