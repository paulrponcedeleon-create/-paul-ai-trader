from app.api.routes.runtime import _with_signal_level
from app.services.signal_levels import classify_signal_level


def test_five_public_levels_cover_expected_boundaries():
    assert classify_signal_level(score=95, confidence=90, action="buy").color == "blue"
    assert classify_signal_level(score=75, confidence=75, action="buy").color == "green"
    assert classify_signal_level(score=55, confidence=65, action="hold").color == "yellow"
    assert classify_signal_level(score=40, confidence=50, action="hold").color == "orange"
    assert classify_signal_level(score=20, confidence=90, action="hold").color == "red"


def test_low_confidence_caps_a_high_score():
    result = classify_signal_level(score=95, confidence=35, action="buy")
    assert result.color == "orange"
    assert result.level == "unfavorable"


def test_sell_action_is_always_red_for_clear_exit_semantics():
    result = classify_signal_level(score=99, confidence=99, action="sell")
    assert result.color == "red"
    assert result.label == "Riesgo alto / salida"


def test_critical_penalty_overrides_score_and_confidence():
    result = classify_signal_level(
        score=100,
        confidence=100,
        action="buy",
        critical_penalty=True,
    )
    assert result.color == "red"
    assert "penalización crítica" in result.explanation


def test_fractional_confidence_is_normalized_to_percent():
    result = classify_signal_level(score=0.90, confidence=0.85, action="buy")
    assert result.color == "blue"
    assert result.score == 90
    assert result.confidence == 85


def test_missing_or_invalid_values_fail_closed():
    result = classify_signal_level(score=None, confidence="invalid", action="hold")
    assert result.color == "red"
    assert result.score == 0
    assert result.confidence == 0


def test_public_payload_is_stable_and_json_ready():
    payload = classify_signal_level(
        score=75.123,
        confidence=80.456,
        action="buy",
    ).to_public_dict()
    assert payload == {
        "level": "favorable",
        "color": "green",
        "label": "Favorable",
        "score": 75.12,
        "confidence": 80.46,
        "level_explanation": "Score y confianza son favorables, sujetos a las reglas de riesgo.",
    }


def test_runtime_decision_contract_keeps_level_with_decision():
    payload = _with_signal_level(
        {
            "action": "buy",
            "score": 88,
            "confidence": 84,
            "book": "btc_mxn",
        }
    )
    assert payload is not None
    assert payload["book"] == "btc_mxn"
    assert payload["level"] == "exceptional"
    assert payload["color"] == "blue"
    assert payload["label"] == "Oportunidad excepcional"


def test_market_endpoint_exposes_five_level_signal(client):
    assert client.post(
        "/api/login",
        json={"password": "test-password"},
    ).status_code == 200
    response = client.get("/api/market/btc_mxn")
    assert response.status_code == 200
    signal = response.json()["signal"]
    assert {"action", "score", "confidence", "level", "color", "label"}.issubset(signal)
    assert signal["color"] in {"blue", "green", "yellow", "orange", "red"}


def test_dashboard_assets_include_five_level_legend(client):
    assert client.post(
        "/api/login",
        json={"password": "test-password"},
    ).status_code == 200
    script = client.get("/static/market-panel-v2.js")
    stylesheet = client.get("/static/market-panel-v2.css")
    assert script.status_code == 200
    assert stylesheet.status_code == 200
    assert "marketSignalLegend" in script.text
    assert "level-blue" in stylesheet.text
    assert "level-orange" in stylesheet.text
