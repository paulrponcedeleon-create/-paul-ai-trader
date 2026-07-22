from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import inspect
from typing import Any

from app.brokers.interface import (
    BrokerBalance,
    BrokerHealth,
    BrokerInterface,
    BrokerOrder,
)
from app.live.audit import ExecutionAuditLog
from app.live.guard import LiveTradingArmState, LiveTradingGuard
from app.live.models import ExecutionAuditRecord, LiveOrderRequest, utc_now


class LiveTradingDisabledError(RuntimeError):
    pass


class BitsoBroker(BrokerInterface):
    name = "bitso"
    mode = "live"

    def __init__(
        self,
        *,
        live_enabled: bool = False,
        settings: Any | None = None,
        client: Any | None = None,
        arm_state: LiveTradingArmState | None = None,
        audit_log: ExecutionAuditLog | None = None,
    ) -> None:
        self.live_enabled = live_enabled
        self.settings = settings
        self.client = client
        self.connected = False
        self.arm_state = arm_state or LiveTradingArmState()
        self.audit_log = audit_log or ExecutionAuditLog()

    def connect(self) -> BrokerHealth:
        self.connected = True
        return self.health()

    def disconnect(self) -> BrokerHealth:
        self.connected = False
        return self.health()

    def health(self) -> BrokerHealth:
        errors = []
        if not self.live_enabled:
            errors.append("Live trading deshabilitado.")
        if self.settings is not None and not (
            getattr(self.settings, "bitso_api_key", "")
            and getattr(self.settings, "bitso_api_secret", "")
        ):
            errors.append("Credenciales privadas ausentes.")
        return BrokerHealth(
            self.connected,
            "live",
            self.live_enabled,
            "connected" if self.connected and self.live_enabled else "live_disabled",
            tuple(errors),
        )

    def get_balance(self) -> BrokerBalance:
        if self.client is None or not hasattr(self.client, "balance"):
            return BrokerBalance(
                Decimal("0"),
                Decimal("0"),
                Decimal("0"),
                {"broker": self.name, "live_enabled": self.live_enabled},
            )
        data = self._call(self.client.balance)
        payload = data.get("payload", data) if isinstance(data, dict) else {}
        balances = payload.get("balances", []) if isinstance(payload, dict) else []
        cash = Decimal("0")
        for row in balances:
            if str(row.get("currency", "")).lower() == "mxn":
                cash += self._decimal(row.get("available", row.get("total", 0)))
        return BrokerBalance(cash, cash, Decimal("0"), {"broker": self.name})

    def get_positions(self) -> list[dict[str, Any]]:
        balance = self.get_balance()
        return [{"currency": "mxn", "available": float(balance.cash_mxn)}]

    def get_orders(self) -> list[BrokerOrder]:
        if self.client is None or not hasattr(self.client, "open_orders"):
            return []
        data = self._call(self.client.open_orders)
        payload = data.get("payload", data) if isinstance(data, dict) else []
        rows = payload if isinstance(payload, list) else payload.get("orders", [])
        return [self._order_from_payload(row) for row in rows]

    def place_market_buy(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder:
        request = LiveOrderRequest(book, "buy", "market", amount_mxn, price)
        return self._place_order(request)

    def place_market_sell(
        self, *, book: str, amount_mxn: Decimal, price: Decimal | None = None
    ) -> BrokerOrder:
        request = LiveOrderRequest(book, "sell", "market", amount_mxn, price)
        return self._place_order(request)

    def place_limit_buy(
        self, *, book: str, amount_mxn: Decimal, price: Decimal
    ) -> BrokerOrder:
        request = LiveOrderRequest(book, "buy", "limit", amount_mxn, price)
        return self._place_order(request)

    def place_limit_sell(
        self, *, book: str, amount_mxn: Decimal, price: Decimal
    ) -> BrokerOrder:
        request = LiveOrderRequest(book, "sell", "limit", amount_mxn, price)
        return self._place_order(request)

    def cancel_order(self, order_id: str) -> BrokerOrder:
        self._ensure_live_action(None, action="cancel")
        if self.client is None or not hasattr(self.client, "cancel_order"):
            raise LiveTradingDisabledError(
                "Cliente Bitso no soporta cancelación segura."
            )
        payload = self._call(self.client.cancel_order, order_id)
        self._audit("unknown", Decimal("0"), "cancelled", "Orden cancelada.", payload)
        return self._order_from_payload(payload if isinstance(payload, dict) else {})

    def get_order_status(self, order_id: str) -> BrokerOrder:
        if self.client is None or not hasattr(self.client, "get_order_status"):
            return BrokerOrder(
                order_id,
                "unknown",
                "buy",
                "market",
                "unavailable",
                Decimal("0"),
                reason="Estado live no disponible sin cliente autenticado.",
            )
        payload = self._call(self.client.get_order_status, order_id)
        return self._order_from_payload(payload if isinstance(payload, dict) else {})

    def get_ticker(self, book: str) -> dict[str, Any]:
        if self.client is not None and hasattr(self.client, "ticker"):
            return self._call(self.client.ticker, book)
        return {"book": book, "source": "bitso_stub", "live_enabled": self.live_enabled}

    def get_candles(
        self, book: str, timeframe: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        return []

    def _place_order(self, request: LiveOrderRequest) -> BrokerOrder:
        self._ensure_live_action(request)
        if self.client is None or not hasattr(self.client, "place_market_order"):
            self._audit(
                request.book,
                request.amount_mxn,
                "rejected",
                "Cliente Bitso no configurado.",
            )
            raise LiveTradingDisabledError(
                "Cliente Bitso no configurado para trading live."
            )
        payload = self._call(
            self.client.place_market_order,
            request.book,
            request.side,
            float(request.amount_mxn),
        )
        order = self._order_from_payload(payload if isinstance(payload, dict) else {})
        self._audit(
            request.book,
            request.amount_mxn,
            "accepted",
            "Orden enviada al broker mock/autenticado.",
            order.to_public_dict(),
        )
        return order

    def _ensure_live_action(
        self, request: LiveOrderRequest | None, *, action: str = "order"
    ) -> None:
        if self.settings is None:
            raise LiveTradingDisabledError(
                "Settings requeridos para validar trading live."
            )
        guard = LiveTradingGuard(
            settings=self.settings, broker=self, arm_state=self.arm_state
        )
        decision = guard.evaluate(request, confirmation_token=self.arm_state.token)
        if not decision.allowed:
            reason = "; ".join(decision.reasons)
            self._audit(
                request.book if request else "unknown",
                request.amount_mxn if request else Decimal("0"),
                "rejected",
                reason,
            )
            raise LiveTradingDisabledError(reason or f"Acción live {action} rechazada.")

    def _audit(
        self,
        book: str,
        amount: Decimal,
        result: str,
        reason: str,
        response: dict[str, Any] | None = None,
    ) -> None:
        self.audit_log.add(
            ExecutionAuditRecord(
                utc_now(),
                "system",
                None,
                None,
                None,
                book,
                amount,
                self.name,
                result,
                reason,
                response or {},
            )
        )

    @staticmethod
    def _call(func: Any, *args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)
        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                return asyncio.run(result)
            raise LiveTradingDisabledError(
                "Cliente async no puede ejecutarse dentro de un loop activo."
            )
        return result

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")

    def _order_from_payload(self, payload: dict[str, Any]) -> BrokerOrder:
        data = payload.get("payload", payload)
        if isinstance(data, list):
            data = data[0] if data else {}
        oid = str(
            data.get("oid")
            or data.get("id")
            or data.get("order_id")
            or f"bitso-{datetime.now(timezone.utc).timestamp()}"
        )
        book = str(data.get("book") or "unknown")
        side = str(data.get("side") or "buy")
        order_type = str(data.get("type") or data.get("order_type") or "market")
        status = str(data.get("status") or "accepted")
        amount = self._decimal(
            data.get("amount_mxn")
            or data.get("minor")
            or data.get("original_amount")
            or 0
        )
        price = data.get("price")
        return BrokerOrder(
            oid,
            book,
            "sell" if side == "sell" else "buy",
            "limit" if order_type == "limit" else "market",
            status,
            amount,
            self._decimal(price) if price is not None else None,
        )
