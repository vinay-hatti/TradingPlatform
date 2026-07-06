from pathlib import Path


class WalkForwardReport:

    def money(self, value):
        return f"${float(value):,.2f}"

    def pct(self, value):
        return f"{float(value) * 100:.2f}%"

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

    def generate(
        self,
        rows,
        path="reports/walkforward/report.html",
    ):
        total_pnl = sum(float(r["net_pnl"]) for r in rows)

        avg_return = (
            sum(float(r["return_pct"]) for r in rows) / len(rows)
            if rows
            else 0.0
        )

        avg_pf = (
            sum(float(r["profit_factor"]) for r in rows) / len(rows)
            if rows
            else 0.0
        )

        ranked = sorted(
            rows,
            key=lambda r: (
                float(r["profit_factor"]),
                float(r["return_pct"]),
            ),
            reverse=True,
        )

        display_rows = []

        for r in rows:
            display_rows.append({
                "window": r["window"],
                "train": f"{r['train_start']} -> {r['train_end']}",
                "test": f"{r['test_start']} -> {r['test_end']}",
                "premium": self.pct(r["option_premium_pct"]),
                "take_profit": self.pct(r["take_profit"]),
                "stop_loss": self.pct(r["stop_loss"]),
                "max_hold": r["max_hold"],
                "trades": r["trades"],
                "win_rate": self.pct(r["win_rate"]) if "win_rate" in r else "",
                "return_pct": self.pct(r["return_pct"]),
                "profit_factor": f"{float(r['profit_factor']):.2f}",
                "net_pnl": self.money(r["net_pnl"]),
                "run_dir": r["run_dir"],
            })

        ranked_rows = []

        for r in ranked:
            ranked_rows.append({
                "window": r["window"],
                "test": f"{r['test_start']} -> {r['test_end']}",
                "trades": r["trades"],
                "return_pct": self.pct(r["return_pct"]),
                "profit_factor": f"{float(r['profit_factor']):.2f}",
                "net_pnl": self.money(r["net_pnl"]),
                "run_dir": r["run_dir"],
            })

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Trading AI Walk-Forward Report</title>
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

<h1>Trading AI Walk-Forward Report</h1>

<div class="card">
    <h2>Summary</h2>
    <div class="metric"><strong>Windows</strong>{len(rows)}</div>
    <div class="metric"><strong>Total PnL</strong>{self.money(total_pnl)}</div>
    <div class="metric"><strong>Avg Return</strong>{self.pct(avg_return)}</div>
    <div class="metric"><strong>Avg Profit Factor</strong>{avg_pf:.2f}</div>
</div>

<div class="card">
    <h2>Ranked Windows</h2>
    {self.build_table(
        ranked_rows,
        [
            ("Window", "window"),
            ("Test", "test"),
            ("Trades", "trades"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Net PnL", "net_pnl"),
            ("Run Dir", "run_dir"),
        ],
    )}
</div>

<div class="card">
    <h2>Full Window Log</h2>
    {self.build_table(
        display_rows,
        [
            ("Window", "window"),
            ("Train", "train"),
            ("Test", "test"),
            ("Premium", "premium"),
            ("TP", "take_profit"),
            ("SL", "stop_loss"),
            ("Hold", "max_hold"),
            ("Trades", "trades"),
            ("Win Rate", "win_rate"),
            ("Return", "return_pct"),
            ("Profit Factor", "profit_factor"),
            ("Net PnL", "net_pnl"),
            ("Run Dir", "run_dir"),
        ],
    )}
</div>

</body>
</html>
"""

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(html)

        return path
