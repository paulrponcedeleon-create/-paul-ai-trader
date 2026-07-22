from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_market_ui_restores_type_and_signal_filters():
    javascript = (ROOT / "app/static/market-catalog.js").read_text(encoding="utf-8")

    for expected in (
        'data-type-filter="all"',
        'data-type-filter="markets"',
        'data-type-filter="stocks"',
        'data-signal-filter="buy"',
        'data-signal-filter="hold"',
        'data-signal-filter="sell"',
    ):
        assert expected in javascript

    assert (
        "catalog.filter(item => typeMatches(item) && signalMatches(item))" in javascript
    )
    assert "catalog.map(item" in javascript


def test_market_signal_colors_override_generic_active_button_style():
    css = (ROOT / "app/static/markets.css").read_text(encoding="utf-8")

    assert ".book.market-book.signal-buy.active" in css
    assert "background: #ecfdf3 !important" in css
    assert ".book.market-book.signal-hold.active" in css
    assert "background: #eff8ff !important" in css
    assert ".book.market-book.signal-sell.active" in css
    assert "background: #fef3f2 !important" in css
