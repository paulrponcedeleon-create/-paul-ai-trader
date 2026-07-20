from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
SameSitePolicy = Literal["lax", "strict", "none"]

DEVELOPMENT_APP_PASSWORD = "paul-demo"
DEVELOPMENT_SESSION_SECRET = "development-only-change-this-session-secret"
EXAMPLE_APP_PASSWORD = "replace-with-a-local-password"
EXAMPLE_SESSION_SECRET = "replace-with-a-random-string-of-at-least-32-characters"
DEFAULT_SIMULATION_BOOKS = (
    "btc_mxn,eth_mxn,xrp_mxn,sol_mxn,doge_mxn,ada_mxn,ltc_mxn,link_mxn,"
    "shib_mxn,pepe_mxn,sui_mxn,hbar_mxn,avax_mxn,dot_mxn,atom_mxn,uni_mxn,"
    "aave_mxn,mana_mxn,gala_mxn,sand_mxn,bch_mxn,bat_mxn,comp_mxn,mkr_mxn"
)


class Settings(BaseSettings):
    app_name: str = "Paul AI Trader"
    app_env: Environment = "development"
    app_password: str = DEVELOPMENT_APP_PASSWORD
    session_secret: str = DEVELOPMENT_SESSION_SECRET
    session_cookie_name: str = "paul_ai_session"
    session_cookie_secure: bool | None = None
    session_cookie_samesite: SameSitePolicy = "lax"
    session_max_age_seconds: int = 60 * 60 * 12

    bitso_base_url: str = "https://api.bitso.com/api/v3"
    bitso_api_key: str = ""
    bitso_api_secret: str = ""

    database_url: str = "sqlite:///./paul_ai_trader.db"

    live_trading: bool = False
    max_order_mxn: float = 200.0
    max_daily_loss_mxn: float = 100.0
    max_open_orders: int = 3
    allowed_books: str = "btc_mxn,eth_mxn,xrp_mxn,sol_mxn"
    simulation_books: str = DEFAULT_SIMULATION_BOOKS

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def resolved_session_cookie_secure(self) -> bool:
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.is_production

    @staticmethod
    def _parse_books(value: str) -> set[str]:
        return {item.strip().lower() for item in value.split(",") if item.strip()}

    @property
    def live_books_set(self) -> set[str]:
        return self._parse_books(self.allowed_books)

    @property
    def simulation_books_set(self) -> set[str]:
        return self._parse_books(self.simulation_books)

    @property
    def allowed_books_set(self) -> set[str]:
        return self.live_books_set if self.live_trading else self.simulation_books_set

    @property
    def enabled_books_set(self) -> set[str]:
        return self.allowed_books_set

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        if self.session_max_age_seconds <= 0:
            raise ValueError("SESSION_MAX_AGE_SECONDS debe ser mayor que cero.")

        if self.session_cookie_samesite == "none" and not self.resolved_session_cookie_secure:
            raise ValueError("SameSite=None requiere SESSION_COOKIE_SECURE=true.")

        database_url = self.database_url.strip()
        if not database_url:
            raise ValueError("DATABASE_URL no puede estar vacío.")

        if not self.live_books_set:
            raise ValueError("ALLOWED_BOOKS debe contener al menos un mercado.")
        if not self.simulation_books_set:
            raise ValueError("SIMULATION_BOOKS debe contener al menos un mercado.")

        if self.is_production:
            insecure_session_secret = (
                len(self.session_secret) < 32
                or self.session_secret in {DEVELOPMENT_SESSION_SECRET, EXAMPLE_SESSION_SECRET}
                or "replace-with" in self.session_secret.lower()
                or "change-this" in self.session_secret.lower()
            )
            if insecure_session_secret:
                raise ValueError(
                    "SESSION_SECRET debe configurarse con al menos 32 caracteres en producción."
                )
            if (
                not self.app_password
                or self.app_password in {DEVELOPMENT_APP_PASSWORD, EXAMPLE_APP_PASSWORD}
                or "replace-with" in self.app_password.lower()
            ):
                raise ValueError("APP_PASSWORD debe configurarse explícitamente en producción.")
            if not self.resolved_session_cookie_secure:
                raise ValueError("Las cookies de sesión deben ser seguras en producción.")
            if database_url.lower().startswith("sqlite"):
                raise ValueError(
                    "DATABASE_URL debe apuntar a PostgreSQL en producción; SQLite no es persistente en Render."
                )

        return self


settings = Settings()
