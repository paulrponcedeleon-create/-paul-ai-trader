from decimal import Decimal

import pytest

from app.paper_trading.exploration import (
    ExplorationConfig,
    PaperExplorationPolicy,
)


def _observe(policy, book="btc_mxn", *, has_position=False, live=False):
    return policy.observe(
        book=book,
        strategy_action="hold",
        has_position=has_position,
        live_trading=live,
        exploration_position=policy.state_for(book).active,
    )


def test_hold_streak_proposes_one_small_paper_entry_and_waits_for_confirmation():
    policy = PaperExplorationPolicy(
        ExplorationConfig(
            hold_cycles_before_entry=3,
            max_holding_cycles=2,
            cooldown_cycles=4,
            amount_mxn=Decimal("10.00"),
        )
    )

    assert _observe(policy) is None
    assert _observe(policy) is None
    action = _observe(policy)

    assert action is not None
    assert action.action == "buy"
    assert action.amount_mxn == Decimal("10.00")
    assert action.reason == "paper_exploration_hold_streak"
    assert policy.state_for("btc_mxn").active is False

    policy.confirm(
        book="btc_mxn",
        action="buy",
        reason=action.reason,
        filled=True,
    )
    assert policy.state_for("btc_mxn").active is True
    assert policy.state_for("btc_mxn").entries == 1


def test_active_exploration_closes_after_bounded_holding_cycles():
    policy = PaperExplorationPolicy(
        ExplorationConfig(
            hold_cycles_before_entry=1,
            max_holding_cycles=2,
            cooldown_cycles=3,
            amount_mxn=Decimal("10.00"),
        )
    )
    entry = _observe(policy, book="eth_mxn")
    policy.confirm(
        book="eth_mxn",
        action="buy",
        reason=entry.reason,
        filled=True,
    )

    assert _observe(policy, book="eth_mxn", has_position=True) is None
    action = _observe(policy, book="eth_mxn", has_position=True)

    assert action is not None
    assert action.action == "sell"
    assert action.reason == "paper_exploration_timeout"
    assert policy.state_for("eth_mxn").active is True

    policy.confirm(
        book="eth_mxn",
        action="sell",
        reason=action.reason,
        filled=True,
    )
    state = policy.state_for("eth_mxn")
    assert state.active is False
    assert state.exits == 1
    assert state.cooldown_remaining == 3


def test_rejected_entry_does_not_create_a_fake_active_exploration():
    policy = PaperExplorationPolicy(ExplorationConfig(hold_cycles_before_entry=1))
    action = _observe(policy)

    policy.confirm(
        book="btc_mxn",
        action="buy",
        reason=action.reason,
        filled=False,
    )

    state = policy.state_for("btc_mxn")
    assert state.active is False
    assert state.entries == 0
    assert state.rejected == 1


def test_exploration_never_runs_in_live_mode():
    policy = PaperExplorationPolicy(ExplorationConfig(hold_cycles_before_entry=1))

    action = _observe(policy, live=True)

    assert action is None
    assert policy.state_for("btc_mxn").active is False


def test_real_strategy_decision_resets_hold_streak():
    policy = PaperExplorationPolicy(ExplorationConfig(hold_cycles_before_entry=2))
    assert _observe(policy, book="sol_mxn") is None
    assert policy.observe(
        book="sol_mxn",
        strategy_action="buy",
        has_position=False,
        live_trading=False,
    ) is None
    assert _observe(policy, book="sol_mxn") is None


@pytest.mark.parametrize(
    "config",
    [
        ExplorationConfig,
    ],
)
def test_config_class_is_importable(config):
    assert config is ExplorationConfig


def test_invalid_exploration_config_is_rejected():
    with pytest.raises(ValueError):
        ExplorationConfig(hold_cycles_before_entry=0)
    with pytest.raises(ValueError):
        ExplorationConfig(max_holding_cycles=0)
    with pytest.raises(ValueError):
        ExplorationConfig(cooldown_cycles=-1)
    with pytest.raises(ValueError):
        ExplorationConfig(amount_mxn=Decimal("0"))
