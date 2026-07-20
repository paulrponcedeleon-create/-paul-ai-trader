from app.risk import validate_order

def test_rejects_large_order():
    assert not validate_order("btc_mxn", "buy", 999999, 0, 0, True).allowed

def test_requires_approval():
    assert not validate_order("btc_mxn", "buy", 100, 0, 0, False).allowed
