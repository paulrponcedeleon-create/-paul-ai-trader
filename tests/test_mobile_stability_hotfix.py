import pytest

pytest.importorskip("fastapi")

pytestmark = pytest.mark.api


def test_dashboard_forces_new_mobile_assets(client):
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/")

    assert response.status_code == 200
    assert "/static/mobile-stability.js?v=20260725-1" in response.text
    assert "/static/dashboard-v2.js?v=20260725-1" in response.text
    assert "/static/app.js?v=20260725-1" in response.text
    assert response.text.index("mobile-stability.js") < response.text.index("app.js")


def test_mobile_stability_keeps_tabs_interactive_and_limits_requests(client):
    response = client.get("/static/mobile-stability.js")

    assert response.status_code == 200
    script = response.text
    assert "MAX_CONCURRENT = 2" in script
    assert "REQUEST_TIMEOUT_MS = 8000" in script
    assert "RESPONSE_CACHE_MS = 15000" in script
    assert "[data-dashboard-tab]" in script
    assert "touchend" in script
    assert "switchTab(tab.dataset.dashboardTab)" in script
    assert "Este módulo se carga al abrir su pestaña" in script
    assert "response.clone()" in script


def test_login_page_does_not_publish_owner_account_label(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "La cuenta principal continúa siendo" not in response.text
    assert "Ingresa tu usuario y contraseña." in response.text
