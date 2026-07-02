from datetime import date, timedelta

from trading_ai.backtest.engine import BacktestEngine
from trading_ai.backtest.simulator import OptionTradeSimulator


def future_prices(entry_date, prices):
    return [
        {
            "date": entry_date + timedelta(days=idx),
            "price": price,
        }
        for idx, price in enumerate(prices, start=1)
    ]


def main():

    simulator = OptionTradeSimulator(
        take_profit_pct=0.25,
        stop_loss_pct=-0.12,
        max_hold_days=10,
    )

    trades = []

    trades.append(
        simulator.simulate(
            symbol="AAPL",
            signal="CALL",
            strategy="LONG_CALL",
            strike=305.0,
            expiry="2026-09-18",
            entry_date=date(2026, 1, 1),
            entry_price=10.0,
            future_prices=future_prices(
                date(2026, 1, 1),
                [10.5, 11.4, 12.8],
            ),
            contracts=1,
            rank_score=77.54,
            option_score=71.35,
            pop=0.5143,
            liquidity=70.0,
            atm_score=100.0,
        )
    )

    trades.append(
        simulator.simulate(
            symbol="MSFT",
            signal="CALL",
            strategy="LONG_CALL",
            strike=440.0,
            expiry="2026-09-18",
            entry_date=date(2026, 1, 2),
            entry_price=8.0,
            future_prices=future_prices(
                date(2026, 1, 2),
                [7.8, 7.3, 6.9],
            ),
            contracts=1,
            rank_score=75.81,
            option_score=72.03,
            pop=0.6004,
            liquidity=70.0,
            atm_score=90.0,
        )
    )

    trades.append(
        simulator.simulate(
            symbol="AMZN",
            signal="CALL",
            strategy="LONG_CALL",
            strike=250.0,
            expiry="2026-08-21",
            entry_date=date(2026, 1, 3),
            entry_price=9.0,
            future_prices=future_prices(
                date(2026, 1, 3),
                [9.2, 9.4, 9.6, 9.7],
            ),
            contracts=1,
            rank_score=77.77,
            option_score=76.92,
            pop=0.6197,
            liquidity=70.0,
            atm_score=90.0,
        )
    )

    engine = BacktestEngine(initial_capital=100000.0)

    result = engine.run(
        trades,
        report_path="reports/backtest_engine_test.html",
    )

    metrics = result["metrics"]

    print()
    print("========== Backtest Engine Test ==========")
    print(f"Trades         : {metrics['trades']}")
    print(f"Wins           : {metrics['wins']}")
    print(f"Losses         : {metrics['losses']}")
    print(f"Win Rate       : {metrics['win_rate']:.2%}")
    print(f"Net PnL        : ${metrics['net_pnl']:,.2f}")
    print(f"Return         : {metrics['return_pct']:.2%}")
    print(f"Profit Factor  : {metrics['profit_factor']:.2f}")
    print(f"Expectancy     : ${metrics['expectancy']:,.2f}")
    print(f"Equity Points  : {len(result['equity_curve'])}")
    print(f"Report         : {result['report_path']}")
    print("==========================================")
    print()


if __name__ == "__main__":
    main()
