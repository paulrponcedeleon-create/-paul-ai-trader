# Capital, Positions, Fees and P&L Audit

## Legacy simulated-order capital

Legacy dashboard trading uses `SqlSimulatedOrderRepository` and service helpers:

- buys are recorded in `simulated_orders`,
- open position summaries use current market prices,
- capital ledger derives available cash from initial capital, open invested amount and realized P&L,
- fee fields were added to simulated orders by migration `20260720_0003`.

## Paper trading capital

`PortfolioManager` tracks:

- initial cash,
- cash,
- realized P&L,
- open positions,
- closed positions,
- orders,
- trades,
- peak equity and max drawdown.

Open positions subtract `amount + entry_fee` from cash. Full closes add gross exit minus exit fee back to cash and realize net P&L. Stop loss, take profit, trailing stop and expiration close through the same close path.

## Backtesting capital

`BrokerSimulator` models one backtest position at a time, subtracts entry fee on buy, subtracts exit fee on close, returns net exit cash and reports P&L/fees/return.

## Findings

1. Fee-aware P&L exists in simulated orders, paper trading and backtesting, but the implementations are separate.
2. Partial position closes are not present in the local v2 baseline; sells close whole paper positions.
3. Capital ledgers for legacy simulated orders and paper broker balances are different sources of truth.
4. Runtime sell requests use a minimum trade amount but the baseline paper broker closes the full matching position, so amount semantics are inconsistent.
5. v3 should consolidate capital invariants: available cash, locked/invested amount, realized/unrealized P&L, entry/exit fees and position quantity.

## Evidence commands

- `sed -n '1,320p' app/repositories/simulated_orders.py`
- `sed -n '1,320p' app/services/portfolio.py app/services/performance.py app/services/risk.py`
- `sed -n '1,320p' app/paper_trading/portfolio.py app/paper_trading/models.py app/paper_trading/risk.py app/paper_trading/sizing.py`
- `sed -n '1,220p' app/services/broker_simulator.py`
- `rg -n "available_cash_mxn|entry_fee|exit_fee|realized_pnl|unrealized_pnl|close_position|capital_ledger" app tests -S`
