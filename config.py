from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    bitso_base_url: str = "https://stage.bitso.com/api/v3"
    bitso_api_key: str = ""
    bitso_api_secret: str = ""
    live_trading: bool = False
    require_manual_approval: bool = True
    max_order_mxn: float = 200.0
    max_daily_loss_mxn: float = 100.0
    max_open_orders: int = 2
    allowed_books: str = "btc_mxn,eth_mxn"
    slippage_tolerance: float = 0.5

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def allowed_books_set(self) -> set[str]:
        return {x.strip().lower() for x in self.allowed_books.split(",") if x.strip()}

settings = Settings()
