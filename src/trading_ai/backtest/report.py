from pathlib import Path
from collections import defaultdict, Counter
import math


class BacktestReport:
    """
    Institutional reporting engine.

    Public API preserved:
        BacktestReport(initial_capital=100000.0).generate(
            trades,
            path="reports/backtest.html",
            rejected=None,
            equity_curve=None,
        )
    """

    MIN_RISK_TRADES = 20
    MIN_ROLLING_TRADES = 20

    def __init__(self, initial_capital=100000.0):
        self.initial_capital = float(initial_capital)

    # ------------------------------------------------------------
    # Safe access / formatting
    # ------------------------------------------------------------
    def val(self, obj, name, default=None):
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def safe_float(self, value, default=0.0):
        try:
            if value in (None, "", "None", "nan"):
                return default
            return float(value)
        except Exception:
            return default

    def safe_int(self, value, default=0):
        try:
            if value in (None, "", "None"):
                return default
            return int(float(value))
        except Exception:
            return default

    def pnl(self, trade):
        net = self.val(trade, "net_pnl", None)
        if net not in (None, ""):
            return self.safe_float(net)
        return self.safe_float(self.val(trade, "pnl", 0.0))

    def money(self, value):
        try:
            return f"${float(value):,.2f}"
        except Exception:
            return "$0.00"

    def pct(self, value):
        try:
            return f"{float(value) * 100:.2f}%"
        except Exception:
            return "0.00%"

    def ratio(self, value, na="N/A"):
        if value in (None, "", "N/A"):
            return na
        try:
            value = float(value)
            if math.isinf(value):
                return "N/A (No losses)"
            if math.isnan(value):
                return na
            return f"{value:.2f}"
        except Exception:
            return na

    def pf_display(self, gross_profit, gross_loss):
        gp = self.safe_float(gross_profit)
        gl = abs(self.safe_float(gross_loss))
        if gl == 0 and gp > 0:
            return "N/A (No losses)"
        if gl == 0:
            return "0.00"
        return f"{gp / gl:.2f}"

    def css_class(self, value):
        value = self.safe_float(value)
        if value > 0:
            return "positive"
        if value < 0:
            return "negative"
        return ""


    # ------------------------------------------------------------
    # Phase 3 distribution-risk helpers
    # ------------------------------------------------------------
    def distribution_risk_profile(self, item):
        """
        Return a valid distribution-risk profile from an object, dictionary,
        or nested metadata. Invalid profiles are treated as unavailable.
        """
        profile = self.val(item, "distribution_risk_profile", None)

        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("distribution_risk_profile")

        if profile is None:
            return None

        return profile if bool(self.val(profile, "valid", False)) else None

    def optional_money(self, value, na="N/A"):
        if value in (None, "", "N/A"):
            return na
        try:
            return f"${float(value):,.2f}"
        except Exception:
            return na

    def optional_pct(self, value, na="N/A"):
        if value in (None, "", "N/A"):
            return na
        try:
            return f"{float(value) * 100:.2f}%"
        except Exception:
            return na

    def optional_number(self, value, digits=2, na="N/A"):
        if value in (None, "", "N/A"):
            return na
        try:
            return f"{float(value):.{digits}f}"
        except Exception:
            return na

    def distribution_risk_values(self, item):
        """
        Return formatted Phase 3 distribution-risk values.

        Direct InstitutionalDecision fields are preferred. If they are absent,
        values are read from distribution_risk_profile.
        """
        profile = self.distribution_risk_profile(item)

        def pick(direct_name, profile_name=None, default=None):
            value = self.val(item, direct_name, None)
            if value is not None:
                return value
            if profile is not None:
                return self.val(
                    profile,
                    profile_name or direct_name,
                    default,
                )
            return default

        available = bool(
            profile is not None
            or self.val(item, "distribution_observation_count", None) is not None
            or self.val(item, "tail_risk_score", None) is not None
        )

        if not available:
            return {
                "available": False,
                "observations": "N/A",
                "historical_var_95": "N/A",
                "historical_es_95": "N/A",
                "parametric_var_95": "N/A",
                "parametric_es_95": "N/A",
                "historical_var_99": "N/A",
                "historical_es_99": "N/A",
                "downside_deviation": "N/A",
                "skewness": "N/A",
                "excess_kurtosis": "N/A",
                "probability_large_loss": "N/A",
                "probability_severe_loss": "N/A",
                "probability_critical_loss": "N/A",
                "drawdown_at_risk": "N/A",
                "expected_drawdown_shortfall": "N/A",
                "ulcer_index": "N/A",
                "pain_index": "N/A",
                "omega_ratio": "N/A",
                "sortino_ratio": "N/A",
                "gain_to_pain_ratio": "N/A",
                "tail_risk_score": "N/A",
                "tail_risk_grade": "N/A",
                "tail_risk_severity": "N/A",
                "approved": "N/A",
                "approval_class": "neutral",
            }

        allowed = bool(
            pick(
                "distribution_risk_allowed",
                "allowed",
                False,
            )
        )

        severity = str(
            pick(
                "tail_risk_severity",
                "risk_severity",
                "UNKNOWN",
            )
            or "UNKNOWN"
        ).upper()

        if allowed:
            approval_class = "positive"
        elif severity in {"CRITICAL", "SEVERE"}:
            approval_class = "negative"
        else:
            approval_class = "warning"

        return {
            "available": True,
            "observations": str(
                self.safe_int(
                    pick(
                        "distribution_observation_count",
                        "observation_count",
                        0,
                    )
                )
            ),
            "historical_var_95": self.optional_money(
                pick(
                    "historical_var_95",
                    "historical_var",
                    None,
                )
            ),
            "historical_es_95": self.optional_money(
                pick(
                    "historical_expected_shortfall_95",
                    "historical_expected_shortfall",
                    None,
                )
            ),
            "parametric_var_95": self.optional_money(
                pick(
                    "parametric_var_95",
                    "parametric_var",
                    None,
                )
            ),
            "parametric_es_95": self.optional_money(
                pick(
                    "parametric_expected_shortfall_95",
                    "parametric_expected_shortfall",
                    None,
                )
            ),
            "historical_var_99": self.optional_money(
                pick(
                    "historical_var_99",
                    "historical_var_99",
                    None,
                )
            ),
            "historical_es_99": self.optional_money(
                pick(
                    "historical_expected_shortfall_99",
                    "historical_expected_shortfall_99",
                    None,
                )
            ),
            "downside_deviation": self.optional_pct(
                pick(
                    "downside_deviation",
                    "downside_deviation",
                    None,
                )
            ),
            "skewness": self.optional_number(
                pick(
                    "skewness",
                    "skewness",
                    None,
                ),
                digits=4,
            ),
            "excess_kurtosis": self.optional_number(
                pick(
                    "excess_kurtosis",
                    "excess_kurtosis",
                    None,
                ),
                digits=4,
            ),
            "probability_large_loss": self.optional_pct(
                pick(
                    "probability_of_large_loss",
                    "probability_of_large_loss",
                    None,
                )
            ),
            "probability_severe_loss": self.optional_pct(
                pick(
                    "probability_of_severe_loss",
                    "probability_of_severe_loss",
                    None,
                )
            ),
            "probability_critical_loss": self.optional_pct(
                pick(
                    "probability_of_critical_loss",
                    "probability_of_critical_loss",
                    None,
                )
            ),
            "drawdown_at_risk": self.optional_pct(
                pick(
                    "drawdown_at_risk",
                    "drawdown_at_risk",
                    None,
                )
            ),
            "expected_drawdown_shortfall": self.optional_pct(
                pick(
                    "expected_drawdown_shortfall",
                    "expected_drawdown_shortfall",
                    None,
                )
            ),
            "ulcer_index": self.optional_number(
                pick(
                    "ulcer_index",
                    "ulcer_index",
                    None,
                ),
                digits=4,
            ),
            "pain_index": self.optional_number(
                pick(
                    "pain_index",
                    "pain_index",
                    None,
                ),
                digits=4,
            ),
            "omega_ratio": self.ratio(
                pick(
                    "omega_ratio",
                    "omega_ratio",
                    None,
                )
            ),
            "sortino_ratio": self.ratio(
                pick(
                    "sortino_ratio",
                    "sortino_ratio",
                    None,
                )
            ),
            "gain_to_pain_ratio": self.ratio(
                pick(
                    "gain_to_pain_ratio",
                    "gain_to_pain_ratio",
                    None,
                )
            ),
            "tail_risk_score": self.optional_number(
                pick(
                    "tail_risk_score",
                    "tail_risk_score",
                    None,
                ),
                digits=2,
            ),
            "tail_risk_grade": str(
                pick(
                    "tail_risk_grade",
                    "tail_risk_grade",
                    "N/A",
                )
                or "N/A"
            ),
            "tail_risk_severity": severity,
            "approved": "YES" if allowed else "NO",
            "approval_class": approval_class,
        }

    def aggregate_distribution_risk_values(self, trades):
        """
        Aggregate available Phase 3 profiles for the report-level summary.
        Dollar risk fields are summed. Scores and shape statistics are averaged.
        """
        profiles = []
        for trade in trades:
            values = self.distribution_risk_values(trade)
            if values["available"]:
                profiles.append(trade)

        if not profiles:
            return {
                "available": False,
                "profile_count": 0,
            }

        def raw(item, direct_name, profile_name=None, default=0.0):
            direct = self.val(item, direct_name, None)
            if direct is not None:
                return self.safe_float(direct, default)

            profile = self.distribution_risk_profile(item)
            if profile is None:
                return default

            return self.safe_float(
                self.val(
                    profile,
                    profile_name or direct_name,
                    default,
                ),
                default,
            )

        def average(direct_name, profile_name=None):
            values = [
                raw(item, direct_name, profile_name)
                for item in profiles
            ]
            return sum(values) / len(values) if values else 0.0

        approved_count = sum(
            1
            for item in profiles
            if bool(
                self.val(
                    item,
                    "distribution_risk_allowed",
                    self.val(
                        self.distribution_risk_profile(item),
                        "allowed",
                        False,
                    ),
                )
            )
        )

        severities = Counter(
            str(
                self.val(
                    item,
                    "tail_risk_severity",
                    self.val(
                        self.distribution_risk_profile(item),
                        "risk_severity",
                        "UNKNOWN",
                    ),
                )
                or "UNKNOWN"
            ).upper()
            for item in profiles
        )

        worst_severity = next(
            (
                severity
                for severity in [
                    "CRITICAL",
                    "SEVERE",
                    "MODERATE",
                    "LOW",
                    "UNKNOWN",
                ]
                if severities.get(severity, 0)
            ),
            "UNKNOWN",
        )

        return {
            "available": True,
            "profile_count": len(profiles),
            "approved_count": approved_count,
            "approval_rate": approved_count / len(profiles),
            "historical_var_95": sum(
                raw(item, "historical_var_95", "historical_var")
                for item in profiles
            ),
            "historical_es_95": sum(
                raw(
                    item,
                    "historical_expected_shortfall_95",
                    "historical_expected_shortfall",
                )
                for item in profiles
            ),
            "historical_var_99": sum(
                raw(item, "historical_var_99", "historical_var_99")
                for item in profiles
            ),
            "historical_es_99": sum(
                raw(
                    item,
                    "historical_expected_shortfall_99",
                    "historical_expected_shortfall_99",
                )
                for item in profiles
            ),
            "avg_tail_risk_score": average(
                "tail_risk_score",
                "tail_risk_score",
            ),
            "avg_downside_deviation": average(
                "downside_deviation",
                "downside_deviation",
            ),
            "avg_skewness": average(
                "skewness",
                "skewness",
            ),
            "avg_excess_kurtosis": average(
                "excess_kurtosis",
                "excess_kurtosis",
            ),
            "avg_drawdown_at_risk": average(
                "drawdown_at_risk",
                "drawdown_at_risk",
            ),
            "avg_expected_drawdown_shortfall": average(
                "expected_drawdown_shortfall",
                "expected_drawdown_shortfall",
            ),
            "worst_severity": worst_severity,
        }

    def distribution_risk_summary_html(self, trades):
        summary = self.aggregate_distribution_risk_values(trades)

        if not summary["available"]:
            return """
<div class="card">
<h2>Distribution Risk &amp; Tail Analytics</h2>
<p class="section-note">
No valid Phase 3 distribution-risk profiles are attached to these trades.
</p>
</div>
"""

        return f"""
<div class="card">
<h2>Distribution Risk &amp; Tail Analytics</h2>
<div class="metric"><strong>Profiles</strong>{summary['profile_count']}</div>
<div class="metric"><strong>Approved</strong>{summary['approved_count']}</div>
<div class="metric"><strong>Approval Rate</strong>{self.pct(summary['approval_rate'])}</div>
<div class="metric"><strong>Aggregate Historical VaR 95</strong>{self.money(summary['historical_var_95'])}</div>
<div class="metric"><strong>Aggregate Historical ES 95</strong>{self.money(summary['historical_es_95'])}</div>
<div class="metric"><strong>Aggregate Historical VaR 99</strong>{self.money(summary['historical_var_99'])}</div>
<div class="metric"><strong>Aggregate Historical ES 99</strong>{self.money(summary['historical_es_99'])}</div>
<div class="metric"><strong>Average Tail Risk Score</strong>{summary['avg_tail_risk_score']:.2f}</div>
<div class="metric"><strong>Average Downside Deviation</strong>{self.pct(summary['avg_downside_deviation'])}</div>
<div class="metric"><strong>Average Skewness</strong>{summary['avg_skewness']:.4f}</div>
<div class="metric"><strong>Average Excess Kurtosis</strong>{summary['avg_excess_kurtosis']:.4f}</div>
<div class="metric"><strong>Average Drawdown-at-Risk</strong>{self.pct(summary['avg_drawdown_at_risk'])}</div>
<div class="metric"><strong>Average Expected DD Shortfall</strong>{self.pct(summary['avg_expected_drawdown_shortfall'])}</div>
<div class="metric"><strong>Worst Tail Severity</strong>{summary['worst_severity']}</div>
</div>
"""

    # ------------------------------------------------------------
    # Table and chart helpers
    # ------------------------------------------------------------
    def table(self, rows, columns, empty="No data available."):
        if not rows:
            return f"<p class='section-note'>{empty}</p>"
        html = "<table><thead><tr>"
        for label, _ in columns:
            html += f"<th>{label}</th>"
        html += "</tr></thead><tbody>"
        for row in rows:
            html += "<tr>"
            for _, key in columns:
                html += f"<td>{row.get(key, '')}</td>"
            html += "</tr>"
        html += "</tbody></table>"
        return html

    def line_chart(self, rows, y_key, title):
        if not rows:
            return "<p class='section-note'>No chart data.</p>"
        values = [self.safe_float(r.get(y_key, 0.0)) for r in rows]
        min_v = min(values)
        max_v = max(values)
        if min_v == max_v:
            min_v -= 1.0
            max_v += 1.0
        width = 1000
        height = 260
        step = width / max(len(rows) - 1, 1)
        points = []
        for i, value in enumerate(values):
            x = i * step
            y = height - ((value - min_v) / (max_v - min_v) * height)
            points.append(f"{x:.2f},{y:.2f}")
        return f"""
<div>
<h3>{title}</h3>
<svg width="100%" viewBox="0 0 {width} {height + 40}" preserveAspectRatio="none">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa" stroke="#ddd"/>
    <polyline points="{' '.join(points)}" fill="none" stroke="#111" stroke-width="2"/>
    <text x="5" y="15" font-size="12">{max_v:,.2f}</text>
    <text x="5" y="{height - 5}" font-size="12">{min_v:,.2f}</text>
</svg>
</div>
"""

    def bar_chart(self, rows, label_key, value_key, title):
        rows = [r for r in rows if self.safe_float(r.get(value_key, 0.0)) != 0.0]
        if not rows:
            return "<p class='section-note'>No non-zero monthly returns.</p>"
        width = 1000
        height = 260
        max_abs = max(abs(self.safe_float(r.get(value_key, 0.0))) for r in rows) or 1.0
        bar_width = width / max(len(rows), 1)
        zero_y = height / 2
        bars = ""
        for i, row in enumerate(rows):
            value = self.safe_float(row.get(value_key, 0.0))
            bar_h = abs(value) / max_abs * (height / 2 - 20)
            x = i * bar_width + 4
            y = zero_y - bar_h if value >= 0 else zero_y
            color = "#c8e6c9" if value >= 0 else "#ffcdd2"
            label = row.get(label_key, "")
            bars += f"""
<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width - 8:.2f}" height="{bar_h:.2f}" fill="{color}" stroke="#999"/>
<text x="{x:.2f}" y="{height + 15}" font-size="10" transform="rotate(45 {x:.2f},{height + 15})">{label}</text>
"""
        return f"""
<div>
<h3>{title}</h3>
<svg width="100%" viewBox="0 0 {width} {height + 80}" preserveAspectRatio="none">
    <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa" stroke="#ddd"/>
    <line x1="0" y1="{zero_y}" x2="{width}" y2="{zero_y}" stroke="#333"/>
    {bars}
</svg>
</div>
"""

    # ------------------------------------------------------------
    # Core analytics
    # ------------------------------------------------------------
    def build_equity_curve(self, trades):
        """Build an equity curve that starts at initial capital."""
        equity = self.initial_capital
        rows = [{
            "date": "START",
            "equity": equity,
            "pnl": 0.0,
            "symbol": "START",
            "exit_reason": "INITIAL_CAPITAL",
        }]
        ordered = sorted(trades, key=lambda t: str(self.val(t, "exit_date", self.val(t, "entry_date", ""))))
        for t in ordered:
            p = self.pnl(t)
            equity += p
            rows.append({
                "date": self.val(t, "exit_date", ""),
                "equity": equity,
                "pnl": p,
                "symbol": self.val(t, "symbol", ""),
                "exit_reason": self.val(t, "exit_reason", ""),
            })
        return rows

    def drawdown_curve(self, equity_curve):
        rows = []
        peak = self.initial_capital
        current_duration = 0
        longest_duration = 0
        max_dd_pct = 0.0
        max_dd_dollars = 0.0
        for point in equity_curve:
            equity = self.safe_float(point.get("equity", self.initial_capital))
            if equity > peak:
                peak = equity
                current_duration = 0
            dd_dollars = equity - peak
            dd_pct = dd_dollars / peak if peak else 0.0
            if dd_pct < 0:
                current_duration += 1
            else:
                current_duration = 0
            longest_duration = max(longest_duration, current_duration)
            if dd_pct < max_dd_pct:
                max_dd_pct = dd_pct
                max_dd_dollars = dd_dollars
            rows.append({
                "date": point.get("date", ""),
                "equity": equity,
                "peak_equity": peak,
                "drawdown_dollars": dd_dollars,
                "drawdown_pct": dd_pct,
                "duration": current_duration,
            })
        return rows, {
            "max_drawdown_pct": max_dd_pct,
            "max_drawdown_dollars": max_dd_dollars,
            "longest_drawdown_duration": longest_duration,
            "current_drawdown_duration": current_duration,
        }

    def recovery_rows(self, dd_curve):
        if not dd_curve:
            return [{"metric": "Recovered", "value": "N/A"}]
        in_drawdown = False
        start_date = None
        recovered_date = None
        for row in dd_curve:
            dd = self.safe_float(row.get("drawdown_pct", 0.0))
            if dd < 0 and not in_drawdown:
                in_drawdown = True
                start_date = row.get("date", "")
            if in_drawdown and dd >= 0:
                recovered_date = row.get("date", "")
                break
        if not in_drawdown:
            return [{"metric": "Recovered", "value": "No drawdown"}]
        return [
            {"metric": "Recovered", "value": "Yes" if recovered_date else "No"},
            {"metric": "Drawdown Start", "value": start_date or "N/A"},
            {"metric": "Recovery Date", "value": recovered_date or "Not recovered"},
        ]

    def trade_metrics(self, trades):
        pnls = [self.pnl(t) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        net_pnl = sum(pnls)
        trades_count = len(pnls)
        return_pct = net_pnl / self.initial_capital if self.initial_capital else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit > 0 else 0.0)
        return {
            "trades": trades_count,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / trades_count if trades_count else 0.0,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_pnl": net_pnl,
            "return_pct": return_pct,
            "profit_factor": profit_factor,
            "expectancy": net_pnl / trades_count if trades_count else 0.0,
            "avg_win": sum(wins) / len(wins) if wins else 0.0,
            "avg_loss": abs(sum(losses) / len(losses)) if losses else 0.0,
            "largest_win": max(wins) if wins else 0.0,
            "largest_loss": min(losses) if losses else 0.0,
            "payoff_ratio": (sum(wins) / len(wins)) / abs(sum(losses) / len(losses)) if wins and losses else None,
        }

    def returns_from_equity(self, equity_curve):
        base = self.initial_capital
        returns = []
        prev = base
        for row in equity_curve:
            if row.get("symbol") == "START":
                prev = self.safe_float(row.get("equity", prev))
                continue
            equity = self.safe_float(row.get("equity", prev))
            if prev > 0:
                returns.append((equity - prev) / prev)
            prev = equity
        return returns

    def risk_metrics(self, trades, equity_curve, dd_metrics):
        returns = self.returns_from_equity(equity_curve)
        count = len(trades)
        out = {
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "calmar_ratio": None,
            "risk_note": f"Insufficient data: {count} observations. Risk ratios require at least {self.MIN_RISK_TRADES}.",
        }
        if count >= self.MIN_RISK_TRADES:
            avg = sum(returns) / count
            variance = sum((r - avg) ** 2 for r in returns) / max(count - 1, 1)
            std = math.sqrt(variance)
            downside = [r for r in returns if r < 0]
            downside_std = math.sqrt(sum(r * r for r in downside) / len(downside)) if downside else 0.0
            out["sharpe_ratio"] = (avg / std) * math.sqrt(252) if std else None
            out["sortino_ratio"] = (avg / downside_std) * math.sqrt(252) if downside_std else None
            out["calmar_ratio"] = (sum(returns) / abs(dd_metrics.get("max_drawdown_pct", 0.0))) if dd_metrics.get("max_drawdown_pct", 0.0) < 0 else None
            out["risk_note"] = ""
        return out

    def extended_risk(self, trades, metrics, dd_metrics):
        pnls = sorted([self.pnl(t) for t in trades])
        var_95 = pnls[int(0.05 * (len(pnls) - 1))] if pnls else 0.0
        tail = [p for p in pnls if p <= var_95] if pnls else []
        cvar_95 = sum(tail) / len(tail) if tail else 0.0
        kelly_raw = self.kelly_fraction(trades)
        kelly_display = max(0.0, min(kelly_raw, 1.0))
        gp = metrics.get("gross_profit", 0.0)
        gl = metrics.get("gross_loss", 0.0)
        omega = gp / gl if gl else None
        recovery = metrics.get("net_pnl", 0.0) / abs(dd_metrics.get("max_drawdown_dollars", 0.0)) if dd_metrics.get("max_drawdown_dollars", 0.0) else None
        ulcer = self.ulcer_index(dd_metrics.get("curve", []))
        return {
            "var_95": var_95,
            "cvar_95": cvar_95,
            "kelly_fraction": kelly_display,
            "kelly_raw": kelly_raw,
            "half_kelly": kelly_display / 2.0,
            "kelly_recommendation": "Do not increase position sizing" if kelly_raw <= 0 else "Use half-Kelly or lower",
            "omega_ratio": omega,
            "recovery_factor": recovery,
            "ulcer_index": ulcer,
            "longest_drawdown_duration": dd_metrics.get("longest_drawdown_duration", 0),
            "time_in_market": min(1.0, len(trades) / max(len(trades), 1)) if trades else 0.0,
        }

    def kelly_fraction(self, trades):
        pnls = [self.pnl(t) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        if not pnls or not wins or not losses:
            return 0.0
        win_rate = len(wins) / len(pnls)
        loss_rate = 1.0 - win_rate
        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)
        b = avg_win / avg_loss if avg_loss else 0.0
        return win_rate - (loss_rate / b) if b else 0.0

    def ulcer_index(self, dd_curve):
        if not dd_curve:
            return 0.0
        squares = [(self.safe_float(r.get("drawdown_pct", 0.0)) * 100) ** 2 for r in dd_curve]
        return math.sqrt(sum(squares) / len(squares)) if squares else 0.0

    def streaks(self, trades):
        max_win = max_loss = cur_win = cur_loss = 0
        for t in trades:
            p = self.pnl(t)
            if p > 0:
                cur_win += 1
                cur_loss = 0
            elif p < 0:
                cur_loss += 1
                cur_win = 0
            else:
                cur_win = cur_loss = 0
            max_win = max(max_win, cur_win)
            max_loss = max(max_loss, cur_loss)
        return {"longest_win_streak": max_win, "longest_loss_streak": max_loss}

    # ------------------------------------------------------------
    # Grouped analytics
    # ------------------------------------------------------------
    def grouped(self, trades, label_key, key_fn):
        groups = defaultdict(list)
        for t in trades:
            groups[str(key_fn(t) or "UNKNOWN")].append(t)
        rows = []
        for key, items in sorted(groups.items()):
            m = self.trade_metrics(items)
            rows.append({
                label_key: key,
                "trades": m["trades"],
                "wins": m["wins"],
                "losses": m["losses"],
                "win_rate": self.pct(m["win_rate"]),
                "net_pnl": self.money(m["net_pnl"]),
                "return_pct": self.pct(m["return_pct"]),
                "avg_pnl": self.money(m["expectancy"]),
                "profit_factor": self.pf_display(m["gross_profit"], m["gross_loss"]),
                "expectancy": self.money(m["expectancy"]),
            })
        return rows

    def rejected_summary_rows(self, rejected):
        counts = Counter(item.get("reason", "UNKNOWN") for item in rejected)
        return [{"reason": reason, "count": count} for reason, count in sorted(counts.items())]

    def rejected_rows(self, rejected, limit=100):
        rows = []
        for item in rejected[:limit]:
            trade = item.get("trade")
            rows.append({
                "symbol": self.val(trade, "symbol", ""),
                "entry_date": self.val(trade, "entry_date", ""),
                "signal": self.val(trade, "signal", ""),
                "strategy": self.val(trade, "strategy", ""),
                "entry_price": f"{self.safe_float(self.val(trade, 'entry_price', 0.0)):.2f}",
                "contracts": self.val(trade, "contracts", ""),
                "reason": item.get("reason", ""),
                "rank_score": f"{self.safe_float(self.val(trade, 'rank_score', 0.0)):.2f}",
                "option_score": f"{self.safe_float(self.val(trade, 'option_score', 0.0)):.2f}",
            })
        return rows

    def pricing_source(self, trade, field="entry"):
        if field == "entry":
            value = self.val(trade, "entry_pricing_source", None) or self.val(trade, "pricing_source", None)
            if value:
                return str(value)
            return "historical_chain" if self.val(trade, "expiry", "") != "BS_ENTRY_PROXY_EXIT" else "black_scholes_proxy"

        value = self.val(trade, "exit_pricing_source", None)
        if value:
            return str(value)
        return "black_scholes_mark_to_model"

    def historical_option_diagnostics(self, trades, rejected):
        total = len(trades) + len(rejected)
        historical_entries = sum(1 for t in trades if self.pricing_source(t, "entry") == "historical_chain")
        bs_entries = sum(1 for t in trades if self.pricing_source(t, "entry") != "historical_chain")
        historical_exits = sum(1 for t in trades if self.pricing_source(t, "exit") == "historical_chain")
        bs_exits = len(trades) - historical_exits
        no_contract = sum(1 for r in rejected if r.get("reason") == "NO_HISTORICAL_ENTRY_CONTRACT")
        liquidity_rejects = sum(1 for r in rejected if "LIQUIDITY" in str(r.get("reason", "")))
        spread_rejects = sum(1 for r in rejected if "SPREAD" in str(r.get("reason", "")))
        volume_rejects = sum(1 for r in rejected if "VOLUME" in str(r.get("reason", "")))
        oi_rejects = sum(1 for r in rejected if "OPEN_INTEREST" in str(r.get("reason", "")) or "OI" in str(r.get("reason", "")))
        coverage = historical_entries / total if total else 0.0
        return [
            {"metric": "Signals evaluated", "value": str(total)},
            {"metric": "Accepted trades", "value": str(len(trades))},
            {"metric": "Rejected trades", "value": str(len(rejected))},
            {"metric": "Historical contracts found", "value": str(historical_entries)},
            {"metric": "Historical option coverage", "value": self.pct(coverage)},
            {"metric": "Rejected: no historical contract", "value": str(no_contract)},
            {"metric": "Rejected: liquidity", "value": str(liquidity_rejects)},
            {"metric": "Rejected: spread", "value": str(spread_rejects)},
            {"metric": "Rejected: volume", "value": str(volume_rejects)},
            {"metric": "Rejected: open interest", "value": str(oi_rejects)},
            {"metric": "Historical entry", "value": str(historical_entries)},
            {"metric": "Black-Scholes entry fallback", "value": str(bs_entries)},
            {"metric": "Historical exit", "value": str(historical_exits)},
            {"metric": "Black-Scholes exit", "value": str(bs_exits)},
        ]

    def historical_coverage_breakdowns(self, trades, rejected):
        combined = []
        for t in trades:
            combined.append({
                "symbol": self.val(t, "symbol", "UNKNOWN"),
                "date": self.val(t, "entry_date", ""),
                "signal": self.val(t, "signal", "UNKNOWN"),
                "accepted": True,
                "historical": self.pricing_source(t, "entry") == "historical_chain",
            })
        for r in rejected:
            t = r.get("trade")
            combined.append({
                "symbol": self.val(t, "symbol", "UNKNOWN"),
                "date": self.val(t, "entry_date", ""),
                "signal": self.val(t, "signal", "UNKNOWN"),
                "accepted": False,
                "historical": False,
            })

        def month_key(value):
            return value.strftime("%Y-%m") if hasattr(value, "strftime") else str(value)[:7]

        def grouped(key_fn, label_name):
            buckets = defaultdict(lambda: {"signals": 0, "historical": 0, "accepted": 0})
            for row in combined:
                key = key_fn(row) or "UNKNOWN"
                buckets[key]["signals"] += 1
                buckets[key]["historical"] += 1 if row["historical"] else 0
                buckets[key]["accepted"] += 1 if row["accepted"] else 0
            out = []
            for key, vals in sorted(buckets.items()):
                coverage = vals["historical"] / vals["signals"] if vals["signals"] else 0.0
                out.append({
                    label_name: key,
                    "signals": vals["signals"],
                    "historical": vals["historical"],
                    "accepted": vals["accepted"],
                    "coverage": self.pct(coverage),
                })
            return out

        return {
            "symbol": grouped(lambda r: r["symbol"], "symbol"),
            "month": grouped(lambda r: month_key(r["date"]), "month"),
            "option_type": grouped(lambda r: r["signal"], "option_type"),
        }

    def monthly_rows(self, trades):
        groups = defaultdict(float)
        for t in trades:
            d = self.val(t, "exit_date", "")
            key = d.strftime("%Y-%b") if hasattr(d, "strftime") else str(d)[:7]
            groups[key] += self.pnl(t)
        rows = []
        for key, pnl in sorted(groups.items()):
            ret = pnl / self.initial_capital if self.initial_capital else 0.0
            rows.append({
                "month": key,
                "return": ret,
                "return_fmt": f"<span class='{self.css_class(ret)}'>{self.pct(ret)}</span>",
                "net_pnl": self.money(pnl),
            })
        return rows

    def rolling_rows(self, equity_curve):
        if len(equity_curve) < self.MIN_ROLLING_TRADES:
            return []
        returns = self.returns_from_equity(equity_curve)
        rows = []
        for i in range(self.MIN_ROLLING_TRADES - 1, len(returns)):
            subset = returns[i - self.MIN_ROLLING_TRADES + 1:i + 1]
            avg = sum(subset) / len(subset)
            var = sum((r - avg) ** 2 for r in subset) / max(len(subset) - 1, 1)
            std = math.sqrt(var)
            sharpe = (avg / std) * math.sqrt(252) if std else None
            rows.append({
                "date": equity_curve[i].get("date", ""),
                "rolling_return": self.pct(sum(subset)),
                "rolling_sharpe": self.ratio(sharpe),
                "rolling_volatility": self.pct(std * math.sqrt(252) if std else 0.0),
            })
        return rows[-30:]

    def trade_distribution_rows(self, trades):
        buckets = [
            ("< -10000", lambda p: p < -10000),
            ("-10000 to -5000", lambda p: -10000 <= p < -5000),
            ("-5000 to -1000", lambda p: -5000 <= p < -1000),
            ("-1000 to 0", lambda p: -1000 <= p < 0),
            ("0 to 1000", lambda p: 0 <= p < 1000),
            ("1000 to 5000", lambda p: 1000 <= p < 5000),
            ("5000 to 10000", lambda p: 5000 <= p < 10000),
            ("> 10000", lambda p: p >= 10000),
        ]
        rows = []
        for label, fn in buckets:
            vals = [self.pnl(t) for t in trades if fn(self.pnl(t))]
            rows.append({
                "bucket": label,
                "trades": len(vals),
                "net_pnl": self.money(sum(vals)),
                "avg_pnl": self.money(sum(vals) / len(vals) if vals else 0.0),
            })
        return rows

    def trade_rows(self, trades):
        rows = []
        for t in trades:
            entry_price = self.safe_float(self.val(t, "entry_price", 0.0))
            contracts = self.safe_float(self.val(t, "contracts", 0.0))
            position_size = self.safe_float(self.val(t, "position_size", entry_price * contracts * 100.0))
            initial_risk = self.safe_float(self.val(t, "initial_risk", position_size))
            r_multiple = self.val(t, "r_multiple", None)
            if r_multiple in (None, ""):
                r_multiple = self.pnl(t) / initial_risk if initial_risk else None

            rows.append({
                "symbol": self.val(t, "symbol", ""),
                "entry_date": self.val(t, "entry_date", ""),
                "exit_date": self.val(t, "exit_date", ""),
                "strategy": self.val(t, "strategy", ""),
                "signal": self.val(t, "signal", ""),
                "regime": self.val(t, "market_regime", self.val(t, "regime", "UNKNOWN")),
                "strike": self.val(t, "strike", ""),
                "expiry": self.val(t, "expiry", ""),
                "entry_price": f"{entry_price:.2f}",
                "exit_price": f"{self.safe_float(self.val(t, 'exit_price', 0.0)):.2f}",
                "entry_source": self.pricing_source(t, "entry"),
                "exit_source": self.pricing_source(t, "exit"),
                "option_symbol": self.val(t, "option_symbol", ""),
                "position_size": self.money(position_size),
                "initial_risk": self.money(initial_risk),
                "r_multiple": self.ratio(r_multiple),
                "contracts": self.val(t, "contracts", ""),
                "pnl": self.money(self.val(t, "pnl", 0.0)),
                "pnl_pct": self.pct(self.val(t, "pnl_pct", 0.0)),
                "gross_pnl": self.money(self.val(t, "gross_pnl", 0.0)),
                "fees": self.money(self.val(t, "fees", 0.0)),
                "net_pnl": self.money(self.pnl(t)),
                "days_held": self.val(t, "days_held", ""),
                "exit_reason": self.val(t, "exit_reason", ""),
                "rank_score": f"{self.safe_float(self.val(t, 'rank_score', 0.0)):.2f}",
                "option_score": f"{self.safe_float(self.val(t, 'option_score', 0.0)):.2f}",
                "delta": f"{self.safe_float(self.val(t, 'entry_delta', 0.0)):.4f}",
                "gamma": f"{self.safe_float(self.val(t, 'entry_gamma', 0.0)):.5f}",
                "theta": f"{self.safe_float(self.val(t, 'entry_theta', 0.0)):.4f}",
                "vega": f"{self.safe_float(self.val(t, 'entry_vega', 0.0)):.4f}",
                "vol": self.pct(self.val(t, "entry_volatility", 0.0)),
                "pop": self.pct(
                    self.val(
                        t,
                        "probability_of_profit",
                        self.val(t, "pop", 0.0),
                    )
                ),
                "distribution_observations": self.distribution_risk_values(t)["observations"],
                "historical_var_95": self.distribution_risk_values(t)["historical_var_95"],
                "historical_es_95": self.distribution_risk_values(t)["historical_es_95"],
                "parametric_var_95": self.distribution_risk_values(t)["parametric_var_95"],
                "parametric_es_95": self.distribution_risk_values(t)["parametric_es_95"],
                "historical_var_99": self.distribution_risk_values(t)["historical_var_99"],
                "historical_es_99": self.distribution_risk_values(t)["historical_es_99"],
                "downside_deviation": self.distribution_risk_values(t)["downside_deviation"],
                "skewness": self.distribution_risk_values(t)["skewness"],
                "excess_kurtosis": self.distribution_risk_values(t)["excess_kurtosis"],
                "probability_large_loss": self.distribution_risk_values(t)["probability_large_loss"],
                "probability_severe_loss": self.distribution_risk_values(t)["probability_severe_loss"],
                "probability_critical_loss": self.distribution_risk_values(t)["probability_critical_loss"],
                "drawdown_at_risk": self.distribution_risk_values(t)["drawdown_at_risk"],
                "expected_drawdown_shortfall": self.distribution_risk_values(t)["expected_drawdown_shortfall"],
                "ulcer_index_tail": self.distribution_risk_values(t)["ulcer_index"],
                "pain_index": self.distribution_risk_values(t)["pain_index"],
                "omega_ratio_tail": self.distribution_risk_values(t)["omega_ratio"],
                "sortino_ratio_tail": self.distribution_risk_values(t)["sortino_ratio"],
                "gain_to_pain_ratio": self.distribution_risk_values(t)["gain_to_pain_ratio"],
                "tail_risk_score": self.distribution_risk_values(t)["tail_risk_score"],
                "tail_risk_grade": self.distribution_risk_values(t)["tail_risk_grade"],
                "tail_risk_severity": self.distribution_risk_values(t)["tail_risk_severity"],
                "distribution_risk_allowed": (
                    f"<span class='{self.distribution_risk_values(t)['approval_class']}'>"
                    f"{self.distribution_risk_values(t)['approved']}</span>"
                ),
            })
        return rows

    def score_bucket(self, t):
        score = self.safe_float(self.val(t, "rank_score", self.val(t, "option_score", 0.0)))
        low = int(score // 10) * 10
        return f"{low}-{low + 10}"

    def delta_bucket(self, t):
        d = abs(self.safe_float(self.val(t, "entry_delta", 0.0)))
        if d < 0.30: return "0.00-0.30"
        if d < 0.45: return "0.30-0.45"
        if d < 0.60: return "0.45-0.60"
        if d < 0.75: return "0.60-0.75"
        return "0.75+"

    def executive_assessment(self, metrics, dd_metrics, rejected, trades):
        pf = metrics.get("profit_factor", 0.0)
        ret = metrics.get("return_pct", 0.0)
        dd = dd_metrics.get("max_drawdown_pct", 0.0)
        coverage = len(trades) / max(len(trades) + len(rejected), 1)
        if ret > 0 and pf >= 1.5 and dd > -0.15:
            rating = "Good"
        elif ret > 0 and pf >= 1.0:
            rating = "Moderate"
        elif len(trades) < 20:
            rating = "Inconclusive"
        else:
            rating = "Weak"
        weaknesses = []
        if len(trades) < 20:
            weaknesses.append("Small sample size; risk ratios are hidden until enough trades exist.")
        if metrics.get("net_pnl", 0.0) < 0:
            weaknesses.append("Negative net PnL and expectancy.")
        if coverage < 0.50:
            weaknesses.append("Low historical option-chain coverage.")
        if dd < -0.10:
            weaknesses.append("Drawdown needs improvement.")
        if not weaknesses:
            weaknesses.append("No major issues detected in this run.")
        rows = [
            {"metric": "Overall rating", "value": rating},
            {"metric": "Primary recommendation", "value": "Increase historical option-chain coverage before interpreting performance." if coverage < 0.50 else "Continue validation on larger windows."},
            {"metric": "Key weakness", "value": weaknesses[0]},
        ]
        return rows

    # ------------------------------------------------------------
    # Main generator
    # ------------------------------------------------------------
    def generate(self, trades, path="reports/backtest.html", rejected=None, equity_curve=None):
        trades = trades or []
        rejected = rejected or []
        curve = equity_curve or self.build_equity_curve(trades)
        dd_curve, dd_metrics = self.drawdown_curve(curve)
        dd_metrics["curve"] = dd_curve
        metrics = self.trade_metrics(trades)
        metrics.update(dd_metrics)
        metrics.update(self.risk_metrics(trades, curve, dd_metrics))
        extended = self.extended_risk(trades, metrics, dd_metrics)
        streaks = self.streaks(trades)
        final_equity = curve[-1]["equity"] if curve else self.initial_capital

        monthly = self.monthly_rows(trades)
        rolling = self.rolling_rows(curve)
        rejected_summary = self.rejected_summary_rows(rejected)
        historical_diag = self.historical_option_diagnostics(trades, rejected)
        coverage_breakdowns = self.historical_coverage_breakdowns(trades, rejected)
        recovery_rows = self.recovery_rows(dd_curve)
        executive_rows = self.executive_assessment(metrics, dd_metrics, rejected, trades)

        equity_rows = [{
            "date": r.get("date", ""),
            "equity": self.money(r.get("equity", 0.0)),
            "pnl": self.money(r.get("pnl", 0.0)),
            "symbol": r.get("symbol", ""),
            "exit_reason": r.get("exit_reason", ""),
        } for r in curve]
        drawdown_rows = [{
            "date": r.get("date", ""),
            "equity": self.money(r.get("equity", 0.0)),
            "peak_equity": self.money(r.get("peak_equity", 0.0)),
            "drawdown_dollars": self.money(r.get("drawdown_dollars", 0.0)),
            "drawdown_pct": self.pct(r.get("drawdown_pct", 0.0)),
        } for r in dd_curve]

        symbol_rows = self.grouped(trades, "symbol", lambda t: self.val(t, "symbol", "UNKNOWN"))
        exit_rows = self.grouped(trades, "exit_reason", lambda t: self.val(t, "exit_reason", "UNKNOWN"))
        signal_rows = self.grouped(trades, "signal", lambda t: self.val(t, "signal", "UNKNOWN"))
        regime_rows = self.grouped(trades, "regime", lambda t: self.val(t, "market_regime", self.val(t, "regime", "UNKNOWN")))
        score_rows = self.grouped(trades, "score_bucket", self.score_bucket)
        delta_rows = self.grouped(trades, "delta_bucket", self.delta_bucket)
        month_perf_rows = self.grouped(trades, "month", lambda t: str(self.val(t, "exit_date", ""))[:7])

        ordered_trades = sorted(trades, key=lambda t: self.pnl(t), reverse=True)
        best_rows = self.trade_rows(ordered_trades[:10])
        worst_rows = self.trade_rows(list(reversed(ordered_trades[-10:])))
        all_trade_rows = self.trade_rows(trades)
        rejected_rows = self.rejected_rows(rejected)
        distribution_rows = self.trade_distribution_rows(trades)

        risk_note_html = f"<p class='warning'>{metrics.get('risk_note')}</p>" if metrics.get("risk_note") else ""
        distribution_risk_summary = (
            self.distribution_risk_summary_html(trades)
        )

        rolling_html = self.table(
            rolling,
            [("Date", "date"), ("Rolling Return", "rolling_return"), ("Rolling Sharpe", "rolling_sharpe"), ("Rolling Volatility", "rolling_volatility")],
            empty=f"Insufficient data for rolling metrics. Requires at least {self.MIN_ROLLING_TRADES} trades.",
        )

        html = f"""
<!DOCTYPE html>
<html>
<head>
<title>Trading AI Backtest Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 30px; background: #f7f7f7; color: #222; }}
h1, h2 {{ color: #111; }}
.card {{ background: white; padding: 20px; margin-bottom: 25px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.12); overflow-x: auto; }}
.metric {{ display: inline-block; margin-right: 30px; margin-bottom: 15px; font-size: 18px; vertical-align: top; }}
.metric strong {{ display: block; font-size: 13px; color: #666; }}
table {{ width: 100%; border-collapse: collapse; background: white; white-space: nowrap; }}
th, td {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; }}
th {{ background: #eee; }}
.positive {{ color: #1b5e20; font-weight: bold; }}
.negative {{ color: #b71c1c; font-weight: bold; }}
.warning {{ color: #e65100; font-weight: bold; }}
.neutral {{ color: #455a64; font-weight: bold; }}
.section-note {{ color: #555; font-size: 14px; margin-bottom: 10px; }}
</style>
</head>
<body>
<h1>Trading AI Backtest Report</h1>

<div class="card"><h2>Executive Assessment</h2>{self.table(executive_rows, [("Metric", "metric"), ("Value", "value")])}</div>

<div class="card">
<h2>Summary</h2>
<div class="metric"><strong>Trades</strong>{metrics['trades']}</div>
<div class="metric"><strong>Accepted</strong>{len(trades)}</div>
<div class="metric"><strong>Rejected</strong>{len(rejected)}</div>
<div class="metric"><strong>Wins</strong>{metrics['wins']}</div>
<div class="metric"><strong>Losses</strong>{metrics['losses']}</div>
<div class="metric"><strong>Win Rate</strong>{self.pct(metrics['win_rate'])}</div>
<div class="metric"><strong>Net PnL</strong>{self.money(metrics['net_pnl'])}</div>
<div class="metric"><strong>Final Equity</strong>{self.money(final_equity)}</div>
<div class="metric"><strong>Return</strong>{self.pct(metrics['return_pct'])}</div>
<div class="metric"><strong>Profit Factor</strong>{self.pf_display(metrics['gross_profit'], metrics['gross_loss'])}</div>
<div class="metric"><strong>Expectancy</strong>{self.money(metrics['expectancy'])}</div>
<div class="metric"><strong>Max Drawdown</strong>{self.pct(metrics['max_drawdown_pct'])}</div>
<div class="metric"><strong>Max DD $</strong>{self.money(metrics['max_drawdown_dollars'])}</div>
<div class="metric"><strong>Sharpe</strong>{self.ratio(metrics.get('sharpe_ratio'))}</div>
<div class="metric"><strong>Sortino</strong>{self.ratio(metrics.get('sortino_ratio'))}</div>
<div class="metric"><strong>Calmar</strong>{self.ratio(metrics.get('calmar_ratio'))}</div>
<div class="metric"><strong>Payoff Ratio</strong>{self.ratio(metrics.get('payoff_ratio'))}</div>
{risk_note_html}
</div>

<div class="card"><h2>Historical Option Coverage</h2>{self.table(historical_diag, [("Metric", "metric"), ("Value", "value")])}</div>
<div class="card"><h2>Historical Coverage by Symbol</h2>{self.table(coverage_breakdowns["symbol"], [("Symbol", "symbol"), ("Signals", "signals"), ("Historical", "historical"), ("Accepted", "accepted"), ("Coverage", "coverage")])}</div>
<div class="card"><h2>Historical Coverage by Month</h2>{self.table(coverage_breakdowns["month"], [("Month", "month"), ("Signals", "signals"), ("Historical", "historical"), ("Accepted", "accepted"), ("Coverage", "coverage")])}</div>
<div class="card"><h2>Historical Coverage by Option Type</h2>{self.table(coverage_breakdowns["option_type"], [("Option Type", "option_type"), ("Signals", "signals"), ("Historical", "historical"), ("Accepted", "accepted"), ("Coverage", "coverage")])}</div>

<div class="card">
<h2>Executive Risk Diagnostics</h2>
<div class="metric"><strong>VaR 95%</strong>{self.money(extended['var_95'])}</div>
<div class="metric"><strong>CVaR 95%</strong>{self.money(extended['cvar_95'])}</div>
<div class="metric"><strong>Kelly</strong>{self.pct(extended['kelly_fraction'])}</div>
<div class="metric"><strong>Half Kelly</strong>{self.pct(extended['half_kelly'])}</div>
<div class="metric"><strong>Kelly Recommendation</strong>{extended['kelly_recommendation']}</div>
<div class="metric"><strong>Ulcer Index</strong>{self.ratio(extended['ulcer_index'])}</div>
<div class="metric"><strong>Omega</strong>{self.ratio(extended['omega_ratio'])}</div>
<div class="metric"><strong>Recovery Factor</strong>{self.ratio(extended['recovery_factor'])}</div>
<div class="metric"><strong>Time in Market</strong>{self.pct(extended['time_in_market'])}</div>
<div class="metric"><strong>Longest DD Duration</strong>{extended['longest_drawdown_duration']} trades</div>
</div>

{distribution_risk_summary}

<div class="card"><h2>Drawdown Recovery</h2>{self.table(recovery_rows, [("Metric", "metric"), ("Value", "value")])}</div>

<div class="card"><h2>Equity Curve Chart</h2>{self.line_chart(curve, 'equity', 'Equity Curve')}</div>
<div class="card"><h2>Underwater Drawdown Chart</h2>{self.line_chart(dd_curve, 'drawdown_pct', 'Underwater Drawdown Curve')}</div>
<div class="card"><h2>Monthly Return Chart</h2>{self.bar_chart(monthly, 'month', 'return', 'Monthly Return Bars')}</div>

<div class="card"><h2>Advanced Risk Metrics</h2>
<div class="metric"><strong>Average Win</strong>{self.money(metrics['avg_win'])}</div>
<div class="metric"><strong>Average Loss</strong>{self.money(metrics['avg_loss'])}</div>
<div class="metric"><strong>Largest Win</strong>{self.money(metrics['largest_win'])}</div>
<div class="metric"><strong>Largest Loss</strong>{self.money(metrics['largest_loss'])}</div>
<div class="metric"><strong>Gross Profit</strong>{self.money(metrics['gross_profit'])}</div>
<div class="metric"><strong>Gross Loss</strong>{self.money(metrics['gross_loss'])}</div>
<div class="metric"><strong>Longest Win Streak</strong>{streaks['longest_win_streak']}</div>
<div class="metric"><strong>Longest Loss Streak</strong>{streaks['longest_loss_streak']}</div>
</div>

<div class="card"><h2>Monthly Return Heatmap</h2>{self.table(monthly, [("Month", "month"), ("Return", "return_fmt"), ("Net PnL", "net_pnl")])}</div>
<div class="card"><h2>Rejected Trade Summary</h2>{self.table(rejected_summary, [("Reason", "reason"), ("Count", "count")])}</div>
<div class="card"><h2>Performance by Symbol</h2>{self.table(symbol_rows, [("Symbol", "symbol"), ("Trades", "trades"), ("Wins", "wins"), ("Losses", "losses"), ("Win Rate", "win_rate"), ("Net PnL", "net_pnl"), ("Return", "return_pct"), ("Profit Factor", "profit_factor"), ("Expectancy", "expectancy")])}</div>
<div class="card"><h2>Performance by Exit Reason</h2>{self.table(exit_rows, [("Exit Reason", "exit_reason"), ("Trades", "trades"), ("Wins", "wins"), ("Losses", "losses"), ("Win Rate", "win_rate"), ("Net PnL", "net_pnl"), ("Return", "return_pct"), ("Profit Factor", "profit_factor"), ("Expectancy", "expectancy")])}</div>
<div class="card"><h2>Performance by Signal</h2>{self.table(signal_rows, [("Signal", "signal"), ("Trades", "trades"), ("Wins", "wins"), ("Losses", "losses"), ("Win Rate", "win_rate"), ("Net PnL", "net_pnl"), ("Return", "return_pct"), ("Profit Factor", "profit_factor"), ("Expectancy", "expectancy")])}</div>
<div class="card"><h2>Regime Performance</h2>{self.table(regime_rows, [("Regime", "regime"), ("Trades", "trades"), ("Wins", "wins"), ("Losses", "losses"), ("Win Rate", "win_rate"), ("Net PnL", "net_pnl"), ("Avg PnL", "avg_pnl"), ("Profit Factor", "profit_factor"), ("Expectancy", "expectancy")])}</div>
<div class="card"><h2>Score Calibration</h2>{self.table(score_rows, [("Score Bucket", "score_bucket"), ("Trades", "trades"), ("Wins", "wins"), ("Losses", "losses"), ("Win Rate", "win_rate"), ("Net PnL", "net_pnl"), ("Avg PnL", "avg_pnl"), ("Profit Factor", "profit_factor"), ("Expectancy", "expectancy")])}</div>
<div class="card"><h2>Performance by Month</h2>{self.table(month_perf_rows, [("Month", "month"), ("Trades", "trades"), ("Wins", "wins"), ("Losses", "losses"), ("Win Rate", "win_rate"), ("Net PnL", "net_pnl"), ("Return", "return_pct"), ("Profit Factor", "profit_factor"), ("Expectancy", "expectancy")])}</div>
<div class="card"><h2>Performance by Delta Bucket</h2>{self.table(delta_rows, [("Delta Bucket", "delta_bucket"), ("Trades", "trades"), ("Wins", "wins"), ("Losses", "losses"), ("Win Rate", "win_rate"), ("Net PnL", "net_pnl"), ("Return", "return_pct"), ("Profit Factor", "profit_factor"), ("Expectancy", "expectancy")])}</div>
<div class="card"><h2>Trade PnL Distribution</h2>{self.table(distribution_rows, [("PnL Bucket", "bucket"), ("Trades", "trades"), ("Net PnL", "net_pnl"), ("Avg PnL", "avg_pnl")])}</div>
<div class="card"><h2>Rolling 20-Trade Risk Metrics</h2>{rolling_html}</div>
<div class="card"><h2>Drawdown Curve</h2>{self.table(drawdown_rows, [("Date", "date"), ("Equity", "equity"), ("Peak Equity", "peak_equity"), ("Drawdown $", "drawdown_dollars"), ("Drawdown %", "drawdown_pct")])}</div>
<div class="card"><h2>Equity Curve</h2>{self.table(equity_rows, [("Date", "date"), ("Equity", "equity"), ("PnL", "pnl"), ("Symbol", "symbol"), ("Exit Reason", "exit_reason")])}</div>
<div class="card"><h2>Best Trades</h2>{self.table(best_rows, [("Symbol", "symbol"), ("Entry", "entry_date"), ("Exit", "exit_date"), ("Signal", "signal"), ("Regime", "regime"), ("PnL", "pnl"), ("PnL %", "pnl_pct"), ("Net PnL", "net_pnl"), ("Exit Reason", "exit_reason"), ("Rank", "rank_score")])}</div>
<div class="card"><h2>Worst Trades</h2>{self.table(worst_rows, [("Symbol", "symbol"), ("Entry", "entry_date"), ("Exit", "exit_date"), ("Signal", "signal"), ("Regime", "regime"), ("PnL", "pnl"), ("PnL %", "pnl_pct"), ("Net PnL", "net_pnl"), ("Exit Reason", "exit_reason"), ("Rank", "rank_score")])}</div>
<div class="card"><h2>Rejected Trades</h2>{self.table(rejected_rows, [("Symbol", "symbol"), ("Entry", "entry_date"), ("Signal", "signal"), ("Strategy", "strategy"), ("Entry Price", "entry_price"), ("Contracts", "contracts"), ("Reason", "reason"), ("Rank", "rank_score"), ("Score", "option_score")])}</div>
<div class="card"><h2>Trade Log</h2>{self.table(all_trade_rows, [
("Symbol", "symbol"), ("Entry", "entry_date"), ("Exit", "exit_date"),
("Signal", "signal"), ("Regime", "regime"), ("Strategy", "strategy"),
("Strike", "strike"), ("Expiry", "expiry"), ("Option Symbol", "option_symbol"),
("Entry Source", "entry_source"), ("Exit Source", "exit_source"),
("Entry Price", "entry_price"), ("Exit Price", "exit_price"),
("Position Size", "position_size"), ("Initial Risk", "initial_risk"),
("R Multiple", "r_multiple"), ("Delta", "delta"), ("Gamma", "gamma"),
("Theta", "theta"), ("Vega", "vega"), ("Vol", "vol"), ("POP", "pop"),
("Distribution Obs.", "distribution_observations"),
("Historical VaR 95", "historical_var_95"),
("Historical ES 95", "historical_es_95"),
("Parametric VaR 95", "parametric_var_95"),
("Parametric ES 95", "parametric_es_95"),
("Historical VaR 99", "historical_var_99"),
("Historical ES 99", "historical_es_99"),
("Downside Deviation", "downside_deviation"),
("Skewness", "skewness"), ("Excess Kurtosis", "excess_kurtosis"),
("P(Large Loss)", "probability_large_loss"),
("P(Severe Loss)", "probability_severe_loss"),
("P(Critical Loss)", "probability_critical_loss"),
("Drawdown-at-Risk", "drawdown_at_risk"),
("Expected DD Shortfall", "expected_drawdown_shortfall"),
("Ulcer Index", "ulcer_index_tail"), ("Pain Index", "pain_index"),
("Omega", "omega_ratio_tail"), ("Sortino", "sortino_ratio_tail"),
("Gain-to-Pain", "gain_to_pain_ratio"),
("Tail Risk Score", "tail_risk_score"),
("Tail Risk Grade", "tail_risk_grade"),
("Tail Severity", "tail_risk_severity"),
("Distribution Approved", "distribution_risk_allowed"),
("Contracts", "contracts"), ("Net PnL", "net_pnl"),
("Hold Days", "days_held"), ("Exit Reason", "exit_reason"),
("Rank", "rank_score")
])}</div>
</body>
</html>
"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(html)
        return path
