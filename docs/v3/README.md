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
   Instructions used for the documentation-only audit of the v2 repository.

9. [`CURRENT_STATE_RECONCILIATION.md`](./CURRENT_STATE_RECONCILIATION.md)  
   Evidence-backed reconciliation between the merged v3 baseline audit and the target architecture, including confirmed gaps, resolved questions, implementation gates, and migration order.

The current-state evidence is maintained under [`../audit/v3-baseline/`](../audit/v3-baseline/).

## Document authority

- Accepted architecture decisions are binding unless superseded by a later ADR.
- The repository audit is the authority for current-state facts.
- `CURRENT_STATE_RECONCILIATION.md` controls how the audited baseline maps to the target architecture.
- The architecture documents define the target state.
- When current reality and target design differ, implementation must use an explicit migration step rather than pretending the target already exists.
- Code and documentation must be updated together when an accepted behavior changes.

## Required reading by work type

### Stabilization or bug fix

Read:

- the current baseline audit,
- `CURRENT_STATE_RECONCILIATION.md`,
- relevant source and tests,
- `IMPLEMENTATION_PLAN.md` Phase 0,
- any applicable ADR.

### Database/accounting work

Read:

- `DATA_MODEL.md`,
- `CURRENT_STATE_RECONCILIATION.md` sections on persistence and accounting,
- ADR-002, ADR-003, ADR-004,
- `IMPLEMENTATION_PLAN.md` Phases 3–4.

### Market/provider work

Read:

- `ARCHITECTURE_V3.md` market modules,
- `CURRENT_STATE_RECONCILIATION.md` market-data section,
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
- `CURRENT_STATE_RECONCILIATION.md` runtime and capital sections,
- ADR-001, ADR-003, ADR-004, ADR-006,
- `DATA_MODEL.md` risk and portfolio entities.

### Dashboard work

Read:

- ADR-009,
- `API_CONTRACTS.md`,
- `CURRENT_STATE_RECONCILIATION.md` dashboard section,
- `IMPLEMENTATION_PLAN.md` Phases 8–10.

### Runtime work

Read:

- ADR-007,
- `ARCHITECTURE_V3.md` runtime sections,
- `CURRENT_STATE_RECONCILIATION.md` runtime section,
- `DATA_MODEL.md` runtime cycle/event model,
- `IMPLEMENTATION_PLAN.md` Phase 7.

### Backtesting work

Read:

- ADR-010 and ADR-011,
- `AI_ENGINE.md`,
- `CURRENT_STATE_RECONCILIATION.md` accounting and market-data sections,
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

1. Confirm the post-hotfix `v2-dashboard` CI baseline is green.
2. Merge this documentation PR only after its refreshed CI passes and the PR is marked Ready for review.
3. Begin Gate 0 work through small PRs: remove duplicate operation IDs, validate migrations, and preserve the simulation/live boundary.
4. Implement Gate 1 accounting foundations before adding advanced dashboard or learning behavior.
5. Keep implementation PRs narrowly scoped and traceable to the reconciliation document.
6. Keep all live-order capability disabled.
