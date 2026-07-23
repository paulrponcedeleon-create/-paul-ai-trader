# Paul AI Trader v3 — Architecture Decision Records

**Status:** Accepted for v3 design unless superseded  
**Scope:** Foundational decisions  
**Safety default:** `LIVE_TRADING=false`

This file consolidates the first architecture decision records. Each decision may later be split into an individual ADR file without changing its content or status.

---

# ADR-001 — Paper-trading-first safety model

**Status:** Accepted  
**Date:** 2026-07-23

## Context

The current product is being developed and validated through simulation. Trading logic, accounting, data quality, runtime behavior, and risk limits are still evolving. Real-money execution would magnify defects in any of these areas.

## Decision

Paul AI Trader v3 remains paper-trading-first.

- `LIVE_TRADING=false` is the default in every environment.
- Missing configuration fails closed.
- The first v3 API exposes paper-order commands only.
- Paper and future live portfolios use separate writable accounts and ledgers.
- A future live environment requires separate credentials, deployment controls, broker permissions, explicit approval, reconciliation, kill switch, and manual rollout.

## Consequences

### Positive

- Defects cannot place real orders by default.
- Accounting and risk behavior can be tested safely.
- Backtesting and paper trading share reusable domain logic.

### Negative

- Live-specific behavior remains unproven until a separate milestone.
- Some broker edge cases cannot be fully reproduced in simulation.

## Rejected alternatives

- Enabling live execution behind only one Boolean flag.
- Sharing the same portfolio/ledger between paper and live modes.
- Letting strategy code call the broker directly.

---

# ADR-002 — PostgreSQL production and SQLite test boundaries

**Status:** Accepted  
**Date:** 2026-07-23

## Context

The application must support durable transactions, fixed-precision arithmetic, constraints, migrations, and concurrent web/runtime access. SQLite is convenient locally but differs from PostgreSQL in locking, types, JSON behavior, constraints, and concurrency.

## Decision

- PostgreSQL is the production and staging database target.
- PostgreSQL integration tests validate migrations and accounting transaction behavior.
- SQLite may be used for focused local/unit tests only when behavior is known to be equivalent.
- Application code must not depend on SQLite-only behavior.
- Alembic migrations are the only supported production schema-change mechanism.

## Consequences

- CI requires at least one PostgreSQL job.
- Some tests run against both databases.
- JSONB, numeric precision, transaction isolation, and constraints are designed for PostgreSQL.

## Rejected alternatives

- SQLite in production.
- Maintaining unrelated schemas for SQLite and PostgreSQL.
- Creating tables implicitly at application startup in production.

---

# ADR-003 — Fixed-precision monetary arithmetic

**Status:** Accepted  
**Date:** 2026-07-23

## Context

Binary floating-point arithmetic can introduce rounding errors in capital, fees, quantities, cost basis, and P&L. Trading values also have venue-specific precision and minimums.

## Decision

- Use decimal-safe types throughout domain, API, persistence, and tests.
- Serialize monetary and quantity values as strings in JSON.
- Define rounding at explicit boundaries: venue validation, order sizing, fee calculation, and reporting.
- Never round intermediate accounting calculations merely for display.
- Store currency and precision context with monetary values.

## Consequences

- Conversion helpers and typed value objects are required.
- Existing float-based behavior must be characterized before migration.
- Frontend code must treat values as formatted decimal strings, not authoritative binary numbers.

## Rejected alternatives

- Using `float` and formatting to two decimals afterward.
- Rounding every operation to display precision.
- Assuming all assets use the same quantity precision.

---

# ADR-004 — Ledger as accounting source of truth

**Status:** Accepted  
**Date:** 2026-07-23

## Context

Cash, reserved cash, positions, fees, realized P&L, and equity can become inconsistent when stored and updated independently. A durable accounting model is required to reconcile every business event.

## Decision

- Immutable ledger entries are the accounting source of truth.
- Fills, fees, deposits, withdrawals, and adjustments create balanced ledger transactions.
- Positions and balances may be materialized for performance but must be rebuildable.
- Corrections use compensating transactions.
- A fill and its accounting effects commit atomically.

## Consequences

- Migration requires an explicit opening-balance/reconciliation process.
- Read models need rebuild and validation tooling.
- Accounting tests become central to CI.

## Rejected alternatives

- Treating the dashboard balance as authoritative.
- Updating a single mutable cash column without transaction history.
- Deleting or rewriting historical fills to correct mistakes.

---

# ADR-005 — Broker-neutral execution gateway

**Status:** Accepted  
**Date:** 2026-07-23

## Context

The current project is connected to Bitso, but future providers may include other crypto exchanges or brokerage services. Strategy, risk, and portfolio code must not depend on Bitso-specific symbols or responses.

## Decision

Define a broker-neutral gateway with normalized capabilities, balances, order previews, submissions, cancellations, and status retrieval.

- Bitso-specific logic remains inside an adapter.
- Domain objects use canonical market and order types.
- Provider payloads are normalized at the infrastructure boundary.
- Capability checks occur before order construction.
- Paper execution implements the same gateway semantics where practical.

## Consequences

- Adapter contract tests are required.
- Provider-specific features may not be exposed until represented explicitly.
- The domain remains portable and testable without network access.

## Rejected alternatives

- Passing raw Bitso JSON throughout the application.
- Embedding provider symbols in strategy rules.
- Creating separate trading logic per broker.

---

# ADR-006 — Strategy and risk-rule versioning

**Status:** Accepted  
**Date:** 2026-07-23

## Context

A score or risk decision is not reproducible if parameters can change without preserving the version used. Performance comparisons also become misleading when historical trades are evaluated against current settings.

## Decision

- Every analysis references an immutable strategy version.
- Every risk decision references an immutable risk-policy version.
- Versions include complete non-secret configuration and a checksum.
- Active versions may change only through an audited activation process.
- Historical analyses and decisions continue to reference their original versions.

## Consequences

- Configuration is treated as data, not mutable global state.
- Backtests and paper results can be compared by version.
- Version lifecycle tooling is required.

## Rejected alternatives

- Overwriting one global parameter file.
- Recording only a human-readable strategy name.
- Allowing autonomous learning to mutate production weights in place.

---

# ADR-007 — Runtime idempotency and durable cycle state

**Status:** Accepted  
**Date:** 2026-07-23

## Context

Render restarts, retries, timeouts, duplicate scheduler triggers, and transient failures can cause the same runtime work to execute more than once. Duplicate financial actions are unacceptable even in paper mode.

## Decision

- Each runtime cycle has a durable unique cycle key.
- Each command/order has a separate idempotency key.
- Cycle state and events are persisted.
- Retries resume or reconcile existing intent instead of blindly repeating it.
- Duplicate analysis may be tolerated only when it cannot create duplicate orders and is identified as duplicate.
- External order reconciliation uses client order ID.

## Consequences

- Runtime orchestration requires explicit states.
- Failure recovery is more complex but deterministic.
- Tests must simulate process interruption and retry.

## Rejected alternatives

- Relying only on in-memory locks.
- Assuming one web worker or one scheduler forever.
- Retrying broker submission without checking prior intent.

---

# ADR-008 — Canonical market identification and verified capabilities

**Status:** Accepted  
**Date:** 2026-07-23

## Context

An asset may exist without a specific tradeable pair being supported. Symbols vary by provider, and display labels are not reliable identifiers. Previously requested assets such as ATOM or PAXG require actual venue verification.

## Decision

A market is identified by:

```text
venue + base asset + quote asset + market type
```

The market catalog stores the exact provider symbol and verified capabilities.

- Only verified active markets may be used for ordering.
- Display symbols are UI labels only.
- Provider discovery does not automatically enable a market.
- Minimums, precision, order types, and verification timestamp are stored.

## Consequences

- Market onboarding is explicit and auditable.
- Unsupported pair errors become clear.
- Strategy analysis can include markets not enabled for ordering, but the distinction is explicit.

## Rejected alternatives

- Inferring `ASSET_MXN` for every known asset.
- Using one symbol string as the primary identity across providers.
- Hiding unsupported markets by silently substituting another pair.

---

# ADR-009 — Dashboard query/read model

**Status:** Accepted  
**Date:** 2026-07-23

## Context

The dashboard requires fast summaries and charts, but JavaScript calculations can diverge from backend accounting. Repeated polling can also duplicate work and cause flicker.

## Decision

- Dashboard endpoints return authoritative read models.
- JavaScript formats and renders values but does not calculate authoritative capital or P&L.
- Open positions and completed trade history use separate queries.
- Recent history defaults to the last ten completed trades.
- Auto-refresh is endpoint-specific and avoids overlapping requests.
- Read models may be materialized but must identify valuation timestamp and quality.

## Consequences

- Backend query services become a formal module.
- UI behavior is easier to test.
- Performance tuning can occur without changing accounting semantics.

## Rejected alternatives

- Reconstructing portfolio totals in the browser.
- Full-page reloads on every quote refresh.
- One endpoint returning unrelated unbounded data.

---

# ADR-010 — Backtesting reuses production domain logic

**Status:** Accepted  
**Date:** 2026-07-23

## Context

A backtest is misleading when it uses different indicators, risk rules, execution assumptions, or accounting than paper trading. Separate implementations drift over time.

## Decision

Backtesting reuses:

- normalized market data,
- feature/indicator engine,
- regime classification,
- strategy evaluation,
- risk engine,
- paper execution model,
- ledger and position accounting,
- performance metrics.

Infrastructure differences are injected through a simulated clock, historical data source, and deterministic execution policy.

## Consequences

- Domain modules must not depend on wall-clock time or network access.
- Historical datasets and parameter versions are checksummed.
- Bias controls and execution assumptions are explicit.

## Rejected alternatives

- A separate notebook implementation as the official backtester.
- Using future candle information.
- Ignoring fees and slippage by default.

---

# ADR-011 — Explainable rules before self-modifying machine learning

**Status:** Accepted  
**Date:** 2026-07-23

## Context

The project aims to become more intelligent, but autonomous parameter mutation can make decisions irreproducible and can optimize noise. The current dataset and operational controls are not yet sufficient for unrestricted online learning.

## Decision

- v3 prioritizes explainable features, regime classification, weighted evidence, score, and confidence.
- Every decision records positive and negative contributions.
- Learning analytics may recommend parameter changes but cannot activate them automatically.
- Any statistical or ML model is versioned, validated out of sample, and compared against a baseline.
- Production activation remains an explicit audited action.

## Consequences

- Intelligence grows incrementally and remains reviewable.
- The system can explain why it bought, sold, held, or rejected a trade.
- Self-modifying optimization is deferred.

## Rejected alternatives

- Automatically increasing indicator weights after every profitable trade.
- Deploying an opaque model without attribution.
- Treating correlation as causation from a small sample.

---

# ADR-012 — Separate future live-trading environment

**Status:** Accepted  
**Date:** 2026-07-23

## Context

A future live mode has materially different security, operational, reconciliation, and incident-response requirements. A simple mode switch inside the same deployment would create unacceptable blast radius.

## Decision

A future live environment must be separately deployed and controlled.

Required controls before any live pilot:

- separate service/environment,
- separate database or strictly isolated writable schema and accounts,
- separate credentials with minimum permissions,
- withdrawals disabled,
- explicit market allowlist,
- maximum order and daily-loss limits,
- manual activation and kill switch,
- broker reconciliation,
- alerting and audit retention,
- rollback and incident runbook,
- owner approval recorded outside the runtime process.

The simulation deployment cannot enable live trading through a dashboard toggle.

## Consequences

- Live rollout costs more operationally.
- Simulation remains safe and independent.
- Live readiness can be reviewed as a distinct project gate.

## Rejected alternatives

- Reusing read-only or simulation credentials and changing permissions in place.
- A single environment variable as the only control.
- Sharing the paper ledger with real balances.

---

# Decision governance

## Adding or changing a decision

A new ADR must include:

1. Context and problem.
2. Decision.
3. Positive and negative consequences.
4. Alternatives considered.
5. Migration impact.
6. Security and testing impact where relevant.

Accepted ADRs are never edited to disguise a changed decision. A superseding ADR references the previous record and explains the change.

## Implementation alignment

A code change that contradicts an accepted ADR must either:

- be rejected,
- include an approved superseding ADR,
- or be explicitly marked as a temporary migration exception with an owner and removal criterion.

## Current open ADR candidates

The repository audit should determine whether additional decisions are needed for:

- web/runtime worker topology on Render,
- scheduler ownership and distributed locking,
- caching technology and invalidation,
- stock-market data provider,
- FIFO versus another lot policy,
- fee-currency conversion,
- event delivery/outbox pattern,
- retention and archival implementation,
- frontend architecture beyond the current server-rendered dashboard.