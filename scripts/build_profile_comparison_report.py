import csv
from pathlib import Path


REPORT_DIR = Path("reports/walkforward")
OUTPUT = REPORT_DIR / "profile_comparison.html"


def money(x):
    return f"${float(x):,.2f}"


def pct(x):
    return f"{float(x)*100:.2f}%"


def load_summary(csv_file):

    rows = list(csv.DictReader(open(csv_file)))

    if not rows:
        return None

    total_pnl = sum(float(r["net_pnl"]) for r in rows)

    avg_return = (
        sum(float(r["return_pct"]) for r in rows)
        / len(rows)
    )

    avg_pf = (
        sum(float(r["profit_factor"]) for r in rows)
        / len(rows)
    )

    total_trades = sum(int(r["trades"]) for r in rows)

    winning_windows = sum(
        float(r["net_pnl"]) > 0
        for r in rows
    )

    return {
        "profile": csv_file.stem,
        "windows": len(rows),
        "winning_windows": winning_windows,
        "total_trades": total_trades,
        "total_pnl": total_pnl,
        "avg_return": avg_return,
        "avg_pf": avg_pf,
    }


profiles = []

for csv_file in sorted(REPORT_DIR.glob("*.csv")):

    if csv_file.name == "summary.csv":
        continue

    summary = load_summary(csv_file)

    if summary:
        profiles.append(summary)

profiles.sort(
    key=lambda x: (
        x["total_pnl"],
        x["avg_pf"],
    ),
    reverse=True,
)

html = """
<html>

<head>

<title>Walk-Forward Profile Comparison</title>

<style>

body{
font-family:Arial;
margin:30px;
background:#f5f5f5;
}

.card{
background:white;
padding:20px;
margin-bottom:20px;
border-radius:8px;
box-shadow:0 0 4px rgba(0,0,0,.15);
}

table{
border-collapse:collapse;
width:100%;
}

th,td{
padding:8px;
border-bottom:1px solid #ddd;
text-align:left;
}

th{
background:#eee;
}

.best{
background:#dff0d8;
font-weight:bold;
}

</style>

</head>

<body>

<h1>Walk-Forward Profile Comparison</h1>

<div class="card">

<table>

<tr>
<th>Rank</th>
<th>Profile</th>
<th>Windows</th>
<th>Winning Windows</th>
<th>Total Trades</th>
<th>Total PnL</th>
<th>Average Return</th>
<th>Average PF</th>
</tr>
"""

for i, p in enumerate(profiles):

    css = "best" if i == 0 else ""

    html += f"""
<tr class="{css}">
<td>{i+1}</td>
<td>{p['profile']}</td>
<td>{p['windows']}</td>
<td>{p['winning_windows']}</td>
<td>{p['total_trades']}</td>
<td>{money(p['total_pnl'])}</td>
<td>{pct(p['avg_return'])}</td>
<td>{p['avg_pf']:.2f}</td>
</tr>
"""

html += """

</table>

</div>

</body>

</html>

"""

OUTPUT.write_text(html)

print()
print("========== Walk-Forward Profile Comparison ==========")
print()

for i, p in enumerate(profiles):

    print(
        f"{i+1:2}. "
        f"{p['profile']:32}"
        f"PnL={money(p['total_pnl']):>12} "
        f"Return={pct(p['avg_return']):>8} "
        f"PF={p['avg_pf']:.2f}"
    )

print()
print(f"Report: {OUTPUT}")
