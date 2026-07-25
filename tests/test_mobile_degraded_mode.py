def test_mobile_redirects_to_login_without_session(client):
    response = client.get("/api/mobile", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_mobile_renders_safe_defaults_and_retry_logic(client):
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/api/mobile")

    assert response.status_code == 200
    html = response.text
    assert "Mostrando valores seguros" in html
    assert "Intento ${attempt} de 3" in html
    assert "credentials:'same-origin'" in html
    assert "location.href='/'" in html
    assert "loadWithRetry()" in html
