from __future__ import annotations

from fastapi import APIRouter, Request

from app.system import SystemService
from app.reporting.system_reports import export_system_health_report

router = APIRouter(tags=["system"])


@router.get("/system/health")
async def system_health(request: Request):
    return _service(request).health.status()


@router.get("/system/status")
async def system_status(request: Request):
    return _service(request).status()


@router.get("/system/watchdog")
async def system_watchdog(request: Request):
    return _service(request).watchdog.inspect()


@router.get("/system/circuit-breakers")
async def system_circuit_breakers(request: Request):
    return _service(request).circuit_breakers.status()


@router.get("/system/recovery")
async def system_recovery(request: Request):
    return _service(request).recovery.status()


@router.get("/system/metrics")
async def system_metrics(request: Request):
    return _service(request).health.metrics().to_public_dict()


@router.post("/system/snapshot")
async def system_snapshot(request: Request):
    service = _service(request)
    snapshot = service.snapshots.create({"status": service.status()})
    return snapshot.to_public_dict()


@router.post("/system/restore")
async def system_restore(request: Request, snapshot_id: str | None = None):
    service = _service(request)
    snapshot = (
        service.snapshots.restore(snapshot_id)
        if snapshot_id
        else service.snapshots.latest()
    )
    return {
        "restored": snapshot is not None,
        "snapshot": snapshot.to_public_dict() if snapshot else None,
    }


@router.get("/system/report")
async def system_report(request: Request):
    return export_system_health_report(_service(request).status())


def _service(request: Request) -> SystemService:
    service = getattr(request.app.state, "system_service", None)
    if service is None:
        service = SystemService()
        request.app.state.system_service = service
    return service
