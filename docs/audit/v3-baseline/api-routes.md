# API and Routes Audit

## Registration model

`create_app()` constructs one FastAPI application, installs `SessionMiddleware`, mounts `/static`, serves Jinja pages and includes routers from `app/api/routes/*`. Legacy dashboard and `/api/*` endpoints are still declared directly in `app/main.py`.

## Route inventory summary

Static analysis found 113 declared HTTP operations.

### Page and legacy API routes in `app/main.py`

- `GET /health`
- `GET /`
- `GET /performance`
- `GET /api/config`
- `GET /api/market/{book}`
- `GET /api/balance`
- `GET /api/simulations`
- `GET /api/performance`
- `GET /api/positions`
- `POST /api/simulations/{simulation_id}/close`
- `POST /api/orders`

### Feature routers

- Strategy/backtesting: `/strategies`, `/backtests`, `/walk-forward`.
- Paper trading: `/paper/start`, `/paper/stop`, `/paper/status`, `/paper/portfolio`, `/paper/positions`, `/paper/orders`, `/paper/history`, `/paper/reset`.
- Markets router: `/markets`, `/market/{book}`, `/positions`, `/simulations/{simulation_id}/close`, `/orders`.
- Runtime: `/runtime/start`, `/runtime/stop`, `/runtime/status`, `/runtime/components`, `/runtime/config`.
- Market data: `/market/live/status`, `/market/live/provider`, `/market/live/ticker`, `/market/rfq/{book}`, `/market/live/orderbook`, `/market/live/candles`, `/market/live/trades`.
- Broker: `/broker/connect`, `/broker/disconnect`, `/broker/status`, `/broker/health`, `/broker/balance`, `/broker/positions`, `/broker/orders`.
- Analytics: `/analytics/summary`, `/analytics/performance`, `/analytics/equity`, `/analytics/drawdown`, `/analytics/strategies`, `/analytics/assets`, `/analytics/ai`, `/analytics/risk`, `/analytics/broker`, `/analytics/time`, `/analytics/trades`, `/analytics/events`, `/analytics/snapshot`.
- Optimization: `/optimization/grid`, `/optimization/random`, `/optimization`, `/optimization/{run_id}`, `/optimization/{run_id}/ranking`.
- AI: `/ai/evaluate`, `/ai/decision`, `/ai/explanation`, `/ai/confidence`.
- Live controls: `/live/status`, `/live/guards`, `/live/arm`, `/live/disarm`, `/live/validate`, `/live/audit`.
- System/readiness/auth/adaptive/research/burnin/experiments/validation routers provide additional status, reports and controls.

## Findings

1. There is duplicated conceptual surface: legacy `/api/orders` and router-level `/orders`; legacy `/api/positions` and router-level `/positions`; legacy `/api/market/{book}` and router-level `/market/{book}`.
2. Most legacy `/api/*` routes explicitly call `require_auth(request)`. Some non-legacy status routes are intentionally unauthenticated or rely on app context; this should be formalized before v3.
3. No `/api/v3/*` namespace exists yet.
4. Operation ID duplication could not be verified through live OpenAPI locally because FastAPI was not installed and package installation was blocked.

## Evidence commands

- Python static route extractor over `app/main.py` and `app/api/routes/*.py`.
- `rg -n "@(application|router)\.(get|post|put|delete|patch)|include_router" app -S`
