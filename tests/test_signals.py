import pytest

pytestmark = pytest.mark.unit

from app.services.indicators import price_position, range_pct
from app.services.signals import Signal, momentum_signal
from app.services.strategy import momentum_signal as compatibility_momentum_signal


def test_momentum_signal_preserves_buy_sell_hold_rules():
    assert momentum_signal(last=99, high=100, low=90, volume=1).action == "buy"
    assert momentum_signal(last=91, high=100, low=90, volume=1).action == "sell"
    assert momentum_signal(last=95, high=100, low=90, volume=1).action == "hold"
    assert momentum_signal(last=0, high=100, low=90, volume=1) == Signal(
        "hold", 0, "Datos insuficientes o inválidos.", 0
    )


def test_strategy_remains_compatibility_layer():
    assert compatibility_momentum_signal is momentum_signal


def test_indicators_match_existing_calculation():
    assert price_position(95, 100, 90) == 0.5
    assert round(range_pct(95, 100, 90), 6) == round((10 / 95) * 100, 6)
