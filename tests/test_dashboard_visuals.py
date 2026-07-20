def test_dashboard_renders_fixed_asset_order_filters_and_new_assets(client):
    client.post("/api/login", json={"password": "test-password"})

    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "/static/market-panel-v2.css" in html
    assert "/static/market-panel-v2.js" in html
    assert 'id="marketFiltersV2"' in html
    assert "Cripto y monedas" in html
    assert ">Comprar<" in html
    assert ">Mantener<" in html
    assert ">Vender<" in html

    expected = [
        ">BTC<",
        ">ETH<",
        ">SOL<",
        ">ATOM<",
        ">MXN<",
        ">USD<",
        ">USDT<",
        ">PAXG<",
        ">XRP<",
        ">ALGN<",
        ">PSTG<",
        ">TSLA<",
        ">AAPL<",
    ]
    positions = [html.index(symbol) for symbol in expected]
    assert positions == sorted(positions)
    assert "AAPL_MXN" not in html
    assert "ALGN_MXN" not in html


def test_new_visual_assets_define_full_card_and_portfolio_colors(client):
    css = client.get("/static/market-panel-v2.css")
    javascript = client.get("/static/market-panel-v2.js")

    assert css.status_code == 200
    assert javascript.status_code == 200
    assert ".market-book-v2.signal-buy" in css.text
    assert ".market-book-v2.signal-hold" in css.text
    assert ".market-book-v2.signal-sell" in css.text
    assert ".position-row:has(.compact-result .negative)" in css.text
    assert ".position-row:has(.compact-result .positive)" in css.text
    assert 'data-type-filter="stocks"' not in javascript.text
    assert "marketFiltersV2" in javascript.text
