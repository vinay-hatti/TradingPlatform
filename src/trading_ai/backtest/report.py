from pathlib import Path
from collections import defaultdict, Counter
from html import escape
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
            "tail_risk_grade": escape(
                str(
                    pick(
                        "tail_risk_grade",
                        "tail_risk_grade",
                        "N/A",
                    )
                    or "N/A"
                )
            ),
            "tail_risk_severity": escape(severity),
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
    # Phase 4 risk-surface and sensitivity helpers
    # ------------------------------------------------------------
    def risk_surface_profile(self, item):
        """Return a valid Phase 4 RiskSurfaceProfile from direct or metadata storage."""
        profile = self.val(item, "risk_surface_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("risk_surface_profile")
        if profile is None:
            return None
        return profile if bool(self.val(profile, "valid", False)) else None

    def risk_surface_values(self, item):
        profile = self.risk_surface_profile(item)

        def pick(direct_name, profile_name=None, default=None):
            value = self.val(item, direct_name, None)
            if value is not None:
                return value
            if profile is not None:
                return self.val(profile, profile_name or direct_name, default)
            return default

        available = bool(
            profile is not None
            or self.val(item, "risk_surface_point_count", None) is not None
            or self.val(item, "risk_surface_score", None) is not None
        )
        if not available:
            return {
                "available": False, "point_count": "N/A", "worst_case_pnl": "N/A",
                "best_case_pnl": "N/A", "base_case_pnl": "N/A",
                "maximum_loss_pct": "N/A", "maximum_gain_pct": "N/A",
                "worst_price_shock": "N/A", "worst_volatility_shock": "N/A",
                "worst_time_offset": "N/A", "delta_gamma_error": "N/A",
                "nonlinear_score": "N/A", "gamma_score": "N/A",
                "vega_score": "N/A", "theta_score": "N/A", "surface_score": "N/A",
                "surface_grade": "N/A", "severity": "N/A", "approved": "N/A",
                "approval_class": "neutral",
            }

        allowed = bool(pick("risk_surface_allowed", "allowed", False))
        severity = str(pick("risk_surface_severity", "risk_severity", "UNKNOWN") or "UNKNOWN").upper()
        approval_class = "positive" if allowed else ("negative" if severity in {"CRITICAL", "SEVERE"} else "warning")
        return {
            "available": True,
            "point_count": str(self.safe_int(pick("risk_surface_point_count", "point_count", 0))),
            "worst_case_pnl": self.optional_money(pick("risk_surface_worst_case_pnl", "worst_case_pnl")),
            "best_case_pnl": self.optional_money(pick("risk_surface_best_case_pnl", "best_case_pnl")),
            "base_case_pnl": self.optional_money(pick("risk_surface_base_case_pnl", "base_case_pnl")),
            "maximum_loss_pct": self.optional_pct(pick("risk_surface_maximum_loss_pct", "maximum_loss_pct_of_capital")),
            "maximum_gain_pct": self.optional_pct(pick("risk_surface_maximum_gain_pct", "maximum_gain_pct_of_capital")),
            "worst_price_shock": self.optional_pct(pick("risk_surface_worst_price_shock_pct", "worst_price_shock_pct")),
            "worst_volatility_shock": self.optional_pct(pick("risk_surface_worst_volatility_shock", "worst_volatility_shock")),
            "worst_time_offset": f"{self.safe_int(pick('risk_surface_worst_time_offset_days', 'worst_time_offset_days', 0))} days",
            "delta_gamma_error": self.optional_number(pick("risk_surface_delta_gamma_error_estimate", "delta_gamma_error_estimate"), 4),
            "nonlinear_score": self.optional_number(pick("risk_surface_nonlinear_exposure_score", "nonlinear_exposure_score"), 2),
            "gamma_score": self.optional_number(pick("risk_surface_gamma_risk_score", "gamma_risk_score"), 2),
            "vega_score": self.optional_number(pick("risk_surface_vega_risk_score", "vega_risk_score"), 2),
            "theta_score": self.optional_number(pick("risk_surface_theta_risk_score", "theta_risk_score"), 2),
            "surface_score": self.optional_number(pick("risk_surface_score", "surface_score"), 2),
            "surface_grade": str(pick("risk_surface_grade", "surface_grade", "N/A") or "N/A"),
            "severity": severity,
            "approved": "YES" if allowed else "NO",
            "approval_class": approval_class,
        }

    def aggregate_risk_surface_values(self, items):
        profiles = [self.risk_surface_profile(item) for item in items]
        profiles = [profile for profile in profiles if profile is not None]
        if not profiles:
            return {"available": False, "profile_count": 0}

        def avg(name):
            return sum(self.safe_float(self.val(p, name, 0.0)) for p in profiles) / len(profiles)

        severity_order = ["CRITICAL", "SEVERE", "MODERATE", "LOW", "UNKNOWN"]
        severities = Counter(str(self.val(p, "risk_severity", "UNKNOWN") or "UNKNOWN").upper() for p in profiles)
        worst_severity = next((s for s in severity_order if severities.get(s)), "UNKNOWN")
        worst_profile = min(profiles, key=lambda p: self.safe_float(self.val(p, "worst_case_pnl", 0.0)))
        return {
            "available": True,
            "profile_count": len(profiles),
            "approved_count": sum(bool(self.val(p, "allowed", False)) for p in profiles),
            "approval_rate": sum(bool(self.val(p, "allowed", False)) for p in profiles) / len(profiles),
            "aggregate_worst_case_pnl": sum(self.safe_float(self.val(p, "worst_case_pnl", 0.0)) for p in profiles),
            "aggregate_best_case_pnl": sum(self.safe_float(self.val(p, "best_case_pnl", 0.0)) for p in profiles),
            "average_surface_score": avg("surface_score"),
            "average_gamma_score": avg("gamma_risk_score"),
            "average_vega_score": avg("vega_risk_score"),
            "average_theta_score": avg("theta_risk_score"),
            "average_nonlinear_score": avg("nonlinear_exposure_score"),
            "worst_severity": worst_severity,
            "largest_surface_loss_symbol": str(self.val(worst_profile, "symbol", "UNKNOWN")),
            "largest_surface_loss": self.safe_float(self.val(worst_profile, "worst_case_pnl", 0.0)),
        }

    def risk_surface_summary_html(self, items):
        summary = self.aggregate_risk_surface_values(items)
        if not summary["available"]:
            return """
<div class="card"><h2>Risk Surfaces &amp; Sensitivity Analytics</h2>
<p class="section-note">No valid Phase 4 risk-surface profiles are attached to these trades.</p></div>
"""
        return f"""
<div class="card"><h2>Risk Surfaces &amp; Sensitivity Analytics</h2>
<div class="metric"><strong>Profiles</strong>{summary['profile_count']}</div>
<div class="metric"><strong>Approved</strong>{summary['approved_count']}</div>
<div class="metric"><strong>Approval Rate</strong>{self.pct(summary['approval_rate'])}</div>
<div class="metric"><strong>Aggregate Worst-Case P/L</strong>{self.money(summary['aggregate_worst_case_pnl'])}</div>
<div class="metric"><strong>Aggregate Best-Case P/L</strong>{self.money(summary['aggregate_best_case_pnl'])}</div>
<div class="metric"><strong>Average Surface Score</strong>{summary['average_surface_score']:.2f}</div>
<div class="metric"><strong>Average Gamma Score</strong>{summary['average_gamma_score']:.2f}</div>
<div class="metric"><strong>Average Vega Score</strong>{summary['average_vega_score']:.2f}</div>
<div class="metric"><strong>Average Theta Score</strong>{summary['average_theta_score']:.2f}</div>
<div class="metric"><strong>Average Nonlinear Score</strong>{summary['average_nonlinear_score']:.2f}</div>
<div class="metric"><strong>Worst Severity</strong>{summary['worst_severity']}</div>
<div class="metric"><strong>Largest Surface Loss</strong>{summary['largest_surface_loss_symbol']} {self.money(summary['largest_surface_loss'])}</div>
</div>
"""

    def risk_surface_attribution_rows(self, profile):
        if profile is None:
            return []
        rows = []
        for item in self.val(profile, "attributions", []) or []:
            pnl = self.safe_float(self.val(item, "pnl", 0.0))
            rows.append({
                "factor": str(self.val(item, "factor", "UNKNOWN")),
                "pnl": self.money(pnl),
                "contribution": self.pct(self.val(item, "contribution_pct", 0.0)),
                "direction": "ADVERSE" if bool(self.val(item, "adverse", pnl < 0.0)) else "FAVORABLE",
                "class": "negative" if pnl < 0.0 else "positive",
            })
        return rows

    def risk_surface_heatmap_html(self, profile, time_offset_days=None):
        if profile is None:
            return "<p class='section-note'>Risk surface unavailable.</p>"
        points = list(self.val(profile, "points", []) or [])
        if not points:
            return "<p class='section-note'>Risk surface contains no points.</p>"
        offsets = sorted({self.safe_int(self.val(p, "time_offset_days", 0)) for p in points})
        selected = offsets[0] if time_offset_days is None else min(offsets, key=lambda value: abs(value - int(time_offset_days)))
        subset = [p for p in points if self.safe_int(self.val(p, "time_offset_days", 0)) == selected]
        price_shocks = sorted({self.safe_float(self.val(p, "price_shock_pct", 0.0)) for p in subset})
        vol_shocks = sorted({self.safe_float(self.val(p, "volatility_shock", 0.0)) for p in subset})
        lookup = {(self.safe_float(self.val(p, "price_shock_pct", 0.0)), self.safe_float(self.val(p, "volatility_shock", 0.0))): self.safe_float(self.val(p, "approximated_pnl", 0.0)) for p in subset}
        values = list(lookup.values()) or [0.0]
        scale = max(abs(min(values)), abs(max(values)), 1.0)

        def cell_style(value):
            intensity = min(abs(value) / scale, 1.0)
            if value < 0:
                return f"background:rgba(198,40,40,{0.12 + 0.55 * intensity:.3f});"
            if value > 0:
                return f"background:rgba(46,125,50,{0.12 + 0.55 * intensity:.3f});"
            return "background:#f5f5f5;"

        html = f"<h3>{self.val(profile, 'symbol', '')} {self.val(profile, 'strategy', '')} — P/L Heatmap at +{selected} Days</h3>"
        html += "<div class='heatmap-wrap'><table class='heatmap'><thead><tr><th>Price Shock / IV Shock</th>"
        for vol in vol_shocks:
            html += f"<th>{self.pct(vol)}</th>"
        html += "</tr></thead><tbody>"
        for price in price_shocks:
            html += f"<tr><th>{self.pct(price)}</th>"
            for vol in vol_shocks:
                value = lookup.get((price, vol), 0.0)
                html += f"<td style='{cell_style(value)}'>{self.money(value)}</td>"
            html += "</tr>"
        html += "</tbody></table></div>"
        return html

    def risk_surface_details_html(self, items, limit=5):
        profiles = [self.risk_surface_profile(item) for item in items]
        profiles = [profile for profile in profiles if profile is not None][:limit]
        if not profiles:
            return ""
        sections = []
        for profile in profiles:
            values = self.risk_surface_values(profile)
            attribution = self.table(
                self.risk_surface_attribution_rows(profile),
                [("Factor", "factor"), ("P/L", "pnl"), ("Contribution", "contribution"), ("Direction", "direction")],
                empty="No Greek attribution is available.",
            )
            offsets = sorted({self.safe_int(self.val(p, "time_offset_days", 0)) for p in (self.val(profile, "points", []) or [])})
            heatmaps = self.risk_surface_heatmap_html(profile, offsets[0] if offsets else 0)
            if len(offsets) > 1:
                heatmaps += self.risk_surface_heatmap_html(profile, offsets[-1])
            sections.append(f"""
<div class="card"><h2>Risk Surface — {self.val(profile, 'symbol', '')} {self.val(profile, 'strategy', '')}</h2>
<div class="metric"><strong>Points</strong>{values['point_count']}</div>
<div class="metric"><strong>Worst Case</strong>{values['worst_case_pnl']}</div>
<div class="metric"><strong>Best Case</strong>{values['best_case_pnl']}</div>
<div class="metric"><strong>Maximum Loss</strong>{values['maximum_loss_pct']}</div>
<div class="metric"><strong>Surface Score</strong>{values['surface_score']}</div>
<div class="metric"><strong>Grade</strong>{values['surface_grade']}</div>
<div class="metric"><strong>Severity</strong>{values['severity']}</div>
<div class="metric"><strong>Approved</strong><span class="{values['approval_class']}">{values['approved']}</span></div>
<h3>Worst-Point Greek Attribution</h3>{attribution}{heatmaps}</div>
""")
        return "".join(sections)

    def portfolio_risk_surface_profile(self, items):
        for item in items:
            profile=self.val(item, "portfolio_risk_surface_profile", None)
            if profile is None:
                metadata=self.val(item, "metadata", {}) or {}
                if isinstance(metadata, dict): profile=metadata.get("portfolio_risk_surface_profile")
            if profile is not None and bool(self.val(profile, "valid", False)): return profile
        return None

    def portfolio_risk_surface_summary_html(self, items):
        profile=self.portfolio_risk_surface_profile(items)
        if profile is None:
            return "<div class='card'><h2>Portfolio Risk Surface</h2><p class='section-note'>No valid portfolio risk-surface profile is attached.</p></div>"
        contributions=self.val(profile, "position_contributions", []) or []
        rows=[]
        for item in contributions:
            rows.append({
                "symbol":self.val(item,"symbol",""),"strategy":self.val(item,"strategy",""),
                "capital":self.money(self.val(item,"capital_required",0.0)),
                "worst_pnl":self.money(self.val(item,"portfolio_worst_point_pnl",0.0)),
                "loss_pct":self.pct(self.val(item,"loss_contribution_pct",0.0)),
                "capital_pct":self.pct(self.val(item,"capital_weight_pct",0.0)),
            })
        table=self.table(rows,[("Symbol","symbol"),("Strategy","strategy"),("Allocated Capital","capital"),("Worst-Point P/L","worst_pnl"),("Loss Contribution","loss_pct"),("Capital Weight","capital_pct")])
        return f"""<div class='card'><h2>Portfolio Risk Surface</h2>
<div class='metric'><strong>Positions</strong>{self.val(profile,'position_count',0)}</div>
<div class='metric'><strong>Worst-Case P/L</strong>{self.money(self.val(profile,'worst_case_pnl',0.0))}</div>
<div class='metric'><strong>Maximum Loss / Capital</strong>{self.pct(self.val(profile,'maximum_loss_pct_of_capital',0.0))}</div>
<div class='metric'><strong>Allocated Exposure</strong>{self.pct(self.val(profile,'portfolio_exposure_pct',0.0))}</div>
<div class='metric'><strong>Diversification Benefit</strong>{self.pct(self.val(profile,'diversification_benefit',0.0))}</div>
<div class='metric'><strong>Loss Concentration</strong>{self.optional_number(self.val(profile,'loss_concentration_score',0.0),4)}</div>
<div class='metric'><strong>Effective Positions</strong>{self.optional_number(self.val(profile,'effective_position_count',0.0),2)}</div>
<div class='metric'><strong>Surface Score</strong>{self.optional_number(self.val(profile,'surface_score',0.0),2)}</div>
<div class='metric'><strong>Grade / Severity</strong>{self.val(profile,'surface_grade','N/A')} / {self.val(profile,'risk_severity','UNKNOWN')}</div>
<h3>Position Risk Attribution</h3>{table}</div>"""


    # ------------------------------------------------------------
    # Phase 5 portfolio-optimization reporting
    # ------------------------------------------------------------
    def portfolio_optimization_profile(self, items):
        """Return the first valid Phase 5 optimization profile attached to the report items."""
        for item in items or []:
            profile = self.val(item, "portfolio_optimization_profile", None)
            if profile is None:
                metadata = self.val(item, "metadata", {}) or {}
                if isinstance(metadata, dict):
                    profile = metadata.get("portfolio_optimization_profile")
            if profile is not None and bool(self.val(profile, "valid", False)):
                return profile
        return None

    def portfolio_optimization_summary_html(self, items):
        profile = self.portfolio_optimization_profile(items)
        if profile is None:
            return """
<div class="card">
<h2>Portfolio Risk Optimization</h2>
<p class="section-note">No valid Phase 5 portfolio-optimization profile is attached.</p>
</div>
"""

        allowed = bool(self.val(profile, "allowed", False))
        approval_class = "positive" if allowed else "negative"
        binding = self.val(profile, "binding_constraints", []) or []
        warnings = self.val(profile, "warnings", []) or []
        rejections = self.val(profile, "rejection_reasons", []) or []

        allocation_rows = []
        for allocation in self.val(profile, "allocations", []) or []:
            allocation_rows.append({
                "symbol": self.val(allocation, "symbol", ""),
                "strategy": self.val(allocation, "strategy", ""),
                "allocation": self.money(self.val(allocation, "allocation_dollars", 0.0)),
                "weight": self.pct(self.val(allocation, "allocation_weight_pct", 0.0)),
                "multiplier": self.optional_number(self.val(allocation, "allocation_multiplier", 0.0), 2),
                "expected_profit": self.money(self.val(allocation, "expected_profit", 0.0)),
                "maximum_loss": self.money(self.val(allocation, "maximum_loss", 0.0)),
                "expected_return": self.pct(self.val(allocation, "expected_return_pct", 0.0)),
                "marginal_score": self.optional_number(self.val(allocation, "marginal_objective_score", 0.0), 2),
                "ranking_score": self.optional_number(self.val(allocation, "ranking_score", 0.0), 2),
                "surface_score": self.optional_number(self.val(allocation, "surface_score", 0.0), 2),
                "sector": self.val(allocation, "sector", "UNKNOWN"),
                "correlation_group": self.val(allocation, "correlation_group", "UNKNOWN"),
            })

        allocation_table = self.table(
            allocation_rows,
            [
                ("Symbol", "symbol"), ("Strategy", "strategy"),
                ("Allocation", "allocation"), ("Weight", "weight"),
                ("Multiplier", "multiplier"), ("Expected Profit", "expected_profit"),
                ("Maximum Loss", "maximum_loss"), ("Expected Return", "expected_return"),
                ("Marginal Score", "marginal_score"), ("Ranking", "ranking_score"),
                ("Surface", "surface_score"), ("Sector", "sector"),
                ("Correlation Group", "correlation_group"),
            ],
            empty="No optimized allocations were selected.",
        )

        def group_table(values, label):
            rows = []
            for value in values or []:
                if isinstance(value, dict):
                    name = value.get("name", value.get("group", value.get(label.lower().replace(" ", "_"), "UNKNOWN")))
                    weight = value.get("weight_pct", value.get("weight", value.get("allocation_weight_pct", 0.0)))
                    dollars = value.get("allocation_dollars", value.get("capital", 0.0))
                else:
                    name = self.val(value, "name", self.val(value, "group", "UNKNOWN"))
                    weight = self.val(value, "weight_pct", self.val(value, "weight", 0.0))
                    dollars = self.val(value, "allocation_dollars", self.val(value, "capital", 0.0))
                rows.append({"group": name, "weight": self.pct(weight), "capital": self.money(dollars)})
            return self.table(rows, [(label, "group"), ("Weight", "weight"), ("Capital", "capital")])

        diagnostics = []
        if binding:
            diagnostics.append("<p class='warning'><strong>Binding Constraints:</strong> " + ", ".join(map(str, binding)) + "</p>")
        if warnings:
            diagnostics.append("<p class='warning'><strong>Warnings:</strong> " + ", ".join(map(str, warnings)) + "</p>")
        if rejections:
            diagnostics.append("<p class='negative'><strong>Rejections:</strong> " + ", ".join(map(str, rejections)) + "</p>")

        greek_totals = self.val(profile, "greek_totals", {}) or {}
        greek_rows = [{"greek": str(k).upper(), "value": self.optional_number(v, 4)} for k, v in greek_totals.items()]

        return f"""
<div class="card">
<h2>Portfolio Risk Optimization</h2>
<div class="metric"><strong>Candidates</strong>{self.val(profile, 'candidate_count', 0)}</div>
<div class="metric"><strong>Selected</strong>{self.val(profile, 'selected_count', 0)}</div>
<div class="metric"><strong>Allocated Capital</strong>{self.money(self.val(profile, 'total_allocated_capital', 0.0))}</div>
<div class="metric"><strong>Portfolio Exposure</strong>{self.pct(self.val(profile, 'portfolio_exposure_pct', 0.0))}</div>
<div class="metric"><strong>Reserve Cash</strong>{self.money(self.val(profile, 'reserve_cash', 0.0))}</div>
<div class="metric"><strong>Reserve Cash %</strong>{self.pct(self.val(profile, 'reserve_cash_pct', 0.0))}</div>
<div class="metric"><strong>Total Maximum Loss</strong>{self.money(self.val(profile, 'total_maximum_loss', 0.0))}</div>
<div class="metric"><strong>Total Risk</strong>{self.pct(self.val(profile, 'total_risk_pct', 0.0))}</div>
<div class="metric"><strong>Expected Portfolio Profit</strong>{self.money(self.val(profile, 'expected_portfolio_profit', 0.0))}</div>
<div class="metric"><strong>Expected Portfolio Return</strong>{self.pct(self.val(profile, 'expected_portfolio_return_pct', 0.0))}</div>
<div class="metric"><strong>Objective Score</strong>{self.optional_number(self.val(profile, 'objective_score', 0.0), 2)}</div>
<div class="metric"><strong>Grade</strong>{self.val(profile, 'optimization_grade', 'N/A')}</div>
<div class="metric"><strong>Severity</strong>{self.val(profile, 'risk_severity', 'UNKNOWN')}</div>
<div class="metric"><strong>Approved</strong><span class="{approval_class}">{'YES' if allowed else 'NO'}</span></div>
<div class="metric"><strong>Weighted Ranking</strong>{self.optional_number(self.val(profile, 'weighted_ranking_score', 0.0), 2)}</div>
<div class="metric"><strong>Weighted Strategy</strong>{self.optional_number(self.val(profile, 'weighted_strategy_score', 0.0), 2)}</div>
<div class="metric"><strong>Weighted Surface</strong>{self.optional_number(self.val(profile, 'weighted_surface_score', 0.0), 2)}</div>
<div class="metric"><strong>Diversification</strong>{self.optional_number(self.val(profile, 'diversification_score', 0.0), 2)}</div>
<div class="metric"><strong>Capital Efficiency</strong>{self.optional_number(self.val(profile, 'capital_efficiency_score', 0.0), 2)}</div>
<div class="metric"><strong>Concentration</strong>{self.optional_number(self.val(profile, 'concentration_score', 0.0), 2)}</div>
<div class="metric"><strong>Greek Utilization</strong>{self.optional_number(self.val(profile, 'greek_utilization_score', 0.0), 2)}</div>
{''.join(diagnostics)}
<h3>Optimized Allocations</h3>{allocation_table}
<h3>Sector Allocation</h3>{group_table(self.val(profile, 'sector_weights', []), 'Sector')}
<h3>Strategy Allocation</h3>{group_table(self.val(profile, 'strategy_weights', []), 'Strategy')}
<h3>Correlation-Group Allocation</h3>{group_table(self.val(profile, 'correlation_group_weights', []), 'Correlation Group')}
<h3>Portfolio Greeks</h3>{self.table(greek_rows, [('Greek', 'greek'), ('Total', 'value')])}
</div>
"""

    def portfolio_optimization_comparison_html(self, items):
        profile = self.portfolio_optimization_profile(items)
        if profile is None:
            return ""
        rows = []
        for item in items or []:
            legacy_selected = bool(self.val(item, "selected", False))
            optimized_selected = bool(self.val(item, "optimization_selected", False))
            status = str(self.val(item, "optimization_status", "UNAVAILABLE") or "UNAVAILABLE")
            rows.append({
                "symbol": self.val(item, "symbol", ""),
                "strategy": self.val(item, "strategy", ""),
                "legacy": "YES" if legacy_selected else "NO",
                "optimized": "YES" if optimized_selected else "NO",
                "status": status,
                "allocation": self.optional_money(self.val(item, "optimized_allocation_dollars", None)),
                "weight": self.optional_pct(self.val(item, "optimized_allocation_weight_pct", None)),
                "expected_profit": self.optional_money(self.val(item, "optimized_expected_profit", None)),
                "maximum_loss": self.optional_money(self.val(item, "optimized_maximum_loss", None)),
                "marginal_score": self.optional_number(self.val(item, "optimization_marginal_score", None), 2),
            })
        return f"""
<div class="card">
<h2>Legacy vs Optimized Portfolio Selection</h2>
<p class="section-note">Legacy selection remains authoritative unless apply_portfolio_optimization=True.</p>
{self.table(rows, [
    ('Symbol','symbol'), ('Strategy','strategy'), ('Legacy Selected','legacy'),
    ('Optimized Selected','optimized'), ('Optimization Status','status'),
    ('Optimized Allocation','allocation'), ('Optimized Weight','weight'),
    ('Optimized Expected Profit','expected_profit'), ('Optimized Maximum Loss','maximum_loss'),
    ('Marginal Score','marginal_score'),
])}
</div>
"""

    # ------------------------------------------------------------
    # Phase 5 optimization-frontier reporting
    # ------------------------------------------------------------
    def portfolio_optimization_frontier_profile(self, items):
        for item in items or []:
            profile = self.val(item, "portfolio_optimization_frontier_profile", None)
            if profile is None:
                metadata = self.val(item, "metadata", {}) or {}
                if isinstance(metadata, dict):
                    profile = metadata.get("portfolio_optimization_frontier_profile")
            if profile is not None and bool(self.val(profile, "valid", False)):
                return profile
        return None

    def portfolio_optimization_frontier_summary_html(self, items):
        profile = self.portfolio_optimization_frontier_profile(items)
        if profile is None:
            return """
<div class="card">
<h2>Portfolio Optimization Frontier &amp; Sensitivity</h2>
<p class="section-note">No valid Phase 5 optimization-frontier profile is attached.</p>
</div>
"""

        point_rows = []
        points = self.val(profile, "points", []) or []
        for point in sorted(
            points,
            key=lambda item: (
                not bool(self.val(item, "pareto_efficient", False)),
                -self.safe_float(self.val(item, "objective_score", 0.0)),
            ),
        ):
            point_rows.append({
                "point_id": self.val(point, "point_id", ""),
                "pareto": "YES" if bool(self.val(point, "pareto_efficient", False)) else "NO",
                "exposure_limit": self.pct(self.val(point, "maximum_exposure_pct", 0.0)),
                "risk_limit": self.pct(self.val(point, "maximum_risk_pct", 0.0)),
                "concentration_limit": self.pct(self.val(point, "maximum_concentration_pct", 0.0)),
                "selected": self.safe_int(self.val(point, "selected_count", 0)),
                "actual_exposure": self.pct(self.val(point, "exposure_pct", 0.0)),
                "actual_risk": self.pct(self.val(point, "risk_pct", 0.0)),
                "expected_return": self.pct(self.val(point, "expected_return_pct", 0.0)),
                "objective": self.optional_number(self.val(point, "objective_score", 0.0), 2),
                "diversification": self.optional_number(self.val(point, "diversification_score", 0.0), 2),
                "concentration": self.optional_number(self.val(point, "concentration_score", 0.0), 2),
                "grade": self.val(point, "optimization_grade", "N/A"),
            })

        point_table = self.table(
            point_rows,
            [
                ("Point", "point_id"), ("Pareto", "pareto"),
                ("Exposure Limit", "exposure_limit"), ("Risk Limit", "risk_limit"),
                ("Concentration Limit", "concentration_limit"), ("Selected", "selected"),
                ("Actual Exposure", "actual_exposure"), ("Actual Risk", "actual_risk"),
                ("Expected Return", "expected_return"), ("Objective", "objective"),
                ("Diversification", "diversification"), ("Concentration", "concentration"),
                ("Grade", "grade"),
            ],
            empty="No frontier points are available.",
        )

        warnings = self.val(profile, "warnings", []) or []
        warning_html = ""
        if warnings:
            warning_html = "<p class='warning'><strong>Warnings:</strong> " + ", ".join(map(str, warnings)) + "</p>"

        return f"""
<div class="card">
<h2>Portfolio Optimization Frontier &amp; Sensitivity</h2>
<div class="metric"><strong>Frontier Points</strong>{self.val(profile, 'point_count', 0)}</div>
<div class="metric"><strong>Valid Points</strong>{self.val(profile, 'valid_point_count', 0)}</div>
<div class="metric"><strong>Pareto-Efficient Points</strong>{self.val(profile, 'pareto_point_count', 0)}</div>
<div class="metric"><strong>Best Point</strong>{self.val(profile, 'best_point_id', 'N/A')}</div>
<div class="metric"><strong>Best Objective</strong>{self.optional_number(self.val(profile, 'best_objective_score', 0.0), 2)}</div>
<div class="metric"><strong>Best Expected Return</strong>{self.pct(self.val(profile, 'best_expected_return_pct', 0.0))}</div>
<div class="metric"><strong>Lowest Risk</strong>{self.pct(self.val(profile, 'lowest_risk_pct', 0.0))}</div>
<div class="metric"><strong>Highest Expected Return</strong>{self.pct(self.val(profile, 'highest_expected_return_pct', 0.0))}</div>
<div class="metric"><strong>Selection Stability</strong>{self.optional_number(self.val(profile, 'selection_stability_score', 0.0), 2)}</div>
<div class="metric"><strong>Allocation Stability</strong>{self.optional_number(self.val(profile, 'allocation_stability_score', 0.0), 2)}</div>
<div class="metric"><strong>Constraint Sensitivity</strong>{self.optional_number(self.val(profile, 'constraint_sensitivity_score', 0.0), 2)}</div>
<div class="metric"><strong>Frontier Score</strong>{self.optional_number(self.val(profile, 'frontier_score', 0.0), 2)}</div>
<div class="metric"><strong>Grade / Severity</strong>{self.val(profile, 'frontier_grade', 'N/A')} / {self.val(profile, 'risk_severity', 'UNKNOWN')}</div>
{warning_html}
<h3>Constraint Sweep and Efficient Frontier</h3>
{point_table}
</div>
"""


    def market_regime_summary_html(self, trades):
        rows=[]
        for item in trades:
            profile=self.val(item,"market_regime_integration_profile",None)
            if profile is None:
                meta=self.val(item,"metadata",{}) or {}; profile=meta.get("market_regime_integration_profile") if isinstance(meta,dict) else None
            if profile is None: continue
            rows.append({
                "symbol":self.val(item,"symbol",""), "strategy":self.val(item,"strategy",""),
                "current":self.val(profile,"current_regime","UNKNOWN"), "forecast":self.val(profile,"forecast_regime","UNKNOWN"),
                "portfolio":self.val(profile,"portfolio_regime","UNKNOWN"), "alignment":self.val(profile,"strategy_alignment","NEUTRAL"),
                "score":self.optional_number(self.val(profile,"regime_score",None)), "confidence":self.optional_number(self.val(profile,"confidence_score",None)),
                "strategy_adj":self.optional_number(self.val(profile,"strategy_score_adjustment",None)), "ranking_adj":self.optional_number(self.val(profile,"ranking_score_adjustment",None)),
                "allowed":"YES" if self.val(profile,"allowed",True) else "NO",
            })
        if not rows:
            return '<div class="card"><h2>Market Regime Analytics</h2><p class="section-note">No valid Phase 8 market-regime profiles are attached.</p></div>'
        table=self.table(rows,[("Symbol","symbol"),("Strategy","strategy"),("Current Regime","current"),("Forecast Regime","forecast"),("Portfolio Regime","portfolio"),("Alignment","alignment"),("Regime Score","score"),("Confidence","confidence"),("Strategy Adj.","strategy_adj"),("Ranking Adj.","ranking_adj"),("Allowed","allowed")])
        return '<div class="card"><h2>Market Regime Analytics &amp; Strategy Adaptation</h2>'+table+'</div>'

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


    def portfolio_optimization_recommendation_profile(self, items):
        for item in items:
            profile = self.val(item, "portfolio_optimization_recommendation", None)
            if profile is None:
                metadata = self.val(item, "metadata", {}) or {}
                if isinstance(metadata, dict):
                    profile = metadata.get("portfolio_optimization_recommendation")
            if profile is not None:
                return profile
        return None

    def portfolio_optimization_recommendation_summary_html(self, items):
        profile = self.portfolio_optimization_recommendation_profile(items)
        if profile is None or not bool(self.val(profile, "valid", False)):
            return """
<div class="card">
<h2>Recommended Portfolio Optimization Policy</h2>
<p class="section-note">No valid Phase 5 frontier policy recommendation is attached.</p>
</div>
"""
        allowed = bool(self.val(profile, "allowed", False))
        return f"""
<div class="card">
<h2>Recommended Portfolio Optimization Policy</h2>
<div class="metric"><strong>Source Frontier Point</strong>{self.val(profile, 'source_point_id', 'N/A')}</div>
<div class="metric"><strong>Maximum Exposure</strong>{self.pct(self.val(profile, 'maximum_portfolio_exposure_pct', 0.0))}</div>
<div class="metric"><strong>Maximum Total Risk</strong>{self.pct(self.val(profile, 'maximum_total_risk_pct', 0.0))}</div>
<div class="metric"><strong>Maximum Concentration</strong>{self.pct(self.val(profile, 'maximum_sector_weight_pct', 0.0))}</div>
<div class="metric"><strong>Expected Return</strong>{self.pct(self.val(profile, 'expected_return_pct', 0.0))}</div>
<div class="metric"><strong>Objective Score</strong>{self.optional_number(self.val(profile, 'objective_score', 0.0), 2)}</div>
<div class="metric"><strong>Confidence Score</strong>{self.optional_number(self.val(profile, 'confidence_score', 0.0), 2)}</div>
<div class="metric"><strong>Grade / Severity</strong>{self.val(profile, 'recommendation_grade', 'N/A')} / {self.val(profile, 'risk_severity', 'UNKNOWN')}</div>
<div class="metric"><strong>Approved</strong><span class="{'positive' if allowed else 'negative'}">{'YES' if allowed else 'NO'}</span></div>
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
                "risk_surface_points": self.risk_surface_values(t)["point_count"],
                "risk_surface_worst_case": self.risk_surface_values(t)["worst_case_pnl"],
                "risk_surface_best_case": self.risk_surface_values(t)["best_case_pnl"],
                "risk_surface_maximum_loss": self.risk_surface_values(t)["maximum_loss_pct"],
                "risk_surface_price_shock": self.risk_surface_values(t)["worst_price_shock"],
                "risk_surface_iv_shock": self.risk_surface_values(t)["worst_volatility_shock"],
                "risk_surface_time_offset": self.risk_surface_values(t)["worst_time_offset"],
                "risk_surface_gamma_score": self.risk_surface_values(t)["gamma_score"],
                "risk_surface_vega_score": self.risk_surface_values(t)["vega_score"],
                "risk_surface_theta_score": self.risk_surface_values(t)["theta_score"],
                "risk_surface_nonlinear_score": self.risk_surface_values(t)["nonlinear_score"],
                "risk_surface_score": self.risk_surface_values(t)["surface_score"],
                "risk_surface_grade": self.risk_surface_values(t)["surface_grade"],
                "risk_surface_severity": self.risk_surface_values(t)["severity"],
                "risk_surface_allowed": (
                    f"<span class='{self.risk_surface_values(t)['approval_class']}'>"
                    f"{self.risk_surface_values(t)['approved']}</span>"
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

    # ------------------------------------------------------------
    # Phase 6 probability-calibration reporting
    # ------------------------------------------------------------
    def probability_calibration_values(self, item):
        profile = self.val(item, "probability_calibration_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("probability_calibration_profile")
        raw = self.val(item, "raw_probability_of_profit", self.val(profile, "raw_probability", None))
        calibrated = self.val(item, "calibrated_probability_of_profit", self.val(profile, "calibrated_probability", None))
        available = bool(profile is not None and self.val(profile, "valid", False))
        return {
            "available": available, "raw": raw, "calibrated": calibrated,
            "adjustment": self.val(item, "probability_calibration_adjustment", self.val(profile, "adjustment", 0.0)),
            "segment": self.val(item, "probability_calibration_segment", self.val(profile, "segment_key", "UNAVAILABLE")),
            "version": self.val(item, "probability_calibration_model_version", self.val(profile, "model_version", "UNAVAILABLE")),
            "method": self.val(item, "probability_calibration_method", self.val(profile, "model_method", "IDENTITY")),
            "score": self.val(item, "probability_calibration_score", self.val(profile, "model_score", 0.0)),
            "grade": self.val(item, "probability_calibration_grade", self.val(profile, "model_grade", "N/A")),
            "severity": self.val(item, "probability_calibration_severity", self.val(profile, "model_severity", "UNKNOWN")),
            "allowed": self.val(item, "probability_calibration_allowed", self.val(profile, "allowed", True)),
            "ranking_adjustment": self.val(item, "calibration_ranking_adjustment", 0.0),
            "adjusted_ranking": self.val(item, "calibration_adjusted_ranking_score", self.val(item, "ranking_score", 0.0)),
        }

    def probability_calibration_summary_html(self, items):
        rows=[]
        for item in items:
            v=self.probability_calibration_values(item)
            if v["available"]:
                rows.append((item,v))
        if not rows:
            return """<div class="card"><h2>Probability Calibration</h2><p class="section-note">No valid Phase 6 probability-calibration profiles are attached.</p></div>"""
        avg_adj=sum(self.safe_float(v["adjustment"]) for _,v in rows)/len(rows)
        avg_score=sum(self.safe_float(v["score"]) for _,v in rows)/len(rows)
        table_rows=[]
        for item,v in rows:
            table_rows.append({
                "symbol": self.val(item,"symbol",""), "strategy": self.val(item,"strategy",""),
                "raw": self.optional_pct(v["raw"]), "calibrated": self.optional_pct(v["calibrated"]),
                "adjustment": self.optional_pct(v["adjustment"]), "segment": v["segment"],
                "method": v["method"], "version": v["version"], "score": self.optional_number(v["score"]),
                "grade": v["grade"], "severity": v["severity"],
                "rank_adj": self.optional_number(v["ranking_adjustment"]),
                "adjusted_rank": self.optional_number(v["adjusted_ranking"]),
            })
        return f"""<div class="card"><h2>Probability Calibration</h2>
<div class="metric"><strong>Calibrated Decisions</strong>{len(rows)}</div>
<div class="metric"><strong>Average Probability Adjustment</strong>{self.pct(avg_adj)}</div>
<div class="metric"><strong>Average Model Score</strong>{avg_score:.2f}</div>
{self.table(table_rows, [("Symbol","symbol"),("Strategy","strategy"),("Raw POP","raw"),("Calibrated POP","calibrated"),("Adjustment","adjustment"),("Segment","segment"),("Method","method"),("Version","version"),("Score","score"),("Grade","grade"),("Severity","severity"),("Ranking Δ","rank_adj"),("Adjusted Ranking","adjusted_rank")])}
</div>"""

    def probability_reliability_diagram_html(self, items):
        points=[]
        for item in items:
            profile=self.val(item,"probability_calibration_profile",None)
            if profile is None:
                metadata=self.val(item,"metadata",{}) or {}
                if isinstance(metadata,dict): profile=metadata.get("probability_calibration_profile")
            bins=self.val(profile,"metadata",{}).get("reliability_bins",[]) if profile is not None and isinstance(self.val(profile,"metadata",{}),dict) else []
            for b in bins or []:
                pred=self.safe_float(self.val(b,"mean_predicted_probability",self.val(b,"mean_probability",0.0)))
                obs=self.safe_float(self.val(b,"observed_frequency",self.val(b,"success_rate",0.0)))
                count=self.safe_int(self.val(b,"count",0))
                if count: points.append((pred,obs,count))
        if not points:
            return """<div class="card"><h2>Calibration Reliability</h2><p class="section-note">Reliability-bin data is unavailable for this report.</p></div>"""
        circles=''.join(f'<circle cx="{40+p*420:.2f}" cy="{460-o*420:.2f}" r="{max(3,min(10,3+c**0.5/3)):.2f}" fill="#333"><title>Predicted {p:.1%}; observed {o:.1%}; n={c}</title></circle>' for p,o,c in points)
        return f"""<div class="card"><h2>Calibration Reliability</h2><svg viewBox="0 0 500 500" width="100%" style="max-width:650px"><rect x="40" y="40" width="420" height="420" fill="#fafafa" stroke="#aaa"/><line x1="40" y1="460" x2="460" y2="40" stroke="#777" stroke-dasharray="6 4"/>{circles}<text x="210" y="492" font-size="13">Predicted probability</text><text x="8" y="250" font-size="13" transform="rotate(-90 8,250)">Observed frequency</text></svg></div>"""


    def probability_calibration_governance_summary_html(self, items):
        governance = drift = None
        for item in items:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                governance = governance or metadata.get("probability_calibration_governance_profile")
                drift = drift or metadata.get("probability_calibration_drift_profile")
        if governance is None and drift is None:
            return """<div class="card"><h2>Calibration Governance &amp; Drift</h2><p class="section-note">No Phase 6 governance or drift profile is attached.</p></div>"""
        parts=['<div class="card"><h2>Calibration Governance &amp; Drift</h2>']
        if drift is not None:
            parts.append(f'<div class="metric"><strong>Drift Score</strong>{self.safe_float(self.val(drift,"drift_score",0)):.2f}</div>')
            parts.append(f'<div class="metric"><strong>Drift Grade</strong>{self.val(drift,"drift_grade","N/A")}</div>')
            parts.append(f'<div class="metric"><strong>Drift Severity</strong>{self.val(drift,"drift_severity","UNKNOWN")}</div>')
            parts.append(f'<div class="metric"><strong>Probability PSI</strong>{self.safe_float(self.val(drift,"probability_psi",0)):.4f}</div>')
            parts.append(f'<div class="metric"><strong>Brier Change</strong>{self.safe_float(self.val(drift,"brier_change",0)):.6f}</div>')
            parts.append(f'<div class="metric"><strong>ECE Change</strong>{self.safe_float(self.val(drift,"ece_change",0)):.6f}</div>')
        if governance is not None:
            parts.append(f'<div class="metric"><strong>Champion</strong>{self.val(governance,"champion_version","N/A")}</div>')
            parts.append(f'<div class="metric"><strong>Challenger</strong>{self.val(governance,"challenger_version","N/A")}</div>')
            parts.append(f'<div class="metric"><strong>Recommendation</strong>{self.val(governance,"recommendation","N/A")}</div>')
            parts.append(f'<div class="metric"><strong>Promotion Eligible</strong>{"YES" if self.val(governance,"promotion_eligible",False) else "NO"}</div>')
            parts.append(f'<div class="metric"><strong>Governance Confidence</strong>{self.safe_float(self.val(governance,"confidence_score",0)):.2f}</div>')
            parts.append(f'<div class="metric"><strong>Brier Improvement</strong>{self.safe_float(self.val(governance,"brier_improvement",0)):.6f}</div>')
        parts.append('</div>')
        return ''.join(parts)


    # ------------------------------------------------------------
    # Phase 7 walk-forward validation reporting
    # ------------------------------------------------------------
    def walk_forward_profile(self, items):
        for item in items or []:
            profile = self.val(item, "walk_forward_profile", None)
            if profile is None:
                metadata = self.val(item, "metadata", {}) or {}
                if isinstance(metadata, dict):
                    profile = metadata.get("walk_forward_profile")
            if profile is not None:
                return profile
        return None

    def walk_forward_summary_html(self, items):
        profile = self.walk_forward_profile(items)
        if profile is None or not bool(self.val(profile, "valid", False)):
            return """<div class="card"><h2>Walk-Forward Validation</h2><p class="section-note">No valid Phase 7 walk-forward profile is attached.</p></div>"""
        raw = self.val(profile, "raw_profile", None) or profile
        results = list(self.val(raw, "results", []) or [])
        rows = []
        for result in results:
            rows.append({
                "window": self.val(result, "window_id", ""),
                "train": self.optional_number(self.val(result, "train_score", None)),
                "validation": self.optional_number(self.val(result, "validation_score", None)),
                "test": self.optional_number(self.val(result, "test_score", None)),
                "oos_return": self.optional_pct(self.val(result, "test_return", None)),
                "oos_sharpe": self.optional_number(self.val(result, "test_sharpe", None)),
                "drawdown": self.optional_pct(self.val(result, "test_max_drawdown_pct", None)),
                "degradation": self.optional_pct(self.val(result, "degradation_pct", None)),
                "parameters": str(self.val(result, "selected_parameters", {}) or {}),
            })
        chart_rows = [{"window": r.get("window", ""), "test_return": self.safe_float(self.val(x, "test_return", 0.0))} for r, x in zip(rows, results)]
        table_html = self.table(rows, [
            ("Window", "window"), ("Train Score", "train"),
            ("Validation Score", "validation"), ("Test Score", "test"),
            ("OOS Return", "oos_return"), ("OOS Sharpe", "oos_sharpe"),
            ("Max Drawdown", "drawdown"), ("Degradation", "degradation"),
            ("Selected Parameters", "parameters"),
        ], empty="No completed walk-forward windows.")
        chart = self.bar_chart(chart_rows, "window", "test_return", "Out-of-Sample Return by Window") if chart_rows else ""
        return f"""<div class="card"><h2>Walk-Forward Validation</h2>
<div class="metric"><strong>Windows</strong>{self.safe_int(self.val(profile, 'window_count', 0))}</div>
<div class="metric"><strong>Completed</strong>{self.safe_int(self.val(profile, 'completed_window_count', 0))}</div>
<div class="metric"><strong>Aggregate OOS Return</strong>{self.pct(self.val(profile, 'aggregate_oos_return', 0.0))}</div>
<div class="metric"><strong>Average OOS Sharpe</strong>{self.optional_number(self.val(profile, 'average_oos_sharpe', None))}</div>
<div class="metric"><strong>Worst OOS Drawdown</strong>{self.pct(self.val(profile, 'worst_oos_drawdown_pct', 0.0))}</div>
<div class="metric"><strong>Average Degradation</strong>{self.pct(self.val(profile, 'average_degradation_pct', 0.0))}</div>
<div class="metric"><strong>Parameter Stability</strong>{self.optional_number(self.val(profile, 'parameter_stability_score', None))}</div>
<div class="metric"><strong>Consistency</strong>{self.optional_number(self.val(profile, 'window_consistency_score', None))}</div>
<div class="metric"><strong>Walk-Forward Score</strong>{self.optional_number(self.val(profile, 'walk_forward_score', None))}</div>
<div class="metric"><strong>Grade</strong>{self.val(profile, 'walk_forward_grade', 'N/A')}</div>
<div class="metric"><strong>Severity</strong>{self.val(profile, 'risk_severity', 'UNKNOWN')}</div>
<div class="metric"><strong>Approved</strong>{'YES' if self.val(profile, 'allowed', False) else 'NO'}</div>
{chart}{table_html}</div>"""


    # ------------------------------------------------------------
    # Phase 7 walk-forward governance reporting (preserved)
    # ------------------------------------------------------------
    def walk_forward_governance_profile(self, items):
        for item in items or []:
            profile = self.val(item, "walk_forward_governance_profile", None)
            if profile is None:
                metadata = self.val(item, "metadata", {}) or {}
                if isinstance(metadata, dict):
                    profile = metadata.get("walk_forward_governance_profile")
            if profile is not None:
                return profile
        return None

    def walk_forward_governance_summary_html(self, items):
        profile = self.walk_forward_governance_profile(items)
        if profile is None or not bool(self.val(profile, "valid", False)):
            return """<div class="card"><h2>Walk-Forward Parameter Governance</h2><p class="section-note">No valid Phase 7 walk-forward governance profile is attached.</p></div>"""
        rejection_text = ", ".join(self.val(profile, "rejection_reasons", []) or []) or "-"
        warning_text = ", ".join(self.val(profile, "warnings", []) or []) or "-"
        return f"""<div class="card"><h2>Walk-Forward Parameter Governance</h2>
<div class="metric"><strong>Champion Version</strong>{self.val(profile, 'champion_version', 'UNAVAILABLE')}</div>
<div class="metric"><strong>Challenger Version</strong>{self.val(profile, 'challenger_version', 'UNAVAILABLE')}</div>
<div class="metric"><strong>Recommendation</strong>{self.val(profile, 'recommendation', 'RETAIN_CHAMPION')}</div>
<div class="metric"><strong>Champion Score</strong>{self.optional_number(self.val(profile, 'champion_score', None))}</div>
<div class="metric"><strong>Challenger Score</strong>{self.optional_number(self.val(profile, 'challenger_score', None))}</div>
<div class="metric"><strong>Score Improvement</strong>{self.optional_number(self.val(profile, 'score_improvement', None))}</div>
<div class="metric"><strong>OOS Return Improvement</strong>{self.optional_pct(self.val(profile, 'oos_return_improvement', None))}</div>
<div class="metric"><strong>Sharpe Improvement</strong>{self.optional_number(self.val(profile, 'sharpe_improvement', None))}</div>
<div class="metric"><strong>Drawdown Deterioration</strong>{self.optional_pct(self.val(profile, 'drawdown_deterioration_pct', None))}</div>
<div class="metric"><strong>Parameter Stability</strong>{self.optional_number(self.val(self.val(profile, 'challenger_profile', None), 'parameter_stability_score', None))}</div>
<div class="metric"><strong>Promotion Eligible</strong>{'YES' if self.val(profile, 'promotion_eligible', False) else 'NO'}</div>
<div class="metric"><strong>Promotion Applied</strong>{'YES' if self.val(profile, 'promotion_applied', False) else 'NO'}</div>
<div class="metric"><strong>Confidence</strong>{self.optional_number(self.val(profile, 'confidence_score', None))}</div>
<div class="metric"><strong>Grade</strong>{self.val(profile, 'governance_grade', 'N/A')}</div>
<div class="metric"><strong>Severity</strong>{self.val(profile, 'risk_severity', 'UNKNOWN')}</div>
<p class="section-note"><strong>Warnings:</strong> {warning_text}</p>
<p class="section-note"><strong>Rejections:</strong> {rejection_text}</p></div>"""



    # ------------------------------------------------------------
    # Phase 8 market-regime governance and drift reporting
    # ------------------------------------------------------------
    def market_regime_governance_profile(self, items):
        for item in items or []:
            profile = self.val(item, "market_regime_governance_profile", None)
            if profile is None:
                metadata = self.val(item, "metadata", {}) or {}
                if isinstance(metadata, dict):
                    profile = metadata.get("market_regime_governance_profile")
            if profile is not None:
                return profile
        return None

    def market_regime_governance_summary_html(self, items):
        profile = self.market_regime_governance_profile(items)
        if profile is None or not bool(self.val(profile, "valid", False)):
            return """<div class="card"><h2>Market Regime Model Governance &amp; Drift</h2><p class="section-note">No valid Phase 8 market-regime governance profile is attached.</p></div>"""
        drift = self.val(profile, "drift_profile", None)
        warning_text = ", ".join(self.val(profile, "warnings", []) or []) or "-"
        rejection_text = ", ".join(self.val(profile, "rejection_reasons", []) or []) or "-"
        return f"""<div class="card"><h2>Market Regime Model Governance &amp; Drift</h2>
<div class="metric"><strong>Champion Version</strong>{self.val(profile, 'champion_version', 'UNAVAILABLE')}</div>
<div class="metric"><strong>Challenger Version</strong>{self.val(profile, 'challenger_version', 'UNAVAILABLE')}</div>
<div class="metric"><strong>Recommendation</strong>{self.val(profile, 'recommendation', 'RETAIN_CHAMPION')}</div>
<div class="metric"><strong>Detection Accuracy Improvement</strong>{self.optional_pct(self.val(profile, 'accuracy_improvement', None))}</div>
<div class="metric"><strong>Forecast Accuracy Improvement</strong>{self.optional_pct(self.val(profile, 'forecast_accuracy_improvement', None))}</div>
<div class="metric"><strong>Transition F1 Improvement</strong>{self.optional_number(self.val(profile, 'transition_f1_improvement', None), digits=4)}</div>
<div class="metric"><strong>Critical FP Deterioration</strong>{self.optional_pct(self.val(profile, 'critical_false_positive_deterioration', None))}</div>
<div class="metric"><strong>Promotion Eligible</strong>{'YES' if self.val(profile, 'promotion_eligible', False) else 'NO'}</div>
<div class="metric"><strong>Promotion Applied</strong>{'YES' if self.val(profile, 'promotion_applied', False) else 'NO'}</div>
<div class="metric"><strong>Governance Confidence</strong>{self.optional_number(self.val(profile, 'confidence_score', None))}</div>
<div class="metric"><strong>Governance Grade</strong>{self.val(profile, 'governance_grade', 'N/A')}</div>
<div class="metric"><strong>Severity</strong>{self.val(profile, 'risk_severity', 'UNKNOWN')}</div>
<div class="metric"><strong>Regime PSI</strong>{self.optional_number(self.val(drift, 'regime_population_stability_index', None), digits=4)}</div>
<div class="metric"><strong>Drift Score</strong>{self.optional_number(self.val(drift, 'drift_score', None))}</div>
<div class="metric"><strong>Drift Grade</strong>{self.val(drift, 'drift_grade', 'N/A')}</div>
<div class="metric"><strong>Drift Severity</strong>{self.val(drift, 'drift_severity', 'UNKNOWN')}</div>
<p class="section-note"><strong>Warnings:</strong> {warning_text}</p>
<p class="section-note"><strong>Rejections:</strong> {rejection_text}</p></div>"""

    # ------------------------------------------------------------
    # Phase 9 Step 5 execution-governance reporting
    # ------------------------------------------------------------
    def execution_governance_integration_profile(self, item):
        profile = self.val(item, "execution_governance_integration_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("execution_governance_integration_profile")
        return profile

    def execution_governance_profile(self, item):
        integration = self.execution_governance_integration_profile(item)
        profile = self.val(item, "execution_governance_profile", None)
        if profile is None and integration is not None:
            profile = self.val(integration, "execution_governance_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("execution_governance_profile")
        return profile

    def execution_route_registry_profile(self, item):
        integration = self.execution_governance_integration_profile(item)
        profile = self.val(item, "execution_route_registry_profile", None)
        if profile is None and integration is not None:
            profile = self.val(integration, "execution_route_registry_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("execution_route_registry_profile")
        return profile

    def execution_champion_challenger_profile(self, item):
        integration = self.execution_governance_integration_profile(item)
        profile = self.val(item, "execution_champion_challenger_profile", None)
        if profile is None and integration is not None:
            profile = self.val(integration, "execution_champion_challenger_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("execution_champion_challenger_profile")
        return profile

    def _first_available_profile(self, items, resolver):
        for item in items or []:
            profile = resolver(item)
            if profile is not None:
                return profile
        return None

    def execution_governance_summary_html(self, items):
        integration = self._first_available_profile(items, self.execution_governance_integration_profile)
        governance = self._first_available_profile(items, self.execution_governance_profile)
        registry = self._first_available_profile(items, self.execution_route_registry_profile)
        comparison = self._first_available_profile(items, self.execution_champion_challenger_profile)

        if all(profile is None for profile in (integration, governance, registry, comparison)):
            return """<div class="card"><h2>Execution Governance</h2><p class="section-note">No valid Phase 9 Step 5 execution-governance profile is attached.</p></div>"""

        valid = bool(self.val(integration, "valid", self.val(governance, "valid", False)))
        allowed = bool(self.val(integration, "allowed", self.val(governance, "allowed", True)))
        score = self.val(integration, "governance_score", self.val(governance, "governance_score", None))
        grade = self.val(integration, "governance_grade", self.val(governance, "governance_grade", "N/A"))
        severity = str(self.val(integration, "governance_severity", self.val(governance, "drift_severity", "UNKNOWN")) or "UNKNOWN").upper()
        recommendation = self.val(integration, "governance_recommendation", self.val(governance, "recommendation", "UNAVAILABLE"))
        aggregate_psi = self.val(integration, "aggregate_psi", self.val(governance, "aggregate_psi", None))
        maximum_psi = self.val(integration, "maximum_metric_psi", self.val(governance, "maximum_metric_psi", None))
        deteriorated = self.val(integration, "deteriorated_metric_count", self.val(governance, "deteriorated_metric_count", 0))
        warnings = list(self.val(integration, "warnings", ()) or ()) + list(self.val(governance, "warnings", ()) or ())
        rejections = list(self.val(integration, "rejection_reasons", ()) or ()) + list(self.val(governance, "rejection_reasons", ()) or ())

        diagnostics = ""
        if warnings:
            diagnostics += "<p class='warning'><strong>Warnings:</strong> " + escape(", ".join(dict.fromkeys(map(str, warnings)))) + "</p>"
        if rejections:
            diagnostics += "<p class='negative'><strong>Rejections:</strong> " + escape(", ".join(dict.fromkeys(map(str, rejections)))) + "</p>"

        approval_class = "positive" if allowed else ("negative" if severity in {"SEVERE", "CRITICAL"} else "warning")
        route_promotion = bool(self.val(integration, "route_promotion_recommended", self.val(comparison, "allowed", False)))
        return f"""
<div class="card"><h2>Execution Governance</h2>
<div class="metric"><strong>Profile Valid</strong>{'YES' if valid else 'NO'}</div>
<div class="metric"><strong>Governance Score</strong>{self.optional_number(score, 2)}</div>
<div class="metric"><strong>Grade</strong>{escape(str(grade or 'N/A'))}</div>
<div class="metric"><strong>Severity</strong>{escape(severity)}</div>
<div class="metric"><strong>Allowed</strong><span class="{approval_class}">{'YES' if allowed else 'NO'}</span></div>
<div class="metric"><strong>Recommendation</strong>{escape(str(recommendation or 'UNAVAILABLE'))}</div>
<div class="metric"><strong>Aggregate PSI</strong>{self.optional_number(aggregate_psi, 4)}</div>
<div class="metric"><strong>Maximum Metric PSI</strong>{self.optional_number(maximum_psi, 4)}</div>
<div class="metric"><strong>Deteriorated Metrics</strong>{self.safe_int(deteriorated, 0)}</div>
<div class="metric"><strong>Registered Routes</strong>{self.safe_int(self.val(registry, 'route_count', self.val(integration, 'route_count', 0)), 0)}</div>
<div class="metric"><strong>Active Route</strong>{escape(str(self.val(registry, 'active_version', self.val(integration, 'active_route_version', 'UNAVAILABLE'))))}</div>
<div class="metric"><strong>Champion Route</strong>{escape(str(self.val(registry, 'champion_version', self.val(integration, 'champion_route_version', 'UNAVAILABLE'))))}</div>
<div class="metric"><strong>Promotion Recommended</strong>{'YES' if route_promotion else 'NO'}</div>
{diagnostics}</div>
"""

    def execution_governance_drift_html(self, items):
        profile = self._first_available_profile(items, self.execution_governance_profile)
        if profile is None:
            return ""

        metric_rows = []
        for metric in self.val(profile, "metric_profiles", ()) or ():
            metric_rows.append({
                "metric": escape(str(self.val(metric, "metric_name", "UNKNOWN"))),
                "baseline": self.optional_number(self.val(metric, "baseline_mean", None), 4),
                "current": self.optional_number(self.val(metric, "current_mean", None), 4),
                "relative": self.optional_pct(self.val(metric, "relative_change", None)),
                "shift": self.optional_number(self.val(metric, "standardized_shift", None), 4),
                "psi": self.optional_number(self.val(metric, "population_stability_index", None), 4),
                "score": self.optional_number(self.val(metric, "drift_score", None), 2),
                "grade": escape(str(self.val(metric, "drift_grade", "N/A"))),
                "severity": escape(str(self.val(metric, "drift_severity", "UNKNOWN"))),
                "deteriorated": "YES" if bool(self.val(metric, "deteriorated", False)) else "NO",
                "allowed": "YES" if bool(self.val(metric, "allowed", True)) else "NO",
            })

        segment_rows = []
        for segment in self.val(profile, "segment_profiles", ()) or ():
            segment_rows.append({
                "type": escape(str(self.val(segment, "segment_type", "UNKNOWN"))),
                "name": escape(str(self.val(segment, "segment_name", "UNKNOWN"))),
                "baseline": self.safe_int(self.val(segment, "baseline_observation_count", 0)),
                "current": self.safe_int(self.val(segment, "current_observation_count", 0)),
                "metrics": self.safe_int(self.val(segment, "metric_count", 0)),
                "psi": self.optional_number(self.val(segment, "aggregate_psi", None), 4),
                "maximum_psi": self.optional_number(self.val(segment, "maximum_psi", None), 4),
                "score": self.optional_number(self.val(segment, "drift_score", None), 2),
                "grade": escape(str(self.val(segment, "drift_grade", "N/A"))),
                "severity": escape(str(self.val(segment, "drift_severity", "UNKNOWN"))),
                "allowed": "YES" if bool(self.val(segment, "allowed", True)) else "NO",
            })

        return f"""
<div class="card"><h2>Execution Drift Monitoring &amp; Population Stability</h2>
<div class="metric"><strong>Baseline</strong>{escape(str(self.val(profile, 'baseline_name', 'UNAVAILABLE')))}</div>
<div class="metric"><strong>Current</strong>{escape(str(self.val(profile, 'current_name', 'UNAVAILABLE')))}</div>
<div class="metric"><strong>Baseline Observations</strong>{self.safe_int(self.val(profile, 'baseline_observation_count', 0))}</div>
<div class="metric"><strong>Current Observations</strong>{self.safe_int(self.val(profile, 'current_observation_count', 0))}</div>
<h3>Metric Drift and PSI</h3>
{self.table(metric_rows, [('Metric','metric'),('Baseline Mean','baseline'),('Current Mean','current'),('Relative Change','relative'),('Standardized Shift','shift'),('PSI','psi'),('Score','score'),('Grade','grade'),('Severity','severity'),('Deteriorated','deteriorated'),('Allowed','allowed')], empty='No metric-level execution drift profiles are available.')}
<h3>Venue and Broker Segment Drift</h3>
{self.table(segment_rows, [('Segment Type','type'),('Segment','name'),('Baseline Obs.','baseline'),('Current Obs.','current'),('Metrics','metrics'),('Aggregate PSI','psi'),('Maximum PSI','maximum_psi'),('Score','score'),('Grade','grade'),('Severity','severity'),('Allowed','allowed')], empty='No segment-level execution drift profiles are available.')}
</div>
"""

    def execution_route_registry_html(self, items):
        profile = self._first_available_profile(items, self.execution_route_registry_profile)
        if profile is None:
            return ""
        rows = []
        for route in self.val(profile, "versions", ()) or ():
            flags = []
            if bool(self.val(route, "active", False)): flags.append("ACTIVE")
            if bool(self.val(route, "champion", False)): flags.append("CHAMPION")
            if bool(self.val(route, "challenger", False)): flags.append("CHALLENGER")
            rows.append({
                "version": escape(str(self.val(route, "version", "UNAVAILABLE"))),
                "type": escape(str(self.val(route, "route_type", "UNKNOWN"))),
                "name": escape(str(self.val(route, "route_name", "UNKNOWN"))),
                "status": escape(str(self.val(route, "status", "REGISTERED"))),
                "role": ", ".join(flags) or "REGISTERED",
                "observations": self.safe_int(self.val(route, "observation_count", 0)),
                "route_score": self.optional_number(self.val(route, "route_score", None), 2),
                "shortfall": self.optional_number(self.val(route, "average_shortfall_bps", None), 4),
                "fill": self.optional_pct(self.val(route, "average_fill_ratio", None)),
                "latency": self.optional_number(self.val(route, "average_latency_seconds", None), 4),
                "spread": self.optional_number(self.val(route, "average_spread_bps", None), 4),
                "governance": self.optional_number(self.val(route, "governance_score", None), 2),
                "grade": escape(str(self.val(route, "governance_grade", "N/A"))),
                "allowed": "YES" if bool(self.val(route, "governance_allowed", True)) else "NO",
            })
        return f"""
<div class="card"><h2>Execution Route Registry</h2>
<div class="metric"><strong>Routes</strong>{self.safe_int(self.val(profile, 'route_count', 0))}</div>
<div class="metric"><strong>Active</strong>{escape(str(self.val(profile, 'active_version', 'UNAVAILABLE')))}</div>
<div class="metric"><strong>Champion</strong>{escape(str(self.val(profile, 'champion_version', 'UNAVAILABLE')))}</div>
<div class="metric"><strong>Challengers</strong>{escape(', '.join(map(str, self.val(profile, 'challenger_versions', ()) or ())) or 'NONE')}</div>
<div class="metric"><strong>Retired</strong>{escape(', '.join(map(str, self.val(profile, 'retired_versions', ()) or ())) or 'NONE')}</div>
<div class="metric"><strong>Audit Events</strong>{self.safe_int(self.val(profile, 'audit_event_count', 0))}</div>
{self.table(rows, [('Version','version'),('Type','type'),('Route','name'),('Status','status'),('Role','role'),('Observations','observations'),('Route Score','route_score'),('Shortfall bps','shortfall'),('Fill Ratio','fill'),('Latency sec.','latency'),('Spread bps','spread'),('Governance','governance'),('Grade','grade'),('Allowed','allowed')], empty='No route versions are registered.')}
</div>
"""

    def execution_champion_challenger_html(self, items):
        profile = self._first_available_profile(items, self.execution_champion_challenger_profile)
        if profile is None:
            return ""
        rows = []
        for metric in self.val(profile, "metric_comparisons", ()) or ():
            rows.append({
                "metric": escape(str(self.val(metric, "metric", "UNKNOWN"))),
                "champion": self.optional_number(self.val(metric, "champion_value", None), 4),
                "challenger": self.optional_number(self.val(metric, "challenger_value", None), 4),
                "change": self.optional_number(self.val(metric, "absolute_change", None), 4),
                "relative": self.optional_pct(self.val(metric, "relative_change", None)),
                "improvement": self.optional_number(self.val(metric, "improvement", None), 4),
                "favorable": "YES" if bool(self.val(metric, "favorable", False)) else "NO",
                "weighted": self.optional_number(self.val(metric, "weighted_score", None), 2),
                "severity": escape(str(self.val(metric, "severity", "UNKNOWN"))),
            })
        allowed = bool(self.val(profile, "allowed", False))
        return f"""
<div class="card"><h2>Champion–Challenger Routing Governance</h2>
<div class="metric"><strong>Champion</strong>{escape(str(self.val(profile, 'champion_version', 'UNAVAILABLE')))} — {escape(str(self.val(profile, 'champion_route_name', 'UNKNOWN')))}</div>
<div class="metric"><strong>Challenger</strong>{escape(str(self.val(profile, 'challenger_version', 'UNAVAILABLE')))} — {escape(str(self.val(profile, 'challenger_route_name', 'UNKNOWN')))}</div>
<div class="metric"><strong>Evaluation Score</strong>{self.optional_number(self.val(profile, 'evaluation_score', None), 2)}</div>
<div class="metric"><strong>Confidence</strong>{self.optional_number(self.val(profile, 'confidence_score', None), 2)}</div>
<div class="metric"><strong>Grade</strong>{escape(str(self.val(profile, 'evaluation_grade', 'N/A')))}</div>
<div class="metric"><strong>Severity</strong>{escape(str(self.val(profile, 'governance_severity', 'UNKNOWN')))}</div>
<div class="metric"><strong>Recommendation</strong>{escape(str(self.val(profile, 'recommendation', 'HOLD_CHAMPION')))}</div>
<div class="metric"><strong>Promotion Eligible</strong><span class="{'positive' if allowed else 'warning'}">{'YES' if allowed else 'NO'}</span></div>
<div class="metric"><strong>Promoted</strong>{'YES' if bool(self.val(profile, 'promoted', False)) else 'NO'}</div>
{self.table(rows, [('Metric','metric'),('Champion','champion'),('Challenger','challenger'),('Change','change'),('Relative','relative'),('Improvement','improvement'),('Favorable','favorable'),('Weighted Score','weighted'),('Severity','severity')], empty='No champion–challenger metric comparisons are available.')}
</div>
"""


    # ------------------------------------------------------------
    # Phase 10 adaptive strategy and ensemble intelligence reporting
    # ------------------------------------------------------------
    def phase10_integration_profile(self, item):
        # Return a Phase 10 integration profile from direct or metadata storage.
        profile = self.val(item, "phase10_decision_integration_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("phase10_decision_integration_profile")
        return profile

    def phase10_profiles(self, items):
        profiles = []
        seen = set()
        for item in items or []:
            profile = self.phase10_integration_profile(item)
            if profile is None:
                continue
            key = id(profile)
            if key not in seen:
                profiles.append(profile)
                seen.add(key)
        return profiles

    def phase10_adaptive_selection_html(self, items):
        profiles = self.phase10_profiles(items)
        if not profiles:
            return '<div class="card"><h2>Adaptive Strategy Selection</h2><p class="section-note">No valid Phase 10 adaptive-strategy integration profile is attached.</p></div>'
        rows=[]
        for profile in profiles:
            adaptive=self.val(profile,"adaptive_strategy_profile",None)
            rows.append({
                "symbol":escape(str(self.val(profile,"symbol",""))),
                "selected":escape(str(self.val(profile,"selected_strategy",self.val(adaptive,"selected_strategy","UNAVAILABLE")) or "UNAVAILABLE")),
                "score":self.optional_number(self.val(profile,"adaptive_score",self.val(adaptive,"selected_score",None))),
                "confidence":self.optional_number(self.val(profile,"adaptive_confidence_score",self.val(adaptive,"selection_confidence_score",None))),
                "weight":self.optional_pct(self.val(profile,"strategy_weight",None)),
                "grade":escape(str(self.val(profile,"grade",self.val(adaptive,"grade","N/A")))),
                "severity":escape(str(self.val(profile,"severity",self.val(adaptive,"severity","UNKNOWN")))),
                "allowed":"YES" if bool(self.val(profile,"allowed",False)) else "NO",
                "recommendation":escape(str(self.val(profile,"recommendation",self.val(adaptive,"recommendation","UNAVAILABLE")))),
            })
        return f'''<div class="card"><h2>Adaptive Strategy Selection</h2>
{self.table(rows,[("Symbol","symbol"),("Selected Strategy","selected"),("Adaptive Score","score"),("Confidence","confidence"),("Dynamic Weight","weight"),("Grade","grade"),("Severity","severity"),("Allowed","allowed"),("Recommendation","recommendation")])}</div>'''

    def phase10_ensemble_dashboard_html(self, items):
        profiles=self.phase10_profiles(items)
        ensemble_profiles=[self.val(p,"ensemble_decision_profile",None) for p in profiles]
        ensemble_profiles=[p for p in ensemble_profiles if p is not None]
        if not ensemble_profiles:
            return '<div class="card"><h2>Ensemble Decision Intelligence</h2><p class="section-note">No Phase 10 ensemble-decision profile is attached.</p></div>'
        summary=[]; strategy_rows=[]; component_rows=[]
        for ensemble in ensemble_profiles:
            summary.append({
                "symbol":escape(str(self.val(ensemble,"symbol",""))),
                "strategy":escape(str(self.val(ensemble,"selected_strategy","UNAVAILABLE") or "UNAVAILABLE")),
                "direction":escape(str(self.val(ensemble,"selected_direction","UNKNOWN") or "UNKNOWN")),
                "score":self.optional_number(self.val(ensemble,"ensemble_score",None)),
                "confidence":self.optional_number(self.val(ensemble,"meta_confidence_score",None)),
                "consensus":self.optional_pct(self.val(ensemble,"consensus_ratio",None)),
                "grade":escape(str(self.val(ensemble,"grade","N/A"))),
                "severity":escape(str(self.val(ensemble,"severity","UNKNOWN"))),
                "allowed":"YES" if bool(self.val(ensemble,"allowed",False)) else "NO",
            })
            for strategy in self.val(ensemble,"strategies",()) or ():
                strategy_rows.append({
                    "symbol":escape(str(self.val(strategy,"symbol",self.val(ensemble,"symbol","")))),
                    "strategy":escape(str(self.val(strategy,"strategy","UNKNOWN"))),
                    "direction":escape(str(self.val(strategy,"direction","UNKNOWN"))),
                    "score":self.optional_number(self.val(strategy,"ensemble_score",None)),
                    "confidence":self.optional_number(self.val(strategy,"meta_confidence_score",None)),
                    "consensus":self.optional_pct(self.val(strategy,"consensus_ratio",None)),
                    "dispersion":self.optional_number(self.val(strategy,"score_dispersion",None),4),
                    "components":self.safe_int(self.val(strategy,"component_count",0)),
                    "allowed_components":self.safe_int(self.val(strategy,"allowed_component_count",0)),
                    "allowed":"YES" if bool(self.val(strategy,"allowed",False)) else "NO",
                })
                for component in self.val(strategy,"components",()) or ():
                    component_rows.append({
                        "symbol":escape(str(self.val(strategy,"symbol",self.val(ensemble,"symbol","")))),
                        "strategy":escape(str(self.val(strategy,"strategy","UNKNOWN"))),
                        "component":escape(str(self.val(component,"name","UNKNOWN"))),
                        "direction":escape(str(self.val(component,"direction","UNKNOWN"))),
                        "score":self.optional_number(self.val(component,"score",None)),
                        "confidence":self.optional_number(self.val(component,"confidence_score",None)),
                        "weight":self.optional_pct(self.val(component,"weight",None)),
                        "weighted":self.optional_number(self.val(component,"weighted_score",None)),
                        "available":"YES" if bool(self.val(component,"available",False)) else "NO",
                        "allowed":"YES" if bool(self.val(component,"allowed",False)) else "NO",
                    })
        return f'''<div class="card"><h2>Ensemble Decision Intelligence</h2>
<h3>Ensemble Summary</h3>{self.table(summary,[("Symbol","symbol"),("Selected Strategy","strategy"),("Direction","direction"),("Ensemble Score","score"),("Meta Confidence","confidence"),("Consensus","consensus"),("Grade","grade"),("Severity","severity"),("Allowed","allowed")])}
<h3>Strategy Fusion Results</h3>{self.table(strategy_rows,[("Symbol","symbol"),("Strategy","strategy"),("Direction","direction"),("Score","score"),("Meta Confidence","confidence"),("Consensus","consensus"),("Dispersion","dispersion"),("Components","components"),("Allowed Components","allowed_components"),("Allowed","allowed")],empty="No ensemble strategy details are available.")}
<h3>Component Attribution</h3>{self.table(component_rows,[("Symbol","symbol"),("Strategy","strategy"),("Component","component"),("Direction","direction"),("Score","score"),("Confidence","confidence"),("Weight","weight"),("Weighted Score","weighted"),("Available","available"),("Allowed","allowed")],empty="No component-level attribution is available.")}</div>'''

    def phase10_learning_weights_html(self, items):
        profiles=self.phase10_profiles(items)
        weighting=next((self.val(p,"dynamic_strategy_weighting_profile",None) for p in profiles if self.val(p,"dynamic_strategy_weighting_profile",None) is not None),None)
        learning=[]
        for p in profiles:
            lp=self.val(p,"strategy_learning_profile",None)
            if lp is not None: learning.append(lp)
        if weighting is None and not learning:
            return '<div class="card"><h2>Strategy Learning &amp; Dynamic Weighting</h2><p class="section-note">No Phase 10 learning or dynamic-weighting profile is attached.</p></div>'
        learning_rows=[]
        for p in learning:
            learning_rows.append({
                "strategy":escape(str(self.val(p,"strategy","UNKNOWN"))),
                "observations":self.safe_int(self.val(p,"observation_count",0)),
                "effective":self.optional_number(self.val(p,"effective_sample_size",None)),
                "win_rate":self.optional_pct(self.val(p,"weighted_win_rate",None)),
                "return":self.optional_pct(self.val(p,"weighted_average_return",None)),
                "profit_factor":self.ratio(self.val(p,"profit_factor",None)),
                "drawdown":self.optional_pct(self.val(p,"maximum_drawdown_pct",None)),
                "performance":self.optional_number(self.val(p,"performance_score",None)),
                "stability":self.optional_number(self.val(p,"stability_score",None)),
                "confidence":self.optional_number(self.val(p,"confidence_score",None)),
                "allowed":"YES" if bool(self.val(p,"allowed",False)) else "NO",
            })
        weight_rows=[]
        candidates=self.val(weighting,"weights",None)
        if candidates is None: candidates=self.val(weighting,"strategies",())
        for w in candidates or ():
            weight_rows.append({
                "strategy":escape(str(self.val(w,"strategy","UNKNOWN"))),
                "prior":self.optional_pct(self.val(w,"prior_weight",None)),
                "performance":self.optional_number(self.val(w,"performance_component",None)),
                "stability":self.optional_number(self.val(w,"stability_component",None)),
                "recency":self.optional_number(self.val(w,"recency_component",None)),
                "raw":self.optional_number(self.val(w,"raw_weight",None),4),
                "normalized":self.optional_pct(self.val(w,"normalized_weight",None)),
                "confidence":self.optional_number(self.val(w,"confidence_score",None)),
                "allowed":"YES" if bool(self.val(w,"allowed",False)) else "NO",
            })
        return f'''<div class="card"><h2>Strategy Learning &amp; Dynamic Weighting</h2>
<div class="metric"><strong>Strategy Count</strong>{self.val(weighting,'strategy_count',len(weight_rows)) if weighting is not None else len(learning_rows)}</div>
<div class="metric"><strong>Weight Concentration</strong>{self.optional_number(self.val(weighting,'concentration_score',None),4) if weighting is not None else 'N/A'}</div>
<div class="metric"><strong>Effective Strategy Count</strong>{self.optional_number(self.val(weighting,'effective_strategy_count',None),2) if weighting is not None else 'N/A'}</div>
<h3>Learned Performance</h3>{self.table(learning_rows,[("Strategy","strategy"),("Observations","observations"),("Effective Sample","effective"),("Win Rate","win_rate"),("Average Return","return"),("Profit Factor","profit_factor"),("Max Drawdown","drawdown"),("Performance","performance"),("Stability","stability"),("Confidence","confidence"),("Allowed","allowed")],empty="No learned strategy profiles are available.")}
<h3>Dynamic Strategy Weights</h3>{self.table(weight_rows,[("Strategy","strategy"),("Prior Weight","prior"),("Performance","performance"),("Stability","stability"),("Recency","recency"),("Raw Weight","raw"),("Normalized Weight","normalized"),("Confidence","confidence"),("Allowed","allowed")],empty="No dynamic strategy weights are available.")}</div>'''

    def phase10_online_adaptation_html(self, items):
        profiles=self.phase10_profiles(items)
        adaptation=next((self.val(p,"online_adaptation_profile",None) for p in profiles if self.val(p,"online_adaptation_profile",None) is not None),None)
        registry=next((self.val(p,"learning_state_registry_profile",None) for p in profiles if self.val(p,"learning_state_registry_profile",None) is not None),None)
        promotion=next((self.val(p,"learning_state_promotion_profile",None) for p in profiles if self.val(p,"learning_state_promotion_profile",None) is not None),None)
        if adaptation is None and registry is None and promotion is None:
            return '<div class="card"><h2>Online Adaptation &amp; Learning-State Governance</h2><p class="section-note">No Phase 10 online-adaptation or learning-state profile is attached.</p></div>'
        update_rows=[]
        for u in self.val(adaptation,"updates",()) or ():
            update_rows.append({
                "strategy":escape(str(self.val(u,"strategy","UNKNOWN"))),
                "current":self.optional_pct(self.val(u,"current_weight",None)),
                "target":self.optional_pct(self.val(u,"target_weight",None)),
                "proposed":self.optional_pct(self.val(u,"proposed_weight",None)),
                "applied":self.optional_pct(self.val(u,"applied_weight",None)),
                "change":self.optional_pct(self.val(u,"absolute_change",None)),
                "score":self.optional_number(self.val(u,"update_score",None)),
                "grade":escape(str(self.val(u,"grade","N/A"))),
                "allowed":"YES" if bool(self.val(u,"allowed",False)) else "NO",
            })
        version_rows=[]
        for v in self.val(registry,"versions",()) or ():
            version_rows.append({
                "version":escape(str(self.val(v,"version",""))),
                "status":escape(str(self.val(v,"status","UNKNOWN"))),
                "score":self.optional_number(self.val(v,"adaptation_score",None)),
                "source":escape(str(self.val(v,"source_version","") or "")),
                "actor":escape(str(self.val(v,"actor","system"))),
                "reason":escape(str(self.val(v,"reason",""))),
                "created":escape(str(self.val(v,"created_at",""))),
            })
        return f'''<div class="card"><h2>Online Adaptation &amp; Learning-State Governance</h2>
<div class="metric"><strong>Adaptation Score</strong>{self.optional_number(self.val(adaptation,'adaptation_score',None))}</div>
<div class="metric"><strong>Applied Updates</strong>{self.val(adaptation,'applied_update_count',0)}</div>
<div class="metric"><strong>Total Absolute Change</strong>{self.optional_pct(self.val(adaptation,'total_absolute_change',None))}</div>
<div class="metric"><strong>Concentration Before / After</strong>{self.optional_number(self.val(adaptation,'concentration_before',None),4)} / {self.optional_number(self.val(adaptation,'concentration_after',None),4)}</div>
<div class="metric"><strong>Active State</strong>{escape(str(self.val(registry,'active_version','UNAVAILABLE') or 'UNAVAILABLE'))}</div>
<div class="metric"><strong>Champion State</strong>{escape(str(self.val(registry,'champion_version','UNAVAILABLE') or 'UNAVAILABLE'))}</div>
<div class="metric"><strong>Challenger State</strong>{escape(str(self.val(registry,'challenger_version','UNAVAILABLE') or 'UNAVAILABLE'))}</div>
<div class="metric"><strong>Promotion Recommendation</strong>{escape(str(self.val(promotion,'recommendation','UNAVAILABLE') or 'UNAVAILABLE'))}</div>
<div class="metric"><strong>Promotion Score</strong>{self.optional_number(self.val(promotion,'promotion_score',None))}</div>
<div class="metric"><strong>Promotion Allowed</strong>{'YES' if bool(self.val(promotion,'allowed',False)) else 'NO'}</div>
<h3>Strategy Weight Updates</h3>{self.table(update_rows,[("Strategy","strategy"),("Current","current"),("Target","target"),("Proposed","proposed"),("Applied","applied"),("Absolute Change","change"),("Update Score","score"),("Grade","grade"),("Allowed","allowed")],empty="No strategy-weight updates are available.")}
<h3>Learning-State Registry</h3>{self.table(version_rows,[("Version","version"),("Status","status"),("Adaptation Score","score"),("Source","source"),("Actor","actor"),("Reason","reason"),("Created","created")],empty="No learning-state versions are available.")}</div>'''

    def phase10_governance_messages_html(self, items):
        warnings=[]; rejections=[]
        for p in self.phase10_profiles(items):
            warnings.extend(str(x) for x in (self.val(p,"warnings",()) or ()))
            rejections.extend(str(x) for x in (self.val(p,"rejection_reasons",()) or ()))
            for nested_name in ("adaptive_strategy_profile","ensemble_decision_profile","online_adaptation_profile","learning_state_promotion_profile"):
                nested=self.val(p,nested_name,None)
                warnings.extend(str(x) for x in (self.val(nested,"warnings",()) or ()))
                rejections.extend(str(x) for x in (self.val(nested,"rejection_reasons",()) or ()))
        warnings=list(dict.fromkeys(warnings)); rejections=list(dict.fromkeys(rejections))
        if not warnings and not rejections: return ""
        warning_html="<p class='warning'><strong>Warnings:</strong> "+", ".join(escape(x) for x in warnings)+"</p>" if warnings else ""
        rejection_html="<p class='negative'><strong>Rejections:</strong> "+", ".join(escape(x) for x in rejections)+"</p>" if rejections else ""
        return f"<div class='card'><h2>Phase 10 Governance Diagnostics</h2>{warning_html}{rejection_html}</div>"

    # ------------------------------------------------------------
    # Phase 9 execution analytics and routing reporting
    # ------------------------------------------------------------
    def execution_integration_profile(self, item):
        profile = self.val(item, "execution_integration_profile", None)
        if profile is None:
            metadata = self.val(item, "metadata", {}) or {}
            if isinstance(metadata, dict):
                profile = metadata.get("execution_integration_profile")
        return profile

    def execution_analytics_summary_html(self, trades):
        profiles = [self.execution_integration_profile(t) for t in trades]
        profiles = [p for p in profiles if p is not None and bool(self.val(p, "valid", False))]
        if not profiles:
            return """<div class="card"><h2>Execution Analytics &amp; Routing Intelligence</h2><p class="section-note">No valid Phase 9 execution-analytics profile is attached.</p></div>"""
        profile = profiles[0]
        aggregation = self.val(profile, "aggregation_profile", None)
        benchmark = self.val(profile, "benchmark_profile", None)
        routing = self.val(profile, "routing_profile", None)
        venue_rows=[]
        for v in self.val(aggregation, "venues", ()) or ():
            venue_rows.append({"rank": self.val(v,"rank",0), "venue": self.val(v,"venue","UNKNOWN"), "orders": self.val(v,"order_count",0), "shortfall": self.optional_number(self.val(v,"average_shortfall_bps",None)), "fill": self.optional_pct(self.val(v,"average_fill_ratio",None)), "latency": self.optional_number(self.val(v,"average_fill_delay_seconds",None)), "score": self.optional_number(self.val(v,"execution_score",None)), "grade": self.val(v,"execution_grade","N/A")})
        benchmark_rows=[]
        for b in self.val(benchmark, "summaries", ()) or ():
            benchmark_rows.append({"name": self.val(b,"benchmark_name","UNKNOWN"), "orders": self.val(b,"order_count",0), "avg": self.optional_number(self.val(b,"average_shortfall_bps",None)), "median": self.optional_number(self.val(b,"median_shortfall_bps",None)), "p90": self.optional_number(self.val(b,"p90_shortfall_bps",None)), "score": self.optional_number(self.val(b,"benchmark_score",None)), "grade": self.val(b,"benchmark_grade","N/A")})
        route_rows=[]
        for r in self.val(routing, "venue_recommendations", ()) or ():
            route_rows.append({"rank":self.val(r,"rank",0),"route":self.val(r,"route_name","UNKNOWN"),"orders":self.val(r,"order_count",0),"score":self.optional_number(self.val(r,"route_score",None)),"confidence":self.optional_number(self.val(r,"confidence_score",None)),"shortfall":self.optional_number(self.val(r,"average_shortfall_bps",None)),"recommended":"YES" if self.val(r,"recommended",False) else "NO"})
        return f"""
<div class="card"><h2>Execution Analytics &amp; Routing Intelligence</h2>
<div class="metric"><strong>Orders</strong>{self.val(profile,'order_count',0)}</div>
<div class="metric"><strong>Execution Score</strong>{self.optional_number(self.val(profile,'execution_score',None))}</div>
<div class="metric"><strong>Execution Grade</strong>{self.val(profile,'execution_grade','N/A')}</div>
<div class="metric"><strong>Severity</strong>{self.val(profile,'execution_severity','UNKNOWN')}</div>
<div class="metric"><strong>Average Shortfall</strong>{self.optional_number(self.val(profile,'average_shortfall_bps',None))} bps</div>
<div class="metric"><strong>Fill Ratio</strong>{self.optional_pct(self.val(profile,'average_fill_ratio',None))}</div>
<div class="metric"><strong>Average Latency</strong>{self.optional_number(self.val(profile,'average_latency_seconds',None))} sec</div>
<div class="metric"><strong>Best Benchmark</strong>{self.val(profile,'best_benchmark','UNAVAILABLE')}</div>
<div class="metric"><strong>Recommended Venue</strong>{self.val(profile,'recommended_venue','UNAVAILABLE')}</div>
<div class="metric"><strong>Recommended Broker</strong>{self.val(profile,'recommended_broker','UNAVAILABLE')}</div>
<div class="metric"><strong>Routing Score</strong>{self.optional_number(self.val(profile,'routing_score',None))}</div>
<h3>Venue Execution Comparison</h3>{self.table(venue_rows, [("Rank","rank"),("Venue","venue"),("Orders","orders"),("Shortfall bps","shortfall"),("Fill Ratio","fill"),("Latency sec","latency"),("Score","score"),("Grade","grade")])}
<h3>Benchmark Comparison</h3>{self.table(benchmark_rows, [("Benchmark","name"),("Orders","orders"),("Average bps","avg"),("Median bps","median"),("P90 bps","p90"),("Score","score"),("Grade","grade")])}
<h3>Venue Routing Recommendations</h3>{self.table(route_rows, [("Rank","rank"),("Route","route"),("Orders","orders"),("Score","score"),("Confidence","confidence"),("Shortfall bps","shortfall"),("Recommended","recommended")])}
</div>
"""

    def execution_shortfall_chart_html(self, trades):
        profile = next((self.execution_integration_profile(t) for t in trades if self.execution_integration_profile(t) is not None), None)
        aggregation = self.val(profile, "aggregation_profile", None) if profile is not None else None
        rows=[]
        for order in self.val(aggregation, "orders", ()) or ():
            rows.append({"order": self.val(order,"order_id",""), "shortfall": self.safe_float(self.val(order,"benchmark_shortfall_bps",0.0))})
        if not rows:
            return ""
        return f'<div class="card"><h2>Execution Shortfall by Order</h2>{self.bar_chart(rows, "order", "shortfall", "Implementation Shortfall (bps)")}</div>'

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
        risk_surface_summary = self.risk_surface_summary_html(trades)
        portfolio_risk_surface_summary = self.portfolio_risk_surface_summary_html(trades)
        risk_surface_details = self.risk_surface_details_html(trades)
        portfolio_optimization_summary = self.portfolio_optimization_summary_html(trades)
        portfolio_optimization_comparison = self.portfolio_optimization_comparison_html(trades)
        portfolio_optimization_frontier = self.portfolio_optimization_frontier_summary_html(trades)
        portfolio_optimization_recommendation = self.portfolio_optimization_recommendation_summary_html(trades)
        probability_calibration_summary = self.probability_calibration_summary_html(trades)
        probability_calibration_governance_summary = self.probability_calibration_governance_summary_html(trades)
        walk_forward_summary = self.walk_forward_summary_html(trades)
        walk_forward_governance_summary = self.walk_forward_governance_summary_html(trades)
        market_regime_governance_summary = self.market_regime_governance_summary_html(trades)
        probability_reliability_diagram = self.probability_reliability_diagram_html(trades)
        execution_analytics_summary = self.execution_analytics_summary_html(trades)
        execution_shortfall_chart = self.execution_shortfall_chart_html(trades)
        execution_governance_summary = self.execution_governance_summary_html(trades)
        execution_governance_drift = self.execution_governance_drift_html(trades)
        execution_route_registry = self.execution_route_registry_html(trades)
        execution_champion_challenger = self.execution_champion_challenger_html(trades)
        phase10_adaptive_selection = self.phase10_adaptive_selection_html(trades)
        phase10_learning_weights = self.phase10_learning_weights_html(trades)
        phase10_ensemble_dashboard = self.phase10_ensemble_dashboard_html(trades)
        phase10_online_adaptation = self.phase10_online_adaptation_html(trades)
        phase10_governance_messages = self.phase10_governance_messages_html(trades)

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
.heatmap-wrap {{ overflow-x: auto; margin: 12px 0 20px; }}
.heatmap th, .heatmap td {{ text-align: center; white-space: nowrap; }}
.neutral {{ color: #555; }}
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

{risk_surface_summary}
{portfolio_risk_surface_summary}
{risk_surface_details}
{portfolio_optimization_summary}
{portfolio_optimization_comparison}
{portfolio_optimization_frontier}
{portfolio_optimization_recommendation}
{probability_calibration_summary}
{probability_calibration_governance_summary}
{walk_forward_summary}
{walk_forward_governance_summary}
{market_regime_governance_summary}
{probability_reliability_diagram}
{execution_analytics_summary}
{execution_shortfall_chart}
{execution_governance_summary}
{execution_governance_drift}
{execution_route_registry}
{execution_champion_challenger}
{phase10_adaptive_selection}
{phase10_learning_weights}
{phase10_ensemble_dashboard}
{phase10_online_adaptation}
{phase10_governance_messages}

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
("Surface Points", "risk_surface_points"),
("Surface Worst Case", "risk_surface_worst_case"),
("Surface Best Case", "risk_surface_best_case"),
("Surface Max Loss", "risk_surface_maximum_loss"),
("Worst Price Shock", "risk_surface_price_shock"),
("Worst IV Shock", "risk_surface_iv_shock"),
("Worst Time Offset", "risk_surface_time_offset"),
("Gamma Risk Score", "risk_surface_gamma_score"),
("Vega Risk Score", "risk_surface_vega_score"),
("Theta Risk Score", "risk_surface_theta_score"),
("Nonlinear Score", "risk_surface_nonlinear_score"),
("Surface Score", "risk_surface_score"),
("Surface Grade", "risk_surface_grade"),
("Surface Severity", "risk_surface_severity"),
("Surface Approved", "risk_surface_allowed"),
("Contracts", "contracts"), ("Net PnL", "net_pnl"),
("Hold Days", "days_held"), ("Exit Reason", "exit_reason"),
("Rank", "rank_score")
])}</div>
{self.market_regime_summary_html(trades)}
</body>
</html>
"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            html,
            encoding="utf-8",
        )
        return path
