from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any


class ParameterSpaceError(ValueError):
    """Raised when an optimization parameter space is invalid."""


@dataclass(frozen=True)
class ParameterSpace:
    values: dict[str, tuple[Any, ...]]

    @classmethod
    def from_dict(
        cls, values: dict[str, list[Any] | tuple[Any, ...]]
    ) -> "ParameterSpace":
        if not isinstance(values, dict) or not values:
            raise ParameterSpaceError("El espacio de parámetros no puede estar vacío.")
        normalized: dict[str, tuple[Any, ...]] = {}
        for key, candidates in values.items():
            if not isinstance(key, str) or not key:
                raise ParameterSpaceError("Nombre de parámetro inválido.")
            if not isinstance(candidates, (list, tuple)) or not candidates:
                raise ParameterSpaceError("Cada parámetro requiere una lista no vacía.")
            seen = set()
            unique = []
            for item in candidates:
                marker = repr(item)
                if marker in seen:
                    raise ParameterSpaceError(
                        "Los valores del espacio deben ser únicos."
                    )
                seen.add(marker)
                unique.append(item)
            normalized[key] = tuple(unique)
        return cls(normalized)

    def combinations(self) -> tuple[dict[str, Any], ...]:
        keys = tuple(sorted(self.values))
        combos = []
        for items in product(*(self.values[key] for key in keys)):
            combos.append(dict(zip(keys, items, strict=True)))
        return tuple(combos)

    def validate_for_strategy(
        self, strategy_factory: Any, name: str, version: str | None = None
    ) -> None:
        for parameters in self.combinations():
            strategy_factory.create(name, version, parameters)
            validate_parameter_combination(parameters)


def validate_parameter_combination(parameters: dict[str, Any]) -> None:
    fast = parameters.get("fast")
    slow = parameters.get("slow")
    if fast is not None and slow is not None and fast >= slow:
        raise ValueError("fast debe ser menor que slow.")
    oversold = parameters.get("oversold")
    overbought = parameters.get("overbought")
    if oversold is not None and overbought is not None and oversold >= overbought:
        raise ValueError("oversold debe ser menor que overbought.")
    for key, value in parameters.items():
        if (
            isinstance(value, (int, float))
            and key in {"window", "period", "fast", "slow", "signal"}
            and value <= 0
        ):
            raise ValueError("Los periodos deben ser positivos.")
