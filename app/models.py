from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str | None = None
    password: str


class RegisterRequest(BaseModel):
    username: str
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    registration_code: str


class AccountPreferencesRequest(BaseModel):
    bot_enabled: bool | None = None
    ai_exploration_enabled: bool | None = None
    shared_learning_enabled: bool | None = None


class BitsoCredentialsRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=300)
    api_secret: str = Field(min_length=8, max_length=500)


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
