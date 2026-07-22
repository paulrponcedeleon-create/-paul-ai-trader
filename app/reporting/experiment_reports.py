from __future__ import annotations

import csv
from html import escape
import io
import json
from typing import Any


def _public(data: Any) -> dict[str, Any]:
    return data.to_public_dict() if hasattr(data, "to_public_dict") else dict(data)


def export_experiment_json(data: Any) -> str:
    return json.dumps(_public(data), ensure_ascii=False, sort_keys=True, indent=2)


def export_experiment_csv(data: Any) -> str:
    public = _public(data)
    rows = public.get("ranking") or public.get("results") or []
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["rank", "experiment_id", "mode", "score", "metrics"])
    for index, row in enumerate(rows, start=1):
        writer.writerow(
            [
                row.get("rank", index),
                row.get("experiment_id"),
                row.get("mode"),
                row.get("score", row.get("metrics", {}).get("stability_score", 0)),
                json.dumps(row.get("metrics", {}), sort_keys=True),
            ]
        )
    return output.getvalue()


def export_experiment_markdown(data: Any) -> str:
    public = _public(data)
    ranking = public.get("ranking", [])
    lines = ["# Strategy Lab Experiment Report", "", "## Executive Summary", ""]
    if public.get("best_experiment_id"):
        lines.append(f"Best experiment: `{public['best_experiment_id']}`")
    else:
        lines.append("No experiment results available.")
    lines.extend(
        [
            "",
            "## Ranking",
            "",
            "| Rank | Experiment | Mode | Score |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in ranking:
        lines.append(
            f"| {row.get('rank')} | {row.get('experiment_id')} | {row.get('mode')} | {row.get('score')} |"
        )
    return "\n".join(lines)


def export_experiment_html(data: Any) -> str:
    public = _public(data)
    ranking = public.get("ranking", [])
    rows = "".join(
        "<tr>"
        f"<td>{escape(str(row.get('rank')))}</td>"
        f"<td>{escape(str(row.get('experiment_id')))}</td>"
        f"<td>{escape(str(row.get('mode')))}</td>"
        f"<td>{escape(str(row.get('score')))}</td>"
        "</tr>"
        for row in ranking
    )
    return (
        "<!doctype html><html><body><h1>Strategy Lab Experiment Report</h1>"
        f"<p>Best experiment: {escape(str(public.get('best_experiment_id')))}</p>"
        "<table><thead><tr><th>Rank</th><th>Experiment</th><th>Mode</th>"
        f"<th>Score</th></tr></thead><tbody>{rows}</tbody></table></body></html>"
    )
