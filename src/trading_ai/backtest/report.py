from pathlib import Path

from trading_ai.backtest.metrics import BacktestMetrics
from trading_ai.backtest.equity import EquityCurveBuilder


class BacktestReport:

    def __init__(self, initial_capital=100000.0):
        self.initial_capital = initial_capital
        self.metrics = BacktestMetrics()
        self.equity = EquityCurveBuilder()

    def money(self, value):
        return f"${float(value):,.2f}"

    def pct(self, value):
        return f"{float(value) * 100:.2f}%"

    def rejected_rows(self, rejected):

        rows = []

        for item in rejected:
            trade = item["trade"]

            rows.append({
                "symbol": trade.symbol,
                "entry_date": trade.entry_date,
                "signal": trade.signal,
                "strategy": trade.strategy,
                "entry_price": f"{float(trade.entry_price):.2f}",
                "contracts": trade.contracts,
                "reason": item["reason"],
                "rank_score": f"{float(trade.rank_score):.2f}",
                "option_score": f"{float(trade.option_score):.2f}",
            })

        return rows

    def build_table(self, rows, columns):
        if not rows:
            return "<p>No data available.</p>"

        html = "<table><thead><tr>"

        for label, key in columns:
            html += f"<th>{label}</th>"

        html += "</tr></thead><tbody>"

        for row in rows:
            html += "<tr>"
            for _, key in columns:
                html += f"<td>{row.get(key, '')}</td>"
            html += "</tr>"

        html += "</tbody></table>"

        return html

    def _metrics_row(self, label_key, label_value, trades):
        metrics = self.metrics.calculate(
            trades,
            initial_capital=self.initial_capital,
        )

        profit_factor = metrics["profit_factor"]

        return {
            label_key: label_value,
            "trades": metrics["trades"],
            "wins": metrics["wins"],
            "losses": metrics["losses"],
            "win_rate": self.pct(metrics["win_rate"]),
            "net_pnl": self.money(metrics["net_pnl"]),
            "return_pct": self.pct(metrics["return_pct"]),
            "profit_factor": (
                "inf"
                if profit_factor == float("inf")
                else f"{profit_factor:.2f}"
            ),
            "expectancy": self.money(metrics["expectancy"]),
        }

    def performance_by_symbol(self, trades):
        grouped = {}

        for trade in trades:
            grouped.setdefault(trade.symbol, []).append(trade)

        return [
            self._metrics_row("symbol", symbol, symbol_trades)
            for symbol, symbol_trades in sorted(grouped.items())
        ]

    def performance_by_exit_reason(self, trades):
        grouped = {}

        for trade in trades:
            grouped.setdefault(trade.exit_reason, []).append(trade)

        return [
            self._metrics_row("exit_reason", reason, reason_trades)
            for reason, reason_trades in sorted(grouped.items())
        ]

    def performance_by_signal(self, trades):
        grouped = {}

        for trade in trades:
            grouped.setdefault(trade.signal, []).append(trade)

        return [
            self._metrics_row("signal", signal, signal_trades)
            for signal, signal_trades in sorted(grouped.items())
        ]

    def performance_by_score_bucket(self, trades):
        grouped = {}

        for trade in trades:
            score = float(trade.rank_score)
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
            days = int(trade.days_held)

            if days <= 3:
                bucket = "0-3 days"
            elif days <= 5:
                bucket = "4-5 days"
            elif days <= 10:
                bucket = "6-10 days"
            elif days <= 20:
                bucket = "11-20 days"
            else:
                bucket = "20+ days"

            grouped.setdefault(bucket, []).append(trade)

        order = {
            "0-3 days": 0,
            "4-5 days": 1,
            "6-10 days": 2,
            "11-20 days": 3,
            "20+ days": 4,
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
            month = trade.exit_date.strftime("%Y-%m")
            grouped.setdefault(month, []).append(trade)

        return [
            self._metrics_row("month", month, month_trades)
            for month, month_trades in sorted(grouped.items())
        ]

    def performance_by_year(self, trades):
        grouped = {}

        for trade in trades:
            year = trade.exit_date.strftime("%Y")
            grouped.setdefault(year, []).append(trade)

        return [
            self._metrics_row("year", year, year_trades)
            for year, year_trades in sorted(grouped.items())
        ]

    def best_trades(self, trades, limit=10):
        return sorted(
            trades,
            key=lambda t: float(t.pnl),
            reverse=True,
        )[:limit]

    def worst_trades(self, trades, limit=10):
        return sorted(
            trades,
            key=lambda t: float(t.pnl),
        )[:limit]

    def trade_rows(self, trades):
        rows = []

        for t in trades:
            rows.append({
                "symbol": t.symbol,
                "entry_date": t.entry_date,
                "exit_date": t.exit_date,
                "strategy": t.strategy,
                "signal": t.signal,
                "strike": t.strike,
                "expiry": t.expiry,
                "entry_price": f"{float(t.entry_price):.2f}",
                "exit_price": f"{float(t.exit_price):.2f}",
                "contracts": t.contracts,
                "pnl": self.money(t.pnl),
                "pnl_pct": f"{t.pnl_pct:.2%}",
                "days_held": t.days_held,
                "exit_reason": t.exit_reason,
                "rank_score": f"{t.rank_score:.2f}",
                "option_score": f"{t.option_score:.2f}",
                "pop": f"{t.pop:.2%}",
                "liquidity": f"{t.liquidity:.2f}",
                "atm_score": f"{t.atm_score:.2f}",
            })

        return rows

#    def generate(self, trades, path="reports/backtest.html"):
    def generate(self, trades, path="reports/backtest.html", rejected=None):

        rejected = rejected or []
        rejected_rows = self.rejected_rows(rejected)

        metrics = self.metrics.calculate(
            trades,
            initial_capital=self.initial_capital,
        )

        curve = self.equity.build(
            trades,
            initial_capital=self.initial_capital,
        )

        max_dd = self.equity.max_drawdown(curve)

        symbol_rows = self.performance_by_symbol(trades)
        exit_reason_rows = self.performance_by_exit_reason(trades)
        signal_rows = self.performance_by_signal(trades)
        score_bucket_rows = self.performance_by_score_bucket(trades)
        hold_days_rows = self.performance_by_hold_days(trades)
        month_rows = self.performance_by_month(trades)
        year_rows = self.performance_by_year(trades)

        trade_rows = self.trade_rows(trades)
        best_trade_rows = self.trade_rows(self.best_trades(trades))
        worst_trade_rows = self.trade_rows(self.worst_trades(trades))

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
    </style>
</head>
<body>

<h1>Trading AI Backtest Report</h1>

<div class="card">
    <h2>Summary</h2>
    <div class="metric"><strong>Trades</strong>{metrics["trades"]}</div>
    <div class="metric"><strong>Wins</strong>{metrics["wins"]}</div>
    <div class="metric"><strong>Losses</strong>{metrics["losses"]}</div>
    <div class="metric"><strong>Win Rate</strong>{self.pct(metrics["win_rate"])}</div>
    <div class="metric"><strong>Net PnL</strong>{self.money(metrics["net_pnl"])}</div>
    <div class="metric"><strong>Return</strong>{self.pct(metrics["return_pct"])}</div>
    <div class="metric"><strong>Profit Factor</strong>{metrics["profit_factor"]:.2f}</div>
    <div class="metric"><strong>Expectancy</strong>{self.money(metrics["expectancy"])}</div>
    <div class="metric"><strong>Max Drawdown</strong>{self.money(max_dd)}</div>
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
    <h2>Equity Curve</h2>
    {self.build_table(
        curve,
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
            ("Contracts", "contracts"),
            ("PnL", "pnl"),
            ("PnL %", "pnl_pct"),
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
