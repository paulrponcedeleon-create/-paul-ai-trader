from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import BacktestRun, BacktestTrade


def dumps_json(value: dict[str, Any]) -> str:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("JSON no serializable.") from exc


def loads_json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("JSON almacenado inválido.") from exc
    if not isinstance(parsed, dict):
        raise ValueError("JSON almacenado inválido.")
    return parsed


def _run_to_dict(row: BacktestRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "created_at": row.created_at,
        "strategy_name": row.strategy_name,
        "strategy_version": row.strategy_version,
        "book": row.book,
        "start_at": row.start_at,
        "end_at": row.end_at,
        "initial_capital_mxn": row.initial_capital_mxn,
        "final_capital_mxn": row.final_capital_mxn,
        "total_return_pct": row.total_return_pct,
        "max_drawdown_pct": row.max_drawdown_pct,
        "win_rate_pct": row.win_rate_pct,
        "trades_count": row.trades_count,
        "parameters": loads_json(row.parameters_json),
        "metrics": loads_json(row.metrics_json),
        "status": row.status,
    }


def _trade_to_dict(row: BacktestTrade) -> dict[str, Any]:
    return {
        "id": row.id,
        "backtest_run_id": row.backtest_run_id,
        "opened_at": row.opened_at,
        "closed_at": row.closed_at,
        "book": row.book,
        "side": row.side,
        "entry_price": row.entry_price,
        "exit_price": row.exit_price,
        "amount_mxn": row.amount_mxn,
        "pnl_mxn": row.pnl_mxn,
        "return_pct": row.return_pct,
        "fees_mxn": row.fees_mxn,
        "signal": loads_json(row.signal_json),
    }


class BacktestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(
        self,
        *,
        strategy_name: str,
        strategy_version: str,
        book: str,
        start_at: datetime | None,
        end_at: datetime | None,
        initial_capital_mxn: float,
        parameters: dict[str, Any] | None = None,
        status: str = "pending",
    ) -> dict[str, Any]:
        row = BacktestRun(
            strategy_name=strategy_name,
            strategy_version=strategy_version,
            book=book.lower(),
            start_at=start_at,
            end_at=end_at,
            initial_capital_mxn=float(initial_capital_mxn),
            parameters_json=dumps_json(parameters or {}),
            metrics_json=dumps_json({}),
            status=status,
        )
        self.session.add(row)
        self.session.flush()
        return _run_to_dict(row)

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = self.session.get(BacktestRun, run_id)
        return _run_to_dict(row) if row else None

    def list_runs(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(BacktestRun)
            .order_by(BacktestRun.created_at.desc(), BacktestRun.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return [_run_to_dict(row) for row in rows]

    def add_trade(
        self,
        *,
        backtest_run_id: int,
        opened_at: datetime,
        closed_at: datetime,
        book: str,
        side: str,
        entry_price: float,
        exit_price: float,
        amount_mxn: float,
        pnl_mxn: float,
        return_pct: float,
        fees_mxn: float,
        signal: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = BacktestTrade(
            backtest_run_id=backtest_run_id,
            opened_at=opened_at,
            closed_at=closed_at,
            book=book.lower(),
            side=side,
            entry_price=float(entry_price),
            exit_price=float(exit_price),
            amount_mxn=float(amount_mxn),
            pnl_mxn=float(pnl_mxn),
            return_pct=float(return_pct),
            fees_mxn=float(fees_mxn),
            signal_json=dumps_json(signal or {}),
        )
        self.session.add(row)
        self.session.flush()
        return _trade_to_dict(row)

    def list_trades(self, run_id: int) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(BacktestTrade)
            .where(BacktestTrade.backtest_run_id == run_id)
            .order_by(BacktestTrade.opened_at.asc(), BacktestTrade.id.asc())
        ).all()
        return [_trade_to_dict(row) for row in rows]

    def update_run_results(
        self,
        run_id: int,
        *,
        final_capital_mxn: float,
        total_return_pct: float,
        max_drawdown_pct: float,
        win_rate_pct: float,
        trades_count: int,
        metrics: dict[str, Any],
        status: str = "completed",
    ) -> dict[str, Any] | None:
        row = self.session.get(BacktestRun, run_id)
        if row is None:
            return None
        row.final_capital_mxn = float(final_capital_mxn)
        row.total_return_pct = float(total_return_pct)
        row.max_drawdown_pct = float(max_drawdown_pct)
        row.win_rate_pct = float(win_rate_pct)
        row.trades_count = int(trades_count)
        row.metrics_json = dumps_json(metrics)
        row.status = status
        self.session.flush()
        return _run_to_dict(row)

    def delete_run(self, run_id: int) -> bool:
        row = self.session.get(BacktestRun, run_id)
        if row is None:
            return False
        self.session.delete(row)
        self.session.flush()
        return True

    def mark_run_failed(self, run_id: int) -> dict[str, Any] | None:
        row = self.session.get(BacktestRun, run_id)
        if row is None:
            return None
        row.status = "failed"
        self.session.flush()
        return _run_to_dict(row)

    def get_run_with_trades(self, run_id: int) -> dict[str, Any] | None:
        row = self.session.scalars(
            select(BacktestRun)
            .options(selectinload(BacktestRun.trades))
            .where(BacktestRun.id == run_id)
        ).first()
        if row is None:
            return None
        result = _run_to_dict(row)
        result["trades"] = [_trade_to_dict(trade) for trade in row.trades]
        return result
