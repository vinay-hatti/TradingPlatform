from __future__ import annotations
from html import escape
from pathlib import Path
from typing import Any

class MarketDataQualityReport:
    def _v(self, obj: Any, name: str, default=None):
        return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)
    def _fmt(self, value):
        return "N/A" if value in (None, "") else escape(str(value))
    def _score(self, value):
        try: return f"{float(value):.2f}"
        except Exception: return "N/A"
    def pipeline_html(self, p):
        if p is None: return "<div class='card'><h2>Normalized Market Data Pipeline</h2><p>Unavailable.</p></div>"
        return f"<div class='card'><h2>Normalized Market Data Pipeline</h2><p>State: {self._fmt(self._v(p,'state'))}</p><p>Score: {self._score(self._v(p,'score'))}</p><p>Received: {self._fmt(self._v(p,'received_count',0))}</p><p>Accepted: {self._fmt(self._v(p,'accepted_count',0))}</p><p>Rejected: {self._fmt(self._v(p,'rejected_count',0))}</p></div>"
    def feed_html(self, p):
        if p is None: return "<div class='card'><h2>Feed Health and Recovery</h2><p>Unavailable.</p></div>"
        return f"<div class='card'><h2>Feed Health and Recovery</h2><p>Provider: {self._fmt(self._v(p,'provider'))}</p><p>State: {self._fmt(self._v(p,'state'))}</p><p>Score: {self._score(self._v(p,'score'))}</p><p>Recommendation: {self._fmt(self._v(p,'recommendation'))}</p></div>"
    def reconciliation_html(self, s):
        if s is None: return "<div class='card'><h2>Live/Historical Reconciliation</h2><p>Unavailable.</p></div>"
        rows = "".join(
            f"<tr><td>{self._fmt(self._v(p,'symbol'))}</td><td>{self._score(self._v(p,'score'))}</td><td>{self._fmt(self._v(p,'recommendation'))}</td></tr>"
            for p in (self._v(s, "profiles", ()) or ())
        )
        return f"<div class='card'><h2>Live/Historical Reconciliation</h2><p>Total: {self._fmt(self._v(s,'total_count',0))}</p><p>Matched: {self._fmt(self._v(s,'matched_count',0))}</p><p>Rejected: {self._fmt(self._v(s,'rejected_count',0))}</p><table><tr><th>Symbol</th><th>Score</th><th>Recommendation</th></tr>{rows}</table></div>"
    def diagnostics_html(self, *profiles):
        warnings, rejections = [], []
        for p in profiles:
            warnings.extend(self._v(p, "warnings", ()) or ())
            rejections.extend(self._v(p, "rejection_reasons", ()) or ())
        return f"<div class='card'><h2>Diagnostics</h2><p>Warnings: {escape(', '.join(map(str,warnings))) if warnings else 'None'}</p><p>Rejections: {escape(', '.join(map(str,rejections))) if rejections else 'None'}</p></div>"
    def generate(self, *, pipeline_profile=None, feed_profile=None, reconciliation_summary=None, path="reports/market_data_quality.html"):
        target = Path(path); target.parent.mkdir(parents=True, exist_ok=True)
        html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'><title>Market Data Quality Report</title>
<style>body{{font-family:Arial;margin:24px;background:#f4f6f8}}.card{{background:white;padding:16px;margin:14px 0;border:1px solid #ddd;border-radius:8px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:8px}}</style>
</head><body><h1>Real-Time Market Data Quality</h1>{self.pipeline_html(pipeline_profile)}{self.feed_html(feed_profile)}{self.reconciliation_html(reconciliation_summary)}{self.diagnostics_html(pipeline_profile,feed_profile,reconciliation_summary)}</body></html>"""
        target.write_text(html, encoding="utf-8")
        return target
