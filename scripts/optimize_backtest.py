from itertools import product

from trading_ai.app.bootstrap import container
from trading_ai.backtest.config import BacktestConfig
from trading_ai.backtest.engine import BacktestEngine
from trading_ai.backtest.report import BacktestReport


def export_results(rows, path="reports/optimization_results.csv"):

    import csv
    from pathlib import Path

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "stop_loss",
                "take_profit",
                "max_hold",
                "min_call_score",
                "min_put_score",
                "min_option_price",
                "min_abs_delta",
                "max_abs_delta",
                "final_pnl",
                "win_rate",
                "profit_factor",
                "max_drawdown",
                "expectancy",
                "closed_positions",
            ],
        )

        writer.writeheader()
        writer.writerows(rows)

    print(f"Optimization results exported to {path}")


def main():

    symbols = ["AAPL", "MSFT"]
    start = "2026-01-01"
    end = "2026-06-01"

    stop_losses = [-0.06, -0.08, -0.10]
    take_profits = [0.12, 0.15, 0.20]
    max_holds = [5, 10, 15]

    min_scores = [60.0, 65.0, 70.0]
    min_option_prices = [0.50, 1.00, 2.00]
    delta_ranges = [
        (0.30, 0.70),
        (0.35, 0.65),
    ]

    report = BacktestReport()

    rows = []

    for (
        stop_loss,
        take_profit,
        max_hold,
        min_score,
        min_option_price,
        delta_range,
    ) in product(
        stop_losses,
        take_profits,
        max_holds,
        min_scores,
        min_option_prices,
        delta_ranges,
    ):

        min_delta, max_delta = delta_range

        config = BacktestConfig(
            symbols=symbols,
            start=start,
            end=end,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
            max_holding_bars=max_hold,
            min_call_score=min_score,
            min_put_score=min_score,
            min_option_price=min_option_price,
            min_abs_delta=min_delta,
            max_abs_delta=max_delta,
        )

        engine = BacktestEngine(
            container.strategy_engine,
            container.market,
            container.pipeline,
            config=config,
        )

        results = engine.run(
            symbols=config.symbols,
            start=config.start,
            end=config.end,
        )

        summary = report.summarize(results)

        rows.append({
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "max_hold": max_hold,
            "min_call_score": min_score,
            "min_put_score": min_score,
            "min_option_price": min_option_price,
            "min_abs_delta": min_delta,
            "max_abs_delta": max_delta,
            "final_pnl": summary["final_pnl"],
            "win_rate": summary["win_rate"],
            "profit_factor": summary["profit_factor"],
            "max_drawdown": summary["max_drawdown"],
            "expectancy": summary["expectancy"],
            "closed_positions": summary["closed_positions"],
        })

    rows = sorted(
        rows,
        key=lambda x: (
            x["profit_factor"],
            x["final_pnl"],
        ),
        reverse=True,
    )

    print()
    print("========== Optimization Results ==========")

    for r in rows[:15]:
        print(
            f"SL={r['stop_loss']:>6.2%} | "
            f"TP={r['take_profit']:>6.2%} | "
            f"Hold={r['max_hold']:>2} | "
            f"Score={r['min_call_score']:>4.0f} | "
            f"MinPrem={r['min_option_price']:>4.2f} | "
            f"Delta={r['min_abs_delta']:.2f}-{r['max_abs_delta']:.2f} | "
            f"PnL={r['final_pnl']:>9.2f} | "
            f"Win={r['win_rate']:>6.2%} | "
            f"PF={r['profit_factor']:>5.2f} | "
            f"DD={r['max_drawdown']:>9.2f} | "
            f"Exp={r['expectancy']:>8.2f} | "
            f"Trades={r['closed_positions']}"
        )

    print("==========================================")
    print()

    export_results(rows)


if __name__ == "__main__":
    main()
