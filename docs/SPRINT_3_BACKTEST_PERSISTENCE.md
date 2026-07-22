# Sprint 3 — Backtesting persistence

Adds SQLAlchemy models and a repository for storing backtest runs and trades. JSON fields use deterministic serialization with sorted keys and reject non-serializable values or invalid stored JSON.

The Alembic migration creates only `backtest_runs`, `backtest_trades`, and related indexes. It does not alter `simulated_orders`.
