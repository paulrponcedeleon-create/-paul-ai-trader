from types import SimpleNamespace

from app.services.readiness import _check_config


def test_health_contract_remains_unchanged(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "simulation"}


def test_release_contract_does_not_expose_user_identity(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    payload = client.get("/api/release").json()

    assert set(payload) == {"release", "branch", "commit", "mode"}
    assert "user_id" not in payload
    assert "username" not in payload


def test_community_learning_is_anonymous(client):
    assert client.post("/api/login", json={"password": "test-password"}).status_code == 200

    payload = client.get("/api/learning/community").json()
    serialized = str(payload).lower()

    assert payload["privacy"] == "aggregated_without_usernames_or_trade_ids"
    assert "paul" not in serialized
    assert "username" not in serialized
    assert "user_id" not in serialized


def test_readiness_accepts_legacy_settings_without_multiuser_fields():
    checks = {}
    errors = []
    settings = SimpleNamespace(
        database_url="sqlite:///test.db",
        enabled_books_set={"btc_mxn"},
        live_trading=False,
    )

    _check_config(settings, checks, errors)

    assert errors == []
    assert checks["multiuser"] == {
        "ok": True,
        "registration_enabled": False,
        "community_learning_enabled": False,
    }
