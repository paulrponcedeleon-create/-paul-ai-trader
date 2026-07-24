from decimal import Decimal

from app.brokers.exploration_persistent_paper import ExplorationPersistentPaperBroker
from app.repositories.order_events import SqlSimulatedOrderEventRepository


def test_automatic_exit_from_exploration_keeps_exploration_source(client):
    broker = ExplorationPersistentPaperBroker(
        session_factory=client.app.state.db_session_factory,
        settings=client.app.state.settings,
    )
    broker.connect()
    broker.set_execution_context(
        source="exploration",
        reason="paper_exploration_hold_streak",
    )

    opened = broker.place_market_buy(
        book="btc_mxn",
        amount_mxn=Decimal("10.00"),
        price=Decimal("100.00"),
    )
    closed = broker.update_market("btc_mxn", Decimal("96.00"))

    assert opened.status == "filled"
    assert len(closed) == 1
    metrics = broker.get_exploration_metrics()
    assert metrics["entries"] == 1
    assert metrics["exits"] == 1

    with client.app.state.db_session_factory() as session:
        events = SqlSimulatedOrderEventRepository(session).list(
            limit=10,
            source="exploration",
        )
    assert [event["side"] for event in events] == ["sell", "buy"]
    assert events[0]["reason"] in {
        "stop_loss",
        "take_profit",
        "trailing_stop",
    }
