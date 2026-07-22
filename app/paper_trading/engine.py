from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.paper_trading.models import PaperTradingRequest
from app.paper_trading.portfolio import PortfolioManager, PortfolioSnapshot
from app.paper_trading.risk import RiskManager
from app.paper_trading.sizing import PositionSizer
from app.services.backtest_metrics import to_decimal
from app.services.historical_data import HistoricalCandle
from app.strategies.factory import StrategyFactory


@dataclass(frozen=True)
class PaperTradingStatus:
    running: bool
    account_id: str
    strategy_name: str | None = None
    book: str | None = None
    message: str = "ok"


class PaperTradingEngine:
    def __init__(
        self,
        *,
        portfolio: PortfolioManager,
        strategy_factory: StrategyFactory | None = None,
        risk_manager: RiskManager | None = None,
        position_sizer: PositionSizer | None = None,
        repository: Any | None = None,
    ) -> None:
        self.portfolio = portfolio
        self.strategy_factory = strategy_factory or StrategyFactory()
        self.risk_manager = risk_manager or RiskManager()
        self.position_sizer = position_sizer or PositionSizer()
        self.repository = repository
        self.running = False
        self.current_request: PaperTradingRequest | None = None
        self.history: list[HistoricalCandle] = []

    def start(self, request: PaperTradingRequest) -> PaperTradingStatus:
        self.strategy_factory.create(
            request.strategy_name, request.strategy_version, request.parameters
        )
        self.current_request = request
        self.running = True
        if self.repository is not None:
            self.repository.upsert_account(
                account_id=request.account_id,
                cash_mxn=float(self.portfolio.cash_mxn),
                status="running",
            )
        return self.status()

    def stop(self) -> PaperTradingStatus:
        self.running = False
        if self.repository is not None and self.current_request is not None:
            self.repository.upsert_account(
                account_id=self.current_request.account_id,
                cash_mxn=float(self.portfolio.cash_mxn),
                status="stopped",
            )
        return self.status("stopped")

    def on_candle(self, candle: HistoricalCandle) -> PortfolioSnapshot:
        if not self.running or self.current_request is None:
            return self.portfolio.snapshot(
                {candle.book: to_decimal(candle.close)}
                if hasattr(candle, "book")
                else {}
            )
        request = self.current_request
        price = to_decimal(candle.close)
        self.history.append(candle)
        prices = {request.book: price}
        fee_rate = to_decimal(request.fee_rate)
        self.portfolio.update_market(prices, fee_rate=fee_rate)
        strategy = self.strategy_factory.create(
            request.strategy_name, request.strategy_version, request.parameters
        )
        signal = strategy.generate_signal(tuple(self.history))
        if signal.action == "buy":
            self._open_from_signal(
                request,
                price,
                signal_data={
                    "action": signal.action,
                    "reason": signal.reason,
                    "confidence": signal.confidence,
                },
            )
        elif signal.action == "sell":
            for position in list(self.portfolio.positions.values()):
                if position.book == request.book:
                    self.portfolio.close_position(
                        position.id,
                        price=price,
                        fee_rate=fee_rate,
                        reason="strategy_sell",
                    )
        snapshot = self.portfolio.snapshot(prices)
        if self.repository is not None:
            self.repository.record_snapshot(
                request.account_id, snapshot.to_public_dict()
            )
        return snapshot

    def close_position(
        self, position_id: str, *, price: Decimal | int | float | str
    ) -> PortfolioSnapshot:
        request = self._require_request()
        self.portfolio.manual_close(
            position_id, price=to_decimal(price), fee_rate=to_decimal(request.fee_rate)
        )
        return self.portfolio.snapshot({request.book: to_decimal(price)})

    def status(self, message: str = "ok") -> PaperTradingStatus:
        request = self.current_request
        return PaperTradingStatus(
            running=self.running,
            account_id=request.account_id if request else "unconfigured",
            strategy_name=request.strategy_name if request else None,
            book=request.book if request else None,
            message=message,
        )

    def _open_from_signal(
        self, request: PaperTradingRequest, price: Decimal, signal_data: dict[str, Any]
    ) -> None:
        equity = self.portfolio.equity({request.book: price})
        amount = self.position_sizer.calculate(
            method=request.sizing_method,
            value=request.sizing_value,
            equity_mxn=equity,
            cash_mxn=self.portfolio.cash_mxn,
            risk_per_trade_pct=to_decimal(
                self.risk_manager.limits.max_risk_per_trade_pct
            ),
        )
        decision = self.risk_manager.evaluate_open(
            book=request.book,
            amount_mxn=amount,
            equity_mxn=equity,
            daily_realized_pnl_mxn=self.portfolio.realized_pnl_mxn,
            open_positions_count=len(self.portfolio.positions),
            asset_exposure_mxn=self.portfolio.exposure(
                request.book, {request.book: price}
            ),
            total_exposure_mxn=self.portfolio.exposure(prices={request.book: price}),
        )
        if not decision.allowed:
            return
        self.portfolio.open_position(
            book=request.book,
            price=price,
            amount_mxn=amount,
            fee_rate=to_decimal(request.fee_rate),
            signal_data=signal_data,
        )

    def _require_request(self) -> PaperTradingRequest:
        if self.current_request is None:
            raise RuntimeError("Paper trading no configurado.")
        return self.current_request
