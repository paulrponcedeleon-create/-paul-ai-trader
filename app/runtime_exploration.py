from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.brokers.execution import ExecutionRequest
from app.paper_trading.exploration import ExplorationConfig, PaperExplorationPolicy
from app.runtime import RuntimeEngine, RuntimeStatus


@dataclass(frozen=True)
class ExplorationExecutionDecision:
    action: str
    reason: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "confidence": 0,
            "score": 0.0,
            "source": "exploration",
            "reason": self.reason,
        }


class ExplorationStatus:
    def __init__(self, base: RuntimeStatus, exploration: dict[str, Any]) -> None:
        self._base = base
        self.exploration = exploration

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def to_public_dict(self) -> dict[str, Any]:
        payload = self._base.to_public_dict()
        payload["exploration"] = self.exploration
        return payload


class ExplorationRuntimeEngine(RuntimeEngine):
    """RuntimeEngine with bounded, simulation-only exploratory paper orders.

    Normal strategy processing always runs first. Exploration is evaluated only
    after the strategy returns HOLD and every exploratory BUY still passes through
    the existing capital reserve and Risk Engine checks.
    """

    def __init__(
        self,
        *,
        exploration_config: ExplorationConfig,
        live_trading: bool,
        **kwargs: Any,
    ) -> None:
        settings = kwargs.get("settings")
        super().__init__(**kwargs)
        self.live_trading = bool(live_trading)
        configured_max_positions = int(
            getattr(
                settings,
                "paper_exploration_max_positions",
                exploration_config.max_positions,
            )
        )
        effective_config = ExplorationConfig(
            enabled=bool(exploration_config.enabled and not self.live_trading),
            hold_cycles_before_entry=exploration_config.hold_cycles_before_entry,
            max_holding_cycles=exploration_config.max_holding_cycles,
            cooldown_cycles=exploration_config.cooldown_cycles,
            amount_mxn=exploration_config.amount_mxn,
            max_positions=configured_max_positions,
        )
        self.exploration = PaperExplorationPolicy(effective_config)
        self.last_exploration: dict[str, Any] | None = None

    @staticmethod
    def _is_exploration_position(position: dict[str, Any]) -> bool:
        signal_data = position.get("signal_data") or {}
        source = str(signal_data.get("source") or "").lower()
        reason = str(
            signal_data.get("reason")
            or signal_data.get("risk_check")
            or position.get("risk_check")
            or ""
        )
        return source == "exploration" or reason.startswith("paper_exploration_")

    @staticmethod
    def _experience_type(action: str) -> str:
        return "experience_buy" if action == "buy" else "experience_exit"

    def _set_execution_context(self, reason: str) -> None:
        setter = getattr(self.broker, "set_execution_context", None)
        if callable(setter):
            setter(source="exploration", reason=reason)

    def _exploration_payload(self) -> dict[str, Any]:
        states = self.exploration.public_state()
        attempts = sum(int(state["attempts"]) for state in states.values())
        entries = sum(int(state["entries"]) for state in states.values())
        exits = sum(int(state["exits"]) for state in states.values())
        rejected = sum(int(state["rejected"]) for state in states.values())
        capacity_blocks = sum(
            int(state["capacity_blocks"]) for state in states.values()
        )
        active = sum(1 for state in states.values() if state["active"])
        persistent_getter = getattr(self.broker, "get_exploration_metrics", None)
        persistent = persistent_getter() if callable(persistent_getter) else {}
        persisted_entries = int(persistent.get("entries", entries))
        persisted_exits = int(persistent.get("exits", exits))
        return {
            "enabled": self.exploration.config.enabled,
            "live_trading_blocked": self.live_trading,
            "hold_cycles_before_entry": self.exploration.config.hold_cycles_before_entry,
            "max_holding_cycles": self.exploration.config.max_holding_cycles,
            "cooldown_cycles": self.exploration.config.cooldown_cycles,
            "amount_mxn": float(self.exploration.config.amount_mxn),
            "max_positions": self.exploration.config.max_positions,
            "active_positions": int(persistent.get("active_positions", active)),
            "attempts": max(attempts, int(persistent.get("attempts", persisted_entries))),
            "entries": persisted_entries,
            "exits": persisted_exits,
            "completed_trades": int(
                persistent.get("completed_trades", persisted_exits)
            ),
            "wins": int(persistent.get("wins", 0)),
            "losses": int(persistent.get("losses", 0)),
            "flat": int(persistent.get("flat", 0)),
            "realized_pnl_mxn": float(persistent.get("realized_pnl_mxn", 0)),
            "rejected": rejected,
            "capacity_blocks": capacity_blocks,
            "last_experience": persistent.get("last_experience")
            or self.last_exploration,
            "states": states,
            "metrics_separate_from_strategy": True,
            "persistent": bool(persistent.get("persistent", False)),
        }

    def status(self) -> ExplorationStatus:
        return ExplorationStatus(super().status(), self._exploration_payload())

    def components(self) -> dict[str, Any]:
        payload = super().components()
        payload["exploration"] = self._exploration_payload()
        return payload

    async def _process_book(self, book: str) -> None:
        await super()._process_book(book)

        decision = self.last_decision or {}
        if decision.get("book") != book:
            return
        strategy_action = str(decision.get("action") or "hold").lower()
        positions = self.broker.get_positions()
        book_positions = [item for item in positions if item.get("book") == book]
        active_exploration_positions = sum(
            1 for item in positions if self._is_exploration_position(item)
        )
        exploration_position = any(
            self._is_exploration_position(item) for item in book_positions
        )
        proposal = self.exploration.observe(
            book=book,
            strategy_action=strategy_action,
            has_position=bool(book_positions),
            live_trading=self.live_trading,
            exploration_position=exploration_position,
            active_exploration_positions=active_exploration_positions,
        )
        if proposal is None or strategy_action != "hold":
            return

        balance = self.broker.get_balance()
        amount = proposal.amount_mxn
        reserve, deployable = self._capital_snapshot(balance)
        if proposal.action == "buy" and amount > deployable:
            reason = "Reserva de capital protegida para exploración."
            self._record_rejected_order(
                book=book,
                side="buy",
                amount_mxn=amount,
                price=Decimal(str(decision.get("price") or 0)),
                reason=reason,
            )
            self.exploration.confirm(
                book=book,
                action="buy",
                reason=proposal.reason,
                filled=False,
            )
            return

        price = Decimal(str(decision.get("price") or 0))
        if price <= 0:
            rows = self.history.get(book) or []
            if not rows:
                return
            price = Decimal(str(rows[-1].close))

        if proposal.action == "buy":
            asset_exposure = sum(
                Decimal(str(item.get("amount_mxn", item.get("invested_mxn", 0)) or 0))
                for item in book_positions
            )
            risk = self.risk_manager.evaluate_open(
                book=book,
                amount_mxn=amount,
                equity_mxn=balance.equity_mxn,
                daily_realized_pnl_mxn=Decimal(
                    str(balance.metadata.get("realized_pnl_mxn", 0))
                ),
                open_positions_count=len(positions),
                asset_exposure_mxn=asset_exposure,
                total_exposure_mxn=balance.positions_value_mxn,
            )
            if not risk.allowed:
                self._record_rejected_order(
                    book=book,
                    side="buy",
                    amount_mxn=amount,
                    price=price,
                    reason=risk.reason,
                )
                self.exploration.confirm(
                    book=book,
                    action="buy",
                    reason=proposal.reason,
                    filled=False,
                )
                self.system.events.publish(
                    "INFO",
                    "Risk",
                    "exploration",
                    risk.reason,
                    {"book": book, "amount_mxn": float(amount)},
                )
                return

        self._set_execution_context(proposal.reason)
        order = self.execution_engine.execute(
            ExecutionRequest(
                ExplorationExecutionDecision(proposal.action, proposal.reason),
                book,
                amount,
                price,
            )
        )
        filled = bool(order is not None and order.status == "filled")
        self.exploration.confirm(
            book=book,
            action=proposal.action,
            reason=proposal.reason,
            filled=filled,
        )
        experience_type = self._experience_type(proposal.action)
        self.last_exploration = {
            "book": book,
            "action": proposal.action,
            "experience_type": experience_type,
            "reason": proposal.reason,
            "amount_mxn": float(amount),
            "price": float(price),
            "status": order.status if order is not None else "not_executed",
        }
        if order is not None:
            self.last_order = {
                **order.to_public_dict(),
                "source": "exploration",
                "experience_type": experience_type,
                "reason": proposal.reason,
            }
        self.last_decision = {
            **decision,
            "exploration_action": proposal.action,
            "exploration_experience_type": experience_type,
            "exploration_reason": proposal.reason,
            "exploration_amount_mxn": float(amount),
        }
        self.system.events.publish(
            "INFO" if filled else "WARNING",
            "Paper",
            "exploration",
            "Experiencia paper procesada.",
            {
                "book": book,
                "action": proposal.action,
                "experience_type": experience_type,
                "reason": proposal.reason,
                "filled": filled,
                "amount_mxn": float(amount),
                "reserve_mxn": float(reserve),
            },
        )
