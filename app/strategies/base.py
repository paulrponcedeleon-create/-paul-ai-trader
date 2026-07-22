from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.services.signals import Signal


class Strategy(ABC):
    name: str
    version: str
    description: str

    def __init__(self, parameters: dict[str, Any] | None = None) -> None:
        self.parameters = self.validate_parameters(parameters or {})

    @classmethod
    @abstractmethod
    def parameters_schema(cls) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def validate_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        schema = cls.parameters_schema()
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        result: dict[str, Any] = {}
        for key in required:
            if key not in parameters and "default" not in properties.get(key, {}):
                raise ValueError(f"Parámetro requerido faltante: {key}")
        for key, spec in properties.items():
            value = parameters.get(key, spec.get("default"))
            if value is None:
                continue
            expected = spec.get("type")
            if expected == "integer":
                value = int(value)
            elif expected == "number":
                value = float(value)
            elif expected == "string":
                value = str(value)
            minimum = spec.get("minimum")
            maximum = spec.get("maximum")
            if minimum is not None and value < minimum:
                raise ValueError(f"Parámetro inválido: {key}")
            if maximum is not None and value > maximum:
                raise ValueError(f"Parámetro inválido: {key}")
            result[key] = value
        unknown = set(parameters) - set(properties)
        if unknown:
            raise ValueError(f"Parámetro desconocido: {sorted(unknown)[0]}")
        return result

    @abstractmethod
    def generate_signal(self, history: tuple[Any, ...]) -> Signal:
        raise NotImplementedError
