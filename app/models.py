from typing import Literal
from pydantic import BaseModel, Field

class LoginRequest(BaseModel):
    password: str

class SimulatedOrderRequest(BaseModel):
    book: str
    side: Literal["buy", "sell"]
    amount_mxn: float = Field(gt=0)
    daily_pnl_mxn: float = 0.0
    open_orders: int = 0

class SignalResponse(BaseModel):
    action: Literal["buy", "sell", "hold"]
    confidence: int
    reason: str
    reference_price: float
