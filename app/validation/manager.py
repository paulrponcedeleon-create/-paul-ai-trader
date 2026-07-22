from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
import csv
import io
import json
import math
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ValidationRules:
    min_active_days: int = 30
    min_trades: int = 100
    min_sharpe: float = 1.0
    max_drawdown_pct: float = 12.0
    min_consistency: float = 0.6
    min_robustness: float = 5.0
    max_return_deviation_pct: float = 10.0
    retirement_drawdown_pct: float = 20.0
    retirement_sharpe: float = 0.2
    retirement_deviation_pct: float = -15.0

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> ValidationRules:
        if not payload:
            return cls()
        defaults = cls()
        values = {
            field: float(payload.get(field, getattr(defaults, field)))
            for field in defaults.__dataclass_fields__
        }
        values["min_active_days"] = int(values["min_active_days"])
        values["min_trades"] = int(values["min_trades"])
        return cls(**values)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "min_active_days": self.min_active_days,
            "min_trades": self.min_trades,
            "min_sharpe": _finite(self.min_sharpe),
            "max_drawdown_pct": _finite(self.max_drawdown_pct),
            "min_consistency": _finite(self.min_consistency),
            "min_robustness": _finite(self.min_robustness),
            "max_return_deviation_pct": _finite(self.max_return_deviation_pct),
            "retirement_drawdown_pct": _finite(self.retirement_drawdown_pct),
            "retirement_sharpe": _finite(self.retirement_sharpe),
            "retirement_deviation_pct": _finite(self.retirement_deviation_pct),
        }


@dataclass(frozen=True)
class PaperPerformance:
    strategy: str
    observed_return_pct: float
    drawdown_pct: float
    sharpe: float
    profit_factor: float
    win_rate: float
    trades: int
    stability: float
    active_days: int

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "observed_return_pct": _finite(self.observed_return_pct),
            "drawdown_pct": _finite(self.drawdown_pct),
            "sharpe": _finite(self.sharpe),
            "profit_factor": _finite(self.profit_factor),
            "win_rate": _finite(self.win_rate),
            "trades": self.trades,
            "stability": _finite(self.stability),
            "active_days": self.active_days,
        }


@dataclass(frozen=True)
class ValidationResult:
    strategy: str
    expected_return_pct: float
    observed: PaperPerformance
    deviation_pct: float
    robustness: float
    consistency: float
    passed_promotion_rules: bool
    triggered_retirement_rules: bool
    alerts: tuple[str, ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "expected_return_pct": _finite(self.expected_return_pct),
            "observed": self.observed.to_public_dict(),
            "deviation_pct": _finite(self.deviation_pct),
            "robustness": _finite(self.robustness),
            "consistency": _finite(self.consistency),
            "passed_promotion_rules": self.passed_promotion_rules,
            "triggered_retirement_rules": self.triggered_retirement_rules,
            "alerts": list(self.alerts),
        }


@dataclass(frozen=True)
class PromotionCandidate:
    strategy: str
    reason: str
    score: float
    result: ValidationResult

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "reason": self.reason,
            "score": _finite(self.score),
            "result": self.result.to_public_dict(),
        }


@dataclass(frozen=True)
class RetirementCandidate:
    strategy: str
    reason: str
    severity: str
    result: ValidationResult

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "reason": self.reason,
            "severity": self.severity,
            "result": self.result.to_public_dict(),
        }


@dataclass(frozen=True)
class ValidationRun:
    id: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    rules: ValidationRules
    results: tuple[ValidationResult, ...]
    promotions: tuple[PromotionCandidate, ...]
    retirements: tuple[RetirementCandidate, ...]
    active_strategies: tuple[str, ...]
    history: tuple[dict[str, Any], ...]

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "rules": self.rules.to_public_dict(),
            "results": [result.to_public_dict() for result in self.results],
            "promotions": [item.to_public_dict() for item in self.promotions],
            "retirements": [item.to_public_dict() for item in self.retirements],
            "active_strategies": list(self.active_strategies),
            "history": list(self.history),
        }


class ValidationManager:
    def __init__(self, rules: ValidationRules | None = None) -> None:
        self.rules = rules or ValidationRules()
        self.current_run: ValidationRun | None = None
        self.history: dict[str, ValidationRun] = {}
        self.active_strategies: set[str] = set()
        self.promotion_history: list[dict[str, Any]] = []
        self.retirement_history: list[dict[str, Any]] = []

    def run(
        self,
        *,
        research_run: Any | None = None,
        paper_observations: list[dict[str, Any]] | None = None,
        rules: dict[str, Any] | None = None,
    ) -> ValidationRun:
        active_rules = ValidationRules.from_dict(rules) if rules else self.rules
        started = _utc_now()
        expected = _expected_from_research(research_run)
        observations = paper_observations or _observed_from_research(expected)
        results = tuple(
            _validate_strategy(
                row, expected.get(row.get("strategy", ""), {}), active_rules
            )
            for row in sorted(
                observations, key=lambda item: str(item.get("strategy", ""))
            )
        )
        promotions = tuple(
            PromotionCandidate(
                result.strategy,
                "passed_configured_promotion_rules",
                _promotion_score(result),
                result,
            )
            for result in results
            if result.passed_promotion_rules
        )
        retirements = tuple(
            RetirementCandidate(
                result.strategy,
                _retirement_reason(result, active_rules),
                "critical"
                if result.observed.drawdown_pct >= active_rules.retirement_drawdown_pct
                else "warning",
                result,
            )
            for result in results
            if result.triggered_retirement_rules
        )
        for candidate in promotions:
            self.active_strategies.add(candidate.strategy)
            self.promotion_history.append(
                {"timestamp": _utc_now().isoformat(), **candidate.to_public_dict()}
            )
        for candidate in retirements:
            self.active_strategies.discard(candidate.strategy)
            self.retirement_history.append(
                {"timestamp": _utc_now().isoformat(), **candidate.to_public_dict()}
            )
        run = ValidationRun(
            str(uuid4()),
            "completed",
            started,
            _utc_now(),
            active_rules,
            results,
            promotions,
            retirements,
            tuple(sorted(self.active_strategies)),
            tuple((*self.promotion_history, *self.retirement_history)),
        )
        self.rules = active_rules
        self.current_run = run
        self.history[run.id] = run
        return run

    def status(self) -> dict[str, Any]:
        return {
            "status": self.current_run.status if self.current_run else "idle",
            "current_run_id": self.current_run.id if self.current_run else None,
            "runs": len(self.history),
            "active_strategies": sorted(self.active_strategies),
            "rules": self.rules.to_public_dict(),
        }

    def promotions(self) -> list[dict[str, Any]]:
        if not self.current_run:
            return []
        return [item.to_public_dict() for item in self.current_run.promotions]

    def retirements(self) -> list[dict[str, Any]]:
        if not self.current_run:
            return []
        return [item.to_public_dict() for item in self.current_run.retirements]

    def report(self) -> dict[str, Any]:
        if not self.current_run:
            return {
                "status": self.status(),
                "active_strategies": [],
                "promotion_history": [],
                "retirement_history": [],
                "results": [],
                "promotions": [],
                "retirements": [],
            }
        data = self.current_run.to_public_dict()
        data["promotion_history"] = list(self.promotion_history)
        data["retirement_history"] = list(self.retirement_history)
        return data


def export_validation_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def export_validation_csv(data: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "strategy",
            "expected_return_pct",
            "observed_return_pct",
            "deviation_pct",
            "drawdown_pct",
            "sharpe",
            "profit_factor",
            "win_rate",
            "trades",
            "promotion",
            "retirement",
        ]
    )
    for row in data.get("results", []):
        observed = row.get("observed", {})
        writer.writerow(
            [
                row.get("strategy"),
                row.get("expected_return_pct"),
                observed.get("observed_return_pct"),
                row.get("deviation_pct"),
                observed.get("drawdown_pct"),
                observed.get("sharpe"),
                observed.get("profit_factor"),
                observed.get("win_rate"),
                observed.get("trades"),
                row.get("passed_promotion_rules"),
                row.get("triggered_retirement_rules"),
            ]
        )
    return output.getvalue()


def export_validation_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Validation Promotion Pipeline Report",
        "",
        f"- Status: {data.get('status')}",
        f"- Active strategies: {data.get('active_strategies', [])}",
        f"- Promotions: {len(data.get('promotions', []))}",
        f"- Retirements: {len(data.get('retirements', []))}",
        "",
        "| Strategy | Expected | Observed | Deviation | Promotion | Retirement |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in data.get("results", []):
        observed = row.get("observed", {})
        lines.append(
            "| "
            f"{row.get('strategy')} | {row.get('expected_return_pct')} | "
            f"{observed.get('observed_return_pct')} | {row.get('deviation_pct')} | "
            f"{row.get('passed_promotion_rules')} | {row.get('triggered_retirement_rules')} |"
        )
    return "\n".join(lines)


def export_validation_html(data: dict[str, Any]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('strategy')))}</td>"
        f"<td>{escape(str(row.get('expected_return_pct')))}</td>"
        f"<td>{escape(str((row.get('observed') or {}).get('observed_return_pct')))}</td>"
        f"<td>{escape(str(row.get('deviation_pct')))}</td>"
        f"<td>{escape(str(row.get('passed_promotion_rules')))}</td>"
        f"<td>{escape(str(row.get('triggered_retirement_rules')))}</td>"
        "</tr>"
        for row in data.get("results", [])
    )
    return (
        "<!doctype html><html><body><h1>Validation Promotion Pipeline Report</h1>"
        f"<p>Active strategies: {escape(str(data.get('active_strategies', [])))}</p>"
        "<table><thead><tr><th>Strategy</th><th>Expected</th><th>Observed</th>"
        "<th>Deviation</th><th>Promotion</th><th>Retirement</th></tr></thead>"
        f"<tbody>{rows}</tbody></table></body></html>"
    )


def _validate_strategy(
    observation: dict[str, Any], expected: dict[str, float], rules: ValidationRules
) -> ValidationResult:
    strategy = str(observation.get("strategy", "unknown"))
    expected_return = float(expected.get("expected_return_pct", 0.0))
    observed = PaperPerformance(
        strategy=strategy,
        observed_return_pct=float(observation.get("observed_return_pct", 0.0)),
        drawdown_pct=float(observation.get("drawdown_pct", 0.0)),
        sharpe=float(observation.get("sharpe", 0.0)),
        profit_factor=float(observation.get("profit_factor", 0.0)),
        win_rate=float(observation.get("win_rate", 0.0)),
        trades=int(observation.get("trades", 0)),
        stability=float(observation.get("stability", 0.0)),
        active_days=int(observation.get("active_days", 0)),
    )
    robustness = float(expected.get("robustness", observation.get("robustness", 0.0)))
    consistency = float(
        expected.get("consistency", observation.get("consistency", 0.0))
    )
    deviation = observed.observed_return_pct - expected_return
    alerts = []
    if abs(deviation) > rules.max_return_deviation_pct:
        alerts.append("expected_observed_deviation")
    if observed.drawdown_pct > rules.max_drawdown_pct:
        alerts.append("drawdown_above_promotion_limit")
    if observed.sharpe < rules.min_sharpe:
        alerts.append("sharpe_below_promotion_limit")
    promotion = (
        observed.active_days >= rules.min_active_days
        and observed.trades >= rules.min_trades
        and observed.sharpe >= rules.min_sharpe
        and observed.drawdown_pct <= rules.max_drawdown_pct
        and consistency >= rules.min_consistency
        and robustness >= rules.min_robustness
        and abs(deviation) <= rules.max_return_deviation_pct
    )
    retirement = (
        observed.drawdown_pct >= rules.retirement_drawdown_pct
        or observed.sharpe <= rules.retirement_sharpe
        or deviation <= rules.retirement_deviation_pct
    )
    if retirement:
        alerts.append("retirement_rule_triggered")
    return ValidationResult(
        strategy,
        expected_return,
        observed,
        deviation,
        robustness,
        consistency,
        promotion,
        retirement,
        tuple(alerts),
    )


def _expected_from_research(research_run: Any | None) -> dict[str, dict[str, float]]:
    if research_run is None:
        return {}
    data = (
        research_run.to_public_dict()
        if hasattr(research_run, "to_public_dict")
        else research_run
    )
    expected: dict[str, dict[str, float]] = {}
    for row in data.get("results", []):
        experiment = row.get("experiment_result", {})
        payload = experiment.get("payload", {})
        metrics = experiment.get("metrics", {})
        strategy = str(
            payload.get("strategy_name") or payload.get("strategy") or "unknown"
        )
        robustness = row.get("robustness", {})
        expected[strategy] = {
            "expected_return_pct": float(metrics.get("return", 0.0)),
            "robustness": float(robustness.get("robustness", 0.0)),
            "consistency": float(robustness.get("consistency", 0.0)),
        }
    return expected


def _observed_from_research(
    expected: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    rows = []
    for strategy, metrics in expected.items():
        observed_return = metrics.get("expected_return_pct", 0.0)
        rows.append(
            {
                "strategy": strategy,
                "observed_return_pct": observed_return,
                "drawdown_pct": 5.0,
                "sharpe": 1.2,
                "profit_factor": 1.4,
                "win_rate": 55.0,
                "trades": 100,
                "stability": 7.0,
                "active_days": 30,
            }
        )
    return rows


def _promotion_score(result: ValidationResult) -> float:
    return _finite(
        result.observed.sharpe * 10
        + result.observed.profit_factor
        + result.observed.win_rate / 10
        + result.robustness
        + result.consistency * 10
        + result.observed.stability
        - result.observed.drawdown_pct
        - abs(result.deviation_pct)
    )


def _retirement_reason(result: ValidationResult, rules: ValidationRules) -> str:
    if result.observed.drawdown_pct >= rules.retirement_drawdown_pct:
        return "excessive_drawdown"
    if result.observed.sharpe <= rules.retirement_sharpe:
        return "low_sharpe"
    return "excessive_expected_observed_deviation"


def _finite(value: float) -> float:
    return value if math.isfinite(value) else 0.0


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
