# Differences Against v3 Architecture Expectations

The exact v3 baseline audit specification could not be read locally because `origin/docs-v3-architecture` was unavailable and GitHub fetch was blocked. This gap analysis therefore compares the real v2 baseline to the v3 expectations described by the task: production-quality structure, clear API boundaries, persistence, runtime determinism, dashboard stability, capital consistency, market-provider discipline, security and CI reliability.

## Alignment already present

- Modular monolith direction is established with packages for runtime, brokers, market data, paper trading, strategies, AI, analytics, validation and system services.
- `LIVE_TRADING=false` is the default, and live-trading guard/audit code exists.
- Alembic migrations exist for the main persisted domains.
- Tests cover many pure-domain features and safety contracts.
- Dashboard v2 has auto-refresh and verified market assets.

## Gaps to close for v3

1. **API namespace**: no `/api/v3` route boundary exists; v3 should separate public health, authenticated dashboard APIs and internal/admin controls.
2. **Runtime determinism**: dynamic sizing and risk checks should share one deterministic contract before orders are attempted.
3. **Persistence**: runtime state, paper positions and strategy/AI decisions need durable storage or explicit volatile-state documentation.
4. **Capital ledger**: legacy simulated orders, paper trading and backtesting should share invariant definitions for cash, invested/locked capital, quantity, fees and P&L.
5. **Market data**: true historical candles and explicit cache TTLs are needed; ticker-derived candles are insufficient for v3-grade analytics.
6. **Dashboard**: global JavaScript coupling should be replaced by explicit modules/components or at least a tested client-state layer.
7. **CI**: full dependency-backed API/database tests must run in CI; local skip behavior should not mask failures.
8. **Security**: central auth policy, CSRF handling and headers should be documented and implemented.
9. **Models/migrations**: nullable fields and JSON blobs should be reviewed against domain invariants before v3 schema stabilization.
10. **Route duplication**: legacy `/api/*` and router-level equivalents should be consolidated or versioned.

## Recommended v3 acceptance gates

- Full pytest suite with dependencies installed and no unexpected skips.
- Ruff pass.
- Alembic migration validation against a fresh database.
- OpenAPI generation with no duplicate operation IDs.
- Simulation-mode integration proving no Bitso order call occurs.
- Capital invariant tests covering buy, sell, partial close, fees, realized/unrealized P&L and restart persistence.
- Dashboard smoke test covering markets, portfolio, capital, open/closed positions, P&L, history and auto-refresh.
