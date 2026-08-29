from datetime import date

from trading_ai.backtest.trade import BacktestTrade
from trading_ai.backtest.report import BacktestReport


def make_trade(symbol, exit_date, pnl, reason):

    return BacktestTrade(
        symbol=symbol,
        entry_date=date(2026, 1, 1),
        exit_date=exit_date,
        strategy="LONG_CALL",
        signal="CALL",
        strike=300.0,
        expiry="2026-09-18",
        entry_price=10.0,
        exit_price=10.0 + pnl / 100.0,
        contracts=1,
        pnl=pnl,
        pnl_pct=pnl / 1000.0,
        max_profit=max(pnl, 0),
        max_drawdown=min(pnl, 0),
        days_held=5,
        exit_reason=reason,
        rank_score=75.0,
        option_score=70.0,
        pop=0.55,
        liquidity=70.0,
        atm_score=100.0,
    )


def main():

    trades = [
        make_trade("AAPL", date(2026, 1, 5), 500.0, "TAKE_PROFIT"),
        make_trade("MSFT", date(2026, 1, 8), -300.0, "STOP_LOSS"),
        make_trade("AMZN", date(2026, 1, 10), 700.0, "TAKE_PROFIT"),
    ]

    path = BacktestReport().generate(
        trades,
        path="reports/backtest_test.html",
    )

    print(f"Backtest report created: {path}")


if __name__ == "__main__":
    main()
