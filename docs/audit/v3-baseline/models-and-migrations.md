# Models and Migrations Audit

## SQLAlchemy model areas

- `app/db/models.py` defines persisted tables for simulated orders, backtest runs/trades, optimization runs/results, paper accounts/positions/trades/orders and analytics snapshots/events.
- Repository modules wrap persistence for simulated orders, backtests, optimizations, paper trading, experiments and analytics.
- Test mode calls `Base.metadata.create_all(bind=engine)` inside `create_app()`; real environments are expected to use Alembic.

## Alembic chain

Observed migration order:

1. `20260720_0001_create_simulated_orders.py`
2. `20260720_0002_add_simulation_position_fields.py`
3. `20260720_0003_add_simulation_fees.py`
4. `20260721_0004_create_backtest_tables.py`
5. `20260722_0005_create_optimization_tables.py`
6. `20260722_0006_create_paper_trading_tables.py`
7. `20260722_0007_create_analytics_tables.py`

## Schema observations

- `simulated_orders` starts with order identity, timestamps, book/side/amount/reference price/status and risk metadata, then gains close fields and fee fields.
- Backtest tables include run metadata and trade-level entry/exit/P&L/fee metrics.
- Optimization tables store parameter JSON, metrics JSON and composite ranking fields.
- Paper tables cover accounts, positions, trades and orders, but the runtime paper broker primarily uses in-memory portfolio state unless a request-scoped repository is explicitly used during `/paper/start`.
- Analytics tables store JSON snapshots/events.

## Findings

1. The migration chain is linear and indexed for common filtering fields.
2. Some fields are nullable because they are added after initial table creation or represent close/exit state; this is valid but should be checked against domain invariants in v3.
3. Persistence is uneven: simulated orders are database-backed through legacy flows, while runtime broker state is in-memory.
4. There is no v3-specific migration plan or v3 schema namespace yet.

## Evidence commands

- `find migrations -maxdepth 3 -type f -print -exec sed -n '1,220p' {} \;`
- `rg -n "class .*\(Base\)|__tablename__|create_table|create_index" app/db migrations -S`
