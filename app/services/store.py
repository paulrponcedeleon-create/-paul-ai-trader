from typing import Any, Protocol


class SimulationRepository(Protocol):
    def list(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        ...

    def count(self) -> int:
        ...

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        ...


def list_simulations(
    repository: SimulationRepository,
    *,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    total = repository.count()
    items = repository.list(limit=limit, offset=offset)
    next_offset = offset + len(items)
    has_more = next_offset < total
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "total": total,
        "has_more": has_more,
        "next_offset": next_offset if has_more else None,
    }


def add_simulation(item: dict[str, Any], repository: SimulationRepository) -> dict[str, Any]:
    return repository.add(item)
