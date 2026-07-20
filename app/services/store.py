from typing import Any, Protocol


class SimulationRepository(Protocol):
    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        ...

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        ...


def list_simulations(repository: SimulationRepository) -> list[dict[str, Any]]:
    return repository.list(limit=100)


def add_simulation(item: dict[str, Any], repository: SimulationRepository) -> dict[str, Any]:
    return repository.add(item)
