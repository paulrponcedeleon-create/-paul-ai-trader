from __future__ import annotations

import csv
from html import escape
import io
import json
from typing import Any


def _public(data: Any) -> dict[str, Any]:
    return data.to_public_dict() if hasattr(data, "to_public_dict") else dict(data)


def export_research_json(data: Any) -> str:
    return json.dumps(_public(data), ensure_ascii=False, sort_keys=True, indent=2)


def export_research_csv(data: Any) -> str:
    public = _public(data)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "rank",
            "experiment_id",
            "return",
            "drawdown",
            "monte_carlo_loss_probability",
            "score",
        ]
    )
    for index, result in enumerate(public.get("ranking", []), start=1):
        experiment = result.get("experiment_result", {})
        metrics = experiment.get("metrics", {})
        monte_carlo = result.get("monte_carlo", {})
        writer.writerow(
            [
                index,
                experiment.get("experiment_id"),
                metrics.get("return"),
                metrics.get("drawdown"),
                monte_carlo.get("probability_of_loss"),
                result.get("rank_score"),
            ]
        )
    return output.getvalue()


def export_research_markdown(data: Any) -> str:
    public = _public(data)
    recommendations = public.get("recommendations", [])
    lines = [
        "# Portfolio Research Report",
        "",
        "## Recommendations",
        "",
        *[f"- {item}" for item in recommendations],
        "",
        "## Ranking",
        "",
        "| Rank | Experiment | Return | Drawdown | Score |",
        "| --- | --- | --- | --- | --- |",
    ]
    for index, result in enumerate(public.get("ranking", []), start=1):
        experiment = result.get("experiment_result", {})
        metrics = experiment.get("metrics", {})
        lines.append(
            f"| {index} | {experiment.get('experiment_id')} | {metrics.get('return')} | {metrics.get('drawdown')} | {result.get('rank_score')} |"
        )
    return "\n".join(lines)


def export_research_html(data: Any) -> str:
    public = _public(data)
    recommendations = "".join(
        f"<li>{escape(str(item))}</li>" for item in public.get("recommendations", [])
    )
    rows = "".join(
        "<tr>"
        f"<td>{index}</td>"
        f"<td>{escape(str(result.get('experiment_result', {}).get('experiment_id')))}</td>"
        f"<td>{escape(str(result.get('experiment_result', {}).get('metrics', {}).get('return')))}</td>"
        f"<td>{escape(str(result.get('rank_score')))}</td>"
        "</tr>"
        for index, result in enumerate(public.get("ranking", []), start=1)
    )
    portfolio = escape(json.dumps(public.get("portfolio", {}), sort_keys=True))
    return (
        "<!doctype html><html><body><h1>Portfolio Research Report</h1>"
        f"<h2>Recommendations</h2><ul>{recommendations}</ul>"
        f"<h2>Portfolio</h2><pre>{portfolio}</pre>"
        "<h2>Ranking</h2><table><thead><tr><th>Rank</th><th>Experiment</th>"
        f"<th>Return</th><th>Score</th></tr></thead><tbody>{rows}</tbody></table>"
        "</body></html>"
    )
