from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "test", "production"]
SameSitePolicy = Literal["lax", "strict", "none"]

DEVELOPMENT_APP_PASSWORD = "paul-demo"
DEVELOPMENT_SESSION_SECRET = "development-only-change-this-session-secret"
EXAMPLE_APP_PASSWORD = "replace-with-a-local-password"
EXAMPLE_SESSION_SECRET = "replace-with-a-random-string-of-at-least-32-characters"
DEVELOPMENT_REGISTRATION_CODE = "family-demo"
DEFAULT_SIMULATION_BOOKS = (
    "btc_mxn,eth_mxn,sol_mxn,xrp_mxn,usdt_mxn,"
    "algn_mxn,tsla_mxn,aapl_mxn"
)


class Settings(BaseSettings):
    app_name: str = "Paul AI Trader"
    app_env: Environment = "development"
    app_password: str = DEVELOPMENT_APP_PASSWORD
    owner_username: str = "paul"
    registration_enabled: bool = True
    user_registration_code: str = DEVELOPMENT_REGISTRATION_CODE
    credential_encryption_key: str = ""
    community_learning_enabled: bool = True
    session_secret: str = DEVELOPMENT_SESSION_SECRET
    session_cookie_name: str = "paul_ai_session"
    session_cookie_secure: bool | None = None
    session_cookie_samesite: SameSitePolicy = "lax"
    session_max_age_seconds: int = 60 * 60 * 12

    bitso_base_url: str = "https://api.bitso.com/api/v3"
    bitso_api_key: str = ""
    bitso_api_secret: str = ""

    database_url: str = "sqlite:///./paul_ai_trader.db"
    paul_data_dir: str = "./data"

    live_trading: bool = False
    simulated_initial_capital_mxn: float = 5000.0
    max_order_mxn: float = 500.0
    max_daily_loss_mxn: float = 500.0
    max_open_orders: int = 12
    allowed_books: str = "btc_mxn,eth_mxn,xrp_mxn,sol_mxn"
    simulation_books: str = DEFAULT_SIMULATION_BOOKS

    system_heartbeat_seconds: int = 60
    system_retry_attempts: int = 3
    system_circuit_breaker_failures: int = 3
    system_snapshot_interval_seconds: int = 300
    system_event_retention: int = 1000

    runtime_auto_start: bool = True
    runtime_loop_interval_seconds: float = 30.0
    runtime_books: str = "btc_mxn,eth_mxn,sol_mxn,xrp_mxn,usdt_mxn"
    runtime_timeframe: str = "1m"
    runtime_strategy: str = "momentum"
    runtime_trade_amount_mxn: float = 50.0
    runtime_market_data_provider: str = "bitso"
    runtime_broker: str = "paper"
    runtime_history_points: int = 200

    paper_stop_loss_pct: float = 3.0
    paper_take_profit_pct: float = 6.0
    paper_trailing_stop_pct: float = 2.0
    paper_exploration_enabled: bool = True
    paper_exploration_hold_cycles: int = 20
    paper_exploration_max_holding_cycles: int = 20
    paper_exploration_cooldown_cycles: int = 40
    paper_exploration_amount_mxn: float = 10.0
    paper_exploration_max_positions: int = 3

    burnin_default_duration: str = "1h"
    burnin_memory_growth_alert_bytes: int = 26214400
    burnin_max_events: int = 1000

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

    @property
    def paper_exploration_active(self) -> bool:
        return (
            self.paper_exploration_enabled
            and not self.live_trading
            and self.runtime_broker == "paper"
        )

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

    @property
    def resolved_paul_data_dir(self) -> Path:
        return Path(self.paul_data_dir).expanduser().resolve()

    @model_validator(mode="after")
    def validate_security_configuration(self) -> "Settings":
        if self.session_max_age_seconds <= 0:
            raise ValueError("SESSION_MAX_AGE_SECONDS debe ser mayor que cero.")
        if self.simulated_initial_capital_mxn <= 0:
            raise ValueError("SIMULATED_INITIAL_CAPITAL_MXN debe ser mayor que cero.")
        if self.runtime_loop_interval_seconds < 5:
            raise ValueError("RUNTIME_LOOP_INTERVAL_SECONDS debe ser de al menos 5 segundos.")
        if self.runtime_history_points < 20 or self.runtime_history_points > 500:
            raise ValueError("RUNTIME_HISTORY_POINTS debe estar entre 20 y 500.")
        if not self.owner_username.strip():
            raise ValueError("OWNER_USERNAME no puede estar vacío.")
        for name, value in {
            "PAPER_STOP_LOSS_PCT": self.paper_stop_loss_pct,
            "PAPER_TAKE_PROFIT_PCT": self.paper_take_profit_pct,
            "PAPER_TRAILING_STOP_PCT": self.paper_trailing_stop_pct,
        }.items():
            if value <= 0 or value > 50:
                raise ValueError(f"{name} debe estar entre 0 y 50.")
        for name, value in {
            "PAPER_EXPLORATION_HOLD_CYCLES": self.paper_exploration_hold_cycles,
            "PAPER_EXPLORATION_MAX_HOLDING_CYCLES": self.paper_exploration_max_holding_cycles,
        }.items():
            if value < 1 or value > 10000:
                raise ValueError(f"{name} debe estar entre 1 y 10000.")
        if (
            self.paper_exploration_cooldown_cycles < 0
            or self.paper_exploration_cooldown_cycles > 10000
        ):
            raise ValueError(
                "PAPER_EXPLORATION_COOLDOWN_CYCLES debe estar entre 0 y 10000."
            )
        if self.paper_exploration_amount_mxn <= 0:
            raise ValueError("PAPER_EXPLORATION_AMOUNT_MXN debe ser mayor que cero.")
        if self.paper_exploration_amount_mxn > self.max_order_mxn:
            raise ValueError(
                "PAPER_EXPLORATION_AMOUNT_MXN no puede superar MAX_ORDER_MXN."
            )
        if (
            self.paper_exploration_max_positions < 1
            or self.paper_exploration_max_positions > 100
        ):
            raise ValueError(
                "PAPER_EXPLORATION_MAX_POSITIONS debe estar entre 1 y 100."
            )
        if self.runtime_broker != "paper" and not self.live_trading:
            raise ValueError("Con LIVE_TRADING=false, RUNTIME_BROKER debe permanecer en paper.")
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
                raise ValueError(
                    "APP_PASSWORD debe configurarse explícitamente en producción."
                )
            if self.registration_enabled and (
                len(self.user_registration_code.strip()) < 12
                or self.user_registration_code == DEVELOPMENT_REGISTRATION_CODE
                or "replace-with" in self.user_registration_code.lower()
            ):
                self.registration_enabled = False
            if not self.resolved_session_cookie_secure:
                raise ValueError(
                    "Las cookies de sesión deben ser seguras en producción."
                )
            if database_url.lower().startswith("sqlite"):
                raise ValueError(
                    "DATABASE_URL debe apuntar a PostgreSQL en producción; SQLite no es persistente en Render."
                )

        return self


settings = Settings()
