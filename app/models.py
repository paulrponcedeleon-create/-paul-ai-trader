from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str


class SimulatedOrderRequest(BaseModel):
    book: str
    side: Literal["buy", "sell"]
    amount_mxn: Decimal = Field(gt=0)
    daily_pnl_mxn: Decimal = Decimal("0")
    open_orders: int = 0


class PartialCloseRequest(BaseModel):
    amount_mxn: Decimal | None = Field(default=None, gt=0)


class SignalResponse(BaseModel):
    action: Literal["buy", "sell", "hold"]
    confidence: int
    reason: str
    reference_price: float
