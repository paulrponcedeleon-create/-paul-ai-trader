import hashlib
import hmac
import json
import time
from typing import Any
import httpx

from app.config import settings

class BitsoError(RuntimeError):
    pass

class BitsoClient:
    def __init__(self) -> None:
        self.base_url = settings.bitso_base_url.rstrip("/")

    @staticmethod
    def _path(endpoint: str) -> str:
        clean = endpoint.lstrip("/")
        return f"/api/v3/{clean}"

    def _auth_header(self, method: str, endpoint: str, payload: dict[str, Any] | None = None) -> str:
        if not settings.bitso_api_key or not settings.bitso_api_secret:
            raise BitsoError("Faltan las credenciales privadas de Bitso.")
        nonce = str(time.time_ns())
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) if payload else ""
        message = f"{nonce}{method.upper()}{self._path(endpoint)}{body}"
        signature = hmac.new(
            settings.bitso_api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"Bitso {settings.bitso_api_key}:{nonce}:{signature}"

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        private: bool = False,
    ) -> dict[str, Any]:
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"
        headers: dict[str, str] = {"Accept": "application/json"}
        if private:
            headers["Authorization"] = self._auth_header(method, endpoint, payload)
            headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(method, url, params=params, json=payload, headers=headers)

        try:
            data = response.json()
        except ValueError as exc:
            raise BitsoError(f"Bitso respondió HTTP {response.status_code} sin JSON válido.") from exc

        if response.is_error or data.get("success") is False:
            error = data.get("error", {})
            message = error.get("message") or str(error) or f"HTTP {response.status_code}"
            raise BitsoError(message)
        return data

    async def ticker(self, book: str) -> dict[str, Any]:
        return await self._request("GET", "ticker", params={"book": book})

    async def available_books(self) -> dict[str, Any]:
        return await self._request("GET", "available_books")

    async def balance(self) -> dict[str, Any]:
        return await self._request("GET", "balance", private=True)

    async def open_orders(self, book: str | None = None) -> dict[str, Any]:
        params = {"book": book} if book else None
        return await self._request("GET", "open_orders", params=params, private=True)

    async def place_market_order(self, book: str, side: str, amount_mxn: float) -> dict[str, Any]:
        # Market buy uses minor amount (MXN). A production sell flow should
        # calculate major asset quantity explicitly from portfolio holdings.
        if side != "buy":
            raise BitsoError("La v1 solo permite compras reales por monto MXN; ventas reales siguen bloqueadas.")
        payload = {
            "book": book,
            "side": side,
            "type": "market",
            "minor": f"{amount_mxn:.2f}",
            "origin_id": f"paul-ai-{time.time_ns()}",
        }
        return await self._request("POST", "orders", payload=payload, private=True)
