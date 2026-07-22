from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.live.models import GuardCheck, LiveOrderRequest


@dataclass(frozen=True)
class OrderValidationRules:
    min_amount_mxn: Decimal = Decimal("1")
    max_amount_mxn: Decimal = Decimal("200")
    allowed_books: frozenset[str] = frozenset(
        {"btc_mxn", "eth_mxn", "xrp_mxn", "sol_mxn"}
    )
    max_decimals: int = 2


class OrderValidator:
    def __init__(self, rules: OrderValidationRules | None = None) -> None:
        self.rules = rules or OrderValidationRules()

    def validate(
        self, request: LiveOrderRequest, *, balance_mxn: Decimal | None = None
    ) -> tuple[GuardCheck, ...]:
        checks = [
            GuardCheck(
                "book_allowed",
                request.book in self.rules.allowed_books,
                "Activo no permitido.",
            ),
            GuardCheck("side", request.side in {"buy", "sell"}, "Lado inválido."),
            GuardCheck(
                "order_type",
                request.order_type in {"market", "limit"},
                "Tipo de orden inválido.",
            ),
            GuardCheck(
                "min_amount",
                request.amount_mxn >= self.rules.min_amount_mxn,
                "Monto menor al mínimo.",
            ),
            GuardCheck(
                "max_amount",
                request.amount_mxn <= self.rules.max_amount_mxn,
                "Monto mayor al máximo.",
            ),
            GuardCheck(
                "precision",
                _scale(request.amount_mxn) <= self.rules.max_decimals,
                "Precisión de monto inválida.",
            ),
            GuardCheck(
                "price",
                request.order_type == "market"
                or (request.price is not None and request.price > 0),
                "Precio inválido.",
            ),
        ]
        if balance_mxn is not None:
            checks.append(
                GuardCheck(
                    "balance",
                    request.amount_mxn <= balance_mxn,
                    "Balance insuficiente.",
                )
            )
        return tuple(checks)


def rules_from_settings(settings: Any) -> OrderValidationRules:
    return OrderValidationRules(
        max_amount_mxn=Decimal(str(getattr(settings, "max_order_mxn", 200))),
        allowed_books=frozenset(
            getattr(
                settings, "live_books_set", {"btc_mxn", "eth_mxn", "xrp_mxn", "sol_mxn"}
            )
        ),
    )


def _scale(value: Decimal) -> int:
    return max(abs(value.as_tuple().exponent), 0)
