from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.services.money import (
    public_money,
    public_price,
    public_quantity,
    public_rate,
    quantize_quantity,
)
from app.services.trade_sources import MANUAL_SOURCE, public_source


class SimulatedOrder(Base):
    __tablename__ = "simulated_orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default="owner", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_position_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    amount_mxn: Mapped[Decimal] = mapped_column(Numeric(20, 2), nullable=False)
    reference_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    entry_fee_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 12), nullable=True)
    entry_fee_mxn: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    exit_fee_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 12), nullable=True)
    exit_fee_mxn: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    realized_pnl_mxn: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="simulated", index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default=MANUAL_SOURCE, index=True)
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signal_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    risk_check: Mapped[str] = mapped_column(String(255), nullable=False)

    def to_dict(self) -> dict[str, object]:
        asset_quantity = None
        if self.reference_price is not None and self.reference_price > 0:
            gross_quantity = self.amount_mxn / self.reference_price
            entry_rate = self.entry_fee_rate or Decimal("0")
            asset_quantity = quantize_quantity(gross_quantity * (Decimal("1") - entry_rate))
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "parent_position_id": self.parent_position_id,
            "status": self.status,
            "book": self.book,
            "side": self.side,
            "amount_mxn": public_money(self.amount_mxn),
            "reference_price": public_price(self.reference_price),
            "asset_quantity": public_quantity(asset_quantity),
            "close_price": public_price(self.close_price),
            "entry_fee_rate": public_rate(self.entry_fee_rate),
            "entry_fee_mxn": public_money(self.entry_fee_mxn),
            "exit_fee_rate": public_rate(self.exit_fee_rate),
            "exit_fee_mxn": public_money(self.exit_fee_mxn),
            "realized_pnl_mxn": public_money(self.realized_pnl_mxn),
            **public_source(self.source),
            "risk_check": self.risk_check,
        }


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_capital_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    final_capital_mxn: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    trades: Mapped[list["BacktestTrade"]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="BacktestTrade.opened_at")


class BacktestTrade(Base):
    __tablename__ = "backtest_trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    backtest_run_id: Mapped[int] = mapped_column(ForeignKey("backtest_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    amount_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    fees_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    signal_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    run: Mapped[BacktestRun] = relationship(back_populates="trades")


class OptimizationRun(Base):
    __tablename__ = "optimization_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    parameter_space_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    results_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results: Mapped[list["OptimizationResultRow"]] = relationship(back_populates="run", cascade="all, delete-orphan", order_by="OptimizationResultRow.composite_score.desc()")


class OptimizationResultRow(Base):
    __tablename__ = "optimization_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    optimization_run_id: Mapped[int] = mapped_column(ForeignKey("optimization_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    strategy_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    total_return_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe: Mapped[float] = mapped_column(Float, nullable=False)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    win_rate_pct: Mapped[float] = mapped_column(Float, nullable=False)
    trades_count: Mapped[int] = mapped_column(Integer, nullable=False)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    run: Mapped[OptimizationRun] = relationship(back_populates="results")


class PaperAccount(Base):
    __tablename__ = "paper_accounts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    cash_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    equity_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="stopped", index=True)


class PaperPositionRow(Base):
    __tablename__ = "paper_positions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    amount_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    realized_pnl_mxn: Mapped[float | None] = mapped_column(Float, nullable=True)


class PaperTradeRow(Base):
    __tablename__ = "paper_trades"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    position_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[float] = mapped_column(Float, nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    pnl_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    fees_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)


class PaperOrderRow(Base):
    __tablename__ = "paper_orders"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    book: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    requested_amount_mxn: Mapped[float] = mapped_column(Float, nullable=False)
    filled_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)


class AnalyticsSnapshotRow(Base):
    __tablename__ = "analytics_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")


class AnalyticsEventRow(Base):
    __tablename__ = "analytics_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
