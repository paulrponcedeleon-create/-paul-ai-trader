# Paul AI Trader v3 — Architecture and Product Specification

**Status:** Working specification  
**Branch:** `docs-v3-architecture`  
**Applies to:** Paul AI Trader v3 target state  
**Safety default:** `LIVE_TRADING=false`

---

## 1. Purpose

Paul AI Trader v3 is a modular algorithmic-trading platform designed to support market analysis, explainable signals, deterministic risk controls, paper trading, backtesting, performance measurement, and—only after explicit approval and separate safeguards—live execution.

The v3 design must improve the current system without discarding working behavior. Migration must be incremental, testable, and reversible.

### 1.1 Primary product goals

1. Preserve a safe paper-trading-first operating model.
2. Produce explainable BUY, HOLD, and SELL recommendations.
3. Separate signal generation from risk approval and order execution.
4. Maintain a consistent capital, position, fee, and P&L ledger.
5. Support multiple assets and future broker adapters without coupling the domain model to Bitso.
6. Provide a professional dashboard with actionable portfolio, risk, and strategy metrics.
7. Make every decision and state transition auditable.
8. Keep CI green and make regressions visible before merge.

### 1.2 Explicit non-goals for the first v3 milestone

- Enabling real-money orders.
- High-frequency or sub-second trading.
- Autonomous parameter changes without validation.
- Black-box machine learning that cannot explain its recommendation.
- Multi-user brokerage custody.
- Promising profitability.

---

## 2. Safety invariants

These rules are mandatory and take precedence over convenience.

1. `LIVE_TRADING=false` remains the default in all environments.
2. Missing or malformed configuration must fail closed.
3. No API key, secret, password, cookie secret, or token may be committed.
4. A signal may never execute an order directly.
5. Every order must pass through the Risk Engine.
6. Paper and live ledgers must never share writable state.
7. A failed persistence write must not be silently treated as a completed order.
8. Duplicate client order IDs must be idempotent.
9. Money and quantities must use decimal-safe arithmetic, not binary floating point.
10. The system must reject a trade when capital, fee, price, quantity, or market data is unavailable or stale.
11. The system must not infer that an exchange supports a market merely because an asset exists.
12. Live execution requires a separate feature gate, environment approval, broker permission checks, and explicit user action.

---

## 3. Architecture principles

### 3.1 Domain before framework

Trading, portfolio, risk, and performance rules belong in framework-independent domain modules. FastAPI, SQLAlchemy, HTML, JavaScript, and broker SDKs are adapters around the domain.

### 3.2 Single source of truth

- The ledger is the source of truth for cash and realized P&L.
- Positions are derived from filled trades and adjustments.
- Market data is timestamped and never treated as timeless.
- Strategy parameters are versioned.
- The database, not browser state, owns durable trading state.

### 3.3 Determinism where money is involved

Given the same configuration, market snapshot, portfolio state, and strategy version, the decision and risk result must be reproducible.

### 3.4 Explainability by construction

Every recommendation stores:

- decision,
- score,
- confidence,
- market regime,
- strongest positive factors,
- strongest negative factors,
- risk blocks,
- data freshness,
- strategy version,
- model or ruleset version.

### 3.5 Incremental migration

Refactoring must use compatibility layers and characterization tests. No large rewrite should replace working behavior in one merge.

---

## 4. System context

```text
                          ┌──────────────────────┐
                          │      Web Client      │
                          │ Dashboard / Settings │
                          └──────────┬───────────┘
                                     │ HTTPS
                          ┌──────────▼───────────┐
                          │   FastAPI Interface   │
                          │ Auth / API / Views    │
                          └──────────┬───────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
       ┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
       │ Runtime Service │  │ Query Services  │  │ Admin Services  │
       └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
                │                    │                    │
       ┌────────▼────────────────────▼────────────────────▼────────┐
       │                    Application Layer                       │
       │ Use cases, orchestration, transactions, idempotency       │
       └────────┬──────────────┬──────────────┬──────────────┬─────┘
                │              │              │              │
       ┌────────▼──────┐ ┌─────▼────────┐ ┌───▼────────┐ ┌──▼─────────┐
       │ Signal Engine │ │ Risk Engine  │ │ Portfolio  │ │ Execution │
       │ + Regime      │ │ + Sizing     │ │ + Ledger   │ │ Gateway   │
       └────────┬──────┘ └─────┬────────┘ └───┬────────┘ └──┬─────────┘
                │              │              │              │
       ┌────────▼──────────────▼──────────────▼──────────────▼───────┐
       │                   Infrastructure Layer                       │
       │ Market providers / Broker adapters / DB / Cache / Logging  │
       └──────────────────────────────────────────────────────────────┘
```

---

## 5. Bounded modules and responsibilities

### 5.1 API and presentation

**Owns**

- Authentication and session boundary.
- Request validation.
- Response schemas.
- Server-rendered views or frontend assets.
- User-facing error mapping.

**Must not own**

- Trading calculations.
- Position sizing.
- Direct SQL.
- Broker-specific decision logic.

### 5.2 Runtime orchestration

**Owns**

- Scheduling analysis cycles.
- Acquiring a consistent market snapshot.
- Invoking feature, regime, signal, risk, and execution use cases.
- Recording cycle status and failures.
- Enforcing cycle-level idempotency.

**Must not own**

- Indicator formulas.
- Portfolio accounting formulas.
- HTML rendering.
- Broker SDK details.

### 5.3 Market data

**Owns**

- Market catalog.
- Provider capability mapping.
- Quotes, candles, volume, and timestamps.
- Retry, rate-limit, timeout, and cache policies.
- Data normalization.
- Freshness and quality flags.

**Key rule:** a `Market` is identified by venue, base asset, quote asset, and market type. Display symbols are not primary identifiers.

### 5.4 Feature and indicator engine

**Owns**

- Pure calculations over normalized candle series.
- Indicator metadata and lookback requirements.
- Missing-data behavior.
- Feature vectors used by strategy evaluation.

**Examples**

- EMA and SMA families.
- RSI.
- MACD.
- ATR and realized volatility.
- ADX or trend-strength measures.
- Return, momentum, and drawdown features.
- Volume and liquidity proxies where data supports them.

Indicator output must include timestamp, inputs used, and validity state.

### 5.5 Market regime engine

Classifies the environment before strategy scoring.

Initial regimes:

- `TREND_UP`
- `TREND_DOWN`
- `RANGE`
- `HIGH_VOLATILITY`
- `LOW_LIQUIDITY`
- `UNCERTAIN`

The regime is an input to strategy evaluation, not an order instruction.

### 5.6 Signal engine

**Owns**

- Strategy evaluation.
- Weighted evidence aggregation.
- Score normalization.
- Confidence calculation.
- BUY, HOLD, SELL recommendation.
- Human-readable explanation.

**Does not own**

- Available cash.
- Maximum exposure.
- Broker calls.
- Final order authorization.

Recommended initial score contract:

```text
score:       0..100
confidence:  0..100
signal:      BUY | HOLD | SELL
quality:     INVALID | LOW | MEDIUM | HIGH
```

A five-level visual label may map to the analytical result without replacing it:

- Blue: exceptional opportunity or strongest validated state.
- Green: favorable.
- Yellow: neutral or wait.
- Orange: unfavorable or reduce exposure.
- Red: blocked, invalid, or high risk.

The exact mapping must be configurable and tested.

### 5.7 Risk engine

The Risk Engine has veto authority.

**Inputs**

- Proposed signal.
- Portfolio snapshot.
- Market snapshot.
- Fees and slippage assumptions.
- Account and strategy limits.
- Existing correlated exposures.
- Recent realized and unrealized losses.

**Outputs**

- `APPROVE`, `REDUCE`, or `REJECT`.
- Approved notional and quantity.
- Stop and exit policy when applicable.
- Explicit reasons and triggered limits.

Initial hard limits:

- Maximum notional per order.
- Maximum exposure per asset.
- Maximum total deployed capital.
- Minimum remaining cash.
- Maximum daily realized loss.
- Maximum portfolio drawdown.
- Maximum open positions.
- Market-data freshness threshold.
- Minimum liquidity or volume threshold where available.
- Cooldown after repeated losses or runtime errors.

### 5.8 Portfolio and accounting

The portfolio domain must keep these concepts separate:

- Cash balance.
- Reserved cash.
- Available cash.
- Position quantity.
- Average cost.
- Market value.
- Unrealized P&L.
- Realized P&L.
- Fees.
- Equity.
- Deposits, withdrawals, and adjustments.

Canonical identities:

```text
available_cash = cash_balance - reserved_cash
position_market_value = quantity * current_price
unrealized_pnl = position_market_value - remaining_cost_basis
portfolio_equity = available_cash + reserved_cash + sum(position_market_value)
```

All values must define currency and rounding policy. Cross-currency valuation requires an explicit conversion rate and timestamp.

### 5.9 Paper broker

The paper broker simulates execution while preserving broker-like behavior.

It must support:

- Validation before acceptance.
- Client order IDs.
- Order states.
- Fees.
- Configurable slippage.
- Partial fills when enabled.
- Rejected and cancelled orders.
- Deterministic fills in tests.
- Atomic ledger and position updates.

Minimum state machine:

```text
CREATED -> VALIDATED -> ACCEPTED -> FILLED
                    \-> REJECTED
          ACCEPTED -> PARTIALLY_FILLED -> FILLED
          ACCEPTED -> CANCELLED
```

### 5.10 Broker gateway

Defines a broker-neutral interface.

```python
class BrokerGateway(Protocol):
    def get_capabilities(self) -> BrokerCapabilities: ...
    def get_balances(self) -> list[BrokerBalance]: ...
    def preview_order(self, request: OrderRequest) -> OrderPreview: ...
    def submit_order(self, request: OrderRequest) -> BrokerOrder: ...
    def cancel_order(self, broker_order_id: str) -> BrokerOrder: ...
    def get_order(self, broker_order_id: str) -> BrokerOrder: ...
```

The Bitso adapter must remain isolated from domain and strategy modules.

### 5.11 Persistence

Persistence provides repositories and unit-of-work boundaries.

**Requirements**

- SQLAlchemy models remain infrastructure concerns.
- Domain entities do not depend on active database sessions.
- Migrations are mandatory for schema changes.
- PostgreSQL is the production target.
- SQLite may be used for local development and focused tests only when behavior is compatible.
- Monetary values use fixed precision.
- Timestamps are UTC in storage.
- Immutable audit records are append-only.

### 5.12 Dashboard and reporting

The dashboard reads from query services and must not calculate authoritative accounting values in JavaScript.

Initial panels:

1. System mode and runtime health.
2. Total equity and available capital.
3. Daily, weekly, monthly, and all-time P&L.
4. Open positions only in the portfolio panel.
5. Last ten completed trades in the recent-history panel.
6. Market ranking with score, confidence, regime, freshness, and explanation.
7. Equity curve.
8. Drawdown curve.
9. Win rate, expectancy, profit factor, and fee impact.
10. Risk limits and current utilization.
11. Runtime cycle status and provider health.

Refresh policies must be event- or endpoint-specific. Avoid full-page reloads and duplicate polling loops.

---

## 6. Proposed source structure

Migration is incremental; these paths describe the target, not an instruction to move everything immediately.

```text
app/
  api/
    dependencies.py
    error_handlers.py
    routes/
      auth.py
      dashboard.py
      markets.py
      orders.py
      portfolio.py
      runtime.py
    schemas/
  application/
    commands/
    queries/
    services/
    unit_of_work.py
  domain/
    common/
    market/
    signals/
    risk/
    portfolio/
    orders/
    performance/
  infrastructure/
    brokers/
      paper/
      bitso/
    market_data/
    persistence/
      models/
      repositories/
      migrations/
    cache/
    observability/
  runtime/
    scheduler.py
    cycle.py
    state.py
  web/
    templates/
    static/
  config/
    settings.py
    logging.py
  main.py

tests/
  unit/
  integration/
  contract/
  end_to_end/
  fixtures/

docs/v3/
```

---

## 7. Core data model

### 7.1 Asset

- `asset_id`
- `symbol`
- `name`
- `asset_type`
- `precision`
- `active`

### 7.2 Market

- `market_id`
- `venue`
- `base_asset_id`
- `quote_asset_id`
- `market_type`
- `provider_symbol`
- `min_quantity`
- `min_notional`
- `price_increment`
- `quantity_increment`
- `active`
- `verified_at`

### 7.3 Candle

- `market_id`
- `timeframe`
- `opened_at`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `provider`
- `quality_status`

Unique key: market, timeframe, opening timestamp, provider.

### 7.4 Analysis snapshot

- `analysis_id`
- `market_id`
- `as_of`
- `strategy_version`
- `feature_set_version`
- `regime`
- `score`
- `confidence`
- `signal`
- `explanation_json`
- `data_quality`
- `created_at`

### 7.5 Order

- `order_id`
- `client_order_id`
- `account_id`
- `market_id`
- `side`
- `order_type`
- `requested_quantity`
- `requested_notional`
- `status`
- `mode`
- `strategy_version`
- `risk_decision_id`
- `broker_order_id`
- `created_at`
- `updated_at`

### 7.6 Fill

- `fill_id`
- `order_id`
- `quantity`
- `price`
- `fee_amount`
- `fee_currency`
- `filled_at`

### 7.7 Ledger entry

- `entry_id`
- `account_id`
- `currency`
- `entry_type`
- `amount`
- `reference_type`
- `reference_id`
- `occurred_at`
- `created_at`

Ledger entries are append-only. Corrections use compensating entries.

### 7.8 Position snapshot

- `position_id`
- `account_id`
- `market_id`
- `quantity`
- `average_cost`
- `remaining_cost_basis`
- `realized_pnl`
- `updated_at`

### 7.9 Risk decision

- `risk_decision_id`
- `analysis_id`
- `decision`
- `requested_notional`
- `approved_notional`
- `rules_version`
- `reasons_json`
- `portfolio_snapshot_json`
- `created_at`

### 7.10 Runtime cycle

- `cycle_id`
- `started_at`
- `completed_at`
- `status`
- `markets_requested`
- `markets_completed`
- `error_summary`
- `code_version`

---

## 8. Runtime cycle contract

A runtime cycle must follow a fixed orchestration sequence.

```text
1. Acquire distributed or process lock.
2. Create RuntimeCycle record.
3. Load validated configuration.
4. Load market catalog and enabled strategies.
5. Fetch or read a timestamp-consistent market snapshot.
6. Validate freshness and data quality.
7. Calculate features.
8. Classify regime.
9. Generate signal and explanation.
10. Load portfolio snapshot.
11. Evaluate risk and position size.
12. If approved, create idempotent order request.
13. Execute through paper broker while live mode is disabled.
14. Persist order, fills, ledger, and position atomically.
15. Persist analysis and risk decision even when no trade occurs.
16. Publish query/read-model updates.
17. Complete cycle with metrics.
18. Release lock.
```

A failure in one market must be isolated where safe, but infrastructure failures affecting accounting must fail the cycle.

---

## 9. Strategy and scoring design

### 9.1 Evidence groups

The initial explainable ruleset should group features into:

- Trend.
- Momentum.
- Volatility.
- Volume/liquidity.
- Mean reversion.
- Market regime compatibility.
- Data quality.
- Portfolio context.

Each group produces:

- normalized contribution,
- weight,
- validity,
- explanation.

### 9.2 Confidence

Confidence is not the same as score. It reflects evidence quality and agreement.

Confidence should decrease when:

- insufficient history exists,
- indicators disagree,
- provider data is stale,
- volatility exceeds strategy limits,
- liquidity data is missing,
- the market regime is uncertain,
- the ruleset lacks validation for the asset or timeframe.

### 9.3 Versioning

Every result references immutable versions for:

- strategy,
- feature set,
- risk rules,
- fee model,
- slippage model.

This is required for backtesting and auditability.

---

## 10. Risk model specification

### 10.1 Risk policy layers

1. **System policy:** live mode, provider health, database health.
2. **Account policy:** drawdown, daily loss, available equity.
3. **Portfolio policy:** exposure, concentration, correlation.
4. **Market policy:** minimum order, liquidity, volatility, freshness.
5. **Strategy policy:** score, confidence, cooldown, regime compatibility.
6. **Order policy:** notional, quantity, fee, rounding, duplicate detection.

Every layer can reject. Only explicit approval proceeds.

### 10.2 Position sizing

The first production-quality sizing model should be deterministic and bounded:

```text
raw_notional = min(
  configured_max_per_trade,
  available_cash * max_cash_fraction,
  equity * risk_budget_fraction / stop_distance_fraction
)

approved_notional = apply_market_limits_and_rounding(raw_notional)
```

When a reliable stop distance cannot be calculated, use the more conservative fixed-notional rule or reject.

Kelly sizing may be reported as an analytical metric later but must not directly control live or paper order size until validated.

### 10.3 Drawdown controls

Track:

- current drawdown,
- maximum drawdown,
- daily drawdown,
- strategy drawdown,
- asset drawdown.

Risk response can progress through:

- normal,
- reduced size,
- no new positions,
- forced simulation pause.

---

## 11. Performance analytics

Definitions must be shared by API, dashboard, reports, and tests.

Minimum metrics:

- Net P&L.
- Gross P&L.
- Fees.
- Return percentage.
- Win rate.
- Average win.
- Average loss.
- Payoff ratio.
- Expectancy.
- Profit factor.
- Maximum drawdown.
- Current drawdown.
- Exposure.
- Turnover.
- Trade count.
- Holding-period statistics.

Sharpe, Sortino, and Calmar require a documented return series, sampling interval, and annualization assumption. Do not display them until the required history is valid.

---

## 12. Backtesting architecture

Backtesting reuses domain logic but replaces external time and execution.

```text
Historical Data -> Simulated Clock -> Strategy -> Risk -> Fill Model -> Ledger
```

Requirements:

- No look-ahead bias.
- No future candle access.
- Fee and slippage models.
- Reproducible seed when randomness is used.
- Walk-forward evaluation.
- Train/validation/test period separation for learned weights.
- Parameter and strategy version tracking.
- Exportable results.

Backtesting must never reuse a production database transaction or live broker adapter.

---

## 13. Learning and optimization guardrails

The first learning layer should be analytical, not self-authorizing.

It may:

- compare outcome by strategy version,
- calculate feature contribution statistics,
- identify regimes where a strategy performs poorly,
- recommend candidate weight changes,
- flag overfitting risk.

It may not:

- directly update production weights,
- bypass risk limits,
- enable live trading,
- delete losing trades,
- train on future data.

Any parameter change must produce a new version, backtest result, review record, and deployment approval.

---

## 14. API design rules

1. Every route has a unique explicit `operation_id`.
2. Request and response bodies use versioned schemas.
3. Domain errors map consistently to HTTP errors.
4. Mutation endpoints support idempotency keys.
5. Timestamps include timezone and are returned in ISO 8601.
6. Monetary responses include amount and currency.
7. List endpoints support pagination where growth is unbounded.
8. Sensitive configuration is never returned.
9. Health endpoints distinguish liveness, readiness, and dependency degradation.
10. Browser sessions and programmatic APIs use separate authentication policies if both exist.

Candidate route groups:

```text
/api/v3/auth
/api/v3/system
/api/v3/markets
/api/v3/analysis
/api/v3/portfolio
/api/v3/orders
/api/v3/trades
/api/v3/performance
/api/v3/risk
/api/v3/runtime
/api/v3/configuration
```

---

## 15. Configuration model

Configuration sources, in precedence order:

1. Safe code defaults.
2. Environment-specific non-secret configuration.
3. Environment variables and secret store.
4. Versioned database settings where runtime editing is allowed.

Configuration categories:

- Application.
- Authentication.
- Database.
- Market providers.
- Broker.
- Runtime frequency.
- Strategy selection and parameters.
- Risk limits.
- Fees and slippage.
- Dashboard refresh.
- Logging and observability.

All settings must validate at startup. Dangerous configuration must not silently fall back.

---

## 16. Security specification

- Passwords are hashed using an appropriate adaptive password hash.
- Session cookies are `HttpOnly`, `SameSite`, and `Secure` in production.
- Session secrets are environment-provided and rotated deliberately.
- CSRF protection is required for cookie-authenticated mutations.
- Login attempts are rate-limited.
- API and provider errors do not expose secrets.
- Logs redact credentials and authorization headers.
- Dependency versions are scanned.
- Production debug mode is disabled.
- Database and broker credentials use least privilege.
- Bitso keys remain read-only until a separate live-trading security review.

---

## 17. Observability

### 17.1 Structured logs

Every runtime cycle, analysis, risk decision, order, and failure includes a correlation identifier.

### 17.2 Metrics

Minimum operational metrics:

- Runtime cycle duration and outcome.
- Market fetch latency and failure rate.
- Cache hit rate.
- Stale-data count.
- Analysis count by signal.
- Risk rejection count by reason.
- Orders and fills by status.
- Database latency and errors.
- Dashboard endpoint latency.

### 17.3 Health

- **Liveness:** process is running.
- **Readiness:** configuration and database are usable.
- **Degraded:** optional provider unavailable, cached/read-only behavior possible.

---

## 18. Testing strategy

### 18.1 Unit tests

Pure domain behavior:

- Indicators.
- Signal contributions.
- Confidence.
- Risk rules.
- Position sizing.
- Fee calculations.
- Ledger identities.
- Position updates.
- Performance metrics.

### 18.2 Integration tests

- SQLAlchemy repositories.
- Migrations.
- FastAPI routes.
- Authentication and sessions.
- Paper broker transaction behavior.
- Runtime cycle with fake providers.

### 18.3 Contract tests

- Bitso adapter response normalization.
- Market-data provider contracts.
- Broker gateway behavior.

External services must be mocked or recorded safely in CI; tests must not place real orders.

### 18.4 End-to-end tests

Critical user flows:

- Login.
- View current markets.
- Open a simulated position.
- Reject an order without funds.
- Close a simulated position.
- Verify realized P&L and fee impact.
- Verify only open positions appear in the portfolio panel.
- Verify recent-history limit.
- Verify automatic refresh without a manual refresh control.

### 18.5 Test quality rules

- Never delete a failing test without documenting why behavior changed.
- A bug fix adds a regression test first or in the same commit.
- Time, randomness, and provider responses are injectable.
- Tests do not depend on execution order.
- CI uses a clean database.

---

## 19. CI and merge policy

Required checks before merge:

1. Formatting and linting.
2. Static type checks for the agreed scope.
3. Unit tests.
4. Integration tests.
5. Migration validation.
6. Secret scan.
7. Dependency vulnerability scan.
8. Duplicate route and `operation_id` validation.
9. Build/startup smoke test.

Pull requests must be logically scoped. Large refactors require a migration plan and characterization tests.

---

## 20. Deployment model

### 20.1 Environments

- Local development.
- CI test.
- Preview/staging.
- Production simulation.
- Future live environment, physically and logically separated.

### 20.2 Production simulation

- PostgreSQL.
- `LIVE_TRADING=false`.
- Explicit migration step.
- Health checks.
- Persistent logs or external log sink.
- Database backup policy.
- Rollback to previous deploy.

### 20.3 Failure recovery

- Runtime cycle state supports safe restart.
- Submitted orders reconcile by client order ID.
- Ledger writes are atomic.
- Database restoration is documented and tested.
- Degraded market providers stop new decisions rather than using unbounded stale data.

---

## 21. Migration roadmap

### Phase 0 — Baseline and stabilization

- Obtain green CI.
- Inventory routes, models, services, settings, and tests.
- Record current behavior with characterization tests.
- Resolve duplicate operation IDs and runtime crashes.
- Preserve simulation behavior.

### Phase 1 — Accounting and paper-broker correctness

- Introduce decimal-safe money types.
- Define ledger invariants.
- Normalize orders, fills, and position updates.
- Add fee and slippage policies.
- Add atomic persistence tests.

### Phase 2 — Market and analysis contracts

- Normalize market identifiers and provider capabilities.
- Add historical candle interface.
- Version feature sets and strategies.
- Separate score from confidence.
- Persist explanations and data quality.

### Phase 3 — Risk Engine

- Introduce explicit risk decisions.
- Add deterministic sizing.
- Add account, portfolio, market, and strategy limits.
- Expose risk utilization in the dashboard.

### Phase 4 — Dashboard and performance

- Implement consistent query services.
- Add P&L periods and asset filters.
- Add equity and drawdown curves.
- Add validated performance metrics.
- Optimize polling and caching.

### Phase 5 — Backtesting

- Add historical runner and simulated clock.
- Reuse strategy, risk, paper execution, and accounting domains.
- Add bias controls and reports.

### Phase 6 — Learning analytics

- Add outcome attribution.
- Add strategy/regime comparisons.
- Generate recommendations only; no automatic production mutation.

### Phase 7 — Live-readiness review

- Security review.
- Broker reconciliation.
- Kill switch.
- Manual approval workflow.
- Separate credentials and environment.
- Live trading remains disabled until the owner explicitly authorizes it.

---

## 22. Architecture decision records to create

- ADR-001: Paper-trading-first safety model.
- ADR-002: PostgreSQL production and SQLite test boundaries.
- ADR-003: Fixed-precision monetary arithmetic.
- ADR-004: Ledger as accounting source of truth.
- ADR-005: Broker-neutral execution gateway.
- ADR-006: Strategy and risk-rule versioning.
- ADR-007: Runtime idempotency model.
- ADR-008: Market symbol normalization.
- ADR-009: Dashboard query/read model.
- ADR-010: Backtesting reuse of domain logic.
- ADR-011: Explainable rules before self-modifying ML.
- ADR-012: Live-trading environment separation.

---

## 23. Definition of done for v3 foundation

The v3 foundation is complete when:

- CI is green.
- Current paper-trading behavior is covered by tests.
- Capital, positions, fees, and P&L reconcile from the ledger.
- Runtime cycles are deterministic and observable.
- Signal, confidence, risk decision, and order execution are separate steps.
- Market data is normalized and freshness-aware.
- Strategy and risk versions are persisted.
- Dashboard values come from authoritative query services.
- Backtesting can reuse domain logic without external broker calls.
- Documentation and ADRs match the implementation.
- Live trading remains disabled.

---

## 24. Open decisions

These decisions require evidence from the current repository audit and should not be guessed:

1. Existing authoritative source for paper cash and positions.
2. Current database schema and migration head.
3. Exact market-data history available from Bitso or other providers.
4. Current timeframes and indicator lookbacks.
5. Whether stock symbols are simulated, delayed, or backed by a provider.
6. Current session/authentication implementation and threat model.
7. Current runtime scheduling and concurrency model.
8. Existing fee calculation source and currency conversion behavior.
9. Required retention period for candles, analyses, and audit records.
10. Render resource limits and worker topology.

The audit must resolve these before implementation sections are marked final.
