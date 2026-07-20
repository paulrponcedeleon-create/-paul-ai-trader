from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Paul AI Trader"
    app_password: str = "paul-demo"
    session_secret: str = "change-this-in-render"

    bitso_base_url: str = "https://api.bitso.com/api/v3"
    bitso_api_key: str = ""
    bitso_api_secret: str = ""

    live_trading: bool = False
    max_order_mxn: float = 200.0
    max_daily_loss_mxn: float = 100.0
    max_open_orders: int = 3
    allowed_books: str = "btc_mxn,eth_mxn,xrp_mxn,sol_mxn"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def allowed_books_set(self) -> set[str]:
        return {x.strip().lower() for x in self.allowed_books.split(",") if x.strip()}

settings = Settings()
