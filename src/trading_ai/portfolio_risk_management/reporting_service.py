from __future__ import annotations

from html import escape
from pathlib import Path

from .policy import PortfolioRiskPolicy
from .profile import PortfolioRiskAssessment
from .serialization import write_json_atomic


class PortfolioRiskReportingService:
    def write(self, assessment: PortfolioRiskAssessment, policy: PortfolioRiskPolicy, json_file: Path, html_file: Path) -> None:
        payload = {"milestone": 37, "status": assessment.status, "policy": policy.to_dict(), "assessment": assessment.to_dict()}
        write_json_atomic(json_file, payload)
        html_file.parent.mkdir(parents=True, exist_ok=True)
        rows = "".join(
            f"<tr><td>{escape(m.name)}</td><td>{m.value:.4f}</td><td>{m.limit:.4f}</td><td>{escape(m.status)}</td></tr>"
            for m in assessment.metrics
        )
        breaches = "".join(
            f"<tr><td>{escape(b.code)}</td><td>{escape(b.severity)}</td><td>{escape(b.message)}</td><td>{escape(b.recommended_action)}</td></tr>"
            for b in assessment.breaches
        ) or '<tr><td colspan="4">No open breaches</td></tr>'
        scenarios = "".join(
            f"<tr><td>{escape(s.name)}</td><td>{s.estimated_pnl:.2f}</td><td>{s.estimated_loss_pct_nav:.4f}%</td><td>{escape(s.status)}</td></tr>"
            for s in assessment.stress_results
        )
        html_file.write_text(f"""<!doctype html><html><head><meta charset='utf-8'><title>Milestone 37 Portfolio Risk</title>
<style>body{{font-family:Arial;margin:32px}}table{{border-collapse:collapse;width:100%;margin:16px 0}}th,td{{border:1px solid #ccc;padding:8px;text-align:left}}.status{{font-size:24px;font-weight:bold}}</style></head><body>
<h1>Milestone 37 — Portfolio Risk Management</h1><div class='status'>{escape(assessment.status)} / {escape(assessment.trading_control)}</div>
<p>Portfolio: {escape(assessment.portfolio_id)} | NAV: {assessment.net_liquidation_value:.2f} | Cash: {assessment.cash_balance:.2f} | Open positions: {assessment.open_position_count}</p>
<h2>Risk Metrics</h2><table><tr><th>Metric</th><th>Observed</th><th>Limit</th><th>Status</th></tr>{rows}</table>
<h2>Breaches</h2><table><tr><th>Code</th><th>Severity</th><th>Message</th><th>Action</th></tr>{breaches}</table>
<h2>Stress Scenarios</h2><table><tr><th>Scenario</th><th>Estimated P&amp;L</th><th>Loss % NAV</th><th>Status</th></tr>{scenarios}</table>
</body></html>""", encoding="utf-8")
