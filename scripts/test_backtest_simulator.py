from datetime import date, timedelta

from trading_ai.backtest.simulator import OptionTradeSimulator


def main():

    simulator = OptionTradeSimulator(
        take_profit_pct=0.25,
        stop_loss_pct=-0.12,
        max_hold_days=10,
    )

    entry_date = date(2026, 1, 1)

    future_prices = [
        {"date": entry_date + timedelta(days=1), "price": 10.50},
        {"date": entry_date + timedelta(days=2), "price": 11.20},
        {"date": entry_date + timedelta(days=3), "price": 12.70},
        {"date": entry_date + timedelta(days=4), "price": 13.00},
    ]

    trade = simulator.simulate(
        symbol="AAPL",
        signal="CALL",
        strategy="LONG_CALL",
        strike=305.0,
        expiry="2026-09-18",
        entry_date=entry_date,
        entry_price=10.0,
        future_prices=future_prices,
        contracts=1,
        rank_score=77.54,
        option_score=71.35,
        pop=0.5143,
        liquidity=70.0,
        atm_score=100.0,
    )

    print()
    print("========== Backtest Simulator Test ==========")
    print(trade)
    print("=============================================")
    print()


if __name__ == "__main__":
    main()
