from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.config import Settings

REQUIRED_TABLES = (
    "user_accounts",
    "simulated_orders",
    "simulated_order_events",
)


@dataclass(frozen=True)
class ReadinessResult:
    ready: bool
    status_code: int
    payload: dict[str, Any]


def check_readiness(settings: Settings, engine: Engine) -> ReadinessResult:
    checks: dict[str, Any] = {}
    errors: list[str] = []

    _check_config(settings, checks, errors)
    _check_data_dir(settings.resolved_paul_data_dir, checks, errors)
    _check_database(engine, checks, errors)

    ready = not errors
    payload = {
        "status": "ready" if ready else "not_ready",
        "mode": "live" if settings.live_trading else "simulation",
        "checks": checks,
    }
    if errors:
        payload["errors"] = errors
    return ReadinessResult(
        ready=ready, status_code=200 if ready else 503, payload=payload
    )


def _check_config(
    settings: Settings, checks: dict[str, Any], errors: list[str]
) -> None:
    valid = bool(settings.database_url.strip()) and bool(settings.enabled_books_set)
    checks["configuration"] = {"ok": valid}
    checks["trading_mode"] = {
        "ok": True,
        "mode": "live" if settings.live_trading else "simulation",
    }
    checks["multiuser"] = {
        "ok": True,
        "registration_enabled": settings.registration_enabled,
        "community_learning_enabled": settings.community_learning_enabled,
    }
    if not valid:
        errors.append("Configuración inválida.")


def _check_data_dir(data_dir: Path, checks: dict[str, Any], errors: list[str]) -> None:
    exists = data_dir.exists()
    is_dir = data_dir.is_dir() if exists else False
    writable = False
    if is_dir:
        writable = bool(data_dir.stat().st_mode & 0o200)
    ok = exists and is_dir and writable
    checks["paul_data_dir"] = {
        "ok": ok,
        "exists": exists,
        "is_dir": is_dir,
        "path": str(data_dir),
    }
    if not ok:
        errors.append("PAUL_DATA_DIR no está disponible.")


def _check_database(engine: Engine, checks: dict[str, Any], errors: list[str]) -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            tables = set(inspect(connection).get_table_names())
    except Exception:
        checks["database"] = {"ok": False}
        errors.append("Base de datos no disponible.")
        return

    missing = sorted(set(REQUIRED_TABLES) - tables)
    checks["database"] = {"ok": not missing}
    checks["required_tables"] = {"ok": not missing, "missing": missing}
    if missing:
        errors.append("Faltan tablas requeridas.")
