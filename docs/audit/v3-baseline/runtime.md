# Runtime Audit

## Components

`RuntimeEngine` coordinates:

- market-data provider (`ProviderFactory`, default `bitso`),
- strategy factory (default `momentum`),
- AI decision engine,
- broker factory (default `paper`),
- execution engine,
- analytics service,
- system service / watchdog / events,
- risk manager with runtime-specific limits.

`RuntimeConfig` defaults to `btc_mxn`, one-minute timeframe, `paper` broker, Bitso provider and bounded history.

## Flow

1. `start()` connects market data and broker, discovers configured books by requesting candles, then marks runtime running.
2. `run_once()` starts lazily if needed, processes each active book, records book-level errors, increments cycle count and heartbeats watchdog.
3. `_process_book()` refreshes candles, updates paper market prices, evaluates strategy and AI, records asset observations, derives dynamic amount, risk-checks buy/sell actions and routes execution through `ExecutionEngine`.
4. Runtime API auto-starts a background loop when `runtime_auto_start` is true.

## Stability observations

- Runtime catches per-book exceptions and records them in `book_errors`, preventing a single market failure from crashing the whole loop.
- If all books fail in a cycle, watchdog records a runtime error.
- History is capped by `max_history`.
- Runtime can skip buys when a position already exists or deployable capital is below minimum.

## Findings

1. Runtime state is in-memory and process-local; restart loses runtime history, asset brains and paper broker positions unless separately persisted.
2. The default risk manager allows a very high position count but caps asset and total exposure.
3. Dynamic sizing in the current baseline can still propose amounts later rejected by risk if max trade amount and risk limit diverge; this is a candidate v3 stabilization item.
4. Background runtime is started from status requests, which is operationally convenient but couples reads to side effects.
5. Market candles from Bitso are synthetic from ticker data, not true OHLCV history.

## Evidence commands

- `sed -n '1,520p' app/runtime.py`
- `sed -n '1,150p' app/api/routes/runtime.py`
- `rg -n "RuntimeEngine|RuntimeConfig|run_once|_process_book|runtime_auto_start" app tests docs -S`
