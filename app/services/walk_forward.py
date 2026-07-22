from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from app.services.backtesting import BacktestEngine, BacktestRequest, BacktestResult

WindowMode = Literal["rolling", "anchored"]


@dataclass(frozen=True)
class WalkForwardRequest:
    dataset_id: str
    strategy_name: str
    strategy_version: str
    initial_capital_mxn: float
    trade_amount_mxn: float
    fee_rate: float
    training_window_days: int
    validation_window_days: int
    start_at: datetime
    end_at: datetime
    mode: WindowMode = "rolling"
    parameters: dict | None = None


@dataclass(frozen=True)
class WalkForwardSegment:
    training_start: datetime
    training_end: datetime
    validation_start: datetime
    validation_end: datetime
    result: BacktestResult


@dataclass(frozen=True)
class WalkForwardReport:
    mode: WindowMode
    segments: tuple[WalkForwardSegment, ...]
    consolidated: dict[str, float]


class WalkForwardEngine:
    def __init__(self, backtest_engine: BacktestEngine) -> None:
        self.backtest_engine = backtest_engine

    def run(self, request: WalkForwardRequest) -> WalkForwardReport:
        if request.training_window_days <= 0 or request.validation_window_days <= 0:
            raise ValueError("Ventanas walk-forward inválidas.")
        if request.start_at >= request.end_at:
            raise ValueError("Rango walk-forward inválido.")

        training_delta = timedelta(days=request.training_window_days)
        validation_delta = timedelta(days=request.validation_window_days)
        cursor = request.start_at
        segments: list[WalkForwardSegment] = []
        while cursor + training_delta < request.end_at:
            training_start = request.start_at if request.mode == "anchored" else cursor
            training_end = cursor + training_delta
            validation_start = training_end
            validation_end = min(validation_start + validation_delta, request.end_at)
            if validation_start >= validation_end:
                break
            result = self.backtest_engine.run(
                BacktestRequest(
                    dataset_id=request.dataset_id,
                    strategy_name=request.strategy_name,
                    strategy_version=request.strategy_version,
                    initial_capital_mxn=request.initial_capital_mxn,
                    trade_amount_mxn=request.trade_amount_mxn,
                    fee_rate=request.fee_rate,
                    start_at=validation_start,
                    end_at=validation_end,
                    parameters=request.parameters or {},
                )
            )
            segments.append(
                WalkForwardSegment(
                    training_start=training_start,
                    training_end=training_end,
                    validation_start=validation_start,
                    validation_end=validation_end,
                    result=result,
                )
            )
            cursor = cursor + validation_delta
        return WalkForwardReport(
            mode=request.mode,
            segments=tuple(segments),
            consolidated=_consolidate(segments),
        )


def _consolidate(segments: list[WalkForwardSegment]) -> dict[str, float]:
    completed = [
        segment.result for segment in segments if segment.result.metrics is not None
    ]
    if not completed:
        return {
            "segments": float(len(segments)),
            "completed": 0.0,
            "average_return_pct": 0.0,
            "total_trades": 0.0,
        }
    return {
        "segments": float(len(segments)),
        "completed": float(len(completed)),
        "average_return_pct": sum(
            float(result.metrics.total_return_pct) for result in completed
        )
        / len(completed),
        "total_trades": float(sum(result.metrics.trades_count for result in completed)),
    }
