import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

pytestmark = pytest.mark.api

from app.db.base import Base


def test_health_behavior_preserved(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "simulation"}


def test_ready_reports_not_ready_without_creating_data_dir(client, tmp_path):
    data_dir = tmp_path / "missing-data"
    client.app.state.settings.paul_data_dir = str(data_dir)
    alias = client.get("/readiness")
    assert alias.status_code == 503
    response = client.get("/ready")
    assert response.status_code == 503
    assert not data_dir.exists()
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["mode"] == "simulation"
    assert "PAUL_DATA_DIR no está disponible." in body["errors"]


def test_ready_success_with_data_dir_and_required_tables(client, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    client.app.state.settings.paul_data_dir = str(data_dir)
    assert client.get("/readiness").status_code == 200
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_uses_safe_public_errors(client, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    client.app.state.settings.paul_data_dir = str(data_dir)
    Base.metadata.drop_all(bind=client.app.state.db_engine)
    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert "errors" in body
    assert "no such table" not in str(body).lower()
