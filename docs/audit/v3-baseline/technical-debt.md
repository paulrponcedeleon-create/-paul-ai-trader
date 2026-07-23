# Technical Debt Audit

## Critical / CI-blocking

1. Runtime baseline test failure: autonomous buy cycles can leave `runtime.last_order` as `None` when dynamic amount is later rejected by risk.
2. Dependency-backed tests cannot run in this container because package installation is blocked; CI must run in an environment with dependencies.

## Architecture debt

1. Duplicate route concepts exist in `app/main.py` and `app/api/routes/markets.py`.
2. Runtime, paper broker and legacy simulated orders maintain separate state/persistence paths.
3. `app/runtime.py` remains a large orchestration file mixing discovery, sizing, decision conversion, execution and status serialization.
4. Dashboard JavaScript has global coupling and no JS lint/test harness.
5. Some caches are implicit or split across provider/service layers.

## Domain debt

1. Partial closes are absent in the baseline paper portfolio.
2. Runtime sell amount semantics are inconsistent with baseline paper broker full-close behavior.
3. Bitso-derived candles are synthetic from ticker data.
4. Multiple fee/P&L implementations require consolidation around one capital ledger invariant.
5. Persistence for runtime-managed paper positions is not guaranteed across process restart.

## Security/operations debt

1. Route auth policy is not expressed centrally.
2. CSRF protection is not visible for session-authenticated state-changing requests.
3. Security headers are not centralized.
4. Background runtime can be started by a status request when auto-start is enabled.
5. No local `.gitignore` in the baseline causes cache directories to appear as untracked files after test runs.

## Evidence commands

- `rg -n "TODO|FIXME|pass$|except Exception|require_auth|setInterval|global|window\." app tests docs -S`
- `python -m pytest -q --tb=short`
- `git status --short` after tests
