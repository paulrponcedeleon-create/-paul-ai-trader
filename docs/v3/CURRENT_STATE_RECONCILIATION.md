# Paul AI Trader v3 — Current-State Reconciliation

**Status:** Evidence-backed reconciliation  
**Current baseline:** `v2-dashboard` after baseline audit and RC1 settings hotfix  
**Target:** Paul AI Trader v3  
**Safety invariant:** `LIVE_TRADING=false`

---

## 1. Purpose

This document reconciles the target v3 specifications with the repository baseline audited under `docs/audit/v3-baseline/`. The audit is authoritative for current-state facts; the v3 documents define the intended target state.

This reconciliation does not claim that target features already exist. It identifies what is already aligned, what remains incomplete, and the implementation order required to close the gaps safely.

---

## 2. Baseline conclusions

The current repository already provides a useful modular-monolith foundation:

- packages exist for runtime, brokers, market data, paper trading, strategies, AI, analytics, validation, and system services;
- `LIVE_TRADING=false` remains the default;
- live-trading guards and audit-oriented controls exist;
- SQLAlchemy and Alembic are present for persisted domains;
- dashboard auto-refresh and a verified market catalog are present;
- the test suite covers many domain and safety behaviors.

The repository is therefore not a rewrite candidate. Migration to v3 must be incremental and must preserve working simulation behavior.

---

## 3. Confirmed gaps and architectural response

### 3.1 API namespace and duplicated routes

**Current fact:** legacy route concepts in `app/main.py` overlap with router-level APIs.

**Target response:**

- introduce `/api/v3` incrementally;
- maintain compatibility adapters for existing dashboard calls during migration;
- give every route a unique explicit `operation_id`;
- consolidate duplicated route ownership before removing legacy paths;
- do not perform a single large route rewrite.

**Acceptance evidence:** OpenAPI generation produces no duplicate operation-ID warnings and compatibility tests pass.

### 3.2 Runtime determinism

**Current fact:** runtime orchestration mixes discovery, sizing, conversion, execution, and status serialization; a baseline failure showed `last_order` may remain `None` after a dynamically sized order is rejected by risk.

**Target response:**

- define one immutable cycle input snapshot;
- separate decision, sizing, risk authorization, execution, and status recording;
- make rejected/no-order outcomes explicit rather than representing them as missing state;
- persist cycle outcome and reason codes;
- add deterministic tests using a fixed clock, fixed provider data, and fixed configuration.

**Acceptance evidence:** identical inputs produce identical cycle results, including explicit `NO_ORDER` or `REJECTED` outcomes.

### 3.3 Persistence boundaries

**Current fact:** runtime state, paper positions, and strategy/AI decisions do not share one durable persistence model; restart persistence is not guaranteed for runtime-managed positions.

**Target response:**

- repositories and unit-of-work boundaries become authoritative;
- runtime cycles, analyses, risk decisions, orders, fills, ledger entries, and position snapshots receive explicit persistence contracts;
- volatile state must be documented when intentionally non-durable;
- schema changes require Alembic migrations and fresh-database validation.

**Acceptance evidence:** restart tests reconstruct paper cash, positions, fees, realized P&L, and open-order reservations from persisted records.

### 3.4 Capital, fees, positions, and P&L

**Current fact:** legacy simulation, paper trading, and backtesting contain separate accounting implementations; partial-close behavior is incomplete and sell semantics are inconsistent.

**Target response:**

- establish one decimal-safe accounting domain and ledger invariant;
- define cash, reserved cash, available cash, cost basis, fees, realized P&L, unrealized P&L, and equity once;
- make paper trading and backtesting reuse the same accounting rules;
- support partial closes explicitly;
- record every adjustment as a typed ledger entry.

**Acceptance evidence:** invariant tests cover buy, sell, partial close, fees, insufficient funds, rejection, restart persistence, and reconciliation.

### 3.5 Market data quality

**Current fact:** current Bitso-derived candles may be synthetic from ticker data; cache behavior is split or implicit.

**Target response:**

- introduce an explicit historical-candle provider contract;
- distinguish true exchange candles from synthetic/test data;
- persist source, timeframe, event time, received time, finality, and quality flags;
- make cache TTL, stale thresholds, retries, and provider capabilities explicit;
- block tradeable recommendations when required market data is invalid or stale.

**Acceptance evidence:** provider contract tests validate normalization, freshness, missing data, ordering, and unsupported markets.

### 3.6 Dashboard and JavaScript

**Current fact:** dashboard JavaScript is globally coupled and lacks a dedicated lint/test harness.

**Target response:**

- keep authoritative accounting calculations server-side;
- split client behavior by panel or feature;
- centralize polling ownership so one endpoint has one refresh loop;
- add client-state and smoke tests for markets, portfolio, capital, P&L, history, and automatic refresh;
- retain the requirement that portfolio shows only open positions and history shows the most recent ten completed trades.

**Acceptance evidence:** dashboard smoke tests verify rendering, refresh cadence, stale/error states, and absence of a manual refresh dependency.

### 3.7 CI reliability

**Current fact:** dependency-backed API/database tests must run in CI and local skips must not hide failures. The RC1 fixture mismatch has been corrected separately.

**Target response:**

Required CI gates:

1. formatting and Ruff;
2. type checks for agreed modules;
3. full pytest suite with required dependencies;
4. migration validation on a fresh database;
5. OpenAPI generation and duplicate-operation-ID validation;
6. secret and dependency scans;
7. startup/health/readiness smoke tests;
8. simulation integration proving no Bitso order submission when `LIVE_TRADING=false`.

### 3.8 Security and operations

**Current fact:** authentication policy is not centrally expressed, CSRF protection is not visible for session-authenticated mutations, and security headers are not centralized. Runtime auto-start may be triggered by a status request.

**Target response:**

- create a central route-auth policy and consistent dependencies;
- define CSRF protection for state-changing session-authenticated requests;
- centralize security headers and cookie policy;
- separate health/status reads from runtime-start commands;
- preserve fail-closed configuration behavior;
- keep live credentials and any future live environment isolated.

**Acceptance evidence:** unauthorized, unauthenticated, CSRF-invalid, and simulation/live-boundary tests pass.

### 3.9 Models and migrations

**Current fact:** nullable fields and JSON blobs require review against domain invariants.

**Target response:**

- classify fields as required, optional, derived, or append-only;
- replace unstructured JSON where querying or invariants require typed columns;
- version strategy, feature, risk-policy, and schema contracts;
- document indexes, uniqueness, idempotency keys, and retention policies.

---

## 4. Resolved architecture questions

The audit resolves these earlier open questions:

1. **Paper cash and position authority:** no single authoritative path currently exists across legacy simulation, paper trading, and runtime; v3 must establish the ledger as authority.
2. **Database capability:** SQLAlchemy and Alembic exist, but persistence coverage is uneven and migration validation must be strengthened.
3. **Historical market data:** current ticker-derived synthetic candles are insufficient for v3 analytics; a real candle provider contract is required.
4. **Runtime topology:** runtime orchestration is currently concentrated and partially volatile; explicit cycle contracts and persistence are required.
5. **Fee and P&L authority:** multiple implementations exist and must converge on one accounting domain.
6. **Dashboard state:** the dashboard has working auto-refresh but global client coupling must be reduced.
7. **Security boundary:** safe defaults exist, but auth policy, CSRF, headers, and status/start separation require implementation.

Questions still requiring deployment-specific evidence:

- Render worker/process topology and resource limits;
- final retention periods for candles, analysis records, runtime events, and audit entries;
- exact external provider used for stock symbols and its delay/licensing behavior;
- supported Bitso historical-candle coverage and rate limits in the deployed account/environment.

---

## 5. Prioritized implementation sequence

### Gate 0 — Green baseline

- all tests pass;
- no duplicate operation IDs;
- migrations validate on a clean database;
- no real-order call is possible in simulation mode.

### Gate 1 — Accounting foundation

- decimal-safe money and quantities;
- canonical ledger entries;
- unified fee and P&L calculations;
- partial-close support;
- restart reconciliation.

### Gate 2 — Market and analysis contracts

- normalized market identifiers;
- real historical-candle provider interface;
- explicit freshness and quality;
- versioned features, score, confidence, and explanations.

### Gate 3 — Deterministic Risk Engine and Runtime

- explicit risk decisions and reason codes;
- deterministic sizing;
- explicit no-order/rejected outcomes;
- durable cycle records and safe restart.

### Gate 4 — API and dashboard read model

- `/api/v3` query contracts;
- compatibility adapters;
- authoritative portfolio/performance queries;
- modular client refresh behavior and smoke coverage.

### Gate 5 — Backtesting and learning analytics

- reuse production domain logic with simulated time and execution;
- enforce bias controls;
- store outcome attribution;
- keep learning recommendations offline and non-self-modifying.

---

## 6. Merge and implementation policy

- This documentation may be merged once CI is green and the PR is no longer Draft.
- Merging documentation does not mean the target architecture is implemented.
- Each implementation phase requires a separate, narrowly scoped PR.
- No large rewrite may replace working v2 behavior in one merge.
- No change may enable live trading without an explicit future authorization, separate environment, and independent safety review.
