from trading_ai.risk.metrics import RiskMetricsEngine


class Trade:
    def __init__(self, net_pnl):
        self.net_pnl = net_pnl


def main():

    equity = [
        {"date": "2026-01-01", "equity": 100000},
        {"date": "2026-01-02", "equity": 101000},
        {"date": "2026-01-03", "equity": 99000},
        {"date": "2026-01-04", "equity": 103000},
        {"date": "2026-01-05", "equity": 102000},
    ]

    trades = [
        Trade(1000),
        Trade(-500),
        Trade(2000),
        Trade(-800),
    ]

    metrics = RiskMetricsEngine().compute(
        equity_curve=equity,
        trades=trades,
        initial_capital=100000,
    )

    print()
    print("========== Risk Metrics Test ==========")

    for key, value in metrics.items():
        if "ratio" in key or "return" in key or "drawdown_pct" in key:
            print(f"{key:24}: {value:.4f}")
        else:
            print(f"{key:24}: ${value:,.2f}")

    print("=======================================")
    print()


if __name__ == "__main__":
    main()
