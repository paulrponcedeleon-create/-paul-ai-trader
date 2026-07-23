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
from app.brokers.interface import BrokerInterface, BrokerOrder
from app.market_data import MarketDataProvider, ProviderFactory
from app.paper_trading.risk import RiskLimits, RiskManager
from app.services.backtest_metrics import round_money, to_decimal
from app.strategies.factory import StrategyFactory
from app.system import SystemService


@dataclass(frozen=True)
class RuntimeConfig:
    loop_interval_seconds: float = 30.0
    books: tuple[str, ...] = ("btc_mxn",)
    timeframe: str = "1m"
    strategy_name: str = "momentum"
    strategy_version: str = "1.0"
    strategy_parameters: dict[str, Any] = field(default_factory=dict)
    trade_amount_mxn: Decimal = Decimal("50")
    min_trade_amount_mxn: Decimal = Decimal("10")
    max_trade_amount_mxn: Decimal = Decimal("500")
    capital_reserve_pct: Decimal = Decimal("20")
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
            "min_trade_amount_mxn": float(self.min_trade_amount_mxn),
            "max_trade_amount_mxn": float(self.max_trade_amount_mxn),
            "capital_reserve_pct": float(self.capital_reserve_pct),
            "market_data_provider": self.market_data_provider,
            "broker_name": self.broker_name,
            "max_history": self.max_history,
        }


@dataclass
class AssetBrain:
    book: str
    observations: int = 0
    buy_decisions: int = 0
    sell_decisions: int = 0
    hold_decisions: int = 0
    last_price: float | None = None
    last_score: float = 0.0
    last_confidence: float = 0.0
    last_action: str = "hold"
    last_strategy: str = "momentum"

    def observe(self, decision: Any, price: Decimal, strategy: str) -> None:
        payload = decision.to_public_dict()
        action = str(payload.get("action", "hold")).lower()
        self.observations += 1
        self.last_price = float(price)
        self.last_action = action
        self.last_strategy = strategy
        self.last_score = float(payload.get("score", payload.get("confidence", 0)) or 0)
        self.last_confidence = float(
            payload.get("confidence", payload.get("confidence_pct", 0)) or 0
        )
        if action == "buy":
            self.buy_decisions += 1
        elif action == "sell":
            self.sell_decisions += 1
        else:
            self.hold_decisions += 1

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "book": self.book,
            "observations": self.observations,
            "buy": self.buy_decisions,
            "sell": self.sell_decisions,
            "hold": self.hold_decisions,
            "last_price": self.last_price,
            "last_score": round(self.last_score, 2),
            "last_confidence": round(self.last_confidence, 2),
            "last_action": self.last_action,
            "last_strategy": self.last_strategy,
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
    observations: int
    learning_stage: str
    learning_progress_pct: float
    decision_counts: dict[str, int]
    books_ready: list[str]
    books_pending: dict[str, str]
    discovered_books: list[str]
    reserve_mxn: float
    deployable_cash_mxn: float
    asset_brains: dict[str, dict[str, Any]]

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
        self.risk_limits = RiskLimits(
            max_risk_per_trade_pct=Decimal("10"),
            max_daily_risk_pct=Decimal("20"),
            max_daily_loss_mxn=Decimal(
                str(getattr(settings, "max_daily_loss_mxn", 500))
            ),
            max_positions=1000000,
            max_asset_exposure_pct=Decimal("35"),
            max_total_exposure_pct=Decimal("80"),
        )
        self.risk_manager = risk_manager or RiskManager(self.risk_limits)
        self.running = False
        self.cycles = 0
        self.last_error: str | None = None
        self.last_decision: dict[str, Any] | None = None
        self.last_order: dict[str, Any] | None = None
        self.active_books: tuple[str, ...] = tuple()
        self.history: dict[str, list[Any]] = {book: [] for book in self.config.books}
        self.book_errors: dict[str, str] = {}
        self.decision_counts: dict[str, int] = {"buy": 0, "sell": 0, "hold": 0}
        self.asset_brains: dict[str, AssetBrain] = {
            book: AssetBrain(book=book) for book in self.config.books
        }
        self.observations = 0
        self.started_at = time.monotonic()

    async def start(self) -> RuntimeStatus:
        await self.market_data.connect()
        self.broker.connect()
        await self._discover_books()
        self.running = True
        self.system.watchdog.heartbeat("Runtime")
        self.system.events.publish(
            "INFO",
            "System",
            "runtime",
            "Runtime iniciado.",
            {"discovered_books": list(self.active_books)},
        )
        return self.status()

    async def _discover_books(self) -> None:
        discovered: list[str] = []
        for book in self.config.books:
            try:
                candles = await self.market_data.get_candles(
                    book, self.config.timeframe, 20
                )
                if candles:
                    discovered.append(book)
                    self.history[book] = list(candles[-self.config.max_history :])
                    self.book_errors.pop(book, None)
                else:
                    self.book_errors[book] = "Mercado no disponible en el proveedor."
            except Exception as exc:
                self.book_errors[book] = f"{type(exc).__name__}: {exc}"
        self.active_books = tuple(discovered)

    async def stop(self) -> RuntimeStatus:
        self.running = False
        await self.market_data.disconnect()
        self.broker.disconnect()
        self.system.events.publish("INFO", "System", "runtime", "Runtime detenido.")
        return self.status()

    async def run_once(self) -> RuntimeStatus:
        if not self.running:
            await self.start()
        cycle_errors: list[str] = []
        books = self.active_books or self.config.books
        for book in books:
            try:
                await self._process_book(book)
                self.book_errors.pop(book, None)
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                self.book_errors[book] = message
                cycle_errors.append(f"{book}: {message}")
                self.system.events.publish(
                    "WARNING",
                    "Market",
                    "runtime",
                    "book_cycle_failed",
                    {"book": book, "error_type": type(exc).__name__},
                )
        self.cycles += 1
        self.system.watchdog.heartbeat("Runtime")
        self.last_error = "; ".join(cycle_errors[:3]) if cycle_errors else None
        if cycle_errors and len(cycle_errors) == len(books):
            self.system.watchdog.record_error("Runtime")
        return self.status()

    async def run_cycles(self, count: int) -> RuntimeStatus:
        if not self.running:
            await self.start()
        for _ in range(count):
            await self.run_once()
            await asyncio.sleep(0)
        return self.status()

    def _learning_stage(self) -> tuple[str, float]:
        if self.observations < 100:
            return "Recolectando datos", self.observations
        if self.observations < 500:
            return "Generando primeras estadísticas", self.observations / 5
        if self.observations < 1000:
            return "Comparando patrones", 50 + (self.observations - 500) / 10
        return "Base suficiente para proponer ajustes", 100.0

    def _capital_snapshot(self, balance: Any) -> tuple[Decimal, Decimal]:
        equity = Decimal(str(balance.equity_mxn))
        cash = Decimal(str(balance.cash_mxn))
        reserve = equity * self.config.capital_reserve_pct / Decimal("100")
        deployable = max(Decimal("0"), cash - reserve)
        return reserve, deployable

    def _dynamic_trade_amount(self, decision: Any, balance: Any) -> Decimal:
        payload = decision.to_public_dict()
        confidence = Decimal(
            str(payload.get("confidence", payload.get("confidence_pct", 50)) or 50)
        )
        if confidence <= 1:
            confidence *= Decimal("100")
        confidence = min(Decimal("100"), max(Decimal("0"), confidence))
        reserve, deployable = self._capital_snapshot(balance)
        if deployable < self.config.min_trade_amount_mxn:
            return Decimal("0")
        span = self.config.max_trade_amount_mxn - self.config.min_trade_amount_mxn
        proposed = self.config.min_trade_amount_mxn + span * confidence / Decimal("100")
        max_risk_amount = (
            Decimal(str(balance.equity_mxn))
            * to_decimal(self.risk_limits.max_risk_per_trade_pct)
            / Decimal("100")
        )
        amount = min(
            proposed, self.config.max_trade_amount_mxn, deployable, max_risk_amount
        )
        if amount < self.config.min_trade_amount_mxn:
            return Decimal("0")
        return round_money(amount)

    def status(self) -> RuntimeStatus:
        balance = self.broker.get_balance()
        meta = balance.metadata or {}
        stage, progress = self._learning_stage()
        ready = sorted(book for book, rows in self.history.items() if rows)
        reserve, deployable = self._capital_snapshot(balance)
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
            self.observations,
            stage,
            round(min(progress, 100.0), 1),
            self.decision_counts.copy(),
            ready,
            self.book_errors.copy(),
            list(self.active_books),
            float(reserve),
            float(deployable),
            {book: brain.to_public_dict() for book, brain in self.asset_brains.items()},
        )

    def components(self) -> dict[str, Any]:
        balance = self.broker.get_balance()
        reserve, deployable = self._capital_snapshot(balance)
        return {
            "market_data": self.market_data.status().to_public_dict(),
            "broker": self.broker.health().to_public_dict(),
            "system": self.system.status(),
            "history_lengths": {book: len(rows) for book, rows in self.history.items()},
            "book_errors": self.book_errors.copy(),
            "discovered_books": list(self.active_books),
            "capital": {
                "reserve_pct": float(self.config.capital_reserve_pct),
                "reserve_mxn": float(reserve),
                "deployable_cash_mxn": float(deployable),
                "min_trade_mxn": float(self.config.min_trade_amount_mxn),
                "max_trade_mxn": float(self.config.max_trade_amount_mxn),
                "position_count_limit": None,
            },
            "asset_brains": {
                book: brain.to_public_dict()
                for book, brain in self.asset_brains.items()
            },
            "risk_rules": {
                "automatic_stop_loss": True,
                "automatic_take_profit": True,
                "automatic_trailing_stop": True,
                "capital_reserve_pct": float(self.config.capital_reserve_pct),
                "max_total_exposure_pct": 80.0,
            },
        }

    def _record_rejected_order(
        self,
        *,
        book: str,
        side: str,
        amount_mxn: Decimal,
        price: Decimal,
        reason: str,
    ) -> None:
        self.last_order = BrokerOrder(
            id=f"runtime-risk-{self.cycles + 1}-{book}",
            book=book,
            side=side,
            type="market",
            status="rejected",
            amount_mxn=amount_mxn,
            price=price,
            reason=reason,
        ).to_public_dict()

    async def _process_book(self, book: str) -> None:
        rows = self.history.setdefault(book, [])
        requested = self.config.max_history if not rows else 1
        candles = await self.market_data.get_candles(
            book, self.config.timeframe, requested
        )
        if not candles:
            raise RuntimeError("Sin velas disponibles para este mercado.")
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
        self.observations += 1
        self.decision_counts[decision.action] = (
            self.decision_counts.get(decision.action, 0) + 1
        )
        brain = self.asset_brains.setdefault(book, AssetBrain(book=book))
        brain.observe(decision, price, self.config.strategy_name)
        dynamic_amount = self._dynamic_trade_amount(decision, balance)
        self.last_decision = {
            **decision.to_public_dict(),
            "book": book,
            "history_points": len(rows),
            "price": float(price),
            "suggested_amount_mxn": float(dynamic_amount),
            "asset_observations": brain.observations,
        }
        order = None
        if decision.action in {"buy", "sell"}:
            has_book_position = any(
                position.get("book") == book for position in self.broker.get_positions()
            )
            if decision.action == "buy" and has_book_position:
                return
            if decision.action == "buy" and dynamic_amount <= 0:
                reason = "Reserva de capital protegida."
                self._record_rejected_order(
                    book=book,
                    side=decision.action,
                    amount_mxn=dynamic_amount,
                    price=price,
                    reason=reason,
                )
                self.system.events.publish("INFO", "Risk", "runtime", reason)
                return
            asset_exposure = sum(
                (
                    Decimal(
                        str(
                            position.get("amount_mxn", position.get("invested_mxn", 0))
                            or 0
                        )
                    )
                    for position in self.broker.get_positions()
                    if position.get("book") == book
                ),
                Decimal("0"),
            )
            amount = (
                dynamic_amount
                if decision.action == "buy"
                else self.config.min_trade_amount_mxn
            )
            risk = self.risk_manager.evaluate_open(
                book=book,
                amount_mxn=amount,
                equity_mxn=balance.equity_mxn,
                daily_realized_pnl_mxn=Decimal(
                    str(balance.metadata.get("realized_pnl_mxn", 0))
                ),
                open_positions_count=len(self.broker.get_positions()),
                asset_exposure_mxn=asset_exposure,
                total_exposure_mxn=balance.positions_value_mxn,
            )
            if risk.allowed or decision.action == "sell":
                order = self.execution_engine.execute(
                    ExecutionRequest(
                        decision,
                        book,
                        amount,
                        price,
                    )
                )
            else:
                self._record_rejected_order(
                    book=book,
                    side=decision.action,
                    amount_mxn=amount,
                    price=price,
                    reason=risk.reason,
                )
                self.system.events.publish(
                    "WARNING",
                    "Risk",
                    "runtime",
                    risk.reason,
                    {
                        "book": book,
                        "side": decision.action,
                        "amount_mxn": float(amount),
                    },
                )
        if order is not None:
            self.last_order = order.to_public_dict()
        self.system.events.publish(
            "INFO",
            "Market",
            "runtime",
            "Ciclo runtime procesado.",
            {
                "book": book,
                "decision": decision.action,
                "amount_mxn": float(dynamic_amount),
                "asset_observations": brain.observations,
            },
        )
