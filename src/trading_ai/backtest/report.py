from pathlib import Path

from trading_ai.backtest.metrics import BacktestMetrics
from trading_ai.backtest.equity import EquityCurveBuilder
from trading_ai.risk.metrics import RiskMetricsEngine
from trading_ai.risk.reporting_analytics import ReportingAnalytics
from trading_ai.risk.html_charts import HtmlCharts


class BacktestReport:

    def __init__(self, initial_capital=100000.0):
        self.initial_capital = float(initial_capital)
        self.metrics = BacktestMetrics()
        self.equity = EquityCurveBuilder()

    # ------------------------------------------------------------
    # Formatting helpers
    # ------------------------------------------------------------
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

    def ratio(self, value):
        try:
            value = float(value)
            if value == float("inf"):
                return "∞"
            return f"{value:.2f}"
        except Exception:
            return "0.00"

    def profit_factor_display(self, value, gross_profit=0.0, gross_loss=0.0):
        try:
            value = float(value)
            gross_profit = float(gross_profit)
            gross_loss = float(gross_loss)

            if gross_loss == 0 and gross_profit > 0:
                return "∞"

            if value == float("inf"):
                return "∞"

            return f"{value:.2f}"
        except Exception:
            return "0.00"

    def pnl_value(self, trade):
        value = getattr(trade, "net_pnl", None)
        if value in (None, 0.0):
            value = getattr(trade, "pnl", 0.0)
        return float(value or 0.0)

    def build_table(self, rows, columns):
        if not rows:
            return "<p>No data available.</p>"

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

    # ------------------------------------------------------------
    # Shared grouped analytics
    # ------------------------------------------------------------
    def _metrics_row(self, label_key, label_value, trades):
        metrics = self.metrics.calculate(
            trades,
            initial_capital=self.initial_capital,
        )

        gross_profit = metrics.get("gross_profit", 0.0)
        gross_loss = metrics.get("gross_loss", 0.0)

        return {
            label_key: label_value,
            "trades": metrics.get("trades", 0),
            "wins": metrics.get("wins", 0),
            "losses": metrics.get("losses", 0),
            "win_rate": self.pct(metrics.get("win_rate", 0.0)),
            "net_pnl": self.money(metrics.get("net_pnl", 0.0)),
            "return_pct": self.pct(metrics.get("return_pct", 0.0)),
            "profit_factor": self.profit_factor_display(
                metrics.get("profit_factor", 0.0),
                gross_profit=gross_profit,
                gross_loss=gross_loss,
            ),
            "expectancy": self.money(metrics.get("expectancy", 0.0)),
            "avg_pnl": self.money(
                metrics.get("net_pnl", 0.0) / metrics.get("trades", 1)
                if metrics.get("trades", 0)
                else 0.0
            ),
        }

    def metric_rows(self, rows, key_name):
        formatted = []

        for r in rows:
            gross_profit = r.get("gross_profit", 0.0)
            gross_loss = r.get("gross_loss", 0.0)

            formatted.append({
                key_name: r.get(key_name, ""),
                "trades": r.get("trades", 0),
                "wins": r.get("wins", 0),
                "losses": r.get("losses", 0),
                "win_rate": self.pct(r.get("win_rate", 0.0)),
                "net_pnl": self.money(r.get("net_pnl", 0.0)),
                "avg_pnl": self.money(r.get("avg_pnl", 0.0)),
                "profit_factor": self.profit_factor_display(
                    r.get("profit_factor", 0.0),
                    gross_profit=gross_profit,
                    gross_loss=gross_loss,
                ),
                "expectancy": self.money(r.get("expectancy", r.get("avg_pnl", 0.0))),
            })

        return formatted

    def performance_by_symbol(self, trades):
        grouped = {}
        for trade in trades:
            grouped.setdefault(getattr(trade, "symbol", "UNKNOWN"), []).append(trade)
        return [
            self._metrics_row("symbol", symbol, symbol_trades)
            for symbol, symbol_trades in sorted(grouped.items())
        ]

    def performance_by_exit_reason(self, trades):
        grouped = {}
        for trade in trades:
            grouped.setdefault(getattr(trade, "exit_reason", "UNKNOWN"), []).append(trade)
        return [
            self._metrics_row("exit_reason", reason, reason_trades)
            for reason, reason_trades in sorted(grouped.items())
        ]

    def performance_by_signal(self, trades):
        grouped = {}
        for trade in trades:
            grouped.setdefault(getattr(trade, "signal", "UNKNOWN"), []).append(trade)
        return [
            self._metrics_row("signal", signal, signal_trades)
            for signal, signal_trades in sorted(grouped.items())
        ]

    def performance_by_strategy_signal(self, trades):
        grouped = {}
        for trade in trades:
            strategy = getattr(trade, "strategy", "UNKNOWN")
            signal = getattr(trade, "signal", "UNKNOWN")
            key = f"{strategy}/{signal}"
            grouped.setdefault(key, []).append(trade)
        return [
            self._metrics_row("strategy_signal", key, grouped_trades)
            for key, grouped_trades in sorted(grouped.items())
        ]

    def performance_by_score_bucket(self, trades):
        grouped = {}
        for trade in trades:
            score = float(getattr(trade, "rank_score", getattr(trade, "option_score", 0.0)) or 0.0)
            bucket_start = int(score // 10) * 10
            bucket_end = bucket_start + 10
            bucket = f"{bucket_start}-{bucket_end}"
            grouped.setdefault(bucket, []).append(trade)
        return [
            self._metrics_row("score_bucket", bucket, bucket_trades)
            for bucket, bucket_trades in sorted(grouped.items())
        ]

    def performance_by_hold_days(self, trades):
        grouped = {}
        for trade in trades:
            days = int(getattr(trade, "days_held", 0) or 0)
            if days <= 1:
                bucket = "0-1 days"
            elif days <= 3:
                bucket = "2-3 days"
            elif days <= 5:
                bucket = "4-5 days"
            elif days <= 10:
                bucket = "6-10 days"
            else:
                bucket = "10+ days"
            grouped.setdefault(bucket, []).append(trade)

        order = {
            "0-1 days": 0,
            "2-3 days": 1,
            "4-5 days": 2,
            "6-10 days": 3,
            "10+ days": 4,
        }

        return [
            self._metrics_row("hold_bucket", bucket, bucket_trades)
            for bucket, bucket_trades in sorted(
                grouped.items(),
                key=lambda item: order.get(item[0], 99),
            )
        ]

    def performance_by_month(self, trades):
        grouped = {}
        for trade in trades:
            exit_date = getattr(trade, "exit_date", "")
            month = exit_date.strftime("%Y-%m") if hasattr(exit_date, "strftime") else str(exit_date)[:7]
            grouped.setdefault(month, []).append(trade)
        return [
            self._metrics_row("month", month, month_trades)
            for month, month_trades in sorted(grouped.items())
        ]

    def performance_by_year(self, trades):
        grouped = {}
        for trade in trades:
            exit_date = getattr(trade, "exit_date", "")
            year = exit_date.strftime("%Y") if hasattr(exit_date, "strftime") else str(exit_date)[:4]
            grouped.setdefault(year, []).append(trade)
        return [
            self._metrics_row("year", year, year_trades)
            for year, year_trades in sorted(grouped.items())
        ]

    def performance_by_delta_bucket(self, trades):
        grouped = {}
        for trade in trades:
            delta = abs(float(getattr(trade, "entry_delta", 0.0) or 0.0))
            if delta < 0.30:
                bucket = "0.00-0.30"
            elif delta < 0.45:
                bucket = "0.30-0.45"
            elif delta < 0.60:
                bucket = "0.45-0.60"
            elif delta < 0.75:
                bucket = "0.60-0.75"
            else:
                bucket = "0.75+"
            grouped.setdefault(bucket, []).append(trade)

        order = {
            "0.00-0.30": 0,
            "0.30-0.45": 1,
            "0.45-0.60": 2,
            "0.60-0.75": 3,
            "0.75+": 4,
        }

        return [
            self._metrics_row("delta_bucket", bucket, bucket_trades)
            for bucket, bucket_trades in sorted(
                grouped.items(),
                key=lambda item: order.get(item[0], 99),
            )
        ]

    # ------------------------------------------------------------
    # Advanced analytics wrappers
    # ------------------------------------------------------------
    def rejected_rows(self, rejected):
        rows = []
        for item in rejected:
            trade = item["trade"]
            rows.append({
                "symbol": getattr(trade, "symbol", ""),
                "entry_date": getattr(trade, "entry_date", ""),
                "signal": getattr(trade, "signal", ""),
                "strategy": getattr(trade, "strategy", ""),
                "entry_price": f"{float(getattr(trade, 'entry_price', 0.0)):.2f}",
                "contracts": getattr(trade, "contracts", ""),
                "reason": item.get("reason", ""),
                "rank_score": f"{float(getattr(trade, 'rank_score', 0.0)):.2f}",
                "option_score": f"{float(getattr(trade, 'option_score', 0.0)):.2f}",
            })
        return rows

    def trade_distribution_rows(self, trades):
        rows = ReportingAnalytics().trade_distribution(trades)
        return [
            {
                "bucket": r["bucket"],
                "trades": r["trades"],
                "net_pnl": self.money(r["net_pnl"]),
                "avg_pnl": self.money(r["avg_pnl"]),
            }
            for r in rows
        ]

    def extended_risk_metrics(self, trades, equity_curve, metrics):
        analytics = ReportingAnalytics()
        var = analytics.var_cvar(trades)
        kelly = analytics.kelly(trades)
        dd_duration = analytics.drawdown_duration(equity_curve)
        total_pnl = float(metrics.get("net_pnl", 0.0))
        max_dd_dollars = float(metrics.get("max_drawdown_dollars", 0.0))

        return {
            **var,
            **kelly,
            **dd_duration,
            "ulcer_index": analytics.ulcer_index(equity_curve),
            "omega_ratio": analytics.omega_ratio(trades),
            "tail_ratio": analytics.tail_ratio(trades),
            "recovery_factor": analytics.recovery_factor(total_pnl, max_dd_dollars),
            "time_in_market": analytics.time_in_market(trades, equity_curve),
        }

    def monthly_heatmap_rows(self, trades, initial_capital=100000.0):
        rows = ReportingAnalytics().monthly_heatmap(trades, initial_capital)
        month_names = {
            "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr",
            "05": "May", "06": "Jun", "07": "Jul", "08": "Aug",
            "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
        }

        out = []
        for r in rows:
            row = {"year": r["year"]}
            for m, name in month_names.items():
                value = float(r.get(m, 0.0))
                css = "positive" if value > 0 else "negative" if value < 0 else ""
                row[name] = f'<span class="{css}">{self.pct(value)}</span>'
                row[f"{name}_raw"] = value
            out.append(row)
        return out

    def monthly_bar_rows(self, monthly_heatmap_rows):
        rows = []
        for r in monthly_heatmap_rows:
            for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]:
                rows.append({
                    "month": f"{r['year']}-{m}",
                    "return": float(r.get(f"{m}_raw", 0.0)),
                })
        return rows

    def regime_rows(self, trades):
        return self.metric_rows(
            ReportingAnalytics().regime_performance(trades),
            "regime",
        )

    def greek_extra_rows(self, trades):
        grouped = ReportingAnalytics().greek_bucket_performance(trades)
        return {
            "gamma": self.metric_rows(grouped["gamma"], "entry_gamma_bucket"),
            "theta": self.metric_rows(grouped["theta"], "entry_theta_bucket"),
            "vega": self.metric_rows(grouped["vega"], "entry_vega_bucket"),
            "volatility": self.metric_rows(grouped["volatility"], "entry_volatility_bucket"),
        }

    def score_calibration_rows(self, trades):
        return self.metric_rows(
            ReportingAnalytics().score_calibration(trades),
            "score_bucket",
        )

    def rolling_rows(self, equity_curve):
        rows = ReportingAnalytics().rolling_metrics(equity_curve, window=20)
        return [
            {
                "date": r["date"],
                "rolling_return": self.pct(r["rolling_return"]),
                "rolling_sharpe": f"{r['rolling_sharpe']:.2f}",
                "rolling_volatility": self.pct(r["rolling_volatility"]),
            }
            for r in rows[-30:]
        ]

    def drawdown_rows(self, equity_curve):
        rows = []
        peak = None
        for point in equity_curve:
            equity = float(point["equity"])
            if peak is None or equity > peak:
                peak = equity
            drawdown_dollars = equity - peak
            drawdown_pct = drawdown_dollars / peak if peak else 0.0
            rows.append({
                "date": point.get("date", ""),
                "equity": self.money(equity),
                "peak_equity": self.money(peak),
                "drawdown_dollars": self.money(drawdown_dollars),
                "drawdown_pct": self.pct(drawdown_pct),
            })
        return rows

    def equity_rows(self, equity_curve):
        return [
            {
                "date": p.get("date", ""),
                "equity": self.money(p.get("equity", 0.0)),
                "pnl": self.money(p.get("pnl", 0.0)),
                "symbol": p.get("symbol", ""),
                "exit_reason": p.get("exit_reason", ""),
            }
            for p in equity_curve
        ]

    def best_trades(self, trades, limit=10):
        return sorted(trades, key=lambda t: self.pnl_value(t), reverse=True)[:limit]

    def worst_trades(self, trades, limit=10):
        return sorted(trades, key=lambda t: self.pnl_value(t))[:limit]

    def trade_rows(self, trades):
        rows = []
        for t in trades:
            rows.append({
                "symbol": getattr(t, "symbol", ""),
                "entry_date": getattr(t, "entry_date", ""),
                "exit_date": getattr(t, "exit_date", ""),
                "strategy": getattr(t, "strategy", ""),
                "signal": getattr(t, "signal", ""),
                "strike": getattr(t, "strike", ""),
                "expiry": getattr(t, "expiry", ""),
                "entry_price": f"{float(getattr(t, 'entry_price', 0.0)):.2f}",
                "exit_price": f"{float(getattr(t, 'exit_price', 0.0)):.2f}",
                "entry_delta": f"{float(getattr(t, 'entry_delta', 0.0)):.4f}",
                "entry_gamma": f"{float(getattr(t, 'entry_gamma', 0.0)):.5f}",
                "entry_theta": f"{float(getattr(t, 'entry_theta', 0.0)):.4f}",
                "entry_vega": f"{float(getattr(t, 'entry_vega', 0.0)):.4f}",
                "entry_rho": f"{float(getattr(t, 'entry_rho', 0.0)):.4f}",
                "entry_volatility": self.pct(getattr(t, "entry_volatility", 0.0)),
                "entry_dte": getattr(t, "entry_dte", ""),
                "contracts": getattr(t, "contracts", ""),
                "pnl": self.money(getattr(t, "pnl", 0.0)),
                "pnl_pct": self.pct(getattr(t, "pnl_pct", 0.0)),
                "gross_pnl": self.money(getattr(t, "gross_pnl", 0.0)),
                "fees": self.money(getattr(t, "fees", 0.0)),
                "net_pnl": self.money(getattr(t, "net_pnl", getattr(t, "pnl", 0.0))),
                "days_held": getattr(t, "days_held", ""),
                "exit_reason": getattr(t, "exit_reason", ""),
                "rank_score": f"{float(getattr(t, 'rank_score', 0.0)):.2f}",
                "option_score": f"{float(getattr(t, 'option_score', 0.0)):.2f}",
                "pop": self.pct(getattr(t, "pop", 0.0)),
                "liquidity": f"{float(getattr(t, 'liquidity', 0.0)):.2f}",
                "atm_score": f"{float(getattr(t, 'atm_score', 0.0)):.2f}",
            })
        return rows

    # ------------------------------------------------------------
    # Main generator
    # ------------------------------------------------------------
    def generate(self, trades, path="reports/backtest.html", rejected=None, equity_curve=None):
        trades = trades or []
        rejected = rejected or []

        curve = equity_curve or self.equity.build(
            trades,
            initial_capital=self.initial_capital,
        )

        metrics = self.metrics.calculate(
            trades,
            initial_capital=self.initial_capital,
        )

        # Add advanced risk metrics directly here so the report never shows stale zero values.
        risk_metrics = RiskMetricsEngine().compute(
            equity_curve=curve,
            trades=trades,
            initial_capital=self.initial_capital,
        )
        metrics.update(risk_metrics)
        metrics["initial_capital"] = self.initial_capital

        accepted_count = len(trades)
        rejected_count = len(rejected)
        final_equity = curve[-1]["equity"] if curve else self.initial_capital

        analytics = ReportingAnalytics()
        charts = HtmlCharts()

        symbol_rows = self.performance_by_symbol(trades)
        exit_reason_rows = self.performance_by_exit_reason(trades)
        signal_rows = self.performance_by_signal(trades)
        strategy_rows = self.performance_by_strategy_signal(trades)
        score_bucket_rows = self.performance_by_score_bucket(trades)
        hold_days_rows = self.performance_by_hold_days(trades)
        month_rows = self.performance_by_month(trades)
        year_rows = self.performance_by_year(trades)
        delta_bucket_rows = self.performance_by_delta_bucket(trades)
        rejected_rows = self.rejected_rows(rejected)
        trade_rows = self.trade_rows(trades)
        best_trade_rows = self.trade_rows(self.best_trades(trades))
        worst_trade_rows = self.trade_rows(self.worst_trades(trades))
        drawdown_rows = self.drawdown_rows(curve)
        equity_rows = self.equity_rows(curve)

        extended_risk = self.extended_risk_metrics(trades, curve, metrics)
        streaks = analytics.streaks(trades)
        monthly_heatmap_rows = self.monthly_heatmap_rows(trades, self.initial_capital)
        monthly_bar_rows = self.monthly_bar_rows(monthly_heatmap_rows)
        trade_distribution_rows = self.trade_distribution_rows(trades)
        regime_rows = self.regime_rows(trades)
        greek_extra = self.greek_extra_rows(trades)
        score_calibration_rows = self.score_calibration_rows(trades)
        rolling_rows = self.rolling_rows(curve)
        drawdown_curve = analytics.drawdown_curve(curve)

        equity_chart = charts.line_chart(
            curve,
            "date",
            "equity",
            title="Equity Curve",
        )

        drawdown_chart = charts.line_chart(
            drawdown_curve,
            "date",
            "drawdown_pct",
            title="Underwater Drawdown Curve",
        )

        monthly_chart = charts.bar_chart(
            monthly_bar_rows,
            "month",
            "return",
            title="Monthly Return Bars",
        )

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading AI Backtest Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 30px;
            background: #f7f7f7;
            color: #222;
        }}
        h1, h2 {{
            color: #111;
        }}
        .card {{
            background: white;
            padding: 20px;
            margin-bottom: 25px;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.12);
            overflow-x: auto;
        }}
        .metric {{
            display: inline-block;
            margin-right: 30px;
            margin-bottom: 15px;
            font-size: 18px;
            vertical-align: top;
        }}
        .metric strong {{
            display: block;
            font-size: 13px;
            color: #666;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            white-space: nowrap;
        }}
        th, td {{
            border-bottom: 1px solid #ddd;
            padding: 8px;
            text-align: left;
            font-size: 14px;
        }}
        th {{
            background: #eee;
        }}
        .positive {{
            color: #1b5e20;
            font-weight: bold;
        }}
        .negative {{
            color: #b71c1c;
            font-weight: bold;
        }}
        .warning {{
            color: #e65100;
            font-weight: bold;
        }}
        .section-note {{
            color: #555;
            font-size: 14px;
            margin-bottom: 10px;
        }}
    </style>
</head>
<body>

<h1>Trading AI Backtest Report</h1>

<div class="card">
    <h2>Summary</h2>
    <div class="metric"><strong>Trades</strong>{metrics.get("trades", 0)}</div>
    <div class="metric"><strong>Accepted</strong>{accepted_count}</div>
    <div class="metric"><strong>Rejected</strong>{rejected_count}</div>
    <div class="metric"><strong>Wins</strong>{metrics.get("wins", 0)}</div>
    <div class="metric"><strong>Losses</strong>{metrics.get("losses", 0)}</div>
    <div class="metric"><strong>Win Rate</strong>{self.pct(metrics.get("win_rate", 0.0))}</div>
    <div class="metric"><strong>Net PnL</strong>{self.money(metrics.get("net_pnl", 0.0))}</div>
    <div class="metric"><strong>Final Equity</strong>{self.money(final_equity)}</div>
    <div class="metric"><strong>Return</strong>{self.pct(metrics.get("return_pct", 0.0))}</div>
    <div class="metric"><strong>Profit Factor</strong>{self.profit_factor_display(metrics.get("profit_factor", 0.0), metrics.get("gross_profit", 0.0), metrics.get("gross_loss", 0.0))}</div>
    <div class="metric"><strong>Expectancy</strong>{self.money(metrics.get("expectancy", 0.0))}</div>
    <div class="metric"><strong>Max Drawdown</strong>{self.pct(metrics.get("max_drawdown_pct", 0.0))}</div>
    <div class="metric"><strong>Max DD $</strong>{self.money(metrics.get("max_drawdown_dollars", 0.0))}</div>
    <div class="metric"><strong>Sharpe</strong>{self.ratio(metrics.get("sharpe_ratio", 0.0))}</div>
    <div class="metric"><strong>Sortino</strong>{self.ratio(metrics.get("sortino_ratio", 0.0))}</div>
    <div class="metric"><strong>Calmar</strong>{self.ratio(metrics.get("calmar_ratio", 0.0))}</div>
    <div class="metric"><strong>Payoff Ratio</strong>{self.ratio(metrics.get("payoff_ratio", 0.0))}</div>
</div>

<div class="card">
    <h2>Executive Risk Diagnostics</h2>
    <div class="metric"><strong>VaR 95%</strong>{self.money(extended_risk.get("var_95", 0.0))}</div>
    <div class="metric"><strong>CVaR 95%</strong>{self.money(extended_risk.get("cvar_95", 0.0))}</div>
    <div class="metric"><strong>Kelly</strong>{self.pct(extended_risk.get("kelly_fraction", 0.0))}</div>
    <div class="metric"><strong>Half Kelly</strong>{self.pct(extended_risk.get("half_kelly", 0.0))}</div>
    <div class="metric"><strong>Ulcer Index</strong>{self.ratio(extended_risk.get("ulcer_index", 0.0))}</div>
    <div class="metric"><strong>Omega</strong>{self.ratio(extended_risk.get("omega_ratio", 0.0))}</div>
    <div class="metric"><strong>Tail Ratio</strong>{self.ratio(extended_risk.get("tail_ratio", 0.0))}</div>
    <div class="metric"><strong>Recovery Factor</strong>{self.ratio(extended_risk.get("recovery_factor", 0.0))}</div>
    <div class="metric"><strong>Time in Market</strong>{self.pct(extended_risk.get("time_in_market", 0.0))}</div>
    <div class="metric"><strong>Longest DD Duration</strong>{extended_risk.get("longest_drawdown_duration", 0)} trades</div>
</div>

<div class="card">
    <h2>Equity Curve Chart</h2>
    {equity_chart}
</div>

<div class="card">
    <h2>Underwater Drawdown Chart</h2>
    {drawdown_chart}
</div>

<div class="card">
    <h2>Monthly Return Chart</h2>
    {monthly_chart}
</div>

<div class="card">
    <h2>Advanced Risk Metrics</h2>
    <div class="metric"><strong>Average Win</strong>{self.money(metrics.get("avg_win", 0.0))}</div>
    <div class="metric"><strong>Average Loss</strong>{self.money(metrics.get("avg_loss", 0.0))}</div>
    <div class="metric"><strong>Largest Win</strong>{self.money(metrics.get("largest_win", 0.0))}</div>
    <div class="metric"><strong>Largest Loss</strong>{self.money(metrics.get("largest_loss", 0.0))}</div>
    <div class="metric"><strong>Gross Profit</strong>{self.money(metrics.get("gross_profit", 0.0))}</div>
    <div class="metric"><strong>Gross Loss</strong>{self.money(metrics.get("gross_loss", 0.0))}</div>
    <div class="metric"><strong>Longest Win Streak</strong>{streaks.get("longest_win_streak", 0)}</div>
    <div class="metric"><strong>Longest Loss Streak</strong>{streaks.get("longest_loss_streak", 0)}</div>
</div>

<div class="card">
    <h2>Monthly Return Heatmap</h2>
    {self.build_table(
        monthly_heatmap_rows,
        [
            ("Year", "year"),
            ("Jan", "Jan"),
            ("Feb", "Feb"),
            ("Mar", "Mar"),
            ("Apr", "Apr"),
            ("May", "May"),
            ("Jun", "Jun"),
            ("Jul", "Jul"),
            ("Aug", "Aug"),
            ("Sep", "Sep"),
            ("Oct", "Oct"),
            ("Nov", "Nov"),
            ("Dec", "Dec"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Symbol</h2>
    {self.build_table(
        symbol_rows,
        [
            ("Symbol", "symbol"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Exit Reason</h2>
    {self.build_table(
        exit_reason_rows,
        [
            ("Exit Reason", "exit_reason"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Signal</h2>
    {self.build_table(
        signal_rows,
        [
            ("Signal", "signal"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Strategy / Signal Performance</h2>
    {self.build_table(
        strategy_rows,
        [
            ("Strategy / Signal", "strategy_signal"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Regime Performance</h2>
    {self.build_table(
        regime_rows,
        [
            ("Regime", "regime"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Avg PnL", "avg_pnl"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Score Calibration</h2>
    <p class="section-note">Shows whether higher-ranked trades actually produce better results.</p>
    {self.build_table(
        score_calibration_rows,
        [
            ("Score Bucket", "score_bucket"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Avg PnL", "avg_pnl"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Score Bucket</h2>
    {self.build_table(
        score_bucket_rows,
        [
            ("Score Bucket", "score_bucket"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Hold Days</h2>
    {self.build_table(
        hold_days_rows,
        [
            ("Hold Days", "hold_bucket"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Month</h2>
    {self.build_table(
        month_rows,
        [
            ("Month", "month"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Year</h2>
    {self.build_table(
        year_rows,
        [
            ("Year", "year"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Performance by Delta Bucket</h2>
    {self.build_table(
        delta_bucket_rows,
        [
            ("Delta Bucket", "delta_bucket"),
            ("Trades", "trades"),
            ("Wins", "wins"),
            ("Losses", "losses"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Gamma Bucket Performance</h2>
    {self.build_table(
        greek_extra["gamma"],
        [
            ("Gamma Bucket", "entry_gamma_bucket"),
            ("Trades", "trades"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Theta Bucket Performance</h2>
    {self.build_table(
        greek_extra["theta"],
        [
            ("Theta Bucket", "entry_theta_bucket"),
            ("Trades", "trades"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Vega Bucket Performance</h2>
    {self.build_table(
        greek_extra["vega"],
        [
            ("Vega Bucket", "entry_vega_bucket"),
            ("Trades", "trades"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Volatility Bucket Performance</h2>
    {self.build_table(
        greek_extra["volatility"],
        [
            ("Vol Bucket", "entry_volatility_bucket"),
            ("Trades", "trades"),
            ("Win Rate", "win_rate"),
            ("Net PnL", "net_pnl"),
            ("Profit Factor", "profit_factor"),
            ("Expectancy", "expectancy"),
        ],
    )}
</div>

<div class="card">
    <h2>Trade PnL Distribution</h2>
    {self.build_table(
        trade_distribution_rows,
        [
            ("PnL Bucket", "bucket"),
            ("Trades", "trades"),
            ("Net PnL", "net_pnl"),
            ("Avg PnL", "avg_pnl"),
        ],
    )}
</div>

<div class="card">
    <h2>Rolling 20-Trade Risk Metrics</h2>
    {self.build_table(
        rolling_rows,
        [
            ("Date", "date"),
            ("Rolling Return", "rolling_return"),
            ("Rolling Sharpe", "rolling_sharpe"),
            ("Rolling Volatility", "rolling_volatility"),
        ],
    )}
</div>

<div class="card">
    <h2>Drawdown Curve</h2>
    {self.build_table(
        drawdown_rows,
        [
            ("Date", "date"),
            ("Equity", "equity"),
            ("Peak Equity", "peak_equity"),
            ("Drawdown $", "drawdown_dollars"),
            ("Drawdown %", "drawdown_pct"),
        ],
    )}
</div>

<div class="card">
    <h2>Equity Curve</h2>
    {self.build_table(
        equity_rows,
        [
            ("Date", "date"),
            ("Equity", "equity"),
            ("PnL", "pnl"),
            ("Symbol", "symbol"),
            ("Exit Reason", "exit_reason"),
        ],
    )}
</div>

<div class="card">
    <h2>Best Trades</h2>
    {self.build_table(
        best_trade_rows,
        [
            ("Symbol", "symbol"),
            ("Entry", "entry_date"),
            ("Exit", "exit_date"),
            ("Signal", "signal"),
            ("PnL", "pnl"),
            ("PnL %", "pnl_pct"),
            ("Gross PnL", "gross_pnl"),
            ("Fees", "fees"),
            ("Net PnL", "net_pnl"),
            ("Exit Reason", "exit_reason"),
            ("Rank", "rank_score"),
            ("Score", "option_score"),
        ],
    )}
</div>

<div class="card">
    <h2>Worst Trades</h2>
    {self.build_table(
        worst_trade_rows,
        [
            ("Symbol", "symbol"),
            ("Entry", "entry_date"),
            ("Exit", "exit_date"),
            ("Signal", "signal"),
            ("PnL", "pnl"),
            ("PnL %", "pnl_pct"),
            ("Gross PnL", "gross_pnl"),
            ("Fees", "fees"),
            ("Net PnL", "net_pnl"),
            ("Exit Reason", "exit_reason"),
            ("Rank", "rank_score"),
            ("Score", "option_score"),
        ],
    )}
</div>

<div class="card">
    <h2>Rejected Trades</h2>
    {self.build_table(
        rejected_rows,
        [
            ("Symbol", "symbol"),
            ("Entry", "entry_date"),
            ("Signal", "signal"),
            ("Strategy", "strategy"),
            ("Entry Price", "entry_price"),
            ("Contracts", "contracts"),
            ("Reason", "reason"),
            ("Rank", "rank_score"),
            ("Score", "option_score"),
        ],
    )}
</div>

<div class="card">
    <h2>Trade Log</h2>
    {self.build_table(
        trade_rows,
        [
            ("Symbol", "symbol"),
            ("Entry", "entry_date"),
            ("Exit", "exit_date"),
            ("Signal", "signal"),
            ("Strategy", "strategy"),
            ("Strike", "strike"),
            ("Expiry", "expiry"),
            ("Entry Price", "entry_price"),
            ("Exit Price", "exit_price"),
            ("Delta", "entry_delta"),
            ("Gamma", "entry_gamma"),
            ("Theta", "entry_theta"),
            ("Vega", "entry_vega"),
            ("Rho", "entry_rho"),
            ("Vol", "entry_volatility"),
            ("DTE", "entry_dte"),
            ("Contracts", "contracts"),
            ("PnL", "pnl"),
            ("PnL %", "pnl_pct"),
            ("Gross PnL", "gross_pnl"),
            ("Fees", "fees"),
            ("Net PnL", "net_pnl"),
            ("Hold Days", "days_held"),
            ("Exit Reason", "exit_reason"),
            ("Rank", "rank_score"),
            ("Option Score", "option_score"),
            ("POP", "pop"),
            ("Liquidity", "liquidity"),
            ("ATM", "atm_score"),
        ],
    )}
</div>

</body>
</html>
"""

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(html)
        return path
