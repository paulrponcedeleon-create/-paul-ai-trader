# Paul AI Trader v3 — Implementation Plan

**Status:** Working execution plan  
**Base branch:** `v2-dashboard`  
**Safety default:** `LIVE_TRADING=false`

---

## 1. Purpose

This plan converts the v3 architecture into small, testable, reversible implementation increments. It is intentionally designed to prevent a large rewrite, uncontrolled Codex changes, or a single pull request that mixes accounting, runtime, API, UI, and infrastructure changes.

The plan begins only after the v2 stabilization work has completed and the repository baseline audit has documented the current system.

---

## 2. Non-negotiable execution rules

1. Do not enable live trading.
2. Do not weaken or delete tests merely to obtain green CI.
3. Do not combine unrelated refactors and features in one PR.
4. Do not change accounting semantics without characterization tests and explicit documentation.
5. Do not move modules only for aesthetics; each move must reduce a known coupling or enable a defined contract.
6. Keep deployed v2 behavior working while v3 components are introduced behind adapters or new routes.
7. Each PR must have a rollback path.
8. Database changes require Alembic migrations and PostgreSQL validation.
9. External services are mocked or safely recorded in CI; no test places a real order.
10. Codex must stop and report rather than guess when repository evidence contradicts the specification.

---

## 3. Required inputs before implementation

The following must exist:

- green or explicitly baselined CI on `v2-dashboard`,
- repository audit under `docs/audit/v3-baseline/`,
- route and operation-ID inventory,
- model/table/migration inventory,
- current source of paper capital and positions,
- current fee and P&L definitions,
- current Runtime scheduling/concurrency behavior,
- verified market catalog and provider behavior,
- current Render deployment topology,
- confirmed test commands.

Unresolved facts are logged as blockers, not filled with assumptions.

---

## 4. Branch and pull-request strategy

Recommended branch families:

```text
v3-foundation/types-and-errors
v3-foundation/accounting-characterization
v3-foundation/market-contracts
v3-foundation/runtime-state
v3-foundation/paper-order-idempotency
v3-foundation/query-services
v3-dashboard/portfolio-panels
v3-risk/policy-engine
v3-backtest/core
```

Rules:

- Branch from the latest accepted `v2-dashboard` or subsequent agreed integration branch.
- Rebase or merge the base before final review.
- One logical objective per PR.
- Prefer fewer than 500 changed implementation lines per PR when practical; generated migrations and tests are excluded from this guidance.
- Large mechanical moves are isolated from behavior changes.
- Draft PRs are opened early for visibility.

---

## 5. Commit standard

Each commit must be independently understandable and preserve a usable repository state when practical.

Examples:

```text
test(accounting): characterize current paper balance behavior
feat(domain): add decimal money and quantity value objects
fix(api): enforce unique operation identifiers
feat(orders): persist paper-order idempotency keys
refactor(runtime): isolate cycle orchestration from market analysis
feat(risk): add deterministic order-notional limits
feat(query): expose authoritative portfolio summary
perf(markets): deduplicate quote polling
migrate(db): add immutable ledger transaction tables
docs(v3): record FIFO lot-accounting decision
```

Avoid:

```text
updates
fix stuff
final changes
all improvements
```

---

# Phase 0 — Stabilize and characterize v2

## Objective

Create a trustworthy baseline before introducing v3 semantics.

## Work packages

### 0.1 CI stabilization

- Reproduce every failing test.
- Classify failures as implementation defect, stale test, environment issue, migration issue, or nondeterminism.
- Fix root causes.
- Record intentionally changed behavior.
- Remove duplicate FastAPI operation IDs.
- Ensure clean-database migration tests.

### 0.2 Accounting characterization

Add tests describing current behavior for:

- initial capital,
- available capital,
- buy validation,
- open position valuation,
- position close,
- realized P&L,
- unrealized P&L,
- fees,
- recent trade history,
- insufficient funds.

Characterization does not imply current behavior is correct; it makes changes visible.

### 0.3 Runtime characterization

- Identify trigger and scheduling model.
- Test one complete cycle with fake providers.
- Test provider failure, empty data, malformed data, and duplicate trigger behavior.
- Eliminate known `NoneType` paths.
- Document mutable global state and worker assumptions.

### 0.4 Baseline gate

Phase 0 is complete only when:

- CI is green,
- required tests run from a clean checkout,
- no real orders are possible,
- current capital/P&L behavior is documented,
- the audit is complete,
- unresolved defects have issues and owners.

---

# Phase 1 — Domain primitives and error contracts

## Objective

Introduce shared safe primitives without changing deployed behavior.

## Deliverables

- `Money`, `Quantity`, `Price`, `Rate`, and currency-aware value objects.
- Explicit rounding policies.
- Stable domain error codes.
- Clock and identifier abstractions.
- Canonical market identifier.
- Unit tests for precision and validation.

## Migration approach

- Introduce adapters around existing float/number inputs.
- Use new types first in newly created v3 services.
- Do not convert every legacy path in one PR.

## Acceptance criteria

- Decimal round-trip tests pass.
- JSON serialization uses strings.
- No authoritative new calculation uses binary float.
- Existing v2 endpoints still pass characterization tests.

---

# Phase 2 — Canonical market catalog and provider contracts

## Objective

Separate verified tradeable markets from generic asset names.

## Deliverables

- Venue, Asset, and Market domain models.
- Canonical market IDs.
- Verified provider symbol/capability mapping.
- Normalized quote and candle contracts.
- Market-data freshness and quality states.
- Bitso adapter contract tests.
- Unsupported/unverified market errors.

## Acceptance criteria

- BTC, ETH, SOL, XRP, ATOM, PAXG, and any other requested assets are shown only where provider support is verified.
- The application never invents a pair from an asset symbol.
- Stale market data blocks new paper orders.
- Provider payloads do not leak into domain services.

---

# Phase 3 — Canonical paper-order state and idempotency

## Objective

Make paper order processing broker-like, deterministic, and retry-safe.

## Deliverables

- Canonical Order and Fill entities.
- Order state machine and append-only events.
- Persistent client order/idempotency keys.
- Deterministic paper execution policy.
- Fee and slippage interfaces.
- Capital/quantity reservation lifecycle.
- Duplicate-submit and retry tests.

## Suggested PR sequence

1. Order/fill models and migrations.
2. State-machine service and tests.
3. Idempotency persistence.
4. Paper execution adapter.
5. Compatibility adapter from existing paper-order endpoint.

## Acceptance criteria

- Same idempotency key and payload returns the same result.
- Same key with different payload is rejected.
- A fill cannot post twice.
- Cancellation releases reservations.
- Restart/retry cannot duplicate an order.

---

# Phase 4 — Ledger and position accounting

## Objective

Create one reconcilable source of truth for cash, positions, fees, and P&L.

## Prerequisite decisions

- Lot policy, initially FIFO unless the audit identifies an intentional different policy.
- Fee allocation policy.
- Opening-balance migration method.
- Base-currency conversion behavior.

## Deliverables

- Portfolios and accounts.
- Ledger transactions and entries.
- Position lots.
- Rebuildable balance and position projections.
- Opening-balance migration.
- Reconciliation command/report.
- Dual-calculation comparison against v2.

## Required invariants

```text
available_cash = cash_balance - reserved_cash
position_quantity = sum(open lot remaining quantities)
portfolio_equity = cash + reserved cash + marked position value
realized P&L reconciles to closed lots and fees
```

## Rollout

1. Write v3 accounting in shadow mode from existing simulated events.
2. Compare v2 and v3 values and classify every difference.
3. Correct migration/data defects.
4. Switch read endpoints to v3 query services.
5. Switch write path only after reconciliation is stable.

## Acceptance criteria

- Every fill produces atomic accounting entries.
- Ledger rebuild reproduces balances and positions.
- Partial closes reconcile.
- Fees are visible and included according to documented formulas.
- No unexplained equity difference remains.

---

# Phase 5 — Analysis and explainability contracts

## Objective

Turn the current score into a reproducible, versioned analytical decision.

## Deliverables

- Normalized feature definitions and lookback metadata.
- Market regime classifier.
- Strategy versions and checksums.
- Signal decision with separate score and confidence.
- Positive/negative contribution records.
- Data-quality state.
- Five-level dashboard mapping.

## Initial five-level policy

The mapping must be configurable. A candidate baseline:

```text
BLUE    exceptional validated favorable state
GREEN   favorable
YELLOW  neutral / wait
ORANGE  unfavorable / reduce
RED     invalid, blocked, or high risk
```

Blue must not simply mean “higher than green” without stronger quality/confidence requirements.

## Acceptance criteria

- Same inputs and strategy version reproduce the same result.
- Missing history yields an invalid/degraded decision, not fabricated indicators.
- Every signal includes an explanation.
- Score and confidence are displayed separately.

---

# Phase 6 — Deterministic Risk Engine

## Objective

Move final trade authorization out of strategy and UI code.

## Deliverables

- Versioned risk policy.
- Rule interface and ordered evaluation.
- `APPROVE`, `REDUCE`, `REJECT` decisions.
- Maximum order notional.
- Maximum exposure per asset and portfolio.
- Minimum remaining cash.
- Maximum daily realized loss.
- Maximum drawdown.
- Maximum open positions.
- Data freshness and liquidity blocks.
- Cooldown policy.
- Risk status read model.

## Acceptance criteria

- Signal code cannot submit an order directly.
- Every automatic or manual paper order has an immutable risk decision.
- Rejected orders create no fill or accounting mutation.
- Current risk usage is visible in the dashboard.
- Limits are deterministic and tested at boundaries.

---

# Phase 7 — Runtime orchestration and recovery

## Objective

Create an observable, idempotent execution cycle safe under restarts.

## Deliverables

- Runtime cycle and event persistence.
- Unique cycle key.
- Explicit states and failure reasons.
- Dependency health/freshness checks.
- Safe retry/reconciliation.
- Analysis-only mode.
- Pause/resume controls.
- No overlapping cycle execution for the same scope.

## Acceptance criteria

- Duplicate triggers do not duplicate paper orders.
- Process restart can reconcile in-progress intent.
- Provider outage degrades or skips safely.
- Runtime health exposes last successful cycle and failure reason.
- Logs contain request/cycle/order correlation IDs and no secrets.

---

# Phase 8 — v3 query services and API

## Objective

Expose authoritative read models and safe commands under `/api/v3`.

## Deliverables

- Standard response/error envelopes.
- Unique operation IDs.
- System status.
- Market catalog, quotes, candles, ranking.
- Portfolio summary, positions, trades, ledger.
- Paper order preview/create/cancel/close.
- Risk status.
- Performance summary and curves.
- Runtime cycle views.
- OpenAPI and contract tests.

## Acceptance criteria

- Browser does not calculate authoritative accounting.
- Decimal values serialize as strings.
- Commands require idempotency and CSRF where applicable.
- Live order routes are absent.
- Existing v2 routes remain until migrated consumers are verified.

---

# Phase 9 — Dashboard migration

## Objective

Move the UI to stable v3 read models without a full frontend rewrite.

## Panel order

1. Mode and health.
2. Market selector and quote freshness.
3. Ranking with automatic book change refresh.
4. Available capital and equity.
5. Open positions only.
6. Last ten completed trades.
7. Day/week/month/all-time P&L.
8. Asset filters.
9. Equity and drawdown curves.
10. Risk utilization and blocks.

## Frontend rules

- One polling owner per data resource.
- Abort or ignore superseded requests.
- No overlapping timer loops.
- Display loading, stale, degraded, and error states distinctly.
- Preserve last good data with visible age when appropriate.
- Never hide a rejected order reason.

## Acceptance criteria

- Changing a selected book refreshes automatically.
- No manual “Actualizar ahora” dependency.
- No visible full-page flicker.
- Portfolio contains only open positions.
- History shows the latest ten completed trades by default.
- Capital and P&L match backend query results exactly.

---

# Phase 10 — Performance analytics

## Objective

Provide professional metrics with correct definitions and sample warnings.

## Deliverables

- Equity curve.
- Drawdown curve.
- Daily, weekly, monthly, and total P&L.
- Gross profit/loss.
- Net P&L after fees.
- Win rate.
- Expectancy.
- Profit factor.
- Maximum drawdown.
- Sharpe/Calmar only when sample and frequency definitions are valid.
- Asset and multi-asset filters.

## Acceptance criteria

- Every metric documents its formula version.
- Metrics return `null` with reason when samples are insufficient.
- Period boundaries use explicit timezone policy.
- Filtered values reconcile to underlying trades and ledger.

---

# Phase 11 — Backtesting foundation

## Objective

Reuse production domain logic over historical data without look-ahead bias.

## Deliverables

- Simulated clock.
- Historical candle source.
- Backtest run configuration and checksum.
- Reused feature, strategy, risk, paper execution, ledger, and metrics.
- Fee/slippage assumptions.
- Trade log and report.
- Walk-forward or train/validation/test separation for any parameter evaluation.

## Acceptance criteria

- No future candle data is visible to a decision.
- Same configuration and dataset checksum reproduce results.
- Fees and slippage are non-zero by default unless explicitly overridden.
- Backtests never call Bitso order APIs.

---

# Phase 12 — Learning analytics, not autonomous mutation

## Objective

Measure which strategy evidence works under which conditions without allowing uncontrolled self-modification.

## Deliverables

- Outcome attribution by strategy version, feature, market, regime, and horizon.
- Confidence calibration analysis.
- False-positive/false-negative analysis.
- Parameter recommendations.
- Approval workflow for a new strategy version.

## Acceptance criteria

- Historical results never rewrite the active strategy automatically.
- Recommendations identify sample size and uncertainty.
- New versions require backtest, paper validation, and explicit activation.

---

# Phase 13 — Live-readiness project gate

This phase does not enable live trading. It determines whether a separate live pilot may be designed.

Required evidence:

- stable paper runtime over an agreed period,
- reconciled accounting,
- broker adapter reconciliation tests,
- risk limits and kill switch,
- security review,
- separate deployment/database/credentials plan,
- alerting and incident runbook,
- owner approval.

A live pilot requires a separate architecture decision and implementation plan.

---

## 6. CI matrix target

Recommended checks:

```text
format/lint
static type checking
unit tests
SQLite focused compatibility tests
PostgreSQL integration tests
Alembic upgrade from clean DB
Alembic upgrade from supported prior schema
API/OpenAPI contract tests
secret scan
dependency vulnerability scan
startup smoke test
paper-order safety test
no-live-routes assertion
```

CI must fail when:

- an operation ID is duplicated,
- a migration is missing,
- secrets are detected,
- live trading defaults true,
- a real broker submission is attempted in tests,
- accounting invariants fail.

---

## 7. Pull-request template for v3 work

```markdown
## Objective

## Current behavior characterized

## Changes

## Explicitly unchanged

- LIVE_TRADING remains false
- No real orders

## Data/migration impact

## API impact

## Security impact

## Tests run

## Reconciliation evidence

## Rollback plan

## Remaining risks
```

---

## 8. Codex execution protocol

For each implementation assignment, Codex must:

1. Fetch and read the current architecture, data model, API contracts, ADRs, audit, and relevant source files.
2. Confirm the current base commit and create a dedicated branch.
3. State the exact scoped objective internally and avoid unrelated cleanup.
4. Add or update tests before or with behavior changes.
5. Run the smallest relevant test set after each logical change.
6. Run the full required suite before opening the PR.
7. Make professional logical commits.
8. Open a draft PR with evidence and known risks.
9. Never merge.
10. Report any specification conflict instead of silently choosing.

Codex must not be assigned two overlapping write tasks against the same modules at the same time.

---

## 9. Progress tracking

Each phase uses one status:

```text
NOT_STARTED
AUDIT_REQUIRED
BLOCKED
IN_PROGRESS
IN_REVIEW
VALIDATED
ROLLED_OUT
```

A phase is not `VALIDATED` because code exists; all acceptance criteria and CI gates must pass.

Recommended tracking table:

| Phase | Status | PRs | Evidence | Blockers |
|---|---|---|---|---|
| 0 Baseline | IN_PROGRESS | — | CI/audit | Current stabilization |
| 1 Domain primitives | NOT_STARTED | — | — | Phase 0 |
| 2 Markets | NOT_STARTED | — | — | Audit/provider evidence |
| 3 Orders | NOT_STARTED | — | — | Phase 1–2 |
| 4 Ledger | NOT_STARTED | — | — | Accounting decisions |
| 5 Analysis | NOT_STARTED | — | — | Historical data contract |
| 6 Risk | NOT_STARTED | — | — | Portfolio/accounting |
| 7 Runtime | NOT_STARTED | — | — | State inventory |
| 8 API | NOT_STARTED | — | — | Query/services |
| 9 Dashboard | NOT_STARTED | — | — | v3 API |
| 10 Metrics | NOT_STARTED | — | — | Ledger/snapshots |
| 11 Backtest | NOT_STARTED | — | — | Domain maturity |
| 12 Learning | NOT_STARTED | — | — | Sufficient outcomes |
| 13 Live review | BLOCKED | — | — | Owner approval and all prior gates |

---

## 10. Final definition of success

The v3 foundation succeeds when:

- CI remains green through incremental migration,
- paper trading is deterministic and retry-safe,
- capital, positions, fees, and P&L reconcile from immutable accounting events,
- markets are provider-verified,
- score, confidence, signal, risk, and execution are separate,
- every decision is explainable and versioned,
- dashboard values come from authoritative read models,
- backtesting reuses production domain logic,
- architecture documentation matches implementation,
- live trading remains disabled.