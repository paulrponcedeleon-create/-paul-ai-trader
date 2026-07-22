from __future__ import annotations

from app.strategies.base import Strategy


class StrategyRegistry:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], type[Strategy]] = {}

    def register(self, strategy_cls: type[Strategy]) -> None:
        self._items[(strategy_cls.name, strategy_cls.version)] = strategy_cls

    def unregister(self, name: str, version: str | None = None) -> None:
        if version is None:
            for key in [key for key in self._items if key[0] == name]:
                self._items.pop(key, None)
            return
        self._items.pop((name, version), None)

    def list(self) -> list[dict[str, object]]:
        return [
            {
                "name": cls.name,
                "version": cls.version,
                "description": cls.description,
                "parameters_schema": cls.parameters_schema(),
            }
            for cls in sorted(
                self._items.values(), key=lambda item: (item.name, item.version)
            )
        ]

    def exists(self, name: str, version: str | None = None) -> bool:
        if version is None:
            return any(key[0] == name for key in self._items)
        return (name, version) in self._items

    def get(self, name: str, version: str | None = None) -> type[Strategy]:
        if version is not None:
            try:
                return self._items[(name, version)]
            except KeyError as exc:
                raise KeyError("Estrategia no registrada.") from exc
        matches = [
            cls for (item_name, _), cls in self._items.items() if item_name == name
        ]
        if not matches:
            raise KeyError("Estrategia no registrada.")
        return sorted(matches, key=lambda item: item.version)[-1]


strategy_registry = StrategyRegistry()
