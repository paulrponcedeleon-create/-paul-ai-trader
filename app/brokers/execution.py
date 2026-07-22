from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.ai.decision_engine import DecisionResult
from app.brokers.factory import BrokerFactory
from app.brokers.interface import BrokerInterface, BrokerOrder
from app.services.backtest_metrics import to_decimal


@dataclass(frozen=True)
class ExecutionRequest:
    decision: DecisionResult
    book: str
    amount_mxn: Decimal | int | float | str
    price: Decimal | int | float | str | None = None


class ExecutionEngine:
    def __init__(
        self,
        *,
        broker: BrokerInterface | None = None,
        broker_factory: BrokerFactory | None = None,
        settings: Any | None = None,
    ) -> None:
        self.settings = settings
        self.broker = (
            broker or (broker_factory or BrokerFactory(settings=settings)).create()
        )

    def execute(self, request: ExecutionRequest) -> BrokerOrder | None:
        if not self.broker.health().connected:
            self.broker.connect()
        amount = to_decimal(request.amount_mxn)
        price = to_decimal(request.price) if request.price is not None else None
        if request.decision.action == "buy":
            return self.broker.place_market_buy(
                book=request.book, amount_mxn=amount, price=price
            )
        if request.decision.action == "sell":
            return self.broker.place_market_sell(
                book=request.book, amount_mxn=amount, price=price
            )
        return None
