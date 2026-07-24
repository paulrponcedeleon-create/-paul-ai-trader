from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re
import secrets
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.user_models import UserAccount
from app.services.money import quantize_money
from app.services.passwords import hash_password, verify_password

_USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
OWNER_USER_ID = "owner"
OWNER_USERNAME = "paul"
BOOTSTRAP_PASSWORD_SENTINEL = "environment_bootstrap"


def normalize_username(value: str) -> str:
    username = str(value or "").strip().lower()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "El usuario debe tener 3 a 32 caracteres: letras, números, punto, guion o guion bajo."
        )
    return username


class SqlUserAccountRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_active(self) -> list[dict[str, Any]]:
        rows = self.session.scalars(
            select(UserAccount)
            .where(UserAccount.is_active.is_(True))
            .order_by(UserAccount.created_at.asc(), UserAccount.username.asc())
        ).all()
        return [row.to_public_dict() for row in rows]

    def get_row(self, user_id: str) -> UserAccount | None:
        return self.session.get(UserAccount, str(user_id))

    def get_by_id(self, user_id: str) -> dict[str, Any] | None:
        row = self.get_row(user_id)
        return row.to_public_dict() if row else None

    def get_row_by_username(self, username: str) -> UserAccount | None:
        normalized = normalize_username(username)
        return self.session.scalar(
            select(UserAccount).where(UserAccount.username == normalized)
        )

    def get_by_username(self, username: str) -> dict[str, Any] | None:
        row = self.get_row_by_username(username)
        return row.to_public_dict() if row else None

    def ensure_owner(
        self,
        *,
        password: str,
        initial_capital_mxn: Any,
        username: str = OWNER_USERNAME,
        display_name: str = "Paul",
    ) -> UserAccount:
        normalized_username = normalize_username(username)
        row = self.get_row(OWNER_USER_ID)
        if row is None:
            row = self.session.scalar(
                select(UserAccount).where(UserAccount.username == normalized_username)
            )
        if row is None:
            row = UserAccount(
                id=OWNER_USER_ID,
                username=normalized_username,
                display_name=str(display_name or normalized_username).strip()[:120],
                password_hash=hash_password(password),
                is_admin=True,
                bot_enabled=True,
                ai_exploration_enabled=True,
                shared_learning_enabled=True,
                simulated_initial_capital_mxn=quantize_money(initial_capital_mxn),
            )
            self.session.add(row)
            self.session.flush()
            return row
        if row.password_hash == BOOTSTRAP_PASSWORD_SENTINEL:
            row.password_hash = hash_password(password)
        if row.id != OWNER_USER_ID:
            row.id = OWNER_USER_ID
        row.username = normalized_username
        row.display_name = str(display_name or row.display_name).strip()[:120]
        row.is_admin = True
        row.is_active = True
        self.session.flush()
        return row

    def authenticate(self, username: str, password: str) -> UserAccount | None:
        try:
            row = self.get_row_by_username(username)
        except ValueError:
            return None
        if row is None or not row.is_active:
            return None
        return row if verify_password(password, row.password_hash) else None

    def create(
        self,
        *,
        username: str,
        display_name: str,
        password: str,
        initial_capital_mxn: Any = Decimal("5000.00"),
        is_admin: bool = False,
    ) -> UserAccount:
        normalized = normalize_username(username)
        if self.session.scalar(
            select(UserAccount.id).where(UserAccount.username == normalized)
        ):
            raise ValueError("Ese nombre de usuario ya existe.")
        clean_name = str(display_name or normalized).strip()[:120]
        if not clean_name:
            raise ValueError("El nombre visible no puede estar vacío.")
        row = UserAccount(
            id=f"usr_{secrets.token_hex(8)}",
            username=normalized,
            display_name=clean_name,
            password_hash=hash_password(password),
            is_admin=bool(is_admin),
            is_active=True,
            bot_enabled=True,
            ai_exploration_enabled=True,
            shared_learning_enabled=True,
            simulated_initial_capital_mxn=quantize_money(initial_capital_mxn),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def update_preferences(
        self,
        user_id: str,
        *,
        bot_enabled: bool | None = None,
        ai_exploration_enabled: bool | None = None,
        shared_learning_enabled: bool | None = None,
    ) -> UserAccount:
        row = self.get_row(user_id)
        if row is None:
            raise ValueError("Usuario no encontrado.")
        if bot_enabled is not None:
            row.bot_enabled = bool(bot_enabled)
        if ai_exploration_enabled is not None:
            row.ai_exploration_enabled = bool(ai_exploration_enabled)
        if shared_learning_enabled is not None:
            row.shared_learning_enabled = bool(shared_learning_enabled)
        row.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return row

    def save_bitso_credentials(
        self,
        user_id: str,
        *,
        encrypted_key: str,
        encrypted_secret: str,
    ) -> UserAccount:
        row = self.get_row(user_id)
        if row is None:
            raise ValueError("Usuario no encontrado.")
        row.bitso_api_key_encrypted = encrypted_key
        row.bitso_api_secret_encrypted = encrypted_secret
        row.bitso_connected_at = datetime.now(timezone.utc)
        row.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return row

    def clear_bitso_credentials(self, user_id: str) -> UserAccount:
        row = self.get_row(user_id)
        if row is None:
            raise ValueError("Usuario no encontrado.")
        row.bitso_api_key_encrypted = None
        row.bitso_api_secret_encrypted = None
        row.bitso_connected_at = None
        row.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return row
