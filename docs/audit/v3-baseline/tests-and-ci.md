# Tests and CI Audit

## Test layout

The test suite covers pure units, API routes, database persistence, runtime, dashboard visual contracts, market data, capital, paper trading, brokers, live guards, analytics, optimization, validation, research, burn-in and RC1 integration.

## Local results

On this container, pure and import-available tests pass, while dependency-backed API/database tests are skipped when FastAPI/SQLAlchemy/Pydantic are unavailable.

- `python -m pytest -q --tb=short`: failed in the local v2 baseline with one runtime `NoneType` failure in `tests/test_runtime.py::test_runtime_cycle_market_strategy_ai_broker_portfolio_system`.
- `python -m ruff check .`: passed.
- `python -m pip install -q -r requirements.txt -r requirements-dev.txt`: failed because the configured network path to package index returned `CONNECT tunnel failed, response 403`.
- `python -m mypy app`: cannot be meaningfully validated without dependencies; when attempted in the earlier local environment it reported missing third-party imports and pre-existing type errors.

## CI workflow

`.github/workflows/v2-ci.yml` installs dependencies, runs pytest, publishes pytest output on PR failure, and stops after pytest failure.

## Findings

1. Unit test coverage is broad for pure code.
2. Local dependency isolation means API/database coverage can silently skip in constrained environments.
3. Baseline CI is not green locally because of the runtime `last_order` failure.
4. v3 should require a dependency-ready CI path that runs API/database tests without skips, plus a pure-unit fallback job if desired.
5. There is no explicit coverage threshold enforced locally in the observed command path.

## Evidence commands

- `python -m pytest -q --tb=short`
- `python -m ruff check .`
- `python -m pip install -q -r requirements.txt -r requirements-dev.txt`
- `sed -n '1,140p' .github/workflows/v2-ci.yml`
- `find tests -maxdepth 1 -type f | sort`
