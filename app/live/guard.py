from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.live.models import GuardCheck, GuardDecision, LiveOrderRequest
from app.live.validation import OrderValidator, rules_from_settings


@dataclass
class LiveTradingArmState:
    armed: bool = False
    token: str | None = None

    def arm(self, token: str) -> None:
        self.armed = True
        self.token = token

    def disarm(self) -> None:
        self.armed = False
        self.token = None


class LiveTradingGuard:
    def __init__(
        self,
        *,
        settings: Any,
        broker: Any,
        arm_state: LiveTradingArmState | None = None,
        validator: OrderValidator | None = None,
    ) -> None:
        self.settings = settings
        self.broker = broker
        self.arm_state = arm_state or LiveTradingArmState()
        self.validator = validator or OrderValidator(rules_from_settings(settings))

    def evaluate(
        self,
        request: LiveOrderRequest | None = None,
        *,
        confirmation_token: str | None = None,
    ) -> GuardDecision:
        credentials_present = bool(
            getattr(self.settings, "bitso_api_key", "")
        ) and bool(getattr(self.settings, "bitso_api_secret", ""))
        environment = str(getattr(self.settings, "app_env", "development"))
        allowed_environment = environment in {"production", "staging", "test"}
        live_enabled = bool(getattr(self.settings, "live_trading", False))
        broker_health = self.broker.health()
        checks = [
            GuardCheck("live_trading", live_enabled, "LIVE_TRADING debe ser True."),
            GuardCheck(
                "credentials", credentials_present, "Credenciales privadas ausentes."
            ),
            GuardCheck(
                "environment",
                allowed_environment,
                "Entorno no permitido para trading real.",
            ),
            GuardCheck("armed", self.arm_state.armed, "Trading real no armado."),
            GuardCheck(
                "confirmation",
                bool(confirmation_token and confirmation_token == self.arm_state.token),
                "Confirmación explícita inválida.",
            ),
            GuardCheck(
                "broker_connected", broker_health.connected, "Broker no conectado."
            ),
            GuardCheck(
                "broker_live", broker_health.live_enabled, "Broker live deshabilitado."
            ),
        ]
        if request is not None:
            balance = self._balance()
            checks.extend(self.validator.validate(request, balance_mxn=balance))
        return GuardDecision(all(check.passed for check in checks), tuple(checks))

    def _balance(self) -> Decimal | None:
        try:
            return self.broker.get_balance().cash_mxn
        except Exception:
            return None
