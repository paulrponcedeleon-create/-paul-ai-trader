from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import logging
from typing import Any, Protocol
from app.services.backtest_metrics import (
    BacktestMetrics,
    calculate_backtest_metrics,
    round_money,
    to_decimal,
)
from app.services.broker_simulator import (
    BacktestTradeResult,
    BrokerSimulator,
    InsufficientFundsError as BrokerInsufficientFundsError,
)
from app.services.historical_data import HistoricalCandle, HistoricalDataProvider
from app.services.signals import Signal
from app.strategies.factory import StrategyFactory

logger = logging.getLogger(__name__)


class BacktestError(Exception):
    public_message = "Error de backtesting."


class InvalidBacktestRequestError(BacktestError):
    public_message = "Solicitud de backtesting inválida."


class InsufficientHistoricalDataError(BacktestError):
    public_message = "Datos históricos insuficientes."


class UnsupportedStrategyError(BacktestError):
    public_message = "Estrategia no soportada."


class BacktestExecutionError(BacktestError):
    public_message = "No fue posible ejecutar el backtest."


class InsufficientFundsError(BacktestError):
    public_message = "Fondos insuficientes para ejecutar la operación."


@dataclass(frozen=True)
class BacktestRequest:
    dataset_id: str
    strategy_name: str
    strategy_version: str
    initial_capital_mxn: Decimal | int | float | str
    trade_amount_mxn: Decimal | int | float | str
    fee_rate: Decimal | int | float | str
    start_at: datetime | None = None
    end_at: datetime | None = None
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestResult:
    status: str
    strategy_name: str
    strategy_version: str
    dataset_id: str
    book: str | None
    start_at: datetime | None
    end_at: datetime | None
    metrics: BacktestMetrics | None
    trades: tuple[BacktestTradeResult, ...]
    parameters: dict[str, Any]
    error: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "dataset_id": self.dataset_id,
            "book": self.book,
            "start_at": self.start_at.isoformat() if self.start_at else None,
            "end_at": self.end_at.isoformat() if self.end_at else None,
            "metrics": self.metrics.to_public_dict() if self.metrics else None,
            "trades": [trade.to_public_dict() for trade in self.trades],
            "parameters": self.parameters,
            "error": self.error,
        }


class SignalStrategy(Protocol):
    def __call__(self, candles: tuple[HistoricalCandle, ...]) -> Signal: ...


class BacktestEngine:
    def __init__(
        self,
        *,
        historical_data_provider: HistoricalDataProvider,
        repository: Any | None = None,
        strategy_factory: StrategyFactory | None = None,
        strategies: dict[str, SignalStrategy] | None = None,
    ) -> None:
        self.historical_data_provider = historical_data_provider
        self.repository = repository
        self.strategy_factory = strategy_factory or StrategyFactory()
        self.strategies = strategies or {}

    def run(self, request: BacktestRequest) -> BacktestResult:
        run_id: int | None = None
        try:
            normalized = self._validate_request(request)
            dataset = self.historical_data_provider.load_dataset(request.dataset_id)
            candles = self._filter_candles(
                tuple(dataset.candles), request.start_at, request.end_at
            )
            if self.repository is not None:
                persisted_run = self.repository.create_run(
                    strategy_name=request.strategy_name,
                    strategy_version=request.strategy_version,
                    book=dataset.book,
                    start_at=candles[0].timestamp if candles else dataset.start_at,
                    end_at=candles[-1].timestamp if candles else dataset.end_at,
                    initial_capital_mxn=float(normalized["initial_capital_mxn"]),
                    parameters=request.parameters,
                    status="running",
                )
                run_id = int(persisted_run["id"])
            if not candles:
                raise InsufficientHistoricalDataError(
                    "Dataset histórico vacío para el rango solicitado."
                )
            if len(candles) < 2:
                raise InsufficientHistoricalDataError(
                    "Se requieren al menos dos velas históricas."
                )
            strategy = self._get_strategy(
                request.strategy_name, request.strategy_version, request.parameters
            )

            broker = BrokerSimulator(
                initial_capital_mxn=normalized["initial_capital_mxn"],
                fee_rate=normalized["fee_rate"],
            )
            equity_curve: list[dict[str, Any]] = []
            exposure_periods = 0

            for index, candle in enumerate(candles):
                window = candles[: index + 1]
                signal = strategy(window)
                signal_data = self._signal_data(signal, index)

                if signal.action == "buy" and not broker.has_position:
                    try:
                        broker.buy(
                            opened_at=candle.timestamp,
                            price=to_decimal(candle.close),
                            amount_mxn=normalized["trade_amount_mxn"],
                            signal_data=signal_data,
                        )
                    except BrokerInsufficientFundsError as exc:
                        raise InsufficientFundsError(
                            "Fondos insuficientes para abrir una posición."
                        ) from exc
                elif signal.action == "sell" and broker.has_position:
                    trade = broker.close(
                        closed_at=candle.timestamp,
                        price=to_decimal(candle.close),
                        book=dataset.book,
                        signal_data=signal_data,
                    )
                    if (
                        trade is not None
                        and self.repository is not None
                        and run_id is not None
                    ):
                        self._persist_trade(run_id, trade)

                if broker.has_position:
                    exposure_periods += 1
                equity_curve.append(
                    {
                        "timestamp": candle.timestamp.isoformat(),
                        "equity_mxn": float(broker.equity(to_decimal(candle.close))),
                        "cash_mxn": float(broker.available_cash()),
                        "has_position": broker.has_position,
                    }
                )

            if broker.has_position:
                last = candles[-1]
                closing_signal = {
                    "action": "sell",
                    "reason": "Cierre automático al finalizar dataset.",
                }
                trade = broker.close(
                    closed_at=last.timestamp,
                    price=to_decimal(last.close),
                    book=dataset.book,
                    signal_data=closing_signal,
                )
                if (
                    trade is not None
                    and self.repository is not None
                    and run_id is not None
                ):
                    self._persist_trade(run_id, trade)
                equity_curve.append(
                    {
                        "timestamp": last.timestamp.isoformat(),
                        "equity_mxn": float(broker.equity(to_decimal(last.close))),
                        "cash_mxn": float(broker.available_cash()),
                        "has_position": broker.has_position,
                    }
                )

            final_capital = round_money(broker.equity())
            metrics = calculate_backtest_metrics(
                initial_capital_mxn=normalized["initial_capital_mxn"],
                final_capital_mxn=final_capital,
                trades=broker.trades,
                equity_curve=equity_curve,
                exposure_periods=exposure_periods,
                total_periods=len(candles),
            )
            if self.repository is not None and run_id is not None:
                self.repository.update_run_results(
                    run_id,
                    final_capital_mxn=float(metrics.final_capital_mxn),
                    total_return_pct=float(metrics.total_return_pct),
                    max_drawdown_pct=float(metrics.max_drawdown_pct),
                    win_rate_pct=float(metrics.win_rate_pct),
                    trades_count=metrics.trades_count,
                    metrics=metrics.to_public_dict(),
                    status="completed",
                )
            return BacktestResult(
                status="completed",
                strategy_name=request.strategy_name,
                strategy_version=request.strategy_version,
                dataset_id=request.dataset_id,
                book=dataset.book,
                start_at=candles[0].timestamp,
                end_at=candles[-1].timestamp,
                metrics=metrics,
                trades=tuple(broker.trades),
                parameters=dict(request.parameters),
            )
        except BacktestError as exc:
            logger.warning("backtest_failed", exc_info=True)
            self._mark_failed(run_id)
            return self._failed_result(request, exc.public_message)
        except Exception:
            logger.exception("unexpected_backtest_failure")
            self._mark_failed(run_id)
            return self._failed_result(request, BacktestExecutionError.public_message)

    def _validate_request(self, request: BacktestRequest) -> dict[str, Decimal]:
        if (
            request.start_at is not None
            and request.end_at is not None
            and request.start_at > request.end_at
        ):
            raise InvalidBacktestRequestError("Rango de fechas inválido.")
        initial = to_decimal(request.initial_capital_mxn)
        trade_amount = to_decimal(request.trade_amount_mxn)
        fee_rate = to_decimal(request.fee_rate)
        if initial <= 0:
            raise InvalidBacktestRequestError("Capital inicial inválido.")
        if trade_amount <= 0:
            raise InvalidBacktestRequestError("Monto por operación inválido.")
        if fee_rate < 0:
            raise InvalidBacktestRequestError("Comisión inválida.")
        if trade_amount + round_money(trade_amount * fee_rate) > initial:
            raise InsufficientFundsError(
                "El monto por operación excede el capital disponible."
            )
        return {
            "initial_capital_mxn": round_money(initial),
            "trade_amount_mxn": round_money(trade_amount),
            "fee_rate": fee_rate,
        }

    def _get_strategy(
        self,
        strategy_name: str,
        strategy_version: str | None,
        parameters: dict[str, Any],
    ) -> SignalStrategy:
        injected = self.strategies.get(strategy_name)
        if injected is not None:
            return injected
        try:
            strategy = self.strategy_factory.create(
                strategy_name, strategy_version, parameters
            )
        except KeyError as exc:
            raise UnsupportedStrategyError("Estrategia no soportada.") from exc
        except ValueError as exc:
            raise InvalidBacktestRequestError(
                "Parámetros de estrategia inválidos."
            ) from exc
        return strategy.generate_signal

    def _filter_candles(
        self,
        candles: tuple[HistoricalCandle, ...],
        start_at: datetime | None,
        end_at: datetime | None,
    ) -> tuple[HistoricalCandle, ...]:
        result = candles
        if start_at is not None:
            result = tuple(candle for candle in result if candle.timestamp >= start_at)
        if end_at is not None:
            result = tuple(candle for candle in result if candle.timestamp <= end_at)
        return result

    def _signal_data(self, signal: Signal, candle_index: int) -> dict[str, Any]:
        return {
            "action": signal.action,
            "confidence": signal.confidence,
            "reason": signal.reason,
            "reference_price": signal.reference_price,
            "candle_index": candle_index,
        }

    def _persist_trade(self, run_id: int, trade: BacktestTradeResult) -> None:
        if self.repository is None:
            return
        self.repository.add_trade(
            backtest_run_id=run_id,
            opened_at=trade.opened_at,
            closed_at=trade.closed_at,
            book=trade.book,
            side=trade.side,
            entry_price=float(trade.entry_price),
            exit_price=float(trade.exit_price),
            amount_mxn=float(trade.amount_mxn),
            pnl_mxn=float(trade.pnl_mxn),
            return_pct=float(trade.return_pct),
            fees_mxn=float(trade.fees_mxn),
            signal=trade.signal_data,
        )

    def _mark_failed(self, run_id: int | None) -> None:
        if self.repository is None or run_id is None:
            return
        mark_failed = getattr(self.repository, "mark_run_failed", None)
        if callable(mark_failed):
            try:
                mark_failed(run_id)
            except Exception:
                logger.exception("backtest_mark_failed_error")

    def _failed_result(
        self, request: BacktestRequest, public_message: str
    ) -> BacktestResult:
        return BacktestResult(
            status="failed",
            strategy_name=request.strategy_name,
            strategy_version=request.strategy_version,
            dataset_id=request.dataset_id,
            book=None,
            start_at=request.start_at,
            end_at=request.end_at,
            metrics=None,
            trades=tuple(),
            parameters=dict(request.parameters),
            error=public_message,
        )
