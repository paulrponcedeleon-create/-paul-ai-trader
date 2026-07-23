# Codex Parallel Task — Current-State Baseline Audit

Use the prompt below in a **second Codex task only if the first Codex task is still stabilizing or refactoring the application**.

This task is intentionally read-only for production code so the two tasks do not collide.

```text
You are performing a comprehensive current-state audit of the repository:

paulrponcedeleon-create/-paul-ai-trader

The application stabilization/refactoring task is being handled by another Codex session. You must not compete with it or modify production behavior.

OBJECTIVE

Create an evidence-based technical baseline of the repository so that the target v3 architecture can be implemented without guessing.

BRANCH AND SCOPE

1. Start from the latest v2-dashboard branch.
2. Create and work only on a new branch named:
   audit-v3-baseline
3. Do not edit application code, templates, static assets, migrations, tests, CI workflows, configuration, or dependencies.
4. Only add Markdown or machine-readable inventory files under:
   docs/audit/v3-baseline/
5. Do not merge the branch.
6. Open one draft pull request to v2-dashboard when complete.

CONCURRENCY SAFETY

Another session may change v2-dashboard while you work.

- Do not rebase repeatedly during the audit.
- Do not modify files outside docs/audit/v3-baseline/.
- If the base changes, record the audited commit SHA prominently.
- Do not copy speculative future architecture into the baseline.
- Report current implementation exactly as it exists at the audited SHA.

AUDIT PRINCIPLES

- Base every statement on repository evidence.
- Include file paths, class/function names, route paths, model names, and test names.
- Clearly label facts, inferences, risks, and unknowns.
- Do not claim a feature works merely because code exists.
- Do not call external APIs or place orders.
- Never expose secrets or environment values.
- Keep LIVE_TRADING=false and do not change runtime configuration.

REQUIRED OUTPUT FILES

Create all of the following:

1. docs/audit/v3-baseline/README.md
2. docs/audit/v3-baseline/REPOSITORY_MAP.md
3. docs/audit/v3-baseline/API_INVENTORY.md
4. docs/audit/v3-baseline/DATA_MODEL_AND_MIGRATIONS.md
5. docs/audit/v3-baseline/RUNTIME_FLOW.md
6. docs/audit/v3-baseline/MARKET_AND_BROKER_ADAPTERS.md
7. docs/audit/v3-baseline/CAPITAL_POSITION_PNL_FLOW.md
8. docs/audit/v3-baseline/DASHBOARD_AND_FRONTEND.md
9. docs/audit/v3-baseline/TEST_AND_CI_INVENTORY.md
10. docs/audit/v3-baseline/SECURITY_CONFIGURATION.md
11. docs/audit/v3-baseline/TECHNICAL_DEBT_REGISTER.md
12. docs/audit/v3-baseline/V3_GAP_MATRIX.md
13. docs/audit/v3-baseline/inventory.json

REQUIRED CONTENT

A. Repository map

Inventory every relevant package and important file.
For each item include:
- responsibility,
- public entry points,
- dependencies,
- approximate size,
- whether it mixes responsibilities,
- whether it appears active, legacy, duplicated, or unclear.

Identify:
- application entry point,
- FastAPI app construction,
- settings/configuration,
- runtime/scheduler,
- market clients,
- Bitso integration,
- paper trading,
- capital and P&L,
- ranking/score/indicators,
- persistence,
- templates and JavaScript,
- migrations,
- tests,
- deployment and CI.

B. API inventory

Create a table for every route with:
- HTTP method,
- path,
- explicit or generated operation_id,
- source file and function,
- authentication requirement,
- request schema,
- response schema or actual response shape,
- side effects,
- database access,
- broker/provider access,
- tests covering the route,
- duplicates or conflicts.

Specifically detect duplicate FastAPI operation IDs and duplicate route registrations.

C. Data model and migrations

Inventory:
- every SQLAlchemy model,
- every table,
- columns and important constraints,
- relationships,
- indexes,
- decimal/float usage,
- nullable fields,
- status fields and values,
- SQLite/PostgreSQL differences,
- Alembic migration chain and current head.

Trace how simulated orders, positions, scores, and capital are persisted.
Flag any state kept only in memory or browser state.

D. Runtime flow

Trace the actual runtime from startup through one analysis/trading cycle.
Include a Mermaid sequence diagram.

Document:
- startup hooks,
- global state,
- background tasks,
- locks,
- refresh intervals,
- exception boundaries,
- NoneType risks,
- retry behavior,
- provider calls,
- score generation,
- order simulation,
- persistence,
- shutdown behavior.

E. Market and broker adapters

For every market/provider/broker integration document:
- supported assets and markets as coded,
- provider symbol mapping,
- quote and historical-data endpoints,
- caching,
- timeouts and retries,
- fees,
- rate-limit handling,
- read-only versus order permissions,
- fake/mock adapters,
- provider-specific logic leaking into domain/UI code.

Do not verify support from the public internet; this audit is repository-only.
Mark external capabilities as unknown unless demonstrated by code/tests.

F. Capital, positions, and P&L

Trace every code path that calculates or mutates:
- initial capital,
- available balance,
- reserved or locked balance,
- order notional,
- quantity,
- average cost,
- open positions,
- closed positions,
- realized P&L,
- unrealized P&L,
- total equity,
- fees,
- currency conversion.

Create a dependency diagram and identify competing sources of truth.
State where floats are used for money.
State whether transactions are atomic.

G. Dashboard/frontend

Inventory:
- templates,
- JavaScript modules,
- API calls,
- polling intervals,
- event listeners,
- DOM IDs,
- data formatting,
- open/closed position rendering,
- recent-history limits,
- auto-refresh behavior,
- dead controls and listeners,
- duplicated fetches,
- client-side authoritative calculations.

H. Tests and CI

Inventory every test module by category.
Map tests to modules and routes.
Report:
- test count where reliably measurable,
- fixtures,
- database isolation,
- mocked external services,
- flaky/time-sensitive tests,
- skipped or xfailed tests,
- coverage gaps,
- outdated expectations,
- CI workflows and required checks,
- migration validation,
- lint/type/format/security checks.

Do not change tests in this task.

I. Security and configuration

Document without exposing values:
- required environment variable names,
- defaults,
- unsafe fallbacks,
- session cookie settings,
- authentication flow,
- password handling,
- CSRF posture,
- CORS,
- security headers,
- secret logging risk,
- live-trading gates,
- API-key capability checks,
- production debug behavior.

J. Technical debt register

Give each item a stable ID such as TD-001.
For each include:
- title,
- evidence,
- affected files,
- type: bug/security/architecture/data/testing/performance/UX/docs,
- severity: critical/high/medium/low,
- probability,
- impact,
- recommended correction,
- likely dependencies,
- suggested implementation phase.

Do not inflate severity.

K. V3 gap matrix

Compare the repository baseline against docs/v3/ARCHITECTURE_V3.md if that file exists on the branch or can be inspected from the docs-v3-architecture branch.

Use statuses:
- IMPLEMENTED
- PARTIAL
- ABSENT
- UNKNOWN
- CONFLICTS_WITH_TARGET

For each target capability cite repository evidence and list the minimum migration needed.
This is analysis only; do not implement the migration.

L. inventory.json

Create a valid JSON inventory containing at minimum:
- audited_commit_sha,
- generated_at_utc,
- entry_points,
- packages,
- routes,
- models,
- migrations,
- environment_variables,
- external_integrations,
- runtime_jobs,
- frontend_pollers,
- tests,
- technical_debt_ids,
- unknowns.

Do not include secrets or actual environment values.

VALIDATION

Before finishing:

1. Verify that only docs/audit/v3-baseline/* changed.
2. Validate inventory.json parses successfully.
3. Check all documented paths and symbols exist at the audited SHA.
4. Check Mermaid blocks are syntactically reasonable.
5. Search for accidentally copied secrets or tokens.
6. Confirm no application code, test, workflow, dependency, or configuration file changed.

COMMITS

Use logical documentation commits, for example:

- docs(audit): map repository and application entry points
- docs(audit): inventory API and persistence model
- docs(audit): trace runtime and portfolio accounting
- docs(audit): assess frontend tests security and technical debt
- docs(audit): add v3 gap matrix and machine-readable inventory

FINAL RESPONSE

Return only:

1. Audited commit SHA.
2. Draft PR number and URL.
3. Commit list.
4. Five highest-risk verified findings.
5. Important unknowns.
6. Confirmation that no files outside docs/audit/v3-baseline/ changed.
```
