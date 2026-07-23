from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

pytestmark = pytest.mark.unit

from app.paper_trading import (
    PaperTradingEngine,
    PaperTradingRequest,
    PortfolioManager,
    PositionSizer,
    RiskLimits,
    RiskManager,
)
from app.reporting.paper_reports import (
    export_paper_csv,
    export_paper_json,
    export_paper_markdown,
)
from app.services.historical_data import HistoricalCandle


def candle(index: int, close: float) -> HistoricalCandle:
    return HistoricalCandle(
        datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=index),
        close - 1,
        close + 1,
        close - 2,
        close,
        10,
    )


def test_portfolio_opens_closes_tracks_pnl_fees_and_drawdown():
    portfolio = PortfolioManager(initial_cash_mxn=1000)
    position = portfolio.open_position(
        book="btc_mxn",
        price=Decimal("100"),
        amount_mxn=Decimal("100"),
        fee_rate=Decimal("0.01"),
        signal_data={"action": "buy"},
    )
    assert position is not None
    assert portfolio.cash_mxn == Decimal("899.00")
    snapshot = portfolio.snapshot({"btc_mxn": Decimal("90")})
    assert snapshot.unrealized_pnl_mxn < 0
    assert snapshot.max_drawdown_pct > 0
    trade = portfolio.close_position(
        position.id,
        price=Decimal("110"),
        fee_rate=Decimal("0.01"),
        reason="manual_close",
    )
    assert trade is not None
    assert trade.pnl_mxn == Decimal("7.90")
    assert trade.fees_mxn == Decimal("2.10")
    assert portfolio.realized_pnl_mxn == Decimal("7.90")


def test_portfolio_supports_partial_position_closes():
    portfolio = PortfolioManager(initial_cash_mxn=1000)
    position = portfolio.open_position(
        book="btc_mxn",
        price=Decimal("100"),
        amount_mxn=Decimal("200"),
        fee_rate=Decimal("0"),
    )
    assert position is not None

    trade = portfolio.close_position(
        position.id,
        price=Decimal("120"),
        fee_rate=Decimal("0"),
        reason="manual_partial_close",
        amount_mxn=Decimal("50"),
    )

    assert trade is not None
    assert trade.quantity == Decimal("0.50")
    assert trade.pnl_mxn == Decimal("10.00")
    assert portfolio.positions[position.id].amount_mxn == Decimal("150.00")
    assert portfolio.positions[position.id].quantity == Decimal("1.50")
    assert portfolio.closed_positions[-1].amount_mxn == Decimal("50.00")
    assert portfolio.closed_positions[-1].status == "closed"
    assert portfolio.realized_pnl_mxn == Decimal("10.00")


def test_position_management_stop_take_profit_trailing_and_expiration():
    portfolio = PortfolioManager(initial_cash_mxn=1000)
    stop = portfolio.open_position(
        book="btc_mxn",
        price=Decimal("100"),
        amount_mxn=Decimal("100"),
        fee_rate=Decimal("0"),
        stop_loss=Decimal("95"),
    )
    assert stop is not None
    closed = portfolio.update_market({"btc_mxn": Decimal("94")}, fee_rate=Decimal("0"))
    assert closed[0].reason == "stop_loss"

    take = portfolio.open_position(
        book="btc_mxn",
        price=Decimal("100"),
        amount_mxn=Decimal("100"),
        fee_rate=Decimal("0"),
        take_profit=Decimal("105"),
    )
    assert take is not None
    assert (
        portfolio.update_market({"btc_mxn": Decimal("106")}, fee_rate=Decimal("0"))[
            0
        ].reason
        == "take_profit"
    )

    trailing = portfolio.open_position(
        book="btc_mxn",
        price=Decimal("100"),
        amount_mxn=Decimal("100"),
        fee_rate=Decimal("0"),
        trailing_stop_pct=Decimal("5"),
    )
    assert trailing is not None
    portfolio.update_market({"btc_mxn": Decimal("120")}, fee_rate=Decimal("0"))
    assert trailing.trailing_stop_price == Decimal("114.00")
    assert (
        portfolio.update_market({"btc_mxn": Decimal("113")}, fee_rate=Decimal("0"))[
            0
        ].reason
        == "trailing_stop"
    )

    expired = portfolio.open_position(
        book="btc_mxn",
        price=Decimal("100"),
        amount_mxn=Decimal("100"),
        fee_rate=Decimal("0"),
        expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    assert expired is not None
    assert (
        portfolio.update_market({"btc_mxn": Decimal("100")}, fee_rate=Decimal("0"))[
            0
        ].reason
        == "expired"
    )


def test_risk_manager_blocks_limits_and_position_sizing_methods():
    risk = RiskManager(
        RiskLimits(
            max_risk_per_trade_pct=10,
            max_positions=1,
            max_asset_exposure_pct=20,
            max_total_exposure_pct=30,
        )
    )
    denied = risk.evaluate_open(
        book="btc_mxn",
        amount_mxn=Decimal("200"),
        equity_mxn=Decimal("1000"),
        daily_realized_pnl_mxn=Decimal("0"),
        open_positions_count=0,
        asset_exposure_mxn=Decimal("0"),
        total_exposure_mxn=Decimal("0"),
    )
    assert not denied.allowed
    max_positions = risk.evaluate_open(
        book="btc_mxn",
        amount_mxn=Decimal("50"),
        equity_mxn=Decimal("1000"),
        daily_realized_pnl_mxn=Decimal("0"),
        open_positions_count=1,
        asset_exposure_mxn=Decimal("0"),
        total_exposure_mxn=Decimal("0"),
    )
    assert not max_positions.allowed

    sizer = PositionSizer()
    assert sizer.calculate(
        method="fixed_size",
        value=100,
        equity_mxn=Decimal("1000"),
        cash_mxn=Decimal("500"),
    ) == Decimal("100.00")
    assert sizer.calculate(
        method="percentage_of_equity",
        value=10,
        equity_mxn=Decimal("1000"),
        cash_mxn=Decimal("500"),
    ) == Decimal("100.00")
    assert sizer.calculate(
        method="fixed_fractional",
        value=50,
        equity_mxn=Decimal("1000"),
        cash_mxn=Decimal("500"),
        risk_per_trade_pct=Decimal("10"),
    ) == Decimal("50.00")


def test_paper_trading_engine_uses_strategy_and_keeps_portfolio():
    portfolio = PortfolioManager(initial_cash_mxn=1000)
    engine = PaperTradingEngine(portfolio=portfolio)
    engine.start(
        PaperTradingRequest(
            account_id="acct",
            book="btc_mxn",
            strategy_name="momentum",
            parameters={"window": 2},
            sizing_value=100,
            fee_rate=0,
        )
    )
    first = engine.on_candle(candle(0, 100))
    second = engine.on_candle(candle(1, 120))
    assert second.open_positions >= first.open_positions
    assert portfolio.cash_mxn >= 0
    engine.on_candle(candle(2, 80))
    assert portfolio.snapshot({"btc_mxn": Decimal("80")}).equity_mxn >= 0
    assert engine.stop().running is False


def test_paper_reports_are_valid_json_csv_and_markdown():
    portfolio = PortfolioManager(initial_cash_mxn=1000)
    snapshot = portfolio.snapshot()
    assert json.loads(export_paper_json(snapshot))["cash_mxn"] == 1000.0
    assert "portfolio" in export_paper_csv(snapshot)
    assert "Paper Trading Report" in export_paper_markdown(snapshot)
