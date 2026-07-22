from __future__ import annotations

from uuid import uuid4

from app.system.models import StateSnapshot, utc_now


class SnapshotManager:
    def __init__(self) -> None:
        self.snapshots: dict[str, StateSnapshot] = {}

    def create(self, payload: dict) -> StateSnapshot:
        snapshot = StateSnapshot(str(uuid4()), utc_now(), payload)
        self.snapshots[snapshot.id] = snapshot
        return snapshot

    def restore(self, snapshot_id: str) -> StateSnapshot | None:
        return self.snapshots.get(snapshot_id)

    def latest(self) -> StateSnapshot | None:
        if not self.snapshots:
            return None
        return max(self.snapshots.values(), key=lambda item: item.created_at)
