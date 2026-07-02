from datetime import date

from trading_ai.backtest.trade import BacktestTrade
from trading_ai.backtest.metrics import BacktestMetrics


def main():

    trades = [
        BacktestTrade(
            symbol="AAPL",
            entry_date=date(2026, 1, 1),
            exit_date=date(2026, 1, 5),
            strategy="LONG_CALL",
            signal="CALL",
            strike=300.0,
            expiry="2026-09-18",
            entry_price=10.0,
            exit_price=12.0,
            contracts=1,
            pnl=200.0,
            pnl_pct=0.20,
            max_profit=250.0,
            max_drawdown=-50.0,
            days_held=4,
            exit_reason="TAKE_PROFIT",
            rank_score=77.5,
            option_score=71.3,
            pop=0.51,
            liquidity=70.0,
            atm_score=100.0,
        ),
        BacktestTrade(
            symbol="MSFT",
            entry_date=date(2026, 1, 2),
            exit_date=date(2026, 1, 8),
            strategy="LONG_CALL",
            signal="CALL",
            strike=440.0,
            expiry="2026-09-18",
            entry_price=8.0,
            exit_price=7.0,
            contracts=1,
            pnl=-100.0,
            pnl_pct=-0.125,
            max_profit=80.0,
            max_drawdown=-140.0,
            days_held=6,
            exit_reason="STOP_LOSS",
            rank_score=75.8,
            option_score=72.0,
            pop=0.60,
            liquidity=70.0,
            atm_score=90.0,
        ),
    ]

    metrics = BacktestMetrics().calculate(
        trades,
        initial_capital=100000.0,
    )

    print()
    print("========== Backtest Metrics Test ==========")

    for key, value in metrics.items():
        print(f"{key:20}: {value}")

    print("===========================================")
    print()


if __name__ == "__main__":
    main()
