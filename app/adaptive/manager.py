from __future__ import annotations

from dataclasses import dataclass
import csv
from html import escape
import io
import json
import math
from statistics import mean, pstdev
from typing import Any, Literal

MarketRegime = Literal[
    "bullish_trend", "bearish_trend", "sideways", "high_volatility", "low_volatility"
]
AllocationMethod = Literal["equal", "score", "risk", "volatility"]


@dataclass(frozen=True)
class StrategyProfile:
    name: str
    performance_history: tuple[float, ...]
    robustness_metrics: dict[str, float]
    recent_drawdown_pct: float
    sharpe: float
    profit_factor: float
    stability: float
    compatible_assets: tuple[str, ...]
    compatible_timeframes: tuple[str, ...]
    expected_return_pct: float = 0.0
    observed_return_pct: float = 0.0

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "performance_history": list(self.performance_history),
            "robustness_metrics": {
                key: _finite(value) for key, value in self.robustness_metrics.items()
            },
            "recent_drawdown_pct": _finite(self.recent_drawdown_pct),
            "sharpe": _finite(self.sharpe),
            "profit_factor": _finite(self.profit_factor),
            "stability": _finite(self.stability),
            "compatible_assets": list(self.compatible_assets),
            "compatible_timeframes": list(self.compatible_timeframes),
            "expected_return_pct": _finite(self.expected_return_pct),
            "observed_return_pct": _finite(self.observed_return_pct),
        }


@dataclass(frozen=True)
class StrategySelection:
    regime: MarketRegime
    ranking: tuple[dict[str, Any], ...]
    selected: tuple[StrategyProfile, ...]
    alerts: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "ranking": list(self.ranking),
            "selected": [item.to_public_dict() for item in self.selected],
            "alerts": list(self.alerts),
        }


@dataclass(frozen=True)
class PortfolioAllocation:
    method: AllocationMethod
    weights: dict[str, float]
    max_weight: float

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "weights": {key: _finite(value) for key, value in self.weights.items()},
            "max_weight": self.max_weight,
        }


class StrategyRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, StrategyProfile] = {}

    def upsert(self, profile: StrategyProfile) -> StrategyProfile:
        self._profiles[profile.name] = profile
        return profile

    def get(self, name: str) -> StrategyProfile | None:
        return self._profiles.get(name)

    def list(self) -> list[StrategyProfile]:
        return [self._profiles[name] for name in sorted(self._profiles)]

    def load_research_results(self, research_run: Any) -> None:
        data = (
            research_run.to_public_dict()
            if hasattr(research_run, "to_public_dict")
            else research_run
        )
        for item in data.get("results", []):
            experiment = item.get("experiment_result", {})
            payload = experiment.get("payload", {})
            metrics = experiment.get("metrics", {})
            robustness = item.get("robustness", {})
            strategy = str(
                payload.get("strategy_name") or payload.get("strategy") or "unknown"
            )
            dataset = str(payload.get("dataset_id") or "btc_mxn/1m/default.csv")
            parts = dataset.split("/")
            asset = parts[0] if parts else "btc_mxn"
            timeframe = parts[1] if len(parts) > 1 else "1m"
            previous = self._profiles.get(strategy)
            history = list(previous.performance_history) if previous else []
            history.append(float(metrics.get("return", 0.0)))
            self.upsert(
                StrategyProfile(
                    name=strategy,
                    performance_history=tuple(history),
                    robustness_metrics={
                        key: float(value) for key, value in robustness.items()
                    },
                    recent_drawdown_pct=float(metrics.get("drawdown", 0.0)),
                    sharpe=float(metrics.get("sharpe", 0.0)),
                    profit_factor=float(metrics.get("profit_factor", 0.0)),
                    stability=float(metrics.get("stability_score", 0.0)),
                    compatible_assets=tuple(
                        sorted(
                            {*(previous.compatible_assets if previous else ()), asset}
                        )
                    ),
                    compatible_timeframes=tuple(
                        sorted(
                            {
                                *(previous.compatible_timeframes if previous else ()),
                                timeframe,
                            }
                        )
                    ),
                    expected_return_pct=mean(history),
                    observed_return_pct=history[-1],
                )
            )


class MarketRegimeDetector:
    def detect(self, closes: tuple[float, ...]) -> MarketRegime:
        clean = [float(value) for value in closes if math.isfinite(float(value))]
        if len(clean) < 2:
            return "sideways"
        total_return = ((clean[-1] - clean[0]) / clean[0]) * 100 if clean[0] else 0.0
        returns = [
            (current - previous) / previous * 100
            for previous, current in zip(clean, clean[1:], strict=False)
            if previous
        ]
        volatility = pstdev(returns) if len(returns) > 1 else 0.0
        if volatility >= 3.0:
            return "high_volatility"
        if volatility <= 0.2 and abs(total_return) <= 1.0:
            return "low_volatility"
        if total_return >= 2.0:
            return "bullish_trend"
        if total_return <= -2.0:
            return "bearish_trend"
        return "sideways"


class StrategySelector:
    def select(
        self,
        profiles: list[StrategyProfile],
        *,
        regime: MarketRegime,
        asset: str,
        timeframe: str,
        top_n: int = 3,
    ) -> StrategySelection:
        candidates = [
            profile
            for profile in profiles
            if asset in profile.compatible_assets
            and timeframe in profile.compatible_timeframes
        ]
        ranking = sorted(
            (_rank_row(profile, regime) for profile in candidates),
            key=lambda row: row["score"],
            reverse=True,
        )
        selected_names = {row["strategy"] for row in ranking[:top_n]}
        selected = tuple(
            profile for profile in candidates if profile.name in selected_names
        )
        alerts = tuple(
            f"degradation:{profile.name}"
            for profile in selected
            if profile.observed_return_pct < profile.expected_return_pct - 5.0
        )
        return StrategySelection(regime, tuple(ranking), selected, alerts)


class PortfolioAllocator:
    def allocate(
        self,
        selection: StrategySelection,
        *,
        method: AllocationMethod = "score",
        max_weight: float = 0.5,
    ) -> PortfolioAllocation:
        profiles = list(selection.selected)
        if not profiles:
            return PortfolioAllocation(method, {}, max_weight)
        if method == "equal":
            raw = {profile.name: 1.0 for profile in profiles}
        elif method == "risk":
            raw = {
                profile.name: 1 / max(profile.recent_drawdown_pct, 0.1)
                for profile in profiles
            }
        elif method == "volatility":
            raw = {
                profile.name: 1 / max(_volatility(profile.performance_history), 0.1)
                for profile in profiles
            }
        else:
            scores = {
                row["strategy"]: max(row["score"], 0.0) for row in selection.ranking
            }
            raw = {profile.name: scores.get(profile.name, 0.0) for profile in profiles}
            if sum(raw.values()) == 0:
                raw = {profile.name: 1.0 for profile in profiles}
        capped = _normalize_with_cap(raw, max_weight)
        return PortfolioAllocation(method, capped, max_weight)


class PerformanceTracker:
    def compare(
        self, profiles: list[StrategyProfile], threshold_pct: float = 5.0
    ) -> dict[str, Any]:
        rows = []
        alerts = []
        for profile in profiles:
            difference = profile.observed_return_pct - profile.expected_return_pct
            degraded = difference <= -abs(threshold_pct)
            if degraded:
                alerts.append(f"performance_degradation:{profile.name}")
            rows.append(
                {
                    "strategy": profile.name,
                    "expected_return_pct": _finite(profile.expected_return_pct),
                    "observed_return_pct": _finite(profile.observed_return_pct),
                    "difference_pct": _finite(difference),
                    "degraded": degraded,
                }
            )
        return {"rows": rows, "alerts": alerts}


class AdaptiveManager:
    def __init__(self, registry: StrategyRegistry | None = None) -> None:
        self.registry = registry or StrategyRegistry()
        self.regime_detector = MarketRegimeDetector()
        self.selector = StrategySelector()
        self.allocator = PortfolioAllocator()
        self.tracker = PerformanceTracker()
        self.last_selection: StrategySelection | None = None
        self.last_allocation: PortfolioAllocation | None = None
        self.last_tracking: dict[str, Any] = {"rows": [], "alerts": []}

    def load_research(self, research_run: Any) -> None:
        self.registry.load_research_results(research_run)

    def status(self) -> dict[str, Any]:
        return {
            "profiles": len(self.registry.list()),
            "selected": len(self.last_selection.selected) if self.last_selection else 0,
            "regime": self.last_selection.regime if self.last_selection else None,
        }

    def selection(
        self,
        *,
        closes: tuple[float, ...],
        asset: str = "btc_mxn",
        timeframe: str = "1m",
        top_n: int = 3,
    ) -> StrategySelection:
        regime = self.regime_detector.detect(closes)
        self.last_selection = self.selector.select(
            self.registry.list(),
            regime=regime,
            asset=asset,
            timeframe=timeframe,
            top_n=top_n,
        )
        self.last_tracking = self.tracker.compare(list(self.last_selection.selected))
        return self.last_selection

    def portfolio(
        self, *, method: AllocationMethod = "score", max_weight: float = 0.5
    ) -> PortfolioAllocation:
        if self.last_selection is None:
            self.last_selection = self.selector.select(
                self.registry.list(), regime="sideways", asset="btc_mxn", timeframe="1m"
            )
        self.last_allocation = self.allocator.allocate(
            self.last_selection, method=method, max_weight=max_weight
        )
        return self.last_allocation

    def report(self) -> dict[str, Any]:
        return {
            "status": self.status(),
            "selection": self.last_selection.to_public_dict()
            if self.last_selection
            else None,
            "portfolio": self.last_allocation.to_public_dict()
            if self.last_allocation
            else None,
            "performance_tracking": self.last_tracking,
        }


def export_adaptive_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def export_adaptive_csv(data: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["strategy", "score", "weight", "degraded"])
    weights = (data.get("portfolio") or {}).get("weights", {})
    degraded = {
        row["strategy"]: row.get("degraded", False)
        for row in data.get("performance_tracking", {}).get("rows", [])
    }
    for row in (data.get("selection") or {}).get("ranking", []):
        strategy = row.get("strategy")
        writer.writerow(
            [
                strategy,
                row.get("score"),
                weights.get(strategy, 0),
                degraded.get(strategy, False),
            ]
        )
    return output.getvalue()


def export_adaptive_markdown(data: dict[str, Any]) -> str:
    selection = data.get("selection") or {}
    portfolio = data.get("portfolio") or {}
    lines = [
        "# Adaptive Portfolio Report",
        "",
        f"- Regime: {selection.get('regime')}",
        f"- Weights: {portfolio.get('weights', {})}",
        "",
        "## Ranking",
        "",
        "| Strategy | Score |",
        "| --- | --- |",
    ]
    for row in selection.get("ranking", []):
        lines.append(f"| {row.get('strategy')} | {row.get('score')} |")
    return "\n".join(lines)


def export_adaptive_html(data: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('strategy')))}</td>"
        f"<td>{escape(str(row.get('score')))}</td>"
        "</tr>"
        for row in (data.get("selection") or {}).get("ranking", [])
    )
    return (
        "<!doctype html><html><body><h1>Adaptive Portfolio Report</h1>"
        f"<p>Regime: {escape(str((data.get('selection') or {}).get('regime')))}</p>"
        f"<table><tbody>{rows}</tbody></table></body></html>"
    )


def _rank_row(profile: StrategyProfile, regime: MarketRegime) -> dict[str, Any]:
    regime_bonus = _regime_bonus(profile, regime)
    consistency = profile.robustness_metrics.get("consistency", 0.0) * 10
    robustness = profile.robustness_metrics.get("robustness", 0.0)
    score = (
        robustness
        + profile.stability
        + profile.sharpe * 10
        + profile.profit_factor
        + consistency
        + regime_bonus
        - profile.recent_drawdown_pct
    )
    return {
        "strategy": profile.name,
        "score": _finite(score),
        "regime_bonus": regime_bonus,
        "drawdown": profile.recent_drawdown_pct,
        "sharpe": profile.sharpe,
        "profit_factor": profile.profit_factor,
        "stability": profile.stability,
        "robustness": robustness,
        "consistency": consistency,
    }


def _regime_bonus(profile: StrategyProfile, regime: MarketRegime) -> float:
    avg_return = (
        mean(profile.performance_history) if profile.performance_history else 0.0
    )
    vol = _volatility(profile.performance_history)
    if regime == "bullish_trend" and avg_return > 0:
        return 5.0
    if regime == "bearish_trend" and profile.recent_drawdown_pct <= 5:
        return 3.0
    if regime == "sideways" and profile.stability >= 5:
        return 2.0
    if regime == "high_volatility" and vol <= 5:
        return 2.0
    if regime == "low_volatility" and profile.profit_factor >= 1:
        return 1.0
    return 0.0


def _normalize_with_cap(raw: dict[str, float], max_weight: float) -> dict[str, float]:
    if not raw:
        return {}
    total = sum(max(value, 0.0) for value in raw.values())
    if total <= 0:
        total = float(len(raw))
        raw = {key: 1.0 for key in raw}
    weights = {key: max(value, 0.0) / total for key, value in raw.items()}
    capped = {key: min(value, max_weight) for key, value in weights.items()}
    remainder = 1.0 - sum(capped.values())
    while remainder > 1e-9:
        room = {
            key: max_weight - value
            for key, value in capped.items()
            if value < max_weight
        }
        if not room:
            break
        add_each = remainder / len(room)
        distributed = 0.0
        for key, room_value in room.items():
            add = min(add_each, room_value)
            capped[key] += add
            distributed += add
        if distributed == 0:
            break
        remainder -= distributed
    return {key: round(value, 6) for key, value in capped.items()}


def _volatility(values: tuple[float, ...]) -> float:
    return pstdev(values) if len(values) > 1 else 0.0


def _finite(value: float) -> float:
    return value if math.isfinite(value) else 0.0
