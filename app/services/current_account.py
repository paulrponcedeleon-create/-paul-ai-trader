from __future__ import annotations

from fastapi import HTTPException, Request

from app.repositories.users import SqlUserAccountRepository


def load_user_account(request: Request, user_id: str):
    with request.app.state.db_session_factory() as session:
        row = SqlUserAccountRepository(session).get_row(user_id)
        if row is None or not row.is_active:
            raise HTTPException(status_code=401, detail="La cuenta no está disponible.")
        session.expunge(row)
    return row


def user_initial_capital_mxn(request: Request, user_id: str):
    return load_user_account(request, user_id).simulated_initial_capital_mxn
