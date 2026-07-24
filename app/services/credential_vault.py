from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class CredentialVaultError(RuntimeError):
    pass


class CredentialVault:
    def __init__(self, encryption_secret: str) -> None:
        value = str(encryption_secret or "").strip()
        if not value:
            raise CredentialVaultError(
                "CREDENTIAL_ENCRYPTION_KEY no está configurada."
            )
        try:
            self._fernet = Fernet(value.encode("ascii"))
        except (ValueError, UnicodeEncodeError):
            key = base64.urlsafe_b64encode(hashlib.sha256(value.encode("utf-8")).digest())
            self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        plain = str(value or "").strip()
        if not plain:
            raise CredentialVaultError("No se puede cifrar una credencial vacía.")
        return self._fernet.encrypt(plain.encode("utf-8")).decode("ascii")

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(str(token).encode("ascii")).decode("utf-8")
        except (InvalidToken, UnicodeError, ValueError) as exc:
            raise CredentialVaultError("No fue posible descifrar la credencial.") from exc
