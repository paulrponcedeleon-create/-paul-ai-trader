# Repository Structure Audit

## Top-level inventory

- `app/`: application package and current production code.
- `app/main.py`: FastAPI app factory, root dashboard pages, legacy `/api/*` simulation endpoints, middleware and router registration.
- `app/api/routes/`: feature routers for runtime, markets, paper trading, analytics, optimization, live guards, system, auth, readiness and other modules.
- `app/templates/`: Jinja dashboards (`index.html`, `performance.html`).
- `app/static/`: JavaScript and CSS for dashboard, market panels, capital balance and performance pages.
- `app/db/`, `app/repositories/`, `migrations/`: SQLAlchemy models, repositories and Alembic migration chain.
- `app/runtime.py`: autonomous paper runtime orchestration.
- `app/brokers/`: broker abstraction, Bitso guarded implementation and paper broker.
- `app/market_data/`: read-only provider abstractions, mock provider, Bitso public provider, cache and websocket controller.
- `app/services/`: legacy service layer for Bitso, portfolio math, risk, simulations, market catalog, historical data and backtesting.
- `app/paper_trading/`: newer paper engine, portfolio, risk and sizing modules.
- `app/strategies/`, `app/ai/`, `app/analytics/`, `app/optimization/`, `app/validation/`, `app/adaptive/`, `app/burnin/`, `app/research/`, `app/system/`, `app/live/`: modular domain packages added during v2 evolution.
- `tests/`: unit, API and database tests; dependency-backed groups use `pytest.importorskip`.
- `.github/workflows/v2-ci.yml`: GitHub CI for the v2 branch.
- `requirements.txt`, `requirements-dev.txt`, `pyproject.toml`, `pytest.ini`, `render.yaml`, `render-v2.yaml`: dependency, lint, test and deploy configuration.

## Architecture observation

The codebase already moved beyond a single-file app into a modular monolith. However, the architecture is still transitional: legacy routes remain in `app/main.py` while newer routers live under `app/api/routes/`; similarly, simulated order persistence and paper-trading persistence coexist.

## Evidence commands

- `find . -maxdepth 3 -type f -not -path './.git/*' | sort`
- `rg -n "include_router|APIRouter|FastAPI|SessionMiddleware" app -S`
