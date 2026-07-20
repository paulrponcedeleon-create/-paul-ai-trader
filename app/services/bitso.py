import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from app.config import Settings, settings


class BitsoError(RuntimeError):
    pass


class BitsoClient:
    def __init__(self, client_settings: Settings | None = None) -> None:
        self.settings = client_settings or settings
        self.base_url = self.settings.bitso_base_url.rstrip("/")
        api_root = self.base_url.removesuffix("/api/v3")
        self.rfq_base_url = f"{api_root}/rfq/v1"

    @staticmethod
    def _path(endpoint: str) -> str:
        clean = endpoint.lstrip("/")
        return f"/api/v3/{clean}"

    def _auth_header_for_path(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        if not self.settings.bitso_api_key or not self.settings.bitso_api_secret:
            raise BitsoError("Faltan las credenciales privadas de Bitso.")
        nonce = str(time.time_ns())
        body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) if payload else ""
        message = f"{nonce}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.settings.bitso_api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"Bitso {self.settings.bitso_api_key}:{nonce}:{signature}"

    def _auth_header(
        self,
        method: str,
        endpoint: str,
        payload: dict[str, Any] | None = None,
    ) -> str:
        return self._auth_header_for_path(method, self._path(endpoint), payload)

    @staticmethod
    def _error_message(data: Any, status_code: int) -> str:
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                return str(error.get("message") or error)
            errors = data.get("errors")
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    return str(first.get("message") or first.get("code") or first)
                return str(first)
        return f"HTTP {status_code}"

    async def _request_url(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
        private: bool = False,
        signature_path: str | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Cache-Control": "no-cache",
        }
        if private:
            path = signature_path or self._path(url.rsplit("/", 1)[-1])
            headers["Authorization"] = self._auth_header_for_path(method, path, payload)
            headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.request(
                method,
                url,
                params=params,
                json=payload,
                headers=headers,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise BitsoError(
                f"Bitso respondió HTTP {response.status_code} sin JSON válido."
            ) from exc

        if response.is_error or (isinstance(data, dict) and data.get("success") is False):
            raise BitsoError(self._error_message(data, response.status_code))
        return data

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
        return await self._request_url(
            method,
            f"{self.base_url}/{endpoint}",
            params=params,
            payload=payload,
            private=private,
            signature_path=self._path(endpoint),
        )

    async def ticker(self, book: str) -> dict[str, Any]:
        return await self._request(
            "GET", "ticker", params={"book": book, "_": time.time_ns()}
        )

    async def available_books(self) -> dict[str, Any]:
        return await self._request("GET", "available_books")

    async def rfq_pairs(
        self,
        source: str | None = None,
        target: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {}
        if source:
            params["source"] = source.upper()
        if target:
            params["target"] = target.upper()
        return await self._request_url(
            "GET",
            f"{self.rfq_base_url}/pairs",
            params=params or None,
        )

    async def rfq_quote(
        self,
        *,
        source: str,
        target: str,
        source_amount: str | None = None,
        target_amount: str | None = None,
    ) -> dict[str, Any]:
        if bool(source_amount) == bool(target_amount):
            raise BitsoError(
                "La cotización RFQ requiere source_amount o target_amount, pero no ambos."
            )
        payload: dict[str, str] = {
            "source": source.upper(),
            "target": target.upper(),
        }
        if source_amount is not None:
            payload["source_amount"] = source_amount
        if target_amount is not None:
            payload["target_amount"] = target_amount

        return await self._request_url(
            "POST",
            f"{self.rfq_base_url}/quotes",
            payload=payload,
            private=bool(
                self.settings.bitso_api_key and self.settings.bitso_api_secret
            ),
            signature_path="/rfq/v1/quotes",
        )

    async def balance(self) -> dict[str, Any]:
        return await self._request("GET", "balance", private=True)

    async def fees(self) -> dict[str, Any]:
        return await self._request("GET", "fees", private=True)

    async def open_orders(self, book: str | None = None) -> dict[str, Any]:
        params = {"book": book} if book else None
        return await self._request("GET", "open_orders", params=params, private=True)

    async def place_market_order(
        self, book: str, side: str, amount_mxn: float
    ) -> dict[str, Any]:
        # Market buy uses minor amount (MXN). A production sell flow should
        # calculate major asset quantity explicitly from portfolio holdings.
        if side != "buy":
            raise BitsoError(
                "La v1 solo permite compras reales por monto MXN; ventas reales siguen bloqueadas."
            )
        payload = {
            "book": book,
            "side": side,
            "type": "market",
            "minor": f"{amount_mxn:.2f}",
            "origin_id": f"paul-ai-{time.time_ns()}",
        }
        return await self._request("POST", "orders", payload=payload, private=True)
