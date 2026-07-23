# Paul AI Trader v3 — Analysis, Signal, and Learning Engine

**Status:** Working specification  
**Scope:** Explainable analysis and recommendation generation  
**Safety:** The engine never submits orders

---

## 1. Purpose

The v3 Analysis Engine converts normalized market history into reproducible features, market-regime classification, explainable BUY/HOLD/SELL recommendations, score, confidence, and quality. It is intentionally separated from capital, portfolio, risk approval, and order execution.

The first v3 milestone uses transparent deterministic logic. Statistical and machine-learning components may be added later only when they remain versioned, validated, and explainable.

---

## 2. Responsibilities

The engine owns:

- input-data validation,
- feature calculation,
- indicator calculation,
- market-regime classification,
- strategy evaluation,
- factor contribution calculation,
- score normalization,
- confidence estimation,
- signal recommendation,
- explanation generation,
- analytical versioning,
- outcome attribution for later learning analytics.

The engine does not own:

- available cash,
- position sizing,
- portfolio exposure,
- maximum loss limits,
- broker calls,
- order persistence,
- dashboard rendering.

---

## 3. Processing pipeline

```text
Normalized candles/quote
        |
        v
Data-quality validation
        |
        v
Feature and indicator calculation
        |
        v
Market-regime classification
        |
        v
Strategy evidence evaluation
        |
        v
Raw factor contributions
        |
        v
Score + confidence + quality
        |
        v
BUY / HOLD / SELL recommendation
        |
        v
Persisted explanation and versions
```

If required data fails validation, the result is `INVALID` or `DEGRADED`; the engine does not fabricate missing values.

---

## 4. Input contract

A single analysis request contains:

```python
AnalysisRequest(
    market_id,
    analysis_at,
    quote,
    candles_by_timeframe,
    strategy_version,
    feature_schema_version,
    optional_context,
)
```

Required metadata:

- market identifier,
- provider/source,
- event timestamps,
- received timestamps,
- selected timeframes,
- candle finality,
- requested strategy version,
- input checksum.

The engine consumes a snapshot; it does not fetch network data itself.

---

## 5. Data-quality model

Quality states:

```text
VALID
DEGRADED
STALE
INSUFFICIENT_HISTORY
INVALID
```

Each feature has:

- value,
- validity,
- source timeframe,
- lookback used,
- latest input timestamp,
- quality flags.

Example flags:

```text
MISSING_CANDLES
NON_FINAL_CANDLE_USED
DUPLICATE_TIMESTAMP
OUT_OF_ORDER_DATA
PRICE_GAP
ZERO_OR_NEGATIVE_PRICE
STALE_QUOTE
INSUFFICIENT_LOOKBACK
MISSING_VOLUME
PROVIDER_DISCONTINUITY
```

Hard-invalid conditions block a tradeable recommendation. Degraded conditions reduce confidence and are visible in the explanation.

---

## 6. Initial feature families

The exact enabled set is strategy-versioned.

### 6.1 Trend

- SMA/EMA relationships.
- Price relative to selected moving averages.
- Moving-average slope.
- Higher-high/lower-low structure.
- ADX or equivalent trend strength.
- Multi-timeframe trend agreement.

### 6.2 Momentum

- RSI.
- MACD line, signal, and histogram.
- Rate of change.
- Consecutive return behavior.
- Distance from recent extrema.

### 6.3 Volatility

- ATR.
- ATR as percentage of price.
- Realized return volatility.
- Bollinger-band width or equivalent dispersion.
- Gap or shock detection.

### 6.4 Volume and liquidity

Only when provider data supports it:

- current volume relative to rolling average,
- 24-hour volume,
- spread percentage,
- quote depth proxy,
- abnormal volume event.

Missing liquidity data must not be silently scored as favorable.

### 6.5 Risk context features

The Analysis Engine may describe but not enforce:

- recent drawdown in the market,
- downside volatility,
- extreme-move flags,
- correlation estimates supplied by a separate portfolio analytics service.

Final risk authorization remains outside this engine.

---

## 7. Indicator implementation rules

1. Indicator functions are pure and deterministic.
2. Lookback requirements are explicit.
3. Time-series order is validated.
4. Warm-up periods are not treated as valid outputs.
5. NaN/infinite values are invalid.
6. Timeframe aggregation is performed before indicator calculation and is tested.
7. Libraries may be used behind an adapter, but formulas and versions are documented.
8. Tests include known reference vectors.
9. No indicator reads global configuration directly.
10. No indicator produces a BUY or SELL action by itself.

---

## 8. Market-regime engine

Initial regimes:

```text
TREND_UP
TREND_DOWN
RANGE
HIGH_VOLATILITY
LOW_VOLATILITY
LOW_LIQUIDITY
TRANSITION
UNCERTAIN
```

A regime result contains:

- primary regime,
- optional secondary flags,
- confidence,
- evidence,
- thresholds/version.

Example:

```json
{
  "primary": "TREND_UP",
  "confidence": "76.2",
  "flags": ["ELEVATED_VOLATILITY"],
  "evidence": [
    {"code": "EMA_ALIGNMENT", "value": "POSITIVE"},
    {"code": "ADX", "value": "28.4"}
  ]
}
```

Regime classification changes how factors are weighted; it never directly submits an order.

---

## 9. Strategy evidence model

A strategy consists of named factors. Each factor returns:

```python
FactorResult(
    code,
    direction,          # POSITIVE, NEGATIVE, NEUTRAL, INVALID
    raw_value,
    normalized_value,   # -1..1 where meaningful
    base_weight,
    regime_multiplier,
    quality_multiplier,
    contribution,
    explanation,
)
```

Contribution is deterministic and bounded.

Candidate initial factors:

- trend alignment,
- momentum confirmation,
- MACD direction,
- RSI state and divergence warning,
- breakout/breakdown evidence,
- volatility suitability,
- volume confirmation,
- spread/liquidity quality,
- multi-timeframe agreement,
- overextension penalty,
- data-quality penalty.

A factor may be disabled by strategy version; disabled is different from neutral or missing.

---

## 10. Score calculation

The score represents directional favorability, not certainty.

Recommended conceptual model:

```text
raw_directional_value = sum(valid factor contributions)
normalized_direction  = bounded(raw_directional_value, -1, +1)
score                 = 50 + 50 * normalized_direction
```

Thus:

```text
0   strongly unfavorable
50  neutral
100 strongly favorable
```

Exact normalization, clipping, and factor caps are strategy-versioned.

Rules:

- Missing required factors can invalidate the score.
- One extreme factor cannot dominate unless explicitly allowed.
- Penalties remain visible.
- Score is stored with precision but displayed appropriately.

---

## 11. Confidence calculation

Confidence measures trust in the analysis, not expected profit.

Candidate components:

- data completeness,
- data freshness,
- factor agreement,
- regime-classification confidence,
- multi-timeframe agreement,
- historical calibration for the same strategy/regime,
- liquidity/data-quality state.

Conceptual structure:

```text
confidence = weighted combination of quality and agreement terms
confidence = bounded 0..100
```

Low confidence can convert an otherwise favorable score to HOLD.

Confidence must never be derived solely from the score magnitude.

---

## 12. Signal policy

The signal is a recommendation before risk approval.

Candidate baseline policy, configurable by strategy version:

```text
BUY  when score >= buy threshold
          and confidence >= minimum confidence
          and quality is valid
          and regime is not blocked for the strategy

SELL when score <= sell threshold
          and confidence >= minimum confidence
          and quality is valid

HOLD otherwise
```

The signal policy may distinguish:

- opening a new position,
- holding an existing position,
- reducing exposure,
- closing a position.

The initial API may expose only BUY/HOLD/SELL while retaining more specific internal intent codes.

---

## 13. Five-level visual state

The visual color is a presentation mapping, not the analytical truth.

Recommended constraints:

### Blue

Requires an exceptional favorable score, high confidence, valid data, favorable regime, and no severe warning. Blue should be rare.

### Green

Favorable score and sufficient confidence/quality.

### Yellow

Neutral, conflicting, insufficiently confident, or wait state.

### Orange

Unfavorable conditions, deterioration, or reduce/avoid recommendation without a hard invalidation.

### Red

Invalid data, risk/prohibition block, strongly adverse state, or system condition requiring no new trade.

The dashboard should show the textual reason and not rely on color alone.

---

## 14. Explanation contract

Every decision stores:

- one-sentence summary,
- strongest positive factors,
- strongest negative factors,
- regime explanation,
- data-quality warnings,
- score and confidence,
- strategy and feature versions,
- analysis timestamp and input cutoff.

Example summary:

```text
BUY recommendation: the medium- and long-term trends are aligned and momentum is positive, but elevated volatility reduces confidence.
```

Explanations must be generated from structured factor results, not from an unconstrained language model inventing reasons.

A language model may later improve phrasing only if the structured facts remain the source and output is validated.

---

## 15. Strategy version format

A strategy version contains:

```json
{
  "strategy_code": "MULTI_FACTOR_SPOT",
  "version": "3.0.0",
  "feature_schema_version": "3.0.0",
  "timeframes": ["1h", "4h", "1d"],
  "factors": {
    "trend_alignment": {"weight": "0.22", "enabled": true},
    "momentum": {"weight": "0.18", "enabled": true},
    "volatility_penalty": {"weight": "0.14", "enabled": true}
  },
  "thresholds": {
    "buy_score": "68.0",
    "sell_score": "32.0",
    "minimum_confidence": "60.0"
  },
  "checksum": "..."
}
```

All active configuration is immutable and checksummed.

---

## 16. Historical outcome attribution

After a signal, the system may calculate later outcomes at predefined horizons without changing the original decision.

Example horizons:

```text
1 hour
4 hours
1 day
7 days
position close
```

Outcome record may include:

- forward return,
- maximum favorable excursion,
- maximum adverse excursion,
- whether a hypothetical threshold was reached,
- actual paper-trade result when applicable,
- fees and slippage where applicable,
- market regime at decision time.

Outcome records support analysis; they do not prove causation.

---

## 17. Learning analytics

The initial Learning Engine is an offline recommendation system.

It may answer:

- Which factors correlate with favorable outcomes?
- In which regimes does a strategy perform poorly?
- Is confidence calibrated?
- Which assets/timeframes have insufficient samples?
- Are weights too sensitive to recent data?
- How do results change after fees and slippage?

It may propose:

- candidate factor weights,
- threshold changes,
- disabled factors,
- regime-specific variants,
- further data collection.

It may not:

- modify the active strategy automatically,
- execute orders,
- select only favorable historical periods,
- claim profitability without proper validation.

---

## 18. Validation protocol for strategy changes

Any candidate strategy version must pass:

1. Unit/reference tests.
2. Historical data-quality checks.
3. In-sample development analysis.
4. Out-of-sample validation.
5. Walk-forward or time-based validation where practical.
6. Fee/slippage sensitivity.
7. Regime and asset breakdown.
8. Comparison against a simple baseline.
9. Paper-trading observation period.
10. Explicit activation approval.

A candidate that improves total return but materially worsens drawdown, stability, or sample robustness must be flagged.

---

## 19. Avoiding common analytical errors

The system and reports must guard against:

- look-ahead bias,
- survivorship bias,
- data snooping,
- repeated parameter search without correction,
- leakage between training and validation periods,
- changing universe definitions after seeing results,
- ignoring fees/slippage,
- treating one asset or period as universal,
- using incomplete candles as final data,
- reporting metrics from too few trades.

---

## 20. Interfaces

Suggested domain protocols:

```python
class FeatureEngine(Protocol):
    def calculate(self, snapshot: MarketSnapshot, schema: FeatureSchema) -> FeatureSet: ...

class RegimeEngine(Protocol):
    def classify(self, features: FeatureSet, version: RegimeVersion) -> RegimeResult: ...

class SignalEngine(Protocol):
    def evaluate(
        self,
        features: FeatureSet,
        regime: RegimeResult,
        strategy: StrategyVersion,
    ) -> SignalDecision: ...

class OutcomeAttributor(Protocol):
    def evaluate(self, decision: SignalDecision, future_data: HistoricalWindow) -> OutcomeResult: ...
```

Implementations must be independent of FastAPI, SQLAlchemy sessions, and broker SDKs.

---

## 21. Persistence requirements

Persist:

- exact strategy version,
- exact feature schema version,
- input checksum,
- analysis and cutoff timestamps,
- feature values and quality,
- regime result,
- factor contributions,
- score,
- confidence,
- signal,
- explanation,
- model/ruleset version,
- later outcome attribution separately.

Do not overwrite an old decision when a new strategy version is activated.

---

## 22. Testing requirements

### Unit

- known indicator vectors,
- insufficient lookback,
- invalid data,
- factor bounds,
- score normalization,
- confidence boundaries,
- signal thresholds,
- explanation ordering,
- deterministic repeated output.

### Property/invariant

- score remains 0..100,
- confidence remains 0..100,
- invalid required data cannot produce a tradeable BUY/SELL,
- same inputs/version produce identical result,
- factor contributions sum to the documented raw score.

### Integration

- persisted analysis round-trip,
- version/checksum resolution,
- runtime snapshot to analysis flow,
- API ranking/read model.

### Backtest validation

- no future data visible,
- incomplete final candle handling,
- time-zone boundaries,
- fee/slippage inclusion.

---

## 23. Initial milestone definition of done

The v3 Analysis Engine foundation is complete when:

- historical candles are normalized and freshness-aware,
- indicators are pure and reference-tested,
- market regime is explicit,
- strategy versions are immutable,
- score and confidence are separate,
- every decision has structured positive and negative reasons,
- invalid/insufficient data fails closed,
- results are reproducible from persisted inputs and versions,
- no engine component can submit an order,
- learning analytics can evaluate outcomes without changing active settings.