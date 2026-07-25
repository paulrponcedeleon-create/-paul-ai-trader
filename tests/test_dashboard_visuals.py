def test_dashboard_renders_verified_assets_filters_and_controlled_refresh(client):
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "/static/market-panel-v2.css" in html
    assert "/static/market-panel-v2.js" in html
    assert 'id="marketFiltersV2"' in html
    assert ">Cripto<" in html
    assert ">Comprar<" in html
    assert ">Mantener<" in html
    assert ">Vender si tienes<" in html
    assert 'id="refreshBtn"' not in html
    assert "Actualización bajo demanda" in html

    market_html = html.split('id="marketGridV2"', 1)[1].split('id="marketResult"', 1)[0]
    expected = [
        ">BTC<",
        ">ETH<",
        ">SOL<",
        ">USDT<",
        ">XRP<",
        ">ALGN<",
        ">TSLA<",
        ">AAPL<",
    ]
    positions = [market_html.index(symbol) for symbol in expected]
    assert positions == sorted(positions)
    for removed in (">ATOM<", ">MXN<", ">USD<", ">PAXG<", ">PSTG<"):
        assert removed not in market_html


def test_new_visual_assets_define_full_card_portfolio_colors_and_refresh_intervals(
    client,
):
    css = client.get("/static/market-panel-v2.css")
    javascript = client.get("/static/market-panel-v2.js")

    assert css.status_code == 200
    assert javascript.status_code == 200
    assert ".market-book-v2.signal-buy" in css.text
    assert ".market-book-v2.signal-hold" in css.text
    assert ".market-book-v2.signal-sell" in css.text
    assert ".position-row:has(.compact-result .negative)" in css.text
    assert ".position-row:has(.compact-result .positive)" in css.text
    assert "marketFiltersV2" in javascript.text
    assert "marketGridV2" in javascript.text
    assert "const CRYPTO_REFRESH_MS = 15000" in javascript.text
    assert "const STOCK_REFRESH_MS = 60000" in javascript.text
    assert "const CARD_AGE_REFRESH_MS = 5000" in javascript.text
    assert "refreshBtn" not in javascript.text


def test_dashboard_refresh_uses_null_safe_dom_updates(client):
    javascript = client.get("/static/dashboard-v2.js")

    assert javascript.status_code == 200
    assert "const setText = (selector, value)" in javascript.text
    assert "if (node) node.textContent = value" in javascript.text
    assert "if (!endpoints[name]) return null" in javascript.text
