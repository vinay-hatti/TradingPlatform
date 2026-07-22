from __future__ import annotations

import csv
import html
import io
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .atomic_publisher import AtomicFilePublisher
from .liquidity_profile import LiquidityEvaluation, LiquidityScreenResult


def _json_default(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value).__name__)


def write_json(path: Path, payload) -> None:
    AtomicFilePublisher.publish_text(path, json.dumps(payload, indent=2, sort_keys=True, default=_json_default) + "\n")


def evaluations_csv(evaluations: tuple[LiquidityEvaluation, ...]) -> str:
    columns = ["symbol", "status", "liquidity_score", "rejection_reasons", "price", "average_daily_volume", "average_daily_dollar_volume", "bid_ask_spread_pct", "market_cap", "option_volume", "option_open_interest", "exchange", "asset_type", "options_eligible"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for item in evaluations:
        metrics = item.metrics
        writer.writerow({
            "symbol": item.symbol, "status": item.status, "liquidity_score": item.liquidity_score,
            "rejection_reasons": "|".join(item.rejection_reasons), "price": getattr(metrics, "price", ""),
            "average_daily_volume": getattr(metrics, "average_daily_volume", ""),
            "average_daily_dollar_volume": getattr(metrics, "average_daily_dollar_volume", ""),
            "bid_ask_spread_pct": getattr(metrics, "bid_ask_spread_pct", ""), "market_cap": getattr(metrics, "market_cap", ""),
            "option_volume": getattr(metrics, "option_volume", ""), "option_open_interest": getattr(metrics, "option_open_interest", ""),
            "exchange": item.security.get("exchange", ""), "asset_type": item.security.get("asset_type", ""),
            "options_eligible": item.security.get("options_eligible", ""),
        })
    return output.getvalue()


def report_html(result: LiquidityScreenResult) -> str:
    rows = "".join(f"<tr><td>{html.escape(reason)}</td><td>{count}</td></tr>" for reason, count in sorted(result.rejection_breakdown.items(), key=lambda pair: (-pair[1], pair[0])))
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Liquidity Governance</title><style>body{{font-family:Arial;margin:32px}}table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:7px 12px}}.READY{{color:green}}.REVIEW{{color:#a66b00}}</style></head><body><h1>Institutional Liquidity Governance</h1><p>Status: <strong class='{result.status}'>{result.status}</strong></p><ul><li>Evaluated: {result.evaluated_count}</li><li>Eligible: {result.eligible_count}</li><li>Rejected: {result.rejected_count}</li><li>Review: {result.review_count}</li><li>Missing metrics: {result.missing_metrics_count}</li><li>Stale metrics: {result.stale_metrics_count}</li></ul><h2>Rejection breakdown</h2><table><tr><th>Reason</th><th>Count</th></tr>{rows}</table></body></html>"""
