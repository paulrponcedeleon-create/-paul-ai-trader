from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from app.optimization.ranking import RankingEngine
from app.services import indicators
from app.services.backtest_metrics import to_decimal
from app.services.signals import Signal

DecisionAction = Literal["buy", "sell", "hold"]
MarketRegime = Literal["bull", "bear", "sideways", "high_volatility", "low_volatility"]


@dataclass(frozen=True)
class StrategySignalInput:
    strategy_name: str
    signal: Signal
    weight: Decimal | int | float | str = Decimal("1")


@dataclass(frozen=True)
class HistoricalMetricsInput:
    total_return_pct: Decimal | int | float | str = Decimal("0")
    max_drawdown_pct: Decimal | int | float | str = Decimal("0")
    sharpe: Decimal | int | float | str = Decimal("0")
    profit_factor: Decimal | int | float | str | None = None
    win_rate_pct: Decimal | int | float | str = Decimal("0")
    stability_pct: Decimal | int | float | str = Decimal("50")


@dataclass(frozen=True)
class PaperPortfolioInput:
    equity_mxn: Decimal | int | float | str
    cash_mxn: Decimal | int | float | str
    realized_pnl_mxn: Decimal | int | float | str = Decimal("0")
    unrealized_pnl_mxn: Decimal | int | float | str = Decimal("0")
    max_drawdown_pct: Decimal | int | float | str = Decimal("0")
    open_positions: int = 0


@dataclass(frozen=True)
class IndicatorInput:
    closes: tuple[float, ...] = tuple()
    highs: tuple[float, ...] = tuple()
    lows: tuple[float, ...] = tuple()
    volumes: tuple[float, ...] = tuple()
    current: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class DecisionRequest:
    strategy_signals: tuple[StrategySignalInput, ...]
    optimization_results: tuple[Any, ...] = tuple()
    historical_metrics: HistoricalMetricsInput = field(
        default_factory=HistoricalMetricsInput
    )
    paper_portfolio: PaperPortfolioInput | None = None
    indicators: IndicatorInput = field(default_factory=IndicatorInput)


@dataclass(frozen=True)
class DecisionExplanation:
    strategies_for: tuple[str, ...]
    strategies_against: tuple[str, ...]
    risk_factors: tuple[str, ...]
    confidence: int
    primary_reason: str

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategies_for": list(self.strategies_for),
            "strategies_against": list(self.strategies_against),
            "risk_factors": list(self.risk_factors),
            "confidence": self.confidence,
            "primary_reason": self.primary_reason,
        }


@dataclass(frozen=True)
class DecisionResult:
    action: DecisionAction
    confidence: int
    score: Decimal
    market_regime: MarketRegime
    explanation: DecisionExplanation

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "score": float(self.score),
            "market_regime": self.market_regime,
            "explanation": self.explanation.to_public_dict(),
        }


class MarketRegimeDetector:
    def detect(self, data: IndicatorInput) -> MarketRegime:
        closes = list(data.closes)
        if len(closes) < 5:
            return "sideways"
        fast = indicators.sma(closes, min(5, len(closes)))
        slow_period = min(20, len(closes))
        slow = indicators.sma(closes, slow_period)
        volatility = indicators.rolling_std(closes, min(10, len(closes))) or 0
        mean = indicators.rolling_mean(closes, min(10, len(closes))) or closes[-1]
        vol_pct = 0 if mean == 0 else (volatility / mean) * 100
        if vol_pct >= 4:
            return "high_volatility"
        if vol_pct <= 0.5:
            return "low_volatility"
        if fast is not None and slow is not None and fast > slow * 1.005:
            return "bull"
        if fast is not None and slow is not None and fast < slow * 0.995:
            return "bear"
        return "sideways"


class ConfidenceEngine:
    def calculate(
        self, request: DecisionRequest, regime: MarketRegime, consensus_pct: Decimal
    ) -> int:
        metrics = request.historical_metrics
        score = Decimal("0")
        score += consensus_pct * Decimal("0.35")
        score += min(
            max(to_decimal(metrics.win_rate_pct), Decimal("0")), Decimal("100")
        ) * Decimal("0.15")
        score += _bounded_metric(to_decimal(metrics.sharpe), Decimal("3")) * Decimal(
            "0.15"
        )
        pf = (
            to_decimal(metrics.profit_factor)
            if metrics.profit_factor is not None
            else Decimal("0")
        )
        score += _bounded_metric(pf, Decimal("3")) * Decimal("0.15")
        score += max(
            Decimal("0"), Decimal("100") - to_decimal(metrics.max_drawdown_pct)
        ) * Decimal("0.10")
        score += min(
            max(to_decimal(metrics.stability_pct), Decimal("0")), Decimal("100")
        ) * Decimal("0.05")
        if regime == "high_volatility":
            score -= Decimal("10")
        elif regime in {"bull", "low_volatility"}:
            score += Decimal("5")
        return int(max(Decimal("0"), min(Decimal("100"), score)).to_integral_value())


class ExplanationEngine:
    def explain(
        self,
        *,
        action: DecisionAction,
        request: DecisionRequest,
        confidence: int,
        risk_factors: tuple[str, ...],
    ) -> DecisionExplanation:
        strategies_for = tuple(
            item.strategy_name
            for item in request.strategy_signals
            if item.signal.action == action
        )
        strategies_against = tuple(
            item.strategy_name
            for item in request.strategy_signals
            if item.signal.action not in {action, "hold"}
        )
        primary = (
            "Consenso insuficiente; mantener posición."
            if action == "hold"
            else f"Consenso ponderado favorece {action.upper()}."
        )
        if risk_factors:
            primary = f"{primary} Riesgo detectado: {risk_factors[0]}"
        return DecisionExplanation(
            strategies_for, strategies_against, risk_factors, confidence, primary
        )


class AIDecisionEngine:
    def __init__(
        self,
        *,
        regime_detector: MarketRegimeDetector | None = None,
        confidence_engine: ConfidenceEngine | None = None,
        explanation_engine: ExplanationEngine | None = None,
    ) -> None:
        self.regime_detector = regime_detector or MarketRegimeDetector()
        self.confidence_engine = confidence_engine or ConfidenceEngine()
        self.explanation_engine = explanation_engine or ExplanationEngine()
        self.last_decision: DecisionResult | None = None

    def evaluate(self, request: DecisionRequest) -> DecisionResult:
        regime = self.regime_detector.detect(request.indicators)
        votes = _weighted_votes(request.strategy_signals)
        total_weight = sum(votes.values(), Decimal("0"))
        buy_score = votes["buy"]
        sell_score = votes["sell"]
        hold_score = votes["hold"]
        if buy_score > sell_score and buy_score > hold_score:
            action: DecisionAction = "buy"
            consensus = (
                (buy_score / total_weight) * Decimal("100")
                if total_weight
                else Decimal("0")
            )
        elif sell_score > buy_score and sell_score > hold_score:
            action = "sell"
            consensus = (
                (sell_score / total_weight) * Decimal("100")
                if total_weight
                else Decimal("0")
            )
        else:
            action = "hold"
            consensus = (
                (max(votes.values()) / total_weight) * Decimal("100")
                if total_weight
                else Decimal("0")
            )
        risk_factors = _risk_factors(request, regime)
        confidence = self.confidence_engine.calculate(request, regime, consensus)
        if risk_factors and action == "buy" and confidence < 75:
            action = "hold"
        score = _decision_score(request, action, confidence, risk_factors)
        explanation = self.explanation_engine.explain(
            action=action,
            request=request,
            confidence=confidence,
            risk_factors=risk_factors,
        )
        self.last_decision = DecisionResult(
            action, confidence, score, regime, explanation
        )
        return self.last_decision


def _weighted_votes(
    signals: tuple[StrategySignalInput, ...],
) -> dict[DecisionAction, Decimal]:
    votes: dict[DecisionAction, Decimal] = {
        "buy": Decimal("0"),
        "sell": Decimal("0"),
        "hold": Decimal("0"),
    }
    for item in signals:
        weight = max(to_decimal(item.weight), Decimal("0"))
        votes[item.signal.action] += (
            weight * Decimal(str(item.signal.confidence)) / Decimal("100")
        )
    return votes


def _risk_factors(request: DecisionRequest, regime: MarketRegime) -> tuple[str, ...]:
    factors: list[str] = []
    metrics = request.historical_metrics
    if to_decimal(metrics.max_drawdown_pct) > 20:
        factors.append("drawdown histórico elevado")
    if regime == "high_volatility":
        factors.append("régimen de alta volatilidad")
    if (
        request.paper_portfolio is not None
        and to_decimal(request.paper_portfolio.max_drawdown_pct) > 10
    ):
        factors.append("drawdown del portafolio paper elevado")
    return tuple(factors)


def _decision_score(
    request: DecisionRequest,
    action: DecisionAction,
    confidence: int,
    risk_factors: tuple[str, ...],
) -> Decimal:
    metrics = request.historical_metrics
    base = Decimal(confidence)
    base += to_decimal(metrics.total_return_pct) * Decimal("0.2")
    base += _best_optimizer_score(request.optimization_results) * Decimal("0.1")
    if action == "hold":
        base -= Decimal("5")
    base -= Decimal(len(risk_factors) * 10)
    return base.quantize(Decimal("0.0001"))


def _best_optimizer_score(results: tuple[Any, ...]) -> Decimal:
    if not results:
        return Decimal("0")
    try:
        best = RankingEngine().top(list(results), 1)[0]
        return to_decimal(best.composite_score)
    except Exception:
        scores = [
            to_decimal(item.get("composite_score", 0))
            for item in results
            if isinstance(item, dict)
        ]
        return max(scores, default=Decimal("0"))


def _bounded_metric(value: Decimal, best: Decimal) -> Decimal:
    if value <= 0:
        return Decimal("0")
    return min(value / best * Decimal("100"), Decimal("100"))
