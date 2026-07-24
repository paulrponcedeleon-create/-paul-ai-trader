from __future__ import annotations

from decimal import Decimal

from app.brokers.paper import PaperBroker
from app.brokers.persistent_paper import PersistentPaperBroker
from app.paper_trading.models import PaperTrade


class ExplorationPersistentPaperBroker(PersistentPaperBroker):
    """Persistent paper broker that preserves exploration lineage on auto exits."""

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
