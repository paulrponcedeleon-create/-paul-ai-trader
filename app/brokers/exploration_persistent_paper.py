from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.brokers.paper import PaperBroker
from app.brokers.persistent_paper import PersistentPaperBroker
from app.paper_trading.models import PaperTrade
from app.repositories.order_events import SqlSimulatedOrderEventRepository
from app.repositories.simulated_orders import SqlSimulatedOrderRepository
from app.services.money import public_money, quantize_money


class ExplorationPersistentPaperBroker(PersistentPaperBroker):
    """Persistent paper broker that preserves and summarizes exploration lineage."""

    def get_exploration_metrics(self) -> dict[str, Any]:
        with self.session_factory() as session:
            event_repository = SqlSimulatedOrderEventRepository(session)
            order_repository = SqlSimulatedOrderRepository(session)
            entries = event_repository.count(source="exploration", side="buy")
            exits = event_repository.count(source="exploration", side="sell")
            latest_rows = event_repository.list(limit=1, source="exploration")
            active = sum(
                1
                for row in order_repository.list_open()
                if str(row.get("risk_check") or "").startswith(
                    "paper_exploration_"
                )
            )
            closed_events: list[dict[str, Any]] = []
            offset = 0
            while True:
                batch = event_repository.list(
                    limit=500,
                    offset=offset,
                    source="exploration",
                    side="sell",
                )
                closed_events.extend(batch)
                if len(batch) < 500:
                    break
                offset += len(batch)

        wins = losses = flat = 0
        realized_pnl = Decimal("0")
        for event in closed_events:
            pnl = Decimal(str(event.get("realized_pnl_mxn") or 0))
            realized_pnl += pnl
            if pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            else:
                flat += 1

        latest = latest_rows[0] if latest_rows else None
        if latest is not None:
            latest = {
                **latest,
                "experience_type": (
                    "experience_buy"
                    if str(latest.get("side") or "").lower() == "buy"
                    else "experience_exit"
                ),
            }
        return {
            "attempts": entries,
            "entries": entries,
            "exits": exits,
            "completed_trades": exits,
            "wins": wins,
            "losses": losses,
            "flat": flat,
            "realized_pnl_mxn": public_money(quantize_money(realized_pnl)),
            "events": entries + exits,
            "active_positions": active,
            "last_experience": latest,
            "persistent": True,
        }

    def update_market(self, book: str, price: Decimal) -> list[PaperTrade]:
        self._sync_from_database()
        exploration_position_ids = {
            position.id
            for position in self.engine.portfolio.positions.values()
            if str((position.signal_data or {}).get("source") or "").lower()
            == "exploration"
            or str((position.signal_data or {}).get("reason") or "").startswith(
                "paper_exploration_"
            )
        }
        closed = PaperBroker.update_market(self, book, price)
        for trade in closed:
            source = (
                "exploration"
                if trade.position_id in exploration_position_ids
                else "automatic_exit"
            )
            self._persist_closed_trade(trade, source=source)
        return closed
