from datetime import date

from trading_ai.backtest.trade import BacktestTrade
from trading_ai.backtest.equity import EquityCurveBuilder


def make_trade(symbol, exit_date, pnl):

    return BacktestTrade(
        symbol=symbol,
        entry_date=date(2026, 1, 1),
        exit_date=exit_date,
        strategy="LONG_CALL",
        signal="CALL",
        strike=300.0,
        expiry="2026-09-18",
        entry_price=10.0,
        exit_price=12.0,
        contracts=1,
        pnl=pnl,
        pnl_pct=pnl / 1000.0,
        max_profit=max(pnl, 0),
        max_drawdown=min(pnl, 0),
        days_held=5,
        exit_reason="TEST",
        rank_score=75.0,
        option_score=70.0,
        pop=0.55,
        liquidity=70.0,
        atm_score=100.0,
    )


def main():

    trades = [
        make_trade("AAPL", date(2026, 1, 5), 500.0),
        make_trade("MSFT", date(2026, 1, 8), -300.0),
        make_trade("AMZN", date(2026, 1, 10), 700.0),
    ]

    builder = EquityCurveBuilder()

    curve = builder.build(
        trades,
        initial_capital=100000.0,
    )

    print()
    print("========== Equity Curve Test ==========")

    for point in curve:
        print(point)

    print(f"Max Drawdown: {builder.max_drawdown(curve)}")
    print("=======================================")
    print()


if __name__ == "__main__":
    main()
