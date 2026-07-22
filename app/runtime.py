from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
import time
from typing import Any

from app.ai.decision_engine import (
    AIDecisionEngine,
    DecisionRequest,
    HistoricalMetricsInput,
    IndicatorInput,
    PaperPortfolioInput,
    StrategySignalInput,
)
from app.analytics import AnalyticsService
from app.brokers.execution import ExecutionEngine, ExecutionRequest
from app.brokers.factory import BrokerFactory
from app.brokers.interface import BrokerInterface
from app.market_data import MarketDataProvider, ProviderFactory
from app.paper_trading.risk import RiskManager
from app.strategies.factory import StrategyFactory
from app.system import SystemService


@dataclass(frozen=True)
class RuntimeConfig:
    loop_interval_seconds: float = 60.0
    books: tuple[str, ...] = ("btc_mxn",)
    timeframe: str = "1m"
    strategy_name: str = "momentum"
    strategy_version: str = "1.0"
    strategy_parameters: dict[str, Any] = field(default_factory=dict)
    trade_amount_mxn: Decimal = Decimal("100")
    market_data_provider: str = "bitso"
    broker_name: str = "paper"
    max_history: int = 200

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "loop_interval_seconds": self.loop_interval_seconds,
            "books": list(self.books),
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "strategy_parameters": self.strategy_parameters,
            "trade_amount_mxn": float(self.trade_amount_mxn),
            "market_data_provider": self.market_data_provider,
            "broker_name": self.broker_name,
            "max_history": self.max_history,
        }


@dataclass(frozen=True)
class RuntimeStatus:
    running: bool
    cycles: int
    last_error: str | None
    last_decision: dict[str, Any] | None
    last_order: dict[str, Any] | None
    history_points: int
    open_positions: int
    closed_trades: int
    cash_mxn: float
    equity_mxn: float
    realized_pnl_mxn: float
    unrealized_pnl_mxn: float

    def to_public_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class RuntimeEngine:
    def __init__(
        self,
        *,
        config: RuntimeConfig | None = None,
        market_data: MarketDataProvider | None = None,
        strategy_factory: StrategyFactory | None = None,
        ai_engine: AIDecisionEngine | None = None,
        broker: BrokerInterface | None = None,
        execution_engine: ExecutionEngine | None = None,
        analytics: AnalyticsService | None = None,
        system: SystemService | None = None,
        risk_manager: RiskManager | None = None,
        settings: Any | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()
        self.market_data = market_data or ProviderFactory(settings=settings).create(
            self.config.market_data_provider
        )
        self.strategy_factory = strategy_factory or StrategyFactory()
        self.ai_engine = ai_engine or AIDecisionEngine()
        self.broker = broker or BrokerFactory(settings=settings).create(
            self.config.broker_name
        )
        self.execution_engine = execution_engine or ExecutionEngine(
            broker=self.broker, settings=settings
        )
        self.analytics = analytics or AnalyticsService(broker=self.broker)
        self.system = system or SystemService()
        self.risk_manager = risk_manager or RiskManager()
        self.running = False
        self.cycles = 0
        self.last_error: str | None = None
        self.last_decision: dict[str, Any] | None = None
        self.last_order: dict[str, Any] | None = None
        self.history: dict[str, list[Any]] = {book: [] for book in self.config.books}
        self.started_at = time.monotonic()

    async def start(self) -> RuntimeStatus:
        await self.market_data.connect()
        self.broker.connect()
        self.running = True
        self.system.watchdog.heartbeat("Runtime")
        self.system.events.publish("INFO", "System", "runtime", "Runtime iniciado.")
        return self.status()

    async def stop(self) -> RuntimeStatus:
        self.running = False
        await self.market_data.disconnect()
        self.broker.disconnect()
        self.system.events.publish("INFO", "System", "runtime", "Runtime detenido.")
        return self.status()

    async def run_once(self) -> RuntimeStatus:
        if not self.running:
            await self.start()
        try:
            for book in self.config.books:
                await self._process_book(book)
            self.cycles += 1
            self.system.watchdog.heartbeat("Runtime")
            self.last_error = None
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            self.system.watchdog.record_error("Runtime")
            self.system.events.publish(
                "ERROR",
                "System",
                "runtime",
                "runtime_cycle_failed",
                {"error_type": type(exc).__name__},
            )
        return self.status()

    async def run_cycles(self, count: int) -> RuntimeStatus:
        if not self.running:
            await self.start()
        for _ in range(count):
            await self.run_once()
            await asyncio.sleep(0)
        return self.status()

    def status(self) -> RuntimeStatus:
        balance = self.broker.get_balance()
        meta = balance.metadata or {}
        return RuntimeStatus(
            self.running,
            self.cycles,
            self.last_error,
            self.last_decision,
            self.last_order,
            sum(len(rows) for rows in self.history.values()),
            len(self.broker.get_positions()),
            int(meta.get("closed_trades", 0)),
            float(balance.cash_mxn),
            float(balance.equity_mxn),
            float(meta.get("realized_pnl_mxn", 0)),
            float(meta.get("unrealized_pnl_mxn", 0)),
        )

    def components(self) -> dict[str, Any]:
        return {
            "market_data": self.market_data.status().to_public_dict(),
            "broker": self.broker.health().to_public_dict(),
            "system": self.system.status(),
            "history_lengths": {book: len(rows) for book, rows in self.history.items()},
            "risk_rules": {
                "automatic_stop_loss": True,
                "automatic_take_profit": True,
                "automatic_trailing_stop": True,
            },
        }

    async def _process_book(self, book: str) -> None:
        rows = self.history.setdefault(book, [])
        requested = self.config.max_history if not rows else 1
        candles = await self.market_data.get_candles(
            book, self.config.timeframe, requested
        )
        if not candles:
            return
        if not rows:
            rows.extend(candles[-self.config.max_history :])
        else:
            candle = candles[-1]
            previous_timestamp = getattr(rows[-1], "timestamp", None)
            current_timestamp = getattr(candle, "timestamp", None)
            if current_timestamp != previous_timestamp:
                rows.append(candle)
        del rows[: -self.config.max_history]
        candle = rows[-1]
        price = Decimal(str(candle.close))

        update_market = getattr(self.broker, "update_market", None)
        if callable(update_market):
            closed = update_market(book, price)
            if closed:
                self.last_order = {
                    "action": "sell",
                    "book": book,
                    "reason": closed[-1].reason,
                    "pnl_mxn": float(closed[-1].pnl_mxn),
                }

        strategy = self.strategy_factory.create(
            self.config.strategy_name,
            self.config.strategy_version,
            self.config.strategy_parameters,
        )
        signal = strategy.generate_signal(tuple(rows))
        balance = self.broker.get_balance()
        decision = self.ai_engine.evaluate(
            DecisionRequest(
                strategy_signals=(
                    StrategySignalInput(self.config.strategy_name, signal),
                ),
                historical_metrics=HistoricalMetricsInput(
                    win_rate_pct=50, stability_pct=70
                ),
                paper_portfolio=PaperPortfolioInput(
                    balance.equity_mxn,
                    balance.cash_mxn,
                    open_positions=len(self.broker.get_positions()),
                ),
                indicators=IndicatorInput(
                    closes=tuple(float(item.close) for item in rows),
                    highs=tuple(float(item.high) for item in rows),
                    lows=tuple(float(item.low) for item in rows),
                    volumes=tuple(float(item.volume) for item in rows),
                ),
            )
        )
        self.last_decision = {
            **decision.to_public_dict(),
            "book": book,
            "history_points": len(rows),
            "price": float(price),
        }
        order = None
        if decision.action in {"buy", "sell"}:
            has_book_position = any(
                position.get("book") == book for position in self.broker.get_positions()
            )
            if decision.action == "buy" and has_book_position:
                return
            risk = self.risk_manager.evaluate_open(
                book=book,
                amount_mxn=self.config.trade_amount_mxn,
                equity_mxn=balance.equity_mxn,
                daily_realized_pnl_mxn=Decimal(str(balance.metadata.get("realized_pnl_mxn", 0))),
                open_positions_count=len(self.broker.get_positions()),
                asset_exposure_mxn=Decimal("0"),
                total_exposure_mxn=balance.positions_value_mxn,
            )
            if risk.allowed or decision.action == "sell":
                order = self.execution_engine.execute(
                    ExecutionRequest(
                        decision,
                        book,
                        self.config.trade_amount_mxn,
                        price,
                    )
                )
            else:
                self.system.events.publish("WARNING", "Risk", "runtime", risk.reason)
        if order is not None:
            self.last_order = order.to_public_dict()
        self.system.events.publish(
            "INFO",
            "Market",
            "runtime",
            "Ciclo runtime procesado.",
            {"book": book, "decision": decision.action},
        )
