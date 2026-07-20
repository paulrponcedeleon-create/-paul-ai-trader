import pytest
from pydantic import ValidationError

from app.config import (
    DEVELOPMENT_APP_PASSWORD,
    DEVELOPMENT_SESSION_SECRET,
    EXAMPLE_APP_PASSWORD,
    EXAMPLE_SESSION_SECRET,
    Settings,
)


def test_safe_defaults_keep_live_trading_disabled():
    configured = Settings(_env_file=None)

    assert configured.app_env == "development"
    assert configured.live_trading is False
    assert configured.resolved_session_cookie_secure is False


def test_production_defaults_to_secure_cookie():
    configured = Settings(
        _env_file=None,
        app_env="production",
        app_password="production-password",
        session_secret="production-session-secret-with-at-least-32-characters",
    )

    assert configured.resolved_session_cookie_secure is True


def test_production_rejects_development_credentials():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            app_password=DEVELOPMENT_APP_PASSWORD,
            session_secret=DEVELOPMENT_SESSION_SECRET,
        )


def test_production_rejects_insecure_cookie_override():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            app_password="production-password",
            session_secret="production-session-secret-with-at-least-32-characters",
            session_cookie_secure=False,
        )


def test_samesite_none_requires_secure_cookie():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="test",
            session_cookie_samesite="none",
            session_cookie_secure=False,
        )


def test_production_rejects_example_placeholders():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            app_password=EXAMPLE_APP_PASSWORD,
            session_secret=EXAMPLE_SESSION_SECRET,
        )
