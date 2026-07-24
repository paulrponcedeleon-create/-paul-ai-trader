import pytest

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from pydantic import ValidationError

from app.config import Settings


def test_exploration_defaults_are_active_only_for_paper_simulation():
    simulation = Settings(_env_file=None, app_env="test", live_trading=False)
    live = Settings(_env_file=None, app_env="test", live_trading=True)

    assert simulation.paper_exploration_active is True
    assert live.paper_exploration_active is False


def test_exploration_amount_cannot_exceed_order_limit():
    with pytest.raises(ValidationError, match="PAPER_EXPLORATION_AMOUNT_MXN"):
        Settings(
            _env_file=None,
            app_env="test",
            max_order_mxn=5,
            paper_exploration_amount_mxn=10,
        )


def test_exploration_cycle_limits_are_validated():
    with pytest.raises(ValidationError, match="PAPER_EXPLORATION_HOLD_CYCLES"):
        Settings(
            _env_file=None,
            app_env="test",
            paper_exploration_hold_cycles=0,
        )
    with pytest.raises(
        ValidationError,
        match="PAPER_EXPLORATION_MAX_HOLDING_CYCLES",
    ):
        Settings(
            _env_file=None,
            app_env="test",
            paper_exploration_max_holding_cycles=0,
        )
