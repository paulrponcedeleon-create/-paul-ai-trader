# Paul AI Trader v3 Documentation

This directory contains the target architecture and implementation specifications for the v3 evolution of Paul AI Trader.

**Current safety posture:** paper trading only; `LIVE_TRADING=false`.

## Documents

1. [`ARCHITECTURE_V3.md`](./ARCHITECTURE_V3.md)  
   System context, module boundaries, runtime flow, dashboard, persistence, testing, deployment, and migration roadmap.

2. [`DATA_MODEL.md`](./DATA_MODEL.md)  
   Canonical venues, assets, markets, market data, analyses, risk decisions, orders, fills, ledger, positions, performance, runtime, configuration, and audit records.

3. [`API_CONTRACTS.md`](./API_CONTRACTS.md)  
   Versioned `/api/v3` routes, authentication boundary, response envelopes, stable errors, idempotency, portfolio queries, paper-order commands, performance, risk, and runtime APIs.

4. [`AI_ENGINE.md`](./AI_ENGINE.md)  
   Data quality, indicators, market regimes, factor contributions, score, confidence, explainability, outcome attribution, and controlled learning analytics.

5. [`RISK_ENGINE.md`](./RISK_ENGINE.md)  
   Deterministic risk policy, order validation, capital and exposure limits, drawdown, sizing, reservations, rejection behavior, and testing.

6. [`ARCHITECTURE_DECISIONS.md`](./ARCHITECTURE_DECISIONS.md)  
   Foundational ADRs covering paper-first safety, PostgreSQL, decimal arithmetic, ledger accounting, broker neutrality, versioning, idempotency, market identity, dashboard reads, backtesting, explainability, and future live isolation.

7. [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md)  
   Incremental phases, branch/PR strategy, merge gates, CI matrix, Codex execution protocol, acceptance criteria, and rollout order.

8. [`CODEX_PARALLEL_BASELINE_AUDIT.md`](./CODEX_PARALLEL_BASELINE_AUDIT.md)  
   Instructions for a documentation-only audit of the current v2 repository, intended to resolve open architecture facts without conflicting with code stabilization.

## Document authority

- Accepted architecture decisions are binding unless superseded by a later ADR.
- The repository audit is the authority for current-state facts.
- The architecture documents define the target state.
- When current reality and target design differ, implementation must use an explicit migration step rather than pretending the target already exists.
- Code and documentation must be updated together when an accepted behavior changes.

## Required reading by work type

### Stabilization or bug fix

Read:

- current audit,
- relevant source/tests,
- `IMPLEMENTATION_PLAN.md` Phase 0,
- any applicable ADR.

### Database/accounting work

Read:

- `DATA_MODEL.md`,
- ADR-002, ADR-003, ADR-004,
- `IMPLEMENTATION_PLAN.md` Phases 3–4.

### Market/provider work

Read:

- `ARCHITECTURE_V3.md` market modules,
- ADR-005 and ADR-008,
- `API_CONTRACTS.md` market routes,
- `IMPLEMENTATION_PLAN.md` Phase 2.

### Score, indicators, or AI work

Read:

- `AI_ENGINE.md`,
- ADR-006 and ADR-011,
- `DATA_MODEL.md` strategy/analysis entities.

### Risk or position sizing work

Read:

- `RISK_ENGINE.md`,
- ADR-001, ADR-003, ADR-004, ADR-006,
- `DATA_MODEL.md` risk and portfolio entities.

### Dashboard work

Read:

- ADR-009,
- `API_CONTRACTS.md`,
- `IMPLEMENTATION_PLAN.md` Phases 8–10.

### Runtime work

Read:

- ADR-007,
- `ARCHITECTURE_V3.md` runtime sections,
- `DATA_MODEL.md` runtime cycle/event model,
- `IMPLEMENTATION_PLAN.md` Phase 7.

### Backtesting work

Read:

- ADR-010 and ADR-011,
- `AI_ENGINE.md`,
- `IMPLEMENTATION_PLAN.md` Phases 11–12.

## Status model

Use these statuses for specifications and implementation tracking:

```text
WORKING_SPECIFICATION
AUDIT_REQUIRED
BLOCKED
ACCEPTED
IMPLEMENTED
VALIDATED
SUPERSEDED
```

A document marked accepted does not imply the code is implemented. A feature is not validated until its tests, reconciliation, and CI gates pass.

## Immediate next steps

1. Complete stabilization of `v2-dashboard`.
2. Complete the baseline repository audit.
3. Resolve the open decisions identified by the architecture.
4. Update these specifications with evidence where needed.
5. Begin Phase 1 through small, non-overlapping PRs.
6. Keep all live-order capability disabled.