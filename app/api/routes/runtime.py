from __future__ import annotations

import asyncio
from contextlib import suppress
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request

from app.api.dependencies import require_auth
from app.brokers.exploration_persistent_paper import ExplorationPersistentPaperBroker
from app.paper_trading.exploration import ExplorationConfig
from app.repositories.users import SqlUserAccountRepository
from app.runtime import RuntimeConfig
from app.runtime_exploration import ExplorationRuntimeEngine
from app.security.user_context import user_scope
from app.services.signal_levels import classify_signal_level

router = APIRouter(tags=["runtime"])

VERIFIED_RUNTIME_BOOKS = (
    "btc_mxn",
    "eth_mxn",
    "sol_mxn",
    "xrp_mxn",
    "usdt_mxn",
)
OWNER_USER_ID = "owner"


def _with_signal_level(decision: dict[str, Any] | None) -> dict[str, Any] | None:
    if not decision:
        return decision
    result = dict(decision)
    level = classify_signal_level(
        score=result.get("score", result.get("confidence", 0)),
        confidence=result.get("confidence", result.get("confidence_pct", 0)),
        action=str(result.get("action", "hold")),
    )
    result.update(level.to_public_dict())
    return result


def _legacy_runtime(request: Request) -> Any | None:
    state = request.app.state
    if hasattr(state, "runtime_engines"):
        return None
    return getattr(state, "runtime_engine", None)


def _legacy_payload(request: Request, runtime: Any, status: Any) -> dict[str, Any]:
    payload = status.to_public_dict()
    payload["last_decision"] = _with_signal_level(payload.get("last_decision"))
    settings = request.app.state.settings
    task = getattr(request.app.state, "runtime_background_task", None)
    payload.update(
        {
            "automatic": bool(getattr(settings, "runtime_auto_start", True)),
            "startup_state": getattr(
                request.app.state,
                "runtime_startup_state",
                "manual",
            ),
            "startup_error": getattr(
                request.app.state,
                "runtime_startup_error",
                None,
            ),
            "background_task_active": bool(task is not None and not task.done()),
            "mode_label": (
                "Simulación automática"
                if not getattr(settings, "live_trading", False)
                else "Dinero real"
            ),
            "provider_label": (
                "Bitso, solo lectura"
                if runtime.config.market_data_provider == "bitso"
                else runtime.config.market_data_provider
            ),
            "broker_label": (
                "Dinero simulado"
                if runtime.config.broker_name == "paper"
                else runtime.config.broker_name
            ),
            "risk_label": (
                "Protección automática: pérdida 3%, objetivo 6% y seguimiento 2%"
            ),
            "history_label": (
                f"{payload.get('history_points', 0)} datos cargados para análisis"
            ),
        }
    )
    return payload


@router.post("/runtime/start")
async def runtime_start(request: Request):
    legacy = _legacy_runtime(request)
    if legacy is not None:
        status = legacy.status() if legacy.running else await legacy.start()
        _ensure_background_loop(request, legacy)
        request.app.state.runtime_startup_state = "manual_running"
        request.app.state.runtime_startup_error = None
        return _legacy_payload(request, legacy, status)

    user_id = require_auth(request)
    if request.app.state.settings.live_trading:
        raise HTTPException(
            status_code=403,
            detail="El Runtime multiusuario solo se puede iniciar en simulación.",
        )
    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        repository.update_preferences(user_id, bot_enabled=True)
        session.commit()
    await apply_user_runtime_preference(request.app, user_id)
    return _runtime_payload(request.app, user_id)


@router.post("/runtime/stop")
async def runtime_stop(request: Request):
    legacy = _legacy_runtime(request)
    if legacy is not None:
        await _cancel_legacy_background_task(request.app)
        status = await legacy.stop() if legacy.running else legacy.status()
        request.app.state.runtime_startup_state = "stopped"
        return _legacy_payload(request, legacy, status)

    user_id = require_auth(request)
    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        repository.update_preferences(user_id, bot_enabled=False)
        session.commit()
    await apply_user_runtime_preference(request.app, user_id)
    return _runtime_payload(request.app, user_id)


@router.get("/runtime/status")
async def runtime_status(request: Request):
    legacy = _legacy_runtime(request)
    if legacy is not None:
        return _legacy_payload(request, legacy, legacy.status())
    user_id = require_auth(request)
    return _runtime_payload(request.app, user_id)


@router.get("/runtime/components")
async def runtime_components(request: Request):
    legacy = _legacy_runtime(request)
    if legacy is not None:
        return legacy.components()
    user_id = require_auth(request)
    runtime = _runtime_for_application(request.app, user_id)
    with user_scope(user_id):
        return runtime.components()


@router.get("/runtime/config")
async def runtime_config(request: Request):
    legacy = _legacy_runtime(request)
    if legacy is not None:
        payload = legacy.config.to_public_dict()
        payload["exploration"] = legacy.status().to_public_dict().get("exploration")
        return payload

    user_id = require_auth(request)
    runtime = _runtime_for_application(request.app, user_id)
    with user_scope(user_id):
        payload = runtime.config.to_public_dict()
        payload["exploration"] = runtime.status().to_public_dict().get("exploration")
    user = _load_user(request.app, user_id)
    payload["account"] = {
        "user_id": user.id,
        "username": user.username,
        "bot_enabled": user.bot_enabled,
        "ai_exploration_enabled": user.ai_exploration_enabled,
        "simulated_initial_capital_mxn": float(user.simulated_initial_capital_mxn),
    }
    return payload


def _registries(application: FastAPI) -> tuple[dict, dict, dict, dict]:
    if not hasattr(application.state, "runtime_engines"):
        application.state.runtime_engines = {}
    if not hasattr(application.state, "runtime_background_tasks"):
        application.state.runtime_background_tasks = {}
    if not hasattr(application.state, "runtime_startup_states"):
        application.state.runtime_startup_states = {}
    if not hasattr(application.state, "runtime_startup_errors"):
        application.state.runtime_startup_errors = {}
    return (
        application.state.runtime_engines,
        application.state.runtime_background_tasks,
        application.state.runtime_startup_states,
        application.state.runtime_startup_errors,
    )


def _load_user(application: FastAPI, user_id: str):
    with application.state.db_session_factory() as session:
        row = SqlUserAccountRepository(session).get_row(user_id)
        if row is None or not row.is_active:
            raise HTTPException(status_code=404, detail="Usuario no encontrado o inactivo.")
        session.expunge(row)
    return row


def _settings_for_user(application: FastAPI, user) -> Any:
    settings = application.state.settings
    return settings.model_copy(
        update={
            "simulated_initial_capital_mxn": float(
                user.simulated_initial_capital_mxn
            ),
            "paper_exploration_enabled": bool(
                settings.paper_exploration_enabled
                and user.ai_exploration_enabled
            ),
            "runtime_auto_start": bool(
                settings.runtime_auto_start and user.bot_enabled
            ),
        }
    )


async def startup_runtime(application: FastAPI) -> None:
    """Start one isolated paper Runtime for every active user who enabled the bot."""
    _registries(application)
    application.state.user_runtime_controller = lambda user_id: apply_user_runtime_preference(
        application, user_id
    )
    settings = application.state.settings
    if getattr(settings, "app_env", "development") == "test":
        return
    if not getattr(settings, "runtime_auto_start", True) or getattr(
        settings, "live_trading", False
    ):
        return
    if str(getattr(settings, "runtime_broker", "paper")).lower() != "paper":
        return

    try:
        with application.state.db_session_factory() as session:
            user_ids = [
                str(item["id"])
                for item in SqlUserAccountRepository(session).list_active()
                if item.get("bot_enabled")
            ]
    except Exception:
        return

    for user_id in user_ids:
        await apply_user_runtime_preference(application, user_id)


async def shutdown_runtime(application: FastAPI) -> None:
    """Cancel legacy or per-user background work without creating unused engines."""
    state = application.state
    legacy_runtime = getattr(state, "runtime_engine", None)
    has_multiuser_registries = hasattr(state, "runtime_engines")

    if not has_multiuser_registries:
        await _cancel_legacy_background_task(application)
        if legacy_runtime is not None and legacy_runtime.running:
            await legacy_runtime.stop()
        return

    engines = state.runtime_engines
    tasks = getattr(state, "runtime_background_tasks", {})
    for user_id in list(tasks):
        await _cancel_background_task(application, user_id)
    for user_id, runtime in list(engines.items()):
        if runtime.running:
            with user_scope(user_id):
                with suppress(Exception):
                    await runtime.stop()
    engines.clear()
    state.runtime_engine = None
    state.runtime_background_task = None


async def apply_user_runtime_preference(application: FastAPI, user_id: str) -> None:
    """Apply one user's Bot/IA switches without affecting any other account."""
    engines, _, states, errors = _registries(application)
    user = _load_user(application, user_id)
    settings = application.state.settings

    await _cancel_background_task(application, user_id)
    existing = engines.pop(user_id, None)
    if existing is not None and existing.running:
        with user_scope(user_id):
            with suppress(Exception):
                await existing.stop()

    errors[user_id] = None
    if not user.bot_enabled:
        states[user_id] = "disabled_by_user"
        return
    if settings.live_trading:
        states[user_id] = "blocked_live_mode"
        return
    if str(settings.runtime_broker).lower() != "paper":
        states[user_id] = "blocked_non_paper_broker"
        return

    try:
        runtime = _runtime_for_application(application, user_id, force_new=True)
        with user_scope(user_id):
            if not runtime.running:
                await runtime.start()
        _ensure_background_task(application, user_id, runtime)
    except Exception as exc:
        states[user_id] = "error"
        errors[user_id] = f"{type(exc).__name__}: {exc}"
        return
    states[user_id] = "automatic_running"


async def _background_loop(
    runtime: ExplorationRuntimeEngine,
    user_id: str = OWNER_USER_ID,
) -> None:
    while True:
        with user_scope(user_id):
            await runtime.run_once()
        await asyncio.sleep(max(runtime.config.loop_interval_seconds, 5.0))


async def _cancel_legacy_background_task(application: FastAPI) -> None:
    task = getattr(application.state, "runtime_background_task", None)
    application.state.runtime_background_task = None
    if task is None:
        return
    if not task.done():
        task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await task


def _ensure_background_loop(request: Request, runtime: Any) -> None:
    """Backward-compatible helper for the original single Runtime contract."""
    if not bool(getattr(request.app.state.settings, "runtime_auto_start", True)):
        return
    task = getattr(request.app.state, "runtime_background_task", None)
    if task is None or task.done():
        request.app.state.runtime_background_task = asyncio.create_task(
            _background_loop(runtime),
            name="paul-ai-paper-runtime",
        )


async def _cancel_background_task(application: FastAPI, user_id: str) -> None:
    _, tasks, _, _ = _registries(application)
    task = tasks.pop(user_id, None)
    if user_id == OWNER_USER_ID:
        application.state.runtime_background_task = None
    if task is None:
        return
    if not task.done():
        task.cancel()
    with suppress(asyncio.CancelledError, Exception):
        await task


def _ensure_background_task(
    application: FastAPI,
    user_id: str,
    runtime: ExplorationRuntimeEngine,
) -> None:
    _, tasks, _, _ = _registries(application)
    task = tasks.get(user_id)
    if task is None or task.done():
        with user_scope(user_id):
            task = asyncio.create_task(
                _background_loop(runtime, user_id),
                name=f"paul-ai-paper-runtime-{user_id}",
            )
        tasks[user_id] = task
        if user_id == OWNER_USER_ID:
            application.state.runtime_background_task = task


def _resolved_runtime_books(settings) -> tuple[str, ...]:
    configured = tuple(
        book.strip().lower()
        for book in getattr(
            settings,
            "runtime_books",
            ",".join(VERIFIED_RUNTIME_BOOKS),
        ).split(",")
        if book.strip()
    )
    verified = tuple(book for book in configured if book in VERIFIED_RUNTIME_BOOKS)
    return verified or VERIFIED_RUNTIME_BOOKS


def _runtime_for_application(
    application: FastAPI,
    user_id: str,
    *,
    force_new: bool = False,
) -> ExplorationRuntimeEngine:
    engines, _, _, _ = _registries(application)
    runtime = None if force_new else engines.get(user_id)
    if runtime is not None:
        return runtime

    user = _load_user(application, user_id)
    settings = _settings_for_user(application, user)
    config = RuntimeConfig(
        loop_interval_seconds=float(settings.runtime_loop_interval_seconds),
        books=_resolved_runtime_books(settings),
        timeframe=settings.runtime_timeframe,
        strategy_name=settings.runtime_strategy,
        trade_amount_mxn=Decimal(str(settings.runtime_trade_amount_mxn)),
        market_data_provider=settings.runtime_market_data_provider,
        broker_name=settings.runtime_broker,
        max_history=int(settings.runtime_history_points),
    )
    exploration_config = ExplorationConfig(
        enabled=bool(settings.paper_exploration_enabled),
        hold_cycles_before_entry=int(settings.paper_exploration_hold_cycles),
        max_holding_cycles=int(settings.paper_exploration_max_holding_cycles),
        cooldown_cycles=int(settings.paper_exploration_cooldown_cycles),
        amount_mxn=Decimal(str(settings.paper_exploration_amount_mxn)),
        max_positions=int(settings.paper_exploration_max_positions),
    )
    with user_scope(user_id):
        broker = None
        if config.broker_name == "paper":
            broker = ExplorationPersistentPaperBroker(
                session_factory=application.state.db_session_factory,
                settings=settings,
            )
        runtime = ExplorationRuntimeEngine(
            config=config,
            exploration_config=exploration_config,
            live_trading=bool(settings.live_trading),
            broker=broker,
            settings=settings,
        )
    engines[user_id] = runtime
    if user_id == OWNER_USER_ID:
        application.state.runtime_engine = runtime
    return runtime


def _runtime_payload(application: FastAPI, user_id: str) -> dict[str, Any]:
    engines, tasks, states, errors = _registries(application)
    user = _load_user(application, user_id)
    runtime = engines.get(user_id)
    if runtime is None:
        runtime = _runtime_for_application(application, user_id)
    with user_scope(user_id):
        payload = runtime.status().to_public_dict()
    payload["last_decision"] = _with_signal_level(payload.get("last_decision"))
    for brain in payload.get("asset_brains", {}).values():
        classified = classify_signal_level(
            score=brain.get("last_score", 0),
            confidence=brain.get("last_confidence", 0),
            action=brain.get("last_action", "hold"),
        )
        brain.update(classified.to_public_dict())
    task = tasks.get(user_id)
    payload.update(
        {
            "user_id": user_id,
            "username": user.username,
            "automatic": bool(user.bot_enabled),
            "ai_exploration_enabled": bool(user.ai_exploration_enabled),
            "startup_state": states.get(
                user_id,
                "ready_to_start" if user.bot_enabled else "disabled_by_user",
            ),
            "startup_error": errors.get(user_id),
            "background_task_active": bool(task is not None and not task.done()),
            "mode_label": "Simulación automática",
            "provider_label": (
                "Bitso, solo lectura"
                if runtime.config.market_data_provider == "bitso"
                else runtime.config.market_data_provider
            ),
            "broker_label": "Dinero simulado",
            "risk_label": (
                "Protección automática: pérdida 3%, objetivo 6% y seguimiento 2%"
            ),
            "history_label": (
                f"{payload.get('history_points', 0)} datos cargados para análisis"
            ),
            "signal_scale": [
                {"color": "blue", "label": "Oportunidad excepcional"},
                {"color": "green", "label": "Favorable"},
                {"color": "yellow", "label": "Mantener y observar"},
                {"color": "orange", "label": "Desfavorable"},
                {"color": "red", "label": "Riesgo alto / salida"},
            ],
        }
    )
    return payload


def _runtime(request: Request) -> ExplorationRuntimeEngine:
    legacy = _legacy_runtime(request)
    if legacy is not None:
        return legacy
    user_id = require_auth(request)
    return _runtime_for_application(request.app, user_id)
