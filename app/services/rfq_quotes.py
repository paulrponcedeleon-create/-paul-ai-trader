from __future__ import annotations

import time
from typing import Any

from app.services.bitso import BitsoClient, BitsoError


class RfqQuoteError(RuntimeError):
    pass


class RfqQuoteResolver:
    INTERMEDIATES = ("USDC", "USDT", "USD")
    REFERENCE_MXN = 100.0

    def __init__(self, bitso: BitsoClient) -> None:
        self.bitso = bitso
        self._pairs: set[tuple[str, str]] = set()
        self._pairs_until = 0.0

    async def pairs(self) -> set[tuple[str, str]]:
        now = time.monotonic()
        if self._pairs and now < self._pairs_until:
            return self._pairs
        try:
            result = await self.bitso.rfq_pairs()
            payload = result.get("payload", result)
            rows = payload.get("pairs", []) if isinstance(payload, dict) else payload
            self._pairs = {
                (
                    str(item.get("source", "")).upper(),
                    str(item.get("target", "")).upper(),
                )
                for item in rows
                if isinstance(item, dict) and item.get("source") and item.get("target")
            }
        except (BitsoError, TypeError, AttributeError):
            self._pairs = set()
        self._pairs_until = now + 300
        return self._pairs

    async def route(self, symbol: str, side: str) -> list[tuple[str, str]]:
        pairs = await self.pairs()
        start, end = ("MXN", symbol) if side == "buy" else (symbol, "MXN")
        if (start, end) in pairs:
            return [(start, end)]
        for intermediate in self.INTERMEDIATES:
            if (start, intermediate) in pairs and (intermediate, end) in pairs:
                return [(start, intermediate), (intermediate, end)]
        raise RfqQuoteError(
            f"Bitso no devolvió una ruta de conversión {start} → {end}."
        )

    @staticmethod
    def _payload(result: dict[str, Any]) -> dict[str, Any]:
        payload = result.get("payload", result)
        if not isinstance(payload, dict):
            raise RfqQuoteError("Bitso devolvió una cotización de conversión inválida.")
        return payload

    async def quote(self, symbol: str, side: str) -> dict[str, Any]:
        route = await self.route(symbol, side)
        if side == "buy":
            amount = self.REFERENCE_MXN
            for source, target in route:
                result = await self.bitso.rfq_quote(
                    source=source,
                    target=target,
                    source_amount=f"{amount:.8f}".rstrip("0").rstrip("."),
                )
                payload = self._payload(result)
                amount = float(payload["target_amount"])
                if amount <= 0:
                    raise RfqQuoteError(
                        "Bitso devolvió una cantidad de conversión inválida."
                    )
            price_mxn = self.REFERENCE_MXN / amount
        else:
            amount = self.REFERENCE_MXN
            for source, target in reversed(route):
                result = await self.bitso.rfq_quote(
                    source=source,
                    target=target,
                    target_amount=f"{amount:.8f}".rstrip("0").rstrip("."),
                )
                payload = self._payload(result)
                amount = float(payload["source_amount"])
                if amount <= 0:
                    raise RfqQuoteError(
                        "Bitso devolvió una cantidad de conversión inválida."
                    )
            price_mxn = self.REFERENCE_MXN / amount

        if price_mxn <= 0:
            raise RfqQuoteError(f"Precio de conversión inválido para {symbol}.")

        route_text = " → ".join([route[0][0], *(target for _, target in route)])
        return {
            "last": price_mxn,
            "high": price_mxn,
            "low": price_mxn,
            "volume": 0.0,
            "effective_fee_rate": 0.0,
            "effective_fee_percent": 0.0,
            "fee_source": "bitso_rfq_inclusive",
            "fee_included_in_quote": True,
            "route": [
                f"rfq:{source.lower()}_{target.lower()}" for source, target in route
            ],
            "route_label": f"Conversión Bitso App · {route_text}",
            "source": "bitso_rfq",
            "delayed": False,
        }
