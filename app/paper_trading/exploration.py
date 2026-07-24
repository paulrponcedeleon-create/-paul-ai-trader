from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ExplorationConfig:
    enabled: bool = True
    hold_cycles_before_entry: int = 20
    max_holding_cycles: int = 20
    cooldown_cycles: int = 40
    amount_mxn: Decimal = Decimal("10.00")

    def __post_init__(self) -> None:
        if self.hold_cycles_before_entry < 1:
            raise ValueError("hold_cycles_before_entry debe ser mayor que cero.")
        if self.max_holding_cycles < 1:
            raise ValueError("max_holding_cycles debe ser mayor que cero.")
        if self.cooldown_cycles < 0:
            raise ValueError("cooldown_cycles no puede ser negativo.")
        if self.amount_mxn <= Decimal("0"):
            raise ValueError("amount_mxn debe ser mayor que cero.")


@dataclass
class ExplorationState:
    consecutive_holds: int = 0
    holding_cycles: int = 0
    cooldown_remaining: int = 0
    active: bool = False
    entries: int = 0
    exits: int = 0
    rejected: int = 0
    last_action: str | None = None
    last_reason: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "consecutive_holds": self.consecutive_holds,
            "holding_cycles": self.holding_cycles,
            "cooldown_remaining": self.cooldown_remaining,
            "active": self.active,
            "entries": self.entries,
            "exits": self.exits,
            "rejected": self.rejected,
            "last_action": self.last_action,
            "last_reason": self.last_reason,
        }


@dataclass(frozen=True)
class ExplorationAction:
    action: str
    amount_mxn: Decimal
    reason: str


class PaperExplorationPolicy:
    """Create bounded, explicitly tagged paper experience after long HOLD streaks.

    The policy only proposes actions. Runtime and Risk Engine decide whether the
    order is allowed, and ``confirm`` mutates active/cooldown state only after the
    broker reports the result. This prevents a rejected order from being treated
    as a completed exploration.
    """

    ENTRY_REASON = "paper_exploration_hold_streak"
    EXIT_REASON = "paper_exploration_timeout"

    def __init__(self, config: ExplorationConfig | None = None) -> None:
        self.config = config or ExplorationConfig()
        self._states: dict[str, ExplorationState] = {}

    def state_for(self, book: str) -> ExplorationState:
        return self._states.setdefault(book.lower(), ExplorationState())

    def reconcile(
        self,
        *,
        book: str,
        has_position: bool,
        exploration_position: bool = False,
    ) -> None:
        state = self.state_for(book)
        if exploration_position:
            state.active = True
            return
        if state.active and not has_position:
            state.active = False
            state.holding_cycles = 0
            state.cooldown_remaining = self.config.cooldown_cycles
            state.exits += 1
            state.last_action = "sell"
            state.last_reason = "paper_exploration_external_exit"

    def observe(
        self,
        *,
        book: str,
        strategy_action: str,
        has_position: bool,
        live_trading: bool,
        exploration_position: bool = False,
    ) -> ExplorationAction | None:
        state = self.state_for(book)
        action = str(strategy_action or "hold").lower()

        if live_trading or not self.config.enabled:
            state.consecutive_holds = 0
            return None

        self.reconcile(
            book=book,
            has_position=has_position,
            exploration_position=exploration_position,
        )

        if state.cooldown_remaining > 0 and not state.active:
            state.cooldown_remaining -= 1

        if state.active:
            if not has_position:
                return None
            if action != "hold":
                state.consecutive_holds = 0
                return None
            state.holding_cycles += 1
            if state.holding_cycles >= self.config.max_holding_cycles:
                return ExplorationAction(
                    action="sell",
                    amount_mxn=self.config.amount_mxn,
                    reason=self.EXIT_REASON,
                )
            return None

        if action != "hold":
            state.consecutive_holds = 0
            return None
        if has_position or state.cooldown_remaining > 0:
            state.consecutive_holds = 0
            return None

        state.consecutive_holds += 1
        if state.consecutive_holds < self.config.hold_cycles_before_entry:
            return None

        state.consecutive_holds = 0
        return ExplorationAction(
            action="buy",
            amount_mxn=self.config.amount_mxn,
            reason=self.ENTRY_REASON,
        )

    def confirm(
        self,
        *,
        book: str,
        action: str,
        reason: str,
        filled: bool,
    ) -> None:
        state = self.state_for(book)
        state.last_action = action
        state.last_reason = reason
        if not filled:
            state.rejected += 1
            return
        if action == "buy":
            state.active = True
            state.holding_cycles = 0
            state.cooldown_remaining = 0
            state.entries += 1
        elif action == "sell":
            state.active = False
            state.holding_cycles = 0
            state.cooldown_remaining = self.config.cooldown_cycles
            state.exits += 1

    def public_state(self) -> dict[str, dict[str, Any]]:
        return {
            book: state.to_public_dict()
            for book, state in sorted(self._states.items())
        }
