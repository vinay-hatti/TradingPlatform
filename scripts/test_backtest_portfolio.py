from datetime import date

from trading_ai.backtest.trade import BacktestTrade
from trading_ai.backtest.portfolio import BacktestPortfolio


def make_trade(symbol, entry_price, exit_price):

    pnl = (exit_price - entry_price) * 100.0

    return BacktestTrade(
        symbol=symbol,
        entry_date=date(2026, 1, 1),
        exit_date=date(2026, 1, 5),
        strategy="LONG_CALL",
        signal="CALL",
        strike=entry_price,
        expiry="STOCK_PROXY",
        entry_price=entry_price,
        exit_price=exit_price,
        contracts=1,
        pnl=pnl,
        pnl_pct=(exit_price - entry_price) / entry_price,
        max_profit=max(pnl, 0.0),
        max_drawdown=min(pnl, 0.0),
        days_held=4,
        exit_reason="TEST",
        rank_score=70.0,
        option_score=70.0,
        pop=0.5,
        liquidity=70.0,
        atm_score=100.0,
    )


def main():

    trades = [
        make_trade("AAPL", 100.0, 105.0),
        make_trade("MSFT", 200.0, 210.0),
        make_trade("AMZN", 5000.0, 5100.0),
    ]

    portfolio = BacktestPortfolio(
        initial_capital=100000.0,
        max_open_positions=5,
        max_position_pct=0.10,
    )

    result = portfolio.process_trades(trades)

    print()
    print("========== Backtest Portfolio Test ==========")
    print(f"Closed Trades : {len(result['closed_trades'])}")
    print(f"Rejected      : {len(result['rejected'])}")
    print(f"Cash          : ${result['cash']:,.2f}")

    for rejected in result["rejected"]:
        print(
            f"Rejected {rejected['trade'].symbol}: "
            f"{rejected['reason']}"
        )

    print("============================================")
    print()


if __name__ == "__main__":
    main()
