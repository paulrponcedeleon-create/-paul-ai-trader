# Dashboard and JavaScript Audit

## Templates and assets

- `app/templates/index.html` is the main control center with authenticated dashboard, market panel, manual simulated buy form, portfolio summary, operations history, learning/control and system panels.
- `app/templates/performance.html` is the performance page with filters and tables.
- `app/static/app.js` handles legacy dashboard login, market fetches, order form, simulation history, position rendering and close actions.
- `app/static/market-panel-v2.js` handles the current automatic market card refresh and filter behavior.
- `app/static/dashboard-v2.js` handles module refreshes for runtime/system/readiness/paper/analytics/adaptive/validation.
- `app/static/capital-balance.js` refreshes capital-related summary values.
- `app/static/performance.js` powers performance filters/visuals.

## Auto refresh

The dashboard intentionally removed the manual market refresh button and relies on automatic intervals. Tests assert auto-refresh contracts and absence of `refreshBtn` in new market panel JavaScript.

## Findings

1. JavaScript is split by concern, but some global bridging remains in the template (`window.marketBridge` and references to `selectedBook`/`refreshMarket`).
2. `dashboard-v2.js` assumes several DOM nodes are present when updating status; missing nodes could still cause client-side exceptions in altered templates.
3. The dashboard has both legacy and v2 market JavaScript assets; v3 should consolidate or explicitly version client modules.
4. Some overview cards contain static explanatory text and initial values; backend refresh updates much of the state, but critical v3 portfolio/capital data should be consistently API-driven.
5. No build step exists; this keeps deployment simple but limits static analysis of JavaScript.

## Evidence commands

- `sed -n '1,220p' app/templates/index.html app/templates/performance.html`
- `sed -n '1,260p' app/static/app.js app/static/dashboard-v2.js app/static/market-panel-v2.js app/static/capital-balance.js app/static/performance.js`
- `rg -n "setInterval|fetch\(|refreshBtn|marketBridge|selectedBook|openPositions|totalPnl|capital" app/static app/templates tests -S`
