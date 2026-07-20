from app.services.risk import validate_order

def test_valid_order():
    assert validate_order("btc_mxn", "buy", 100, 0, 0).allowed

def test_blocks_large_order():
    assert not validate_order("btc_mxn", "buy", 999999, 0, 0).allowed

def test_blocks_bad_book():
    assert not validate_order("doge_usd", "buy", 100, 0, 0).allowed
