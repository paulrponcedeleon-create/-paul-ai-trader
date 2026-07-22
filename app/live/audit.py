from __future__ import annotations

from app.live.models import ExecutionAuditRecord


class ExecutionAuditLog:
    def __init__(self) -> None:
        self._records: list[ExecutionAuditRecord] = []

    def add(self, record: ExecutionAuditRecord) -> ExecutionAuditRecord:
        self._records.append(record)
        return record

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ExecutionAuditRecord]:
        return list(reversed(self._records))[offset : offset + limit]
