from __future__ import annotations

from typing import Any

from app.brokers.bitso import BitsoBroker
from app.brokers.interface import BrokerInterface
from app.brokers.paper import PaperBroker


class BrokerFactory:
    def __init__(self, *, settings: Any | None = None) -> None:
        self.settings = settings

    def create(self, name: str | None = None) -> BrokerInterface:
        selected = (name or self._default_name()).lower()
        if selected == "paper":
            return PaperBroker(settings=self.settings)
        if selected == "bitso":
            live_enabled = bool(getattr(self.settings, "live_trading", False))
            return BitsoBroker(live_enabled=live_enabled, settings=self.settings)
        raise ValueError("Broker no soportado.")

    def _default_name(self) -> str:
        if self.settings is not None and bool(
            getattr(self.settings, "live_trading", False)
        ):
            return "bitso"
        return "paper"
