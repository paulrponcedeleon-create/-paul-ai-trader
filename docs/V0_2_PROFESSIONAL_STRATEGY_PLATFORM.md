# v0.2 — Professional Strategy Platform

## Architecture diagram

```text
HTTP API
  ├─ GET /strategies ───────────────┐
  ├─ POST /backtests ───────────────┼─ StrategyFactory ─ StrategyRegistry ─ Strategy
  └─ POST /walk-forward ────────────┘
                                      │
HistoricalDataProvider ─ BacktestEngine ─ BrokerSimulator ─ BacktestMetrics
                                      │
                                      └─ BacktestRepository (optional)

BacktestResult ─ Report Exporters ─ JSON / CSV / Markdown
```

## Framework

Strategies implement `Strategy`: `name`, `version`, `description`, `parameters_schema()` and `generate_signal(history)`. Strategies are pure and do not depend on FastAPI, SQLAlchemy or Bitso.

## Registry and factory

`StrategyRegistry` owns registration and lookup. `StrategyFactory` creates strategies by name, version and parameters without large conditional blocks. Built-in strategies self-register during package import.

## Strategies

Built-ins: Momentum, RSI, EMA Cross, MACD, Bollinger, Mean Reversion and Breakout. Momentum preserves the existing signal logic.

## Indicators

The indicators library includes EMA, SMA, RSI, MACD, ATR, Bollinger Bands, VWAP, Stochastic, Highest High, Lowest Low, Rolling Mean and Rolling Std.

## Backtesting

`BacktestEngine` receives strategies through `StrategyFactory` or injected callables. It no longer imports or knows `momentum_signal` directly. The engine remains deterministic and reusable.

## Walk Forward

`WalkForwardEngine` reuses `BacktestEngine` for rolling or anchored validation windows and returns a consolidated report.

## API

Implemented endpoints: `GET /strategies`, `GET /strategies/{name}`, `POST /backtests`, `GET /backtests`, `GET /backtests/{id}`, `DELETE /backtests/{id}` and `POST /walk-forward`.

## Reports

Report exporters produce JSON, CSV and Markdown with parameters, trades, metrics, equity curve and executive summary.

## Current exclusions

No Optimizer, Grid Search, Random Search, Paper Trading, Machine Learning, Telegram, Discord, Dashboard, Live Trading or Bitso Live were implemented.
