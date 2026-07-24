import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api

from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app.config import Settings
from app.main import create_app


def test_protected_endpoint_rejects_anonymous_client(client: TestClient):
    response = client.get("/api/config")

    assert response.status_code == 401
    assert response.json() == {"detail": "Inicia sesión."}


def test_login_preserves_current_api_behavior(client: TestClient):
    login = client.post("/api/login", json={"password": "test-password"})

    assert login.status_code == 200
    assert login.json() == {"ok": True}
    assert client.get("/api/config").status_code == 200


def test_wrong_password_is_rejected(client: TestClient):
    response = client.post("/api/login", json={"password": "wrong-password"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Contraseña incorrecta."}


def test_logout_invalidates_session(client: TestClient):
    client.post("/api/login", json={"password": "test-password"})

    logout = client.post("/api/logout")

    assert logout.status_code == 200
    assert client.get("/api/config").status_code == 401


def test_local_cookie_is_http_only_lax_and_not_secure(client: TestClient):
    response = client.post("/api/login", json={"password": "test-password"})
    cookie = response.headers["set-cookie"].lower()

    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie


def test_production_cookie_is_secure(monkeypatch):
    production_settings = Settings(
        _env_file=None,
        app_env="production",
        app_password="production-password",
        session_secret="production-session-secret-with-at-least-32-characters",
        database_url="postgresql://user:password@example.com:5432/paul",
    )
    test_engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    monkeypatch.setattr("app.main.build_engine", lambda _: test_engine)
    application = create_app(production_settings)

    with TestClient(application, base_url="https://testserver") as production_client:
        response = production_client.post(
            "/api/login", json={"password": "production-password"}
        )

    cookie = response.headers["set-cookie"].lower()
    assert "secure" in cookie
    assert "httponly" in cookie


def test_tampered_session_cookie_is_rejected(test_settings: Settings):
    application = create_app(test_settings)

    # An attacker-controlled cookie without a valid SessionMiddleware signature
    # must be treated exactly like an anonymous session.
    invalid_cookie = "invalid-payload.invalid-signature"

    with TestClient(application) as tampered_client:
        tampered_client.cookies.set(
            test_settings.session_cookie_name,
            invalid_cookie,
            path="/",
        )
        response = tampered_client.get("/api/config")

    assert response.status_code == 401
    assert response.json() == {"detail": "Inicia sesión."}
