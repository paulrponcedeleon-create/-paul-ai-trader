from __future__ import annotations

from app.strategies.base import Strategy
from app.strategies.registry import StrategyRegistry, strategy_registry


class StrategyFactory:
    def __init__(self, registry: StrategyRegistry | None = None) -> None:
        self.registry = registry or strategy_registry

    def create(
        self, name: str, version: str | None = None, parameters: dict | None = None
    ) -> Strategy:
        strategy_cls = self.registry.get(name, version)
        return strategy_cls(parameters or {})
