from __future__ import annotations

from typing import Any, Mapping


def render_portfolio_markdown(payload: Mapping[str, Any]) -> str:
    state = payload["state"]
    health = payload["health"]
    lines = [
        "# Milestone 51 Phase 4 — Portfolio Risk Report",
        "",
        f"**Portfolio:** {payload['portfolio_id']}",
        f"**Status:** {payload['status']}",
        f"**Health:** {health['overall']:.2f}/100 ({health['grade']})",
        "",
        "## Portfolio State",
        "",
        f"- Net liquidation value: ${state['net_liquidation_value']:,.2f}",
        f"- Cash: ${state['cash']:,.2f}",
        f"- Buying power: ${state['buying_power']:,.2f}",
        f"- Gross exposure: {state['gross_exposure_pct']:.2f}%",
        f"- Net exposure: {state['net_exposure_pct']:.2f}%",
        f"- Daily P/L: ${state['daily_pnl']:,.2f}",
        f"- Unrealized P/L: ${state['unrealized_pnl']:,.2f}",
        f"- Open positions: {state['open_position_count']}",
        "",
        "## Health Components",
        "",
        f"- Liquidity: {health['liquidity']:.2f}",
        f"- Diversification: {health['diversification']:.2f}",
        f"- Greeks: {health['greeks']:.2f}",
        f"- Risk: {health['risk']:.2f}",
        f"- Drawdown: {health['drawdown']:.2f}",
        f"- Execution: {health['execution']:.2f}",
        "",
        "## Risk Breaches",
        "",
    ]
    breaches = payload.get("risk_breaches") or []
    if breaches:
        for row in breaches:
            lines.append(
                f"- **{row['severity']} — {row['code']}**: {row['message']} "
                f"(actual {row['actual']:.2f}, limit {row['limit']:.2f})"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Recommendations", ""])
    recommendations = payload.get("recommendations") or []
    if recommendations:
        for row in recommendations:
            lines.append(
                f"- **{row['priority']} — {row['action']}**: "
                f"{row['rationale']} Target: {row['target']}."
            )
    else:
        lines.append("- No portfolio changes recommended.")
    return "\n".join(lines) + "\n"
