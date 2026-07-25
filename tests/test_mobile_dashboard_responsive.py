from pathlib import Path


def test_mobile_dashboard_navigation_is_independent_from_api_loading():
    script = Path("app/static/dashboard-v2.js").read_text(encoding="utf-8")

    assert "const REQUEST_TIMEOUT_MS = 8000" in script
    assert "document.addEventListener('click'" in script
    assert "activateTab(tab.dataset.dashboardTab" in script
    assert "panels().forEach" in script
    assert "loadTab(name)" in script
    assert "const controller = new AbortController()" in script
    assert "controller.abort()" in script
    assert "La pantalla sigue disponible" in script


def test_mobile_dashboard_keeps_learning_metrics_and_lazy_loading():
    script = Path("app/static/dashboard-v2.js").read_text(encoding="utf-8")

    assert "if (!endpoints[name]) return null" in script
    assert "Experiencia exploratoria" in script
    assert "Experiencias activas" in script
    assert "Operaciones cerradas aprendidas" in script
    assert "loadedTabs" in script
    assert "if (name === 'paper')" in script
    assert "if (name === 'strategies')" in script
    assert "if (name === 'validation')" in script
    assert "if (name === 'system')" in script
