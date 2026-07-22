# Paul AI Trader v1

Aplicación web privada, optimizada para celular, que consulta mercados de Bitso, muestra señales transparentes y permite simulación controlada.

## Estado de seguridad

- `LIVE_TRADING=false` por defecto.
- No habilita retiros.
- No ejecuta operaciones reales salvo que se configure explícitamente.
- Toda orden pasa por límites deterministas de riesgo.
- Ninguna señal garantiza ganancias.

## Desplegar en Render

Render detecta `render.yaml`. También puedes configurar manualmente:

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

Variables privadas recomendadas:

- `APP_PASSWORD`
- `SESSION_SECRET`
- `BITSO_API_KEY`
- `BITSO_API_SECRET`

Mantén `LIVE_TRADING=false` durante pruebas.

## Ejecutar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000`.


## Readiness and data directory

`PAUL_DATA_DIR` defaults to `./data`. The `/ready` endpoint checks that the directory exists and is usable without creating it automatically. Historical CSV datasets are read from `PAUL_DATA_DIR/historical/`.

## RC1 validation

Install runtime and validation dependencies in a clean environment:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

Run local validation:

```bash
python -m compileall app tests migrations/versions
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
ruff check app tests
ruff format --check app tests
```

Apply database migrations before using persisted backtests:

```bash
alembic upgrade head
```

Strategy platform endpoints available in v0.2/RC1:

- `GET /strategies`
- `GET /strategies/{name}`
- `POST /backtests`
- `GET /backtests`
- `GET /backtests/{id}`
- `DELETE /backtests/{id}`
- `POST /walk-forward`

### Offline test groups

When infrastructure dependencies are unavailable, run the pure RC1 core checks with:

```bash
python -m pytest --collect-only
python -m pytest -m unit
python -m pytest -m "not api and not database"
```

Dependency-specific groups remain explicit:

```bash
python -m pytest -m api
python -m pytest -m database
```

`api` tests require FastAPI/Pydantic/TestClient. `database` tests require SQLAlchemy and, for migration validation, Alembic.

### v0.3 Research Optimization

The research optimization framework reuses the existing strategy factory and
backtest engine to run grid or seeded random searches across strategy parameter
spaces. Available REST endpoints are `POST /optimization/grid`,
`POST /optimization/random`, `GET /optimization`, `GET /optimization/{id}`, and
`GET /optimization/{id}/ranking`. The feature is for offline research only and
does not enable paper trading, live trading, Bitso Live, machine learning, or any
external execution.

### v0.4 Paper Trading

The paper trading engine runs strategy signals against simulated/local market
candles, keeps an in-memory portfolio, applies risk and position sizing rules,
and exposes `/paper/*` endpoints for start/stop/status/portfolio/history flows.
It is explicitly offline/simulated and does not enable live trading, Bitso Live,
AI, Telegram, Discord, or a new dashboard.

### v0.5 AI Decision Engine

The AI decision layer is deterministic and rule-based. It evaluates multiple
strategy signals, optimization results, historical metrics, paper-portfolio
state, and current indicators to produce explainable BUY/SELL/HOLD decisions via
`/ai/evaluate`, `/ai/decision`, `/ai/explanation`, and `/ai/confidence`. It does
not use LLMs, external services, machine learning, or live trading.

### v0.6 Broker Abstraction

The broker abstraction layer routes execution through `BrokerInterface` and
`ExecutionEngine`. With `LIVE_TRADING=false`, `BrokerFactory` selects `PaperBroker`
by default; `BitsoBroker` remains a safe stub that does not send real orders or
require real credentials. Broker endpoints are available under `/broker/*`.

### v0.7 Performance Analytics

The analytics layer summarizes performance, equity, drawdown, strategy/asset
attribution, AI attribution, risk attribution, broker analytics, time buckets,
trade details, snapshots, and monitoring events through `/analytics/*` endpoints.
It is read-only for trading state and never executes orders, connects Bitso, or
enables live trading.

### v0.8 Live Market Data (Read Only)

The live market data layer adds read-only market providers under `app.market_data`
for ticker, candles, order book, recent trades, spreads, volume, VWAP, cache,
internal events, and provider status. Endpoints are exposed under
`/market/live/*`. This layer never sends orders, never uses private API keys, and
does not enable live trading.

### v0.9 Controlled Live Trading Infrastructure

The controlled live trading layer prepares guarded infrastructure for future real
broker usage without enabling trading. `/live/*` endpoints only expose status,
guards, arming/disarming, validation and audit information; they do not execute
orders. `LIVE_TRADING=false` remains the default and explicit arming plus guard
checks are required before any future live broker action can be allowed.

### v1.0 Production Readiness

The production-readiness layer adds system health, watchdog, circuit breakers,
recovery orchestration, snapshots, observability events and metrics under
`app.system` and `/system/*`. It does not add strategies, brokers or trading
execution, and `LIVE_TRADING=false` remains the default.
