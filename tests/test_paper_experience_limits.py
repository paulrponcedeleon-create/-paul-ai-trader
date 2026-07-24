from decimal import Decimal

import pytest

from app.paper_trading.exploration import ExplorationConfig, PaperExplorationPolicy


def test_global_capacity_blocks_new_experience_without_losing_hold_streak():
    policy = PaperExplorationPolicy(
        ExplorationConfig(
            hold_cycles_before_entry=1,
            max_holding_cycles=2,
            cooldown_cycles=1,
            amount_mxn=Decimal("10.00"),
            max_positions=1,
        )
    )

    blocked = policy.observe(
        book="btc_mxn",
        strategy_action="hold",
        has_position=False,
        live_trading=False,
        active_exploration_positions=1,
    )

    assert blocked is None
    state = policy.state_for("btc_mxn")
    assert state.capacity_blocks == 1
    assert state.consecutive_holds == 1
    assert state.last_reason == "paper_exploration_global_limit"

    proposal = policy.observe(
        book="btc_mxn",
        strategy_action="hold",
        has_position=False,
        live_trading=False,
        active_exploration_positions=0,
    )
    assert proposal is not None
    assert proposal.action == "buy"

    policy.confirm(
        book="btc_mxn",
        action="buy",
        reason=proposal.reason,
        filled=True,
    )
    assert state.attempts == 1
    assert state.entries == 1


def test_exploration_max_positions_must_be_positive():
    with pytest.raises(ValueError, match="max_positions"):
        ExplorationConfig(max_positions=0)
