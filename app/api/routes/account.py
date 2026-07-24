from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.dependencies import require_auth
from app.db.user_models import UserAccount
from app.models import AccountPreferencesRequest, BitsoCredentialsRequest
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.repositories.users import SqlUserAccountRepository
from app.services.bitso import BitsoClient, BitsoError
from app.services.credential_vault import CredentialVault, CredentialVaultError
from app.services.learning_observations import learning_source_summary

router = APIRouter(tags=["account"])


def _vault(request: Request) -> CredentialVault:
    try:
        return CredentialVault(request.app.state.settings.credential_encryption_key)
    except CredentialVaultError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "El servidor todavía no tiene configurado el cifrado de credenciales. "
                "La simulación continúa disponible sin conectar Bitso."
            ),
        ) from exc


def _bitso_client(request: Request, api_key: str, api_secret: str):
    factory = getattr(request.app.state, "user_bitso_factory", None)
    if callable(factory):
        return factory(api_key, api_secret)
    return BitsoClient(
        request.app.state.settings,
        api_key=api_key,
        api_secret=api_secret,
    )


def _current_row(request: Request) -> UserAccount:
    user_id = require_auth(request)
    with request.app.state.db_session_factory() as session:
        row = SqlUserAccountRepository(session).get_row(user_id)
        if row is None or not row.is_active:
            request.session.clear()
            raise HTTPException(status_code=401, detail="La cuenta ya no está activa.")
        session.expunge(row)
    return row


def _public_account(request: Request, row: UserAccount) -> dict:
    with request.app.state.db_session_factory() as session:
        repository = SqlSimulatedOrderRepository(session, user_id=row.id)
        ledger = repository.capital_ledger(row.simulated_initial_capital_mxn)
        open_positions = len(repository.list_open())
        closed_positions = len(repository.list_closed())
    return {
        **row.to_public_dict(),
        "simulation": {
            **ledger,
            "open_positions": open_positions,
            "closed_positions": closed_positions,
            "separate_from_other_users": True,
        },
        "bitso": {
            "connected": bool(
                row.bitso_api_key_encrypted and row.bitso_api_secret_encrypted
            ),
            "mode": "read_only_app_usage",
            "required_for_simulation": False,
            "secrets_are_never_returned": True,
        },
    }


def _anonymous_learning_summary(rows: list[dict]) -> dict:
    """Expose aggregate metrics only; never personal labels or trade identifiers."""
    summary = learning_source_summary(rows)
    return {
        "manual_samples": summary.get("manual_samples", 0),
        "runtime_samples": summary.get("runtime_samples", 0),
        "exploration_samples": summary.get("exploration_samples", 0),
        "bot_samples": summary.get("bot_samples", 0),
        "total_samples": summary.get("total_samples", 0),
        "active_tracking_samples": summary.get("active_tracking_samples", 0),
        "completed_result_samples": summary.get("completed_result_samples", 0),
        "realized_pnl_mxn": summary.get("realized_pnl_mxn", 0.0),
        "learning_progress": summary.get(
            "learning_progress",
            {
                "completed_results": 0,
                "minimum_results": 100,
                "percent": 0.0,
                "stage": "recolección",
            },
        ),
        "sources": {
            "manual": summary.get("manual_samples", 0),
            "bot": summary.get("runtime_samples", 0),
            "ai": summary.get("exploration_samples", 0),
        },
    }


@router.get("/account")
async def account(request: Request):
    return _public_account(request, _current_row(request))


@router.patch("/account/preferences")
async def update_account_preferences(
    body: AccountPreferencesRequest,
    request: Request,
):
    user_id = require_auth(request)
    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        try:
            row = repository.update_preferences(
                user_id,
                bot_enabled=body.bot_enabled,
                ai_exploration_enabled=body.ai_exploration_enabled,
                shared_learning_enabled=body.shared_learning_enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.commit()
        session.refresh(row)
        session.expunge(row)

    runtime_controller = getattr(request.app.state, "user_runtime_controller", None)
    if callable(runtime_controller):
        await runtime_controller(user_id)
    return _public_account(request, row)


@router.post("/account/bitso")
async def connect_bitso(body: BitsoCredentialsRequest, request: Request):
    user_id = require_auth(request)
    api_key = body.api_key.strip()
    api_secret = body.api_secret.strip()
    client = _bitso_client(request, api_key, api_secret)
    try:
        await client.balance()
    except BitsoError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Bitso rechazó las credenciales: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="No fue posible validar la conexión con Bitso.",
        ) from exc

    vault = _vault(request)
    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        try:
            row = repository.save_bitso_credentials(
                user_id,
                encrypted_key=vault.encrypt(api_key),
                encrypted_secret=vault.encrypt(api_secret),
            )
        except (ValueError, CredentialVaultError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        session.commit()
        session.refresh(row)
        session.expunge(row)
    return {
        "ok": True,
        "account": _public_account(request, row),
        "message": "Bitso quedó conectado para consultas privadas de esta cuenta.",
    }


@router.delete("/account/bitso")
async def disconnect_bitso(request: Request):
    user_id = require_auth(request)
    with request.app.state.db_session_factory() as session:
        repository = SqlUserAccountRepository(session)
        try:
            row = repository.clear_bitso_credentials(user_id)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        session.commit()
        session.refresh(row)
        session.expunge(row)
    return {"ok": True, "account": _public_account(request, row)}


@router.get("/account/bitso/balance")
async def user_bitso_balance(request: Request):
    row = _current_row(request)
    if not row.bitso_api_key_encrypted or not row.bitso_api_secret_encrypted:
        raise HTTPException(
            status_code=409,
            detail="Esta cuenta todavía no ha conectado Bitso.",
        )
    vault = _vault(request)
    try:
        api_key = vault.decrypt(row.bitso_api_key_encrypted)
        api_secret = vault.decrypt(row.bitso_api_secret_encrypted)
    except CredentialVaultError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    client = _bitso_client(request, api_key, api_secret)
    try:
        result = await client.balance()
    except BitsoError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "connected": True,
        "source": "bitso_private_read_only",
        "payload": result,
    }


@router.get("/learning/community")
async def community_learning(request: Request):
    require_auth(request)
    settings = request.app.state.settings
    if not settings.community_learning_enabled:
        return {
            "enabled": False,
            "participants": 0,
            "privacy": "aggregate_only_without_identity_or_trade_ids",
            "learning_sources": _anonymous_learning_summary([]),
        }
    with request.app.state.db_session_factory() as session:
        participant_ids = set(
            session.scalars(
                select(UserAccount.id).where(
                    UserAccount.is_active.is_(True),
                    UserAccount.shared_learning_enabled.is_(True),
                )
            ).all()
        )
        rows = [
            row
            for row in SqlSimulatedOrderRepository(session, user_id=None).list_closed()
            if row.get("user_id") in participant_ids
        ]
    return {
        "enabled": True,
        "participants": len(participant_ids),
        "privacy": "aggregate_only_without_identity_or_trade_ids",
        "learning_sources": _anonymous_learning_summary(rows),
    }
