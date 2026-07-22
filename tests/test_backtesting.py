from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit
from app.services.backtesting import BacktestEngine, BacktestRequest
from app.services.broker_simulator import BrokerSimulator, InsufficientFundsError
from app.services.historical_data import HistoricalCandle, HistoricalDataset
from app.services.signals import Signal


class FakeProvider:
    def __init__(self, candles):
        self.dataset = HistoricalDataset(
            book="btc_mxn",
            timeframe="1h",
            source="fake",
            start_at=candles[0].timestamp
            if candles
            else datetime(2026, 7, 1, tzinfo=timezone.utc),
            end_at=candles[-1].timestamp
            if candles
            else datetime(2026, 7, 1, tzinfo=timezone.utc),
            candles=tuple(candles),
            metadata={},
        )

    def list_datasets(self):
        return ["btc_mxn/1h/fake.csv"]

    def load_dataset(self, dataset_id):
        return self.dataset

    def get_candles(self, dataset_id, start_at=None, end_at=None):
        return list(self.dataset.candles)

    def validate_dataset(self, dataset_id):
        return None


class FakeRepository:
    def __init__(self):
        self.runs = []
        self.trades = []
        self.updated = []
        self.failed = []

    def create_run(self, **kwargs):
        row = {"id": len(self.runs) + 1, **kwargs}
        self.runs.append(row)
        return row

    def add_trade(self, **kwargs):
        self.trades.append(kwargs)
        return {"id": len(self.trades), **kwargs}

    def update_run_results(self, run_id, **kwargs):
        self.updated.append({"run_id": run_id, **kwargs})
        return self.updated[-1]

    def mark_run_failed(self, run_id):
        self.failed.append(run_id)
        return {"id": run_id, "status": "failed"}


def candles(*closes):
    base = datetime(2026, 7, 1, tzinfo=timezone.utc)
    rows = []
    for index, close in enumerate(closes):
        price = Decimal(str(close))
        rows.append(
            HistoricalCandle(
                timestamp=base + timedelta(hours=index),
                open=float(price),
                high=float(price + Decimal("1")),
                low=float(price - Decimal("1")),
                close=float(price),
                volume=1,
            )
        )
    return rows


def request(**overrides):
    values = {
        "dataset_id": "btc_mxn/1h/fake.csv",
        "strategy_name": "scripted",
        "strategy_version": "test",
        "initial_capital_mxn": Decimal("1000"),
        "trade_amount_mxn": Decimal("100"),
        "fee_rate": Decimal("0.01"),
    }
    values.update(overrides)
    return BacktestRequest(**values)


def scripted(actions):
    def strategy(window):
        index = len(window) - 1
        action = actions[index] if index < len(actions) else "hold"
        return Signal(action, 100, f"{action}-{index}", window[-1].close)

    return strategy


def run_engine(price_rows, actions, repo=None, **request_overrides):
    engine = BacktestEngine(
        historical_data_provider=FakeProvider(candles(*price_rows)),
        repository=repo,
        strategies={"scripted": scripted(actions)},
    )
    return engine.run(request(**request_overrides))


def test_same_input_produces_same_result():
    first = run_engine([100, 110, 120], ["buy", "hold", "sell"]).to_public_dict()
    second = run_engine([100, 110, 120], ["buy", "hold", "sell"]).to_public_dict()
    assert first == second


def test_no_look_ahead_bias_strategy_receives_only_past_window():
    seen = []

    def strategy(window):
        seen.append([candle.close for candle in window])
        return Signal("hold", 1, "hold", window[-1].close)

    engine = BacktestEngine(
        historical_data_provider=FakeProvider(candles(100, 200, 300)),
        strategies={"scripted": strategy},
    )
    engine.run(request())
    assert seen == [[100.0], [100.0, 200.0], [100.0, 200.0, 300.0]]


def test_one_open_position_and_close_on_sell():
    result = run_engine([100, 101, 110], ["buy", "buy", "sell"])
    assert len(result.trades) == 1
    assert result.trades[0].opened_at == candles(100)[0].timestamp


def test_buy_without_funds_is_rejected_by_broker():
    broker = BrokerSimulator(
        initial_capital_mxn=Decimal("100"), fee_rate=Decimal("0.01")
    )
    try:
        broker.buy(
            opened_at=datetime.now(timezone.utc),
            price=Decimal("10"),
            amount_mxn=Decimal("100"),
            signal_data={},
        )
        raised = False
    except InsufficientFundsError:
        raised = True
    assert raised is True
    assert broker.available_cash() == Decimal("100.00")


def test_fees_quantity_and_pnl_are_correct():
    result = run_engine([100, 120], ["buy", "sell"])
    trade = result.trades[0]
    assert trade.quantity == Decimal("1")
    assert trade.fees_mxn == Decimal("2.20")
    assert trade.pnl_mxn == Decimal("17.80")
    assert trade.return_pct == Decimal("17.6238")


def test_auto_close_at_dataset_end_and_capital_never_negative():
    result = run_engine([100, 110, 120], ["buy", "hold", "hold"])
    assert len(result.trades) == 1
    assert result.trades[0].closed_at == candles(100, 110, 120)[-1].timestamp
    assert all(point["cash_mxn"] >= 0 for point in result.metrics.equity_curve)


def test_equity_curve_and_drawdown():
    result = run_engine([100, 80, 120], ["buy", "hold", "sell"])
    assert len(result.metrics.equity_curve) == 3
    assert result.metrics.max_drawdown_pct > 0


def test_win_rate_gross_profit_loss_profit_factor_and_expectancy():
    result = run_engine(
        [100, 120, 100, 80], ["buy", "sell", "buy", "sell"], fee_rate=Decimal("0")
    )
    metrics = result.metrics
    assert metrics.trades_count == 2
    assert metrics.win_rate_pct == Decimal("50.0000")
    assert metrics.gross_profit_mxn == Decimal("20.00")
    assert metrics.gross_loss_mxn == Decimal("20.00")
    assert metrics.profit_factor == Decimal("1.0000")
    assert metrics.expectancy_mxn == Decimal("0.00")


def test_profit_factor_without_losses():
    result = run_engine([100, 120], ["buy", "sell"], fee_rate=Decimal("0"))
    assert result.metrics.profit_factor is None


def test_exposure_pct():
    result = run_engine([100, 110, 120, 130], ["hold", "buy", "hold", "sell"])
    assert result.metrics.exposure_pct == Decimal("50.0000")


def test_dataset_insufficient_and_invalid_request_and_unsupported_strategy():
    assert run_engine([100], ["hold"]).status == "failed"
    assert run_engine([100, 101], ["hold"], initial_capital_mxn=0).status == "failed"
    engine = BacktestEngine(historical_data_provider=FakeProvider(candles(100, 101)))
    result = engine.run(request(strategy_name="missing"))
    assert result.status == "failed"
    assert result.error == "Estrategia no soportada."


def test_execution_without_persistence_and_with_persistence_completed():
    assert run_engine([100, 120], ["buy", "sell"]).status == "completed"
    repo = FakeRepository()
    result = run_engine([100, 120], ["buy", "sell"], repo=repo)
    assert result.status == "completed"
    assert repo.runs[0]["status"] == "running"
    assert len(repo.trades) == 1
    assert repo.updated[0]["status"] == "completed"


def test_failed_status_is_safe_and_persisted():
    repo = FakeRepository()
    result = run_engine([100], ["hold"], repo=repo)
    assert result.status == "failed"
    assert result.error == "Datos históricos insuficientes."
    assert repo.failed == [1]


def test_simulated_orders_model_is_preserved():
    pytest.importorskip("sqlalchemy")
    from app.db.models import SimulatedOrder

    assert SimulatedOrder.__tablename__ == "simulated_orders"


def test_no_live_trading_endpoints_added():
    from pathlib import Path

    route_text = "\n".join(
        path.read_text() for path in Path("app/api/routes").glob("*.py")
    ).lower()
    allowed_read_only = route_text.replace("/market/live", "/market/read-only")
    allowed_controlled = allowed_read_only.replace("/live/", "/controlled-live/")
    assert "/live" not in allowed_controlled
    assert "bitso-live" not in route_text
    assert "/orders/live" not in route_text
