import pytest

pytestmark = pytest.mark.unit

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.reporting.backtest_reports import export_csv, export_json, export_markdown
from app.services import indicators
from app.services.backtesting import BacktestEngine, BacktestRequest
from app.services.historical_data import HistoricalCandle, HistoricalDataset
from app.services.walk_forward import WalkForwardEngine, WalkForwardRequest
from app.strategies import StrategyFactory, strategy_registry
from app.strategies.builtins import MomentumStrategy


class FakeProvider:
    def __init__(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        candles = []
        for index in range(60):
            price = 100 + index
            candles.append(
                HistoricalCandle(
                    base + timedelta(days=index), price, price + 2, price - 2, price, 10
                )
            )
        self.dataset = HistoricalDataset(
            "btc_mxn",
            "1d",
            "fake",
            candles[0].timestamp,
            candles[-1].timestamp,
            tuple(candles),
            {},
        )

    def list_datasets(self):
        return ["btc_mxn/1d/fake.csv"]

    def load_dataset(self, dataset_id):
        return self.dataset

    def get_candles(self, dataset_id, start_at=None, end_at=None):
        return list(self.dataset.candles)

    def validate_dataset(self, dataset_id):
        return None


def test_strategy_registry_and_factory():
    names = {item["name"] for item in strategy_registry.list()}
    assert {
        "momentum",
        "rsi",
        "ema_cross",
        "macd",
        "bollinger",
        "mean_reversion",
        "breakout",
    } <= names
    assert strategy_registry.exists("momentum")
    strategy = StrategyFactory().create("momentum", "1.0", {"window": 5})
    assert isinstance(strategy, MomentumStrategy)
    assert strategy.parameters["window"] == 5


def test_indicators_library():
    values = [float(i) for i in range(1, 40)]
    highs = [value + 1 for value in values]
    lows = [value - 1 for value in values]
    volumes = [10.0 for _ in values]
    assert indicators.sma(values, 3) == 38.0
    assert indicators.rolling_mean(values, 3) == 38.0
    assert indicators.rolling_std(values, 3) is not None
    assert indicators.ema(values, 5) is not None
    assert indicators.rsi(values, 14) == 100.0
    assert indicators.macd(values) is not None
    assert indicators.atr(highs, lows, values) is not None
    assert indicators.bollinger_bands(values) is not None
    assert indicators.vwap(highs, lows, values, volumes) is not None
    assert indicators.stochastic(highs, lows, values) is not None
    assert indicators.highest_high(highs, 5) == highs[-1]
    assert indicators.lowest_low(lows, 5) == lows[-5]


def test_backtest_engine_uses_strategy_factory_without_momentum_dependency():
    result = BacktestEngine(historical_data_provider=FakeProvider()).run(
        BacktestRequest(
            dataset_id="btc_mxn/1d/fake.csv",
            strategy_name="momentum",
            strategy_version="1.0",
            initial_capital_mxn=Decimal("1000"),
            trade_amount_mxn=Decimal("100"),
            fee_rate=Decimal("0"),
            parameters={"window": 5},
        )
    )
    assert result.status == "completed"


def test_walk_forward_uses_backtest_engine():
    engine = BacktestEngine(historical_data_provider=FakeProvider())
    report = WalkForwardEngine(engine).run(
        WalkForwardRequest(
            dataset_id="btc_mxn/1d/fake.csv",
            strategy_name="momentum",
            strategy_version="1.0",
            initial_capital_mxn=1000,
            trade_amount_mxn=100,
            fee_rate=0,
            training_window_days=10,
            validation_window_days=10,
            start_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
            parameters={"window": 5},
        )
    )
    assert report.consolidated["segments"] > 0


def test_report_exporters():
    result = BacktestEngine(historical_data_provider=FakeProvider()).run(
        BacktestRequest(
            "btc_mxn/1d/fake.csv",
            "momentum",
            "1.0",
            1000,
            100,
            0,
            parameters={"window": 5},
        )
    )
    assert "executive_summary" in export_json(result)
    assert "summary" in export_csv(result)
    assert "# Backtest Report" in export_markdown(result)


def test_api_routes_are_declared_without_ui_routes():
    from pathlib import Path

    text = Path("app/api/routes/pro_strategy.py").read_text()
    for path in [
        "/strategies",
        "/strategies/{name}",
        "/backtests",
        "/backtests/{run_id}",
        "/walk-forward",
    ]:
        assert path in text
