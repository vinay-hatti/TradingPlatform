import json
from pathlib import Path


def latest_metrics_file():

    files = sorted(
        Path("reports/backtests").glob("*/metrics.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    return files[0] if files else None


def money(value):
    return f"${float(value):,.2f}"


def pct(value):
    return f"{float(value) * 100:.2f}%"


def main():

    path = latest_metrics_file()

    if path is None:
        raise FileNotFoundError("No backtest metrics.json found.")

    with open(path, "r") as f:
        metrics = json.load(f)

    print()
    print("========== Advanced Risk Analytics ==========")
    print(f"Metrics File : {path}")
    print("---------------------------------------------")
    print(f"Net PnL      : {money(metrics.get('net_pnl', 0.0))}")
    print(f"Return       : {pct(metrics.get('return_pct', 0.0))}")
    print(f"ProfitFactor : {metrics.get('profit_factor', 0.0):.2f}")
    print(f"Win Rate     : {pct(metrics.get('win_rate', 0.0))}")
    print()
    print("Risk Metrics")
    print("---------------------------------------------")
    print(f"Max DD       : {pct(metrics.get('max_drawdown_pct', 0.0))}")
    print(f"Max DD $     : {money(metrics.get('max_drawdown_dollars', 0.0))}")
    print(f"Sharpe       : {metrics.get('sharpe_ratio', 0.0):.2f}")
    print(f"Sortino      : {metrics.get('sortino_ratio', 0.0):.2f}")
    print(f"Calmar       : {metrics.get('calmar_ratio', 0.0):.2f}")
    print()
    print("Trade Quality")
    print("---------------------------------------------")
    print(f"Avg Win      : {money(metrics.get('avg_win', 0.0))}")
    print(f"Avg Loss     : {money(metrics.get('avg_loss', 0.0))}")
    print(f"Payoff Ratio : {metrics.get('payoff_ratio', 0.0):.2f}")
    print(f"Largest Win  : {money(metrics.get('largest_win', 0.0))}")
    print(f"Largest Loss : {money(metrics.get('largest_loss', 0.0))}")
    print("=============================================")
    print()


if __name__ == "__main__":
    main()
