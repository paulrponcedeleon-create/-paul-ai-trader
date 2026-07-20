import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import httpx
from .config import settings

class BitsoError(RuntimeError):
    pass

class BitsoClient:
    def __init__(self) -> None:
        self.base_url = settings.bitso_base_url.rstrip("/")

    @staticmethod
    def _json_body(payload: dict[str, Any] | None) -> str:
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False) if payload else ""

    def _auth_header(self, method: str, request_path: str, body: str = "") -> str:
        if not settings.bitso_api_key or not settings.bitso_api_secret:
            raise BitsoError("Faltan BITSO_API_KEY y BITSO_API_SECRET en el archivo .env")
        nonce = str(int(time.time() * 1000))
        message = f"{nonce}{method.upper()}{request_path}{body}"
        signature = hmac.new(
            settings.bitso_api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"Bitso {settings.bitso_api_key}:{nonce}:{signature}"

    async def public_get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.strip('/')}"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()

    async def private_request(self, method: str, endpoint: str, payload: dict[str, Any] | None = None,
                              params: dict[str, Any] | None = None) -> dict[str, Any]:
        endpoint = endpoint.strip("/")
        query = f"?{urlencode(params)}" if params else ""
        request_path = f"/api/v3/{endpoint}{query}"
        body = self._json_body(payload)
        headers = {
            "Authorization": self._auth_header(method, request_path, body),
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/{endpoint}{query}"
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.request(method, url, headers=headers, content=body or None)
            try:
                data = r.json()
            except Exception:
                data = {"success": False, "error": {"message": r.text}}
            if r.is_error or data.get("success") is False:
                msg = data.get("error", {}).get("message", f"HTTP {r.status_code}")
                raise BitsoError(msg)
            return data

    async def available_books(self):
        return await self.public_get("available_books/")

    async def ticker(self, book: str):
        return await self.public_get("ticker/", {"book": book})

    async def order_book(self, book: str):
        return await self.public_get("order_book/", {"book": book, "aggregate": "true"})

    async def balance(self):
        return await self.private_request("GET", "balance/")

    async def open_orders(self, book: str | None = None):
        params = {"book": book} if book else None
        return await self.private_request("GET", "open_orders", params=params)

    async def user_trades(self, book: str | None = None):
        params = {"book": book} if book else None
        return await self.private_request("GET", "user_trades/", params=params)

    async def fees(self):
        return await self.private_request("GET", "fees")

    async def place_market_order(self, book: str, side: str, amount_mxn: float):
        payload = {
            "book": book,
            "side": side,
            "type": "market",
            "minor": f"{amount_mxn:.2f}",
            "origin_id": f"paulbot-{int(time.time() * 1000)}",
            "slippage_tolerance": settings.slippage_tolerance,
        }
        return await self.private_request("POST", "orders", payload=payload)

    async def cancel_order(self, oid: str):
        return await self.private_request("DELETE", f"orders/{oid}")
