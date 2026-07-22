from __future__ import annotations

import csv
import io
import json
from typing import Any


def _public(snapshot: Any) -> dict[str, Any]:
    return (
        snapshot.to_public_dict()
        if hasattr(snapshot, "to_public_dict")
        else dict(snapshot)
    )


def export_paper_json(snapshot: Any) -> str:
    return json.dumps(_public(snapshot), ensure_ascii=False, sort_keys=True, indent=2)


def export_paper_csv(snapshot: Any) -> str:
    data = _public(snapshot)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "key", "value"])
    for key, value in data.items():
        if key != "trades":
            writer.writerow(["portfolio", key, value])
    for trade in data.get("trades", []):
        writer.writerow(["trade", "item", json.dumps(trade, sort_keys=True)])
    return output.getvalue()


def export_paper_markdown(snapshot: Any) -> str:
    data = _public(snapshot)
    return "\n".join(
        [
            "# Paper Trading Report",
            "",
            f"- Cash MXN: {data.get('cash_mxn')}",
            f"- Equity MXN: {data.get('equity_mxn')}",
            f"- Realized P&L MXN: {data.get('realized_pnl_mxn')}",
            f"- Unrealized P&L MXN: {data.get('unrealized_pnl_mxn')}",
            f"- Max drawdown %: {data.get('max_drawdown_pct')}",
            f"- Open positions: {data.get('open_positions')}",
            f"- Trades: {len(data.get('trades', []))}",
        ]
    )
