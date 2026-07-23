# Paul AI Trader v3 — Risk Engine Specification

**Status:** Working specification  
**Authority:** May reduce or reject any proposed paper order  
**Safety default:** `LIVE_TRADING=false`

---

## 1. Purpose

The Risk Engine is the final authorization boundary between an analytical recommendation and an order request. It determines whether a proposed action is acceptable for the current portfolio, market, data quality, and configured limits.

A favorable score never guarantees approval. The Risk Engine is deterministic, versioned, auditable, and independent of dashboard presentation.

---

## 2. Core principles

1. Risk has veto authority.
2. Missing required information fails closed.
3. Rules are deterministic and versioned.
4. All limits are evaluated with decimal-safe arithmetic.
5. Approval is based on current authoritative portfolio state.
6. Market-data freshness and market verification are mandatory.
7. A rejected decision produces no fill or ledger mutation.
8. A reduced decision explicitly records the requested and approved amounts.
9. Every decision lists triggered rules and input snapshots.
10. Paper and future live policies are isolated.

---

## 3. Inputs

```python
RiskRequest(
    signal_decision,
    order_intent,
    portfolio_snapshot,
    open_positions,
    market_snapshot,
    market_capabilities,
    fee_estimate,
    slippage_estimate,
    risk_policy_version,
    recent_performance,
    correlation_context,
    evaluated_at,
)
```

### Required signal fields

- market,
- BUY/HOLD/SELL or internal intent,
- score,
- confidence,
- quality,
- market regime,
- data cutoff,
- strategy version.

### Required order-intent fields

- side,
- requested notional or quantity,
- order type,
- portfolio and mode,
- source (`MANUAL`, `AUTOMATION`, `CLOSE_POSITION`),
- client/idempotency context.

### Required portfolio fields

- cash balance,
- reserved cash,
- available cash,
- equity,
- gross exposure,
- open positions,
- realized daily P&L,
- current drawdown,
- pending orders/reservations.

---

## 4. Outputs

```python
RiskDecision(
    decision,             # APPROVE, REDUCE, REJECT
    requested_notional,
    approved_notional,
    approved_quantity,
    reference_price,
    estimated_fee,
    estimated_total_cash,
    triggered_rules,
    warnings,
    policy_version,
    evaluated_at,
)
```

### Decision semantics

- `APPROVE`: request is allowed as submitted.
- `REDUCE`: request is allowed only at a smaller notional/quantity.
- `REJECT`: no order may be submitted.

`HOLD` analysis results should normally produce no opening order and therefore no approval request, except for diagnostics.

---

## 5. Rule evaluation order

Rules execute in a stable documented order.

```text
1. System and mode safety
2. Portfolio state
3. Market verification and capability
4. Market-data quality/freshness
5. Order validity and venue minimums
6. Available capital or position quantity
7. Per-order limits
8. Per-asset exposure
9. Portfolio exposure
10. Open-position and concentration limits
11. Loss/drawdown/cooldown limits
12. Correlation/liquidity limits
13. Final approved sizing and rounding
```

Hard rejection stops order submission but all relevant triggered hard rules may still be collected for explanation.

---

## 6. Policy model

A policy is immutable and checksummed.

Example:

```json
{
  "policy_code": "DEFAULT_PAPER",
  "version": "3.0.0",
  "base_currency": "MXN",
  "limits": {
    "max_order_notional": "200.00",
    "max_asset_exposure_pct": "25.0",
    "max_total_exposure_pct": "70.0",
    "minimum_cash_reserve": "500.00",
    "max_open_positions": 8,
    "max_daily_realized_loss": "250.00",
    "max_drawdown_pct": "10.0",
    "maximum_quote_age_seconds": 45,
    "minimum_signal_confidence": "60.0",
    "minimum_market_volume_24h": null,
    "loss_cooldown_minutes": 60
  },
  "sizing": {
    "method": "FIXED_MAX_NOTIONAL",
    "default_notional": "200.00",
    "volatility_adjustment": true,
    "confidence_adjustment": true
  }
}
```

Values above are examples, not approved production settings.

---

## 7. Rule contract

```python
class RiskRule(Protocol):
    code: str
    priority: int

    def evaluate(self, context: RiskContext) -> RiskRuleResult: ...
```

Result:

```python
RiskRuleResult(
    code,
    outcome,       # PASS, WARN, REDUCE, REJECT
    requested_value,
    limit_value,
    approved_value,
    explanation,
    metadata,
)
```

Rules do not mutate portfolio state. Reservation occurs only after an approved decision within the application transaction boundary.

---

## 8. Mandatory hard-safety rules

## 8.1 Live mode disabled

Reject when:

- request mode is live,
- environment is not an explicitly approved live environment,
- live execution feature gate is false,
- broker credentials/capabilities are not separately approved.

Initial v3 behavior: all live-order requests return `LIVE_TRADING_DISABLED`.

## 8.2 Portfolio active

Reject new openings when portfolio is paused, closed, locked, or under reconciliation.

Position-closing actions may be allowed under a separate emergency-reduction policy.

## 8.3 Market verified

Reject when the market is unknown, inactive, unverified, or unsupported for the requested order type.

## 8.4 Fresh market data

Reject when:

```text
age(reference quote) > maximum_quote_age_seconds
```

Also reject invalid, missing, non-positive, or inconsistent prices.

## 8.5 Analysis quality

Reject automated opening orders when:

- signal quality is invalid,
- required features are missing,
- confidence is below policy minimum,
- analysis data cutoff does not correspond to the order market snapshot within tolerance.

Manual paper orders may use a distinct policy but still require market, capital, and exposure controls.

---

## 9. Order validation rules

Validate:

- exactly one supported sizing input,
- positive notional/quantity,
- valid side,
- supported order type,
- limit price present for limit order,
- precision,
- minimum quantity,
- minimum notional,
- estimated fee currency,
- no contradictory close/open instructions.

Invalid requests are rejected rather than silently corrected, except approved deterministic venue rounding.

---

## 10. Capital rules for BUY

Estimated required cash:

```text
estimated_required_cash = gross_notional + estimated_fee + slippage_buffer
```

Approval requires:

```text
estimated_required_cash <= available_cash
available_cash_after_order >= minimum_cash_reserve
```

Available cash includes existing reservations.

If a request exceeds cash but a valid smaller amount remains above venue minimum and reserve requirements, the rule may return `REDUCE`.

---

## 11. Position rules for SELL

Approval requires:

```text
requested_quantity <= available_position_quantity
```

Available position quantity excludes quantities already reserved by pending sell orders.

Rules:

- No synthetic short selling in the initial spot-paper implementation.
- `close_all=true` resolves quantity from authoritative available position state.
- Venue precision may reduce the final quantity.
- Dust below the venue minimum is explicitly reported.

---

## 12. Per-order limit

```text
approved_notional <= max_order_notional
```

The policy may reduce an oversized valid request instead of rejecting it.

The dashboard’s “maximum per operation” is a display of this policy; it is not the enforcement point.

---

## 13. Per-asset exposure

Projected asset exposure:

```text
projected_asset_exposure = current_asset_market_value
                         + approved_buy_notional
                         - expected_sell_value
```

Exposure percentage:

```text
projected_asset_exposure_pct = projected_asset_exposure / projected_equity
```

Rule:

```text
projected_asset_exposure_pct <= max_asset_exposure_pct
```

The calculation must define treatment of quote-currency cash and cross-currency conversion.

---

## 14. Total portfolio exposure

```text
projected_gross_exposure = current_gross_exposure
                         + approved_opening_exposure
                         - expected_closing_exposure
```

Rule:

```text
projected_gross_exposure / projected_equity <= max_total_exposure_pct
```

A position close should generally reduce exposure and may be allowed even when the portfolio currently exceeds an opening limit, subject to market and quantity safety.

---

## 15. Open-position limit

A new opening order is rejected or reduced to zero when:

```text
current_open_positions >= max_open_positions
```

Adding to an existing position is governed by exposure/concentration limits and does not necessarily increment the count.

The definition of “same position” uses canonical market identity.

---

## 16. Concentration and correlation

Initial concentration controls:

- maximum exposure per asset,
- maximum exposure per asset class,
- maximum exposure to highly correlated group when reliable correlation data exists.

Correlation must not be enforced from an insufficient or stale sample.

When correlation quality is insufficient:

- do not fabricate a value,
- record a warning,
- use simpler concentration limits.

A future correlation rule must define:

- return frequency,
- lookback,
- minimum observations,
- missing-data handling,
- recalculation timestamp,
- threshold behavior.

---

## 17. Daily-loss limit

Initial definition:

```text
daily_realized_loss = absolute value of negative realized P&L
                      for the configured trading-day boundary
```

Reject new opening orders when:

```text
daily_realized_loss >= max_daily_realized_loss
```

The trading-day timezone must be explicit. Position-reducing orders may remain allowed.

Unrealized loss may be included in a separate equity/drawdown rule, not mixed silently into realized daily loss.

---

## 18. Drawdown limit

```text
current_drawdown_pct = (peak_equity - current_equity) / peak_equity * 100
```

When current drawdown reaches policy limit:

- reject new opening orders,
- optionally pause automation,
- emit a critical risk event,
- keep position-reduction paths available under policy.

Peak-equity calculation version and reset policy must be documented.

---

## 19. Loss-streak cooldown

Candidate initial rule:

- Count qualifying consecutive closed losing trades.
- When threshold is reached, block new automated openings for a configured duration.
- Manual paper trades may remain blocked or require an explicit administrative override, depending on policy.

The rule must define:

- what constitutes a trade,
- fee inclusion,
- partial closes,
- break/reset condition,
- time boundary.

Cooldown is a risk control, not a claim that a future trade will lose.

---

## 20. Volatility adjustment

Candidate sizing multiplier:

```text
volatility_multiplier = target_volatility / observed_volatility
```

Bound it:

```text
minimum_multiplier <= volatility_multiplier <= 1.0
```

The first implementation may use ATR percentage or realized volatility.

Rules:

- Higher volatility may reduce size.
- Missing/invalid volatility blocks automated opening or uses a documented conservative fallback.
- Volatility adjustment never increases beyond the base maximum unless explicitly approved by policy.

---

## 21. Confidence adjustment

Candidate multiplier:

```text
confidence_multiplier = bounded(
    (confidence - minimum_confidence) /
    (100 - minimum_confidence),
    minimum_confidence_multiplier,
    1.0
)
```

This is optional and policy-versioned.

Confidence can reduce size but cannot bypass hard limits.

---

## 22. Final deterministic sizing

Conceptual flow:

```text
base_notional
  -> min(requested, max order)
  -> capital/reserve cap
  -> asset-exposure cap
  -> total-exposure cap
  -> volatility reduction
  -> confidence reduction
  -> venue precision/minimum validation
  -> final approved notional/quantity
```

All intermediate caps and multipliers are retained in the decision explanation.

Example explanation:

```text
Requested MXN 400.00; reduced to MXN 200.00 by maximum-order limit; reduced to MXN 160.00 due to elevated volatility; final estimated quantity 0.00015362 BTC.
```

---

## 23. Risk decision persistence

Persist:

- request and approved amounts,
- reference price and timestamp,
- fees/slippage assumptions,
- policy version/checksum,
- strategy/signal reference,
- portfolio snapshot,
- market snapshot,
- each rule result,
- final decision,
- evaluation timestamp,
- correlation/request IDs.

Snapshots are redacted and contain no secrets.

Risk decisions are immutable.

---

## 24. Reservation lifecycle

### BUY

```text
approved decision
  -> reserve estimated required cash
  -> create/accept order
  -> on fill: convert reservation into fill accounting
  -> on cancel/reject/expiry: release reservation
```

### SELL

```text
approved decision
  -> reserve position quantity
  -> create/accept order
  -> on fill: reduce position/lot quantity
  -> on cancel/reject/expiry: release quantity
```

Reservation and order intent must be atomic in the database.

A reconciliation process detects and repairs orphaned reservations through audited compensating actions.

---

## 25. Position-reduction exception policy

Risk controls should not trap the portfolio in an unsafe position.

A separate reduction policy may allow SELL/close actions when:

- opening limits are exceeded,
- drawdown limit is active,
- daily loss limit is active,
- automation is paused.

Reduction actions still require:

- verified market,
- fresh valid price,
- sufficient position quantity,
- venue compatibility,
- idempotency.

No rule should transform a close into a larger reverse/short position.

---

## 26. Administrative overrides

Initial v3 should avoid overrides. If added later:

- paper mode only unless separately approved,
- explicit scope and expiration,
- actor/reason required,
- no override of live-disabled safety invariant,
- immutable audit event,
- visible dashboard warning,
- override cannot bypass invalid market data or unsupported market/order type.

---

## 27. Risk status read model

Dashboard/query service should expose:

- active policy/version,
- portfolio risk state: `NORMAL`, `WARNING`, `BLOCKED`, `PAUSED`,
- every active limit,
- current use,
- remaining capacity,
- triggered blocks,
- cooldown expiration,
- valuation timestamp and data quality.

Colors are secondary; textual states are required.

---

## 28. Testing requirements

### Unit and boundary tests

- amount exactly at/above/below each limit,
- available cash including fees and reservations,
- minimum cash reserve,
- venue minimum/precision,
- asset and total exposure,
- open-position count,
- daily loss boundary,
- drawdown boundary,
- quote freshness boundary,
- confidence threshold,
- volatility reduction bounds,
- SELL quantity reservation.

### Invariant/property tests

- approved amount never exceeds requested amount,
- approved amount never exceeds any hard cap,
- rejected decision has zero approved amount,
- final quantity is non-negative and venue-valid,
- same inputs/policy yield same decision,
- risk cannot increase exposure on a close intent,
- missing required state cannot approve.

### Integration tests

- approved decision + reservation atomicity,
- rejected decision creates no order/fill,
- cancellation releases reservation,
- partial fill adjusts reservation correctly,
- duplicate idempotent submit does not reserve twice,
- policy version persisted,
- risk status matches portfolio state.

### Failure tests

- database failure,
- stale quote between preview and submit,
- portfolio changes between preview and submit,
- duplicate runtime cycles,
- provider unavailable,
- malformed fee estimate.

Submit always re-evaluates authoritative state; preview cannot guarantee approval.

---

## 29. Initial implementation sequence

1. Define risk request/result types and stable rule codes.
2. Implement hard safety, market, data freshness, and order validation rules.
3. Implement cash/position availability rules.
4. Implement max order, exposure, and open-position limits.
5. Persist immutable policy versions and decisions.
6. Add reservation lifecycle.
7. Add daily loss/drawdown/cooldown.
8. Add optional volatility/confidence sizing.
9. Add risk status API/dashboard panel.
10. Add correlation only after reliable data and tests exist.

---

## 30. Definition of done

The v3 Risk Engine foundation is complete when:

- every paper order passes through it,
- rules are deterministic and versioned,
- decisions are immutable and explainable,
- missing/stale/invalid inputs fail closed,
- capital and position reservations are atomic,
- exposure, loss, drawdown, and order limits are enforced,
- position-reduction actions remain safely possible,
- the dashboard shows current risk utilization,
- boundary and failure tests pass,
- live trading remains disabled.