import pytest

pytestmark = pytest.mark.integration

from datetime import datetime, timedelta, timezone
import csv
import json

from app.reporting.backtest_reports import export_csv, export_json, export_markdown
from app.services.backtesting import BacktestEngine, BacktestRequest
from app.services.historical_data import LocalCsvHistoricalDataProvider
from app.services.walk_forward import WalkForwardEngine, WalkForwardRequest


def _write_dataset(tmp_path):
    path = tmp_path / "data" / "historical" / "btc_mxn" / "1d" / "rc1.csv"
    path.parent.mkdir(parents=True)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for index in range(80):
            price = 100 + index + (index % 7)
            timestamp = start + timedelta(days=index)
            writer.writerow(
                [timestamp.isoformat(), price, price + 3, price - 3, price, 10 + index]
            )
    return "btc_mxn/1d/rc1.csv", path


class LocalSettings:
    app_name = "Paul AI Trader"
    app_env = "test"
    app_password = "test-password"
    session_secret = "test-session-secret-with-more-than-32-characters"
    session_cookie_secure = False
    live_trading = False
    allowed_books_set = {"btc_mxn"}
    max_order_mxn = 500.0
    simulated_initial_capital_mxn = 5000.0

    def __init__(self, tmp_path):
        self.resolved_paul_data_dir = (tmp_path / "data").resolve()
        self.paul_data_dir = str(tmp_path / "data")
        self.database_url = f"sqlite:///{tmp_path / 'rc1.db'}"


def _settings(tmp_path):
    return LocalSettings(tmp_path)


@pytest.mark.unit
def test_rc1_pure_e2e_csv_strategies_backtest_and_reports(tmp_path):
    dataset_id, _ = _write_dataset(tmp_path)
    provider = LocalCsvHistoricalDataProvider(_settings(tmp_path))
    payloads = []
    for strategy_name, parameters in [
        ("momentum", {"window": 5}),
        ("rsi", {"period": 14, "oversold": 30, "overbought": 70}),
        ("ema_cross", {"fast": 5, "slow": 12}),
    ]:
        request = BacktestRequest(
            dataset_id,
            strategy_name,
            "1.0",
            1000,
            100,
            0.001,
            parameters=parameters,
        )
        first = BacktestEngine(historical_data_provider=provider).run(request)
        second = BacktestEngine(historical_data_provider=provider).run(request)
        first_payload = first.to_public_dict()
        assert first.status == "completed"
        assert first_payload == second.to_public_dict()
        assert first.metrics.equity_curve == tuple(
            sorted(first.metrics.equity_curve, key=lambda point: point["timestamp"])
        )
        assert all(point["cash_mxn"] >= 0 for point in first.metrics.equity_curve)
        assert all(trade.fees_mxn >= 0 for trade in first.trades)
        assert export_json(first)
        assert export_csv(first)
        assert export_markdown(first)
        json.loads(export_json(first))
        payloads.append(first_payload)
    assert len(payloads) == 3


@pytest.mark.database
def test_rc1_end_to_end_csv_strategy_backtest_repository_and_reports(tmp_path):
    pytest.importorskip("sqlalchemy")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db.base import Base
    from app.repositories.backtests import BacktestRepository

    dataset_id, _ = _write_dataset(tmp_path)
    settings = _settings(tmp_path)
    provider = LocalCsvHistoricalDataProvider(settings)
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    first_payloads = []
    second_payloads = []
    with Session() as session:
        repository = BacktestRepository(session)
        backtest_engine = BacktestEngine(
            historical_data_provider=provider, repository=repository
        )
        for strategy_name, parameters in [
            ("momentum", {"window": 5}),
            ("rsi", {"period": 14, "oversold": 30, "overbought": 70}),
            ("ema_cross", {"fast": 5, "slow": 12}),
        ]:
            request = BacktestRequest(
                dataset_id,
                strategy_name,
                "1.0",
                1000,
                100,
                0.001,
                parameters=parameters,
            )
            first = backtest_engine.run(request)
            second = BacktestEngine(historical_data_provider=provider).run(request)
            first_payloads.append(first.to_public_dict())
            second_payloads.append(second.to_public_dict())
            assert first.status == "completed"
            assert all(point["cash_mxn"] >= 0 for point in first.metrics.equity_curve)
            assert export_json(first)
            assert export_csv(first)
            assert export_markdown(first)
            json.loads(export_json(first))
        session.commit()
        assert repository.list_runs()
        assert repository.get_run_with_trades(1)
    assert (
        first_payloads[1]["metrics"]["equity_curve"]
        == second_payloads[1]["metrics"]["equity_curve"]
    )


@pytest.mark.api
def test_rc1_fastapi_strategy_backtest_walk_forward_and_openapi(tmp_path, fake_bitso):
    pytest.importorskip("fastapi")
    pytest.importorskip("sqlalchemy")
    from fastapi.testclient import TestClient
    from app.main import create_app

    dataset_id, _ = _write_dataset(tmp_path)
    app = create_app(_settings(tmp_path), fake_bitso)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 200
        strategies = client.get("/strategies")
        assert strategies.status_code == 200
        assert client.get("/strategies/momentum").status_code == 200
        payload = {
            "dataset_id": dataset_id,
            "strategy_name": "momentum",
            "strategy_version": "1.0",
            "initial_capital_mxn": 1000,
            "trade_amount_mxn": 100,
            "fee_rate": 0.001,
            "parameters": {"window": 5},
        }
        created = client.post("/backtests", json=payload)
        assert created.status_code == 200
        listed = client.get("/backtests")
        assert listed.status_code == 200
        run_id = listed.json()["items"][0]["id"]
        assert client.get(f"/backtests/{run_id}").status_code == 200
        walk_payload = {
            **payload,
            "start_at": "2026-01-01T00:00:00+00:00",
            "end_at": "2026-03-01T00:00:00+00:00",
            "training_window_days": 20,
            "validation_window_days": 10,
            "mode": "rolling",
        }
        assert client.post("/walk-forward", json=walk_payload).status_code == 200
        assert client.get("/openapi.json").status_code == 200
        assert client.delete(f"/backtests/{run_id}").status_code == 200


@pytest.mark.unit
def test_rc1_walk_forward_rolling_and_anchored_are_deterministic(tmp_path):
    dataset_id, _ = _write_dataset(tmp_path)
    provider = LocalCsvHistoricalDataProvider(_settings(tmp_path))
    engine = BacktestEngine(historical_data_provider=provider)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 3, 1, tzinfo=timezone.utc)
    base = dict(
        dataset_id=dataset_id,
        strategy_name="momentum",
        strategy_version="1.0",
        initial_capital_mxn=1000,
        trade_amount_mxn=100,
        fee_rate=0.001,
        training_window_days=20,
        validation_window_days=10,
        start_at=start,
        end_at=end,
        parameters={"window": 5},
    )
    rolling = WalkForwardEngine(engine).run(WalkForwardRequest(**base, mode="rolling"))
    anchored = WalkForwardEngine(engine).run(
        WalkForwardRequest(**base, mode="anchored")
    )
    rolling_again = WalkForwardEngine(engine).run(
        WalkForwardRequest(**base, mode="rolling")
    )
    assert rolling.consolidated == rolling_again.consolidated
    assert rolling.segments[0].training_start < rolling.segments[0].validation_start
    assert anchored.segments[0].training_start == start
