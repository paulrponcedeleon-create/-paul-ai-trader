def test_dashboard_exposes_complete_autonomous_experience_metrics(client):
    response = client.get("/static/dashboard-v2.js")

    assert response.status_code == 200
    assert "Experiencias activas" in response.text
    assert "Intentos exploratorios" in response.text
    assert "Operaciones completas" in response.text
    assert "ganadas" in response.text
    assert "perdidas" in response.text
    assert "P&L exploratorio" in response.text
