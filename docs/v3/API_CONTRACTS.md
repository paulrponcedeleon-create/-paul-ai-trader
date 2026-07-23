# Paul AI Trader v3 — API Contracts

**Status:** Working specification  
**API prefix:** `/api/v3`  
**Safety default:** `LIVE_TRADING=false`

---

## 1. Purpose

This document defines the target HTTP API for the v3 application boundary. It separates read models from trading commands, standardizes errors and idempotency, and prevents the dashboard from becoming an alternative source of business logic.

The v3 API may initially coexist with existing v2 routes. Compatibility adapters should be preferred over a disruptive route replacement.

---

## 2. General rules

1. All JSON endpoints are versioned under `/api/v3`.
2. All timestamps are ISO 8601 UTC values.
3. All money, price, rate, and quantity fields are serialized as strings to preserve decimal precision.
4. Every response includes a request identifier.
5. Commands use explicit idempotency keys.
6. Read endpoints never mutate trading state.
7. Errors use stable machine-readable codes.
8. The API never returns secrets, credential values, or raw provider responses.
9. Paper and future live modes are explicit in every command and response.
10. Live-order endpoints do not exist in the first v3 milestone.

---

## 3. Authentication and session boundary

The existing authenticated web session may remain the first supported mechanism.

Required properties:

- `HttpOnly` session cookie.
- `Secure` in production.
- `SameSite=Lax` or stricter unless a documented flow requires otherwise.
- Session rotation after successful login.
- CSRF protection for browser-originated state-changing commands.
- Rate limiting or lockout strategy for repeated authentication failures.
- Explicit logout invalidation.

Future token authentication must be specified separately and cannot silently reuse browser-session assumptions.

---

## 4. Common headers

### Request

```text
Accept: application/json
Content-Type: application/json
X-Request-ID: optional caller-provided UUID
Idempotency-Key: required for state-changing trading commands
X-CSRF-Token: required for browser commands when applicable
```

### Response

```text
Content-Type: application/json
X-Request-ID: server request identifier
Cache-Control: endpoint-specific
```

The server may accept a valid caller request ID but must generate one when absent.

---

## 5. Response envelopes

### 5.1 Successful single-resource response

```json
{
  "data": {},
  "meta": {
    "request_id": "0190f7d8-2b14-7e2b-a1d6-4f02c3e38d45",
    "generated_at": "2026-07-23T19:30:00Z"
  }
}
```

### 5.2 Successful collection response

```json
{
  "data": [],
  "meta": {
    "request_id": "0190f7d8-2b14-7e2b-a1d6-4f02c3e38d45",
    "generated_at": "2026-07-23T19:30:00Z",
    "next_cursor": null,
    "count": 0
  }
}
```

### 5.3 Error response

```json
{
  "error": {
    "code": "INSUFFICIENT_AVAILABLE_CASH",
    "message": "The paper portfolio does not have enough available cash.",
    "details": {
      "available_cash": "120.00",
      "required_cash": "205.80",
      "currency": "MXN"
    }
  },
  "meta": {
    "request_id": "0190f7d8-2b14-7e2b-a1d6-4f02c3e38d45",
    "generated_at": "2026-07-23T19:30:00Z"
  }
}
```

Error details must be safe for the authenticated user and must not expose stack traces or provider credentials.

---

## 6. HTTP status policy

| Status | Use |
|---|---|
| `200` | Successful read or idempotent command replay |
| `201` | New command/resource accepted and created |
| `202` | Asynchronous command accepted |
| `204` | Successful command with no response body |
| `400` | Malformed request or invalid parameter combination |
| `401` | Authentication required or invalid |
| `403` | Authenticated but not authorized / CSRF rejected |
| `404` | Resource does not exist or is not visible |
| `409` | State conflict or idempotency-key conflict |
| `422` | Semantically valid JSON that violates domain validation |
| `429` | Rate limit exceeded |
| `500` | Unexpected server error |
| `503` | Dependency unavailable or runtime degraded |

Domain rejections such as insufficient funds may use `422` when the command is valid but cannot be approved. State-machine conflicts use `409`.

---

## 7. Stable error codes

Initial codes:

```text
AUTHENTICATION_REQUIRED
AUTHENTICATION_FAILED
CSRF_VALIDATION_FAILED
REQUEST_VALIDATION_FAILED
RESOURCE_NOT_FOUND
IDEMPOTENCY_KEY_REQUIRED
IDEMPOTENCY_KEY_CONFLICT
MARKET_NOT_VERIFIED
MARKET_NOT_SUPPORTED
MARKET_DATA_UNAVAILABLE
MARKET_DATA_STALE
INVALID_ORDER_SIDE
INVALID_ORDER_TYPE
INVALID_ORDER_AMOUNT
MINIMUM_NOTIONAL_NOT_MET
INSUFFICIENT_AVAILABLE_CASH
INSUFFICIENT_POSITION_QUANTITY
RISK_POLICY_REJECTED
PORTFOLIO_PAUSED
ORDER_STATE_CONFLICT
ORDER_ALREADY_COMPLETED
PROVIDER_UNAVAILABLE
RUNTIME_DEGRADED
LIVE_TRADING_DISABLED
INTERNAL_ERROR
```

Codes are part of the public contract and are not renamed casually.

---

## 8. System endpoints

## 8.1 `GET /api/v3/system/status`

Returns operating mode and dependency health without exposing secrets.

Example:

```json
{
  "data": {
    "application": "paul-ai-trader",
    "version": "3.0.0-dev",
    "mode": "PAPER",
    "live_trading_enabled": false,
    "runtime": {
      "status": "HEALTHY",
      "last_cycle_at": "2026-07-23T19:29:00Z",
      "last_cycle_id": "0190f7d8-2b14-7e2b-a1d6-4f02c3e38d45"
    },
    "database": {"status": "HEALTHY"},
    "market_providers": [
      {"code": "BITSO", "status": "HEALTHY", "last_success_at": "2026-07-23T19:29:45Z"}
    ]
  },
  "meta": {
    "request_id": "...",
    "generated_at": "2026-07-23T19:30:00Z"
  }
}
```

Public deployment health checks may expose a smaller response at a non-sensitive route.

## 8.2 `GET /api/v3/system/configuration`

Returns redacted, non-secret active configuration relevant to behavior:

- paper capital limits,
- refresh intervals,
- active strategy version,
- active risk-policy version,
- supported timeframes,
- enabled markets.

Never return secrets or credential presence details beyond a coarse readiness flag.

---

## 9. Market catalog and data

## 9.1 `GET /api/v3/markets`

Query parameters:

```text
venue
asset_type
verified=true|false
active=true|false
cursor
limit
```

Market representation:

```json
{
  "id": "...",
  "venue": "BITSO",
  "venue_symbol": "btc_mxn",
  "display_symbol": "BTC/MXN",
  "base_asset": "BTC",
  "quote_asset": "MXN",
  "market_type": "SPOT",
  "verified": true,
  "active": true,
  "capabilities": {
    "market_orders": true,
    "limit_orders": true
  },
  "limits": {
    "minimum_quantity": "0.000001",
    "minimum_notional": "100.00",
    "price_precision": 2,
    "quantity_precision": 8
  }
}
```

## 9.2 `GET /api/v3/markets/{market_id}/quote`

Returns the latest normalized quote plus freshness.

```json
{
  "data": {
    "market_id": "...",
    "bid": "1041000.00",
    "ask": "1042000.00",
    "last": "1041500.00",
    "mid": "1041500.00",
    "quote_currency": "MXN",
    "provider_event_at": "2026-07-23T19:29:44Z",
    "received_at": "2026-07-23T19:29:45Z",
    "age_seconds": 15,
    "quality": "VALID"
  },
  "meta": {"request_id": "...", "generated_at": "..."}
}
```

## 9.3 `GET /api/v3/markets/{market_id}/candles`

Query parameters:

```text
timeframe=1h
start=ISO_TIMESTAMP
end=ISO_TIMESTAMP
limit=500
cursor
```

The API must identify final versus incomplete candles and enforce maximum ranges.

## 9.4 `GET /api/v3/markets/ranking`

Query parameters:

```text
market_id (repeatable)
asset_type
signal
quality
limit
```

Each row includes:

- market,
- latest price,
- price timestamp and age,
- score,
- confidence,
- signal,
- five-level visual label,
- regime,
- quality,
- strongest positive and negative factors,
- strategy version,
- analysis timestamp.

The endpoint returns persisted or authoritative application results; it does not recompute indicators in the web layer.

---

## 10. Analysis endpoints

## 10.1 `GET /api/v3/analyses/{analysis_id}`

Returns the complete explainable analysis without internal implementation secrets.

```json
{
  "data": {
    "id": "...",
    "market_id": "...",
    "analysis_at": "2026-07-23T19:29:00Z",
    "data_cutoff_at": "2026-07-23T19:28:59Z",
    "strategy": {"code": "MULTI_FACTOR", "version": "3.0.0"},
    "regime": "TREND_UP",
    "signal": "BUY",
    "score": "78.400",
    "confidence": "72.100",
    "quality": "HIGH",
    "visual_level": "GREEN",
    "positive_factors": [
      {"code": "TREND_ALIGNMENT", "contribution": "18.0", "explanation": "..."}
    ],
    "negative_factors": [
      {"code": "ELEVATED_VOLATILITY", "contribution": "-6.0", "explanation": "..."}
    ],
    "data_quality": {
      "status": "VALID",
      "missing_features": [],
      "stale_features": []
    },
    "summary": "..."
  },
  "meta": {"request_id": "...", "generated_at": "..."}
}
```

## 10.2 `POST /api/v3/analyses`

Optional administrative/manual paper-analysis command, not an order command.

Request:

```json
{
  "market_id": "...",
  "strategy_version": "3.0.0",
  "reason": "MANUAL_REVIEW"
}
```

It returns `202` when queued or `201` when completed synchronously. It cannot bypass data freshness checks.

---

## 11. Portfolio read endpoints

## 11.1 `GET /api/v3/portfolios`

Returns portfolios visible to the authenticated user. The first milestone may expose one paper portfolio.

## 11.2 `GET /api/v3/portfolios/{portfolio_id}/summary`

```json
{
  "data": {
    "portfolio_id": "...",
    "mode": "PAPER",
    "base_currency": "MXN",
    "cash_balance": "3500.00",
    "reserved_cash": "200.00",
    "available_cash": "3300.00",
    "positions_market_value": "1725.50",
    "equity": "5225.50",
    "realized_pnl": "110.20",
    "unrealized_pnl": "115.30",
    "fees_total": "14.70",
    "gross_exposure": "1725.50",
    "open_position_count": 3,
    "valued_at": "2026-07-23T19:29:45Z",
    "data_quality": "VALID"
  },
  "meta": {"request_id": "...", "generated_at": "..."}
}
```

Authoritative identities are calculated in application/domain services, not JavaScript.

## 11.3 `GET /api/v3/portfolios/{portfolio_id}/positions`

Query parameters:

```text
status=OPEN|CLOSED|ALL
market_id
cursor
limit
```

The dashboard portfolio panel must call with `status=OPEN`.

Position response includes:

- quantity,
- average cost,
- remaining cost basis,
- mark price,
- market value,
- unrealized P&L and percentage,
- fees allocated according to policy,
- opened time,
- valuation time and quote quality.

## 11.4 `GET /api/v3/portfolios/{portfolio_id}/trades`

Query parameters:

```text
status=OPEN|CLOSED|ALL
market_id (repeatable)
start
end
cursor
limit
```

The recent-history dashboard uses closed/completed trades and `limit=10`.

## 11.5 `GET /api/v3/portfolios/{portfolio_id}/ledger`

Administrative/audit endpoint with pagination. Entries are immutable and may be filtered by transaction type, asset, business reference, and date range.

---

## 12. Paper-order commands

All order commands in the first v3 milestone are explicitly under `paper`.

## 12.1 `POST /api/v3/portfolios/{portfolio_id}/paper/orders/preview`

Preview performs validation, fee/slippage estimation, and risk evaluation without reserving capital or creating an executable order.

Request:

```json
{
  "market_id": "...",
  "side": "BUY",
  "order_type": "MARKET",
  "notional": "200.00",
  "quantity": null,
  "limit_price": null
}
```

Exactly one sizing input is required according to side and order policy.

Response:

```json
{
  "data": {
    "preview_id": "...",
    "expires_at": "2026-07-23T19:31:00Z",
    "reference_price": "1041500.00",
    "estimated_quantity": "0.00019084",
    "gross_notional": "198.75",
    "estimated_fee": "1.25",
    "estimated_total_cash": "200.00",
    "risk": {
      "decision": "APPROVE",
      "approved_notional": "200.00",
      "triggered_rules": []
    },
    "market_data_age_seconds": 8
  },
  "meta": {"request_id": "...", "generated_at": "..."}
}
```

A preview is not a promise of execution and must expire quickly.

## 12.2 `POST /api/v3/portfolios/{portfolio_id}/paper/orders`

Requires `Idempotency-Key`.

Request:

```json
{
  "market_id": "...",
  "side": "BUY",
  "order_type": "MARKET",
  "notional": "200.00",
  "quantity": null,
  "limit_price": null,
  "preview_id": "optional-short-lived-preview-id",
  "client_context": {
    "source": "DASHBOARD",
    "reason": "MANUAL_PAPER_TRADE"
  }
}
```

Server processing order:

1. Authenticate and validate CSRF.
2. Validate idempotency key.
3. Validate paper portfolio and verified market.
4. Obtain fresh market data.
5. Recalculate fees and slippage.
6. Evaluate Risk Engine.
7. Reserve capital or quantity.
8. Create paper order.
9. Simulate fill according to configured policy.
10. Atomically post fill, ledger, position update, and order event.
11. Return order representation.

The client cannot submit a risk approval or authoritative price.

## 12.3 `GET /api/v3/portfolios/{portfolio_id}/paper/orders/{order_id}`

Returns order, events, aggregate fills, fee totals, and rejection details.

## 12.4 `POST /api/v3/portfolios/{portfolio_id}/paper/orders/{order_id}/cancel`

Requires `Idempotency-Key`. Valid only for cancellable states. Releases reservations atomically.

## 12.5 `POST /api/v3/portfolios/{portfolio_id}/paper/positions/{position_id}/close`

Convenience command that creates a SELL order; it does not mutate a position directly.

Request:

```json
{
  "quantity": "0.00019084",
  "close_all": false,
  "order_type": "MARKET"
}
```

Exactly one of quantity or `close_all=true` is accepted.

---

## 13. Performance endpoints

## 13.1 `GET /api/v3/portfolios/{portfolio_id}/performance/summary`

Query parameters:

```text
period=DAY|WEEK|MONTH|ALL
market_id (repeatable)
```

Response metrics:

- start and end equity,
- net P&L,
- realized and unrealized P&L,
- gross profit and loss,
- fees,
- return percentage,
- trade count,
- win rate,
- expectancy,
- profit factor,
- maximum drawdown,
- metric formula version,
- sample warnings.

Metrics with insufficient samples return `null` plus a reason; they are not fabricated.

## 13.2 `GET /api/v3/portfolios/{portfolio_id}/performance/equity-curve`

Query parameters:

```text
start
end
interval=5m|1h|1d
market_id (repeatable)
```

Each point includes timestamp, equity, cash, market value, cumulative fees, and drawdown.

---

## 14. Risk endpoints

## 14.1 `GET /api/v3/portfolios/{portfolio_id}/risk/status`

Returns active limits and current utilization:

```json
{
  "data": {
    "policy": {"code": "DEFAULT_PAPER", "version": "3.0.0"},
    "status": "NORMAL",
    "limits": {
      "max_order_notional": {"limit": "200.00", "used": "0.00", "currency": "MXN"},
      "max_total_exposure": {"limit": "3500.00", "used": "1725.50", "currency": "MXN"},
      "max_daily_realized_loss": {"limit": "250.00", "used": "0.00", "currency": "MXN"},
      "max_open_positions": {"limit": 8, "used": 3}
    },
    "blocks": []
  },
  "meta": {"request_id": "...", "generated_at": "..."}
}
```

## 14.2 `GET /api/v3/risk/decisions/{risk_decision_id}`

Returns the immutable risk decision, triggered rules, and redacted snapshots used.

---

## 15. Runtime endpoints

## 15.1 `GET /api/v3/runtime/cycles`

Filter by status, trigger type, start/end, and cursor.

## 15.2 `GET /api/v3/runtime/cycles/{cycle_id}`

Returns cycle status, timings, markets processed, analyses generated, decisions, orders, warnings, and failures.

## 15.3 `POST /api/v3/runtime/cycles`

Administrative manual paper-analysis trigger. Requires idempotency and does not enable live execution.

Request:

```json
{
  "market_ids": ["..."],
  "analysis_only": true,
  "reason": "MANUAL_DIAGNOSTIC"
}
```

`analysis_only` defaults to true for manual diagnostic cycles. Any paper-order automation must be separately configured and risk-governed.

## 15.4 `POST /api/v3/runtime/pause`

Pauses new runtime cycles and paper automation. It does not destroy state.

## 15.5 `POST /api/v3/runtime/resume`

Resumes only after dependency and configuration validation.

---

## 16. Settings endpoints

Settings changes must create versioned configuration records and audit events.

Initial endpoints:

```text
GET  /api/v3/settings
POST /api/v3/settings/preview
POST /api/v3/settings/activate
GET  /api/v3/settings/versions
```

A preview validates configuration without activation. Activation requires a checksum/version and rejects stale updates.

Secrets are managed through environment/secret infrastructure, never through these endpoints.

---

## 17. Idempotency contract

For every command requiring `Idempotency-Key`:

1. Scope the key by authenticated actor, route/command type, portfolio, and mode.
2. Persist request checksum and final response reference.
3. Replaying the same key with the same request returns the original result.
4. Replaying the same key with a different request returns `409 IDEMPOTENCY_KEY_CONFLICT`.
5. An in-progress key returns the current command status.
6. Keys are retained long enough to prevent duplicate financial actions; accounting references are permanent.

---

## 18. Pagination and filtering

Cursor pagination is required for orders, trades, ledger records, analyses, cycles, and audit records.

Rules:

- Cursors are opaque.
- Default and maximum limits are endpoint-specific.
- Sort order is documented and stable, normally newest first.
- Filters are validated and included in cursor integrity.
- Offset pagination may be used only for small static catalogs.

---

## 19. Caching

- Authenticated portfolio/accounting endpoints default to `Cache-Control: no-store`.
- Market catalog may use short private caching with ETags.
- Quotes use endpoint-specific freshness headers but cannot be treated as authoritative after their maximum age.
- Idempotent command responses may be replayed from persistent idempotency storage.
- Dashboard polling must avoid overlapping requests.

---

## 20. OpenAPI requirements

1. Every route has a unique explicit `operation_id`.
2. Request and response schemas are named and versioned.
3. Decimal strings include format descriptions and examples.
4. Every error code is documented.
5. Security requirements are declared per route.
6. Internal/admin endpoints are clearly tagged.
7. Live-order schemas are absent until a separate approved milestone.
8. CI validates duplicate paths, duplicate operation IDs, and schema generation.

Suggested operation ID format:

```text
v3_get_system_status
v3_list_markets
v3_get_portfolio_summary
v3_preview_paper_order
v3_create_paper_order
v3_close_paper_position
```

---

## 21. Contract tests

Required tests:

- Authentication and CSRF behavior.
- Error-envelope consistency.
- Decimal serialization.
- Stable error codes.
- Duplicate operation-ID rejection.
- Idempotent order replay.
- Idempotency-key conflict.
- Unverified market rejection.
- Stale quote rejection.
- Insufficient cash rejection.
- Partial/full close validation.
- Open-position filtering.
- Recent completed-trade limit of ten.
- Period and asset performance filters.
- Redaction of secrets and raw provider data.
- `LIVE_TRADING=false` status and absence of live command routes.

---

## 22. Compatibility strategy

During migration:

1. Preserve existing v2 routes needed by the deployed dashboard.
2. Build v3 query services behind new endpoints.
3. Add characterization tests comparing v2 and v3 values where definitions are intended to match.
4. Migrate dashboard panels one at a time.
5. Deprecate v2 routes only after usage is removed and tests prove equivalence.
6. Never silently change capital or P&L semantics under an existing response field.

---

## 23. Definition of done

The v3 API foundation is ready when:

- schemas and stable errors are implemented,
- all operation IDs are unique,
- paper commands are idempotent,
- authoritative portfolio values come from domain/query services,
- dashboard polling uses the documented read endpoints,
- contract tests pass in CI,
- OpenAPI contains no live-order routes,
- secrets and provider internals are not exposed.