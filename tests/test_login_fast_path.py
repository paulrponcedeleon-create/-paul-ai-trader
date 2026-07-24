from contextlib import contextmanager


def test_owner_login_does_not_wait_for_database(client):
    @contextmanager
    def unavailable_database():
        raise RuntimeError("database unavailable")
        yield

    client.app.state.db_session_factory = unavailable_database

    response = client.post(
        "/api/login",
        json={"username": "paul", "password": "test-password"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert client.cookies.get(client.app.state.settings.session_cookie_name)


def test_family_login_reports_database_unavailable(client):
    @contextmanager
    def unavailable_database():
        raise RuntimeError("database unavailable")
        yield

    client.app.state.db_session_factory = unavailable_database

    response = client.post(
        "/api/login",
        json={"username": "papa", "password": "password-papa"},
    )

    assert response.status_code == 503
    assert "base de datos" in response.json()["detail"].lower()
