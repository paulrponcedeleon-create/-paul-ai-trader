# v3 Baseline Audit

Branch: `audit-v3-baseline`
Base used: local merge commit `16d2697` (`Merge pull request #23 ... dashboard-auto-refresh-no-manual-button`), which is the latest local `v2-dashboard` equivalent available in this container.

## Scope and constraints

- Audit only; no production code, tests, config, migrations, workflows, templates or dependencies were modified.
- All generated artifacts are under `docs/audit/v3-baseline/`.
- No orders were placed and no external trading services were called.
- `git fetch --all --prune` and `git show origin/docs-v3-architecture:docs/v3/CODEX_PARALLEL_BASELINE_AUDIT.md` were attempted first, but the container had no configured remote initially and GitHub fetch was blocked by `CONNECT tunnel failed, response 403`; no local copy of the requested spec file existed.

## Documents

1. `repository-structure.md`
2. `api-routes.md`
3. `models-and-migrations.md`
4. `runtime.md`
5. `markets-and-bitso.md`
6. `capital-positions-fees-pnl.md`
7. `dashboard-and-javascript.md`
8. `tests-and-ci.md`
9. `security-and-configuration.md`
10. `technical-debt.md`
11. `v3-gap-analysis.md`
12. `inventory.json`

## High-level conclusion

The repository is a modular FastAPI monolith with substantial v2 surface area: dashboard, simulated orders, paper broker, runtime loop, market catalog, backtesting, optimization, analytics, validation, live-trading guards, and Alembic migrations. The strongest baseline properties are safe defaults (`LIVE_TRADING=false`), route-level session checks for legacy `/api/*` endpoints, broad pure-unit test coverage, and read-only market provider abstractions. The largest v3 gaps are duplicated legacy/new route surfaces, partially in-memory operational state, inconsistent persistence depth across subsystems, skipped dependency-backed tests in this environment, and incomplete alignment with a future `/api/v3` architecture.
