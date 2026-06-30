from trading_ai.app.bootstrap import container
from trading_ai.backtest.config import BacktestConfig
from trading_ai.backtest.engine import BacktestEngine
from trading_ai.backtest.report import BacktestReport


def run_window(name, symbols, full_start, full_end, window_start, window_end, config_overrides):

    config = BacktestConfig(
        symbols=symbols,
        start=full_start,
        end=full_end,
        stop_loss_pct=config_overrides["stop_loss_pct"],
        take_profit_pct=config_overrides["take_profit_pct"],
        max_holding_bars=config_overrides["max_holding_bars"],
        min_call_score=config_overrides["min_call_score"],
        min_put_score=config_overrides["min_put_score"],
        min_option_price=config_overrides["min_option_price"],
        min_abs_delta=config_overrides["min_abs_delta"],
        max_abs_delta=config_overrides["max_abs_delta"],
        initial_capital=config_overrides["initial_capital"],
        risk_per_trade_pct=config_overrides["risk_per_trade_pct"],
        max_contracts=config_overrides["max_contracts"],
    )

    engine = BacktestEngine(
        container.strategy_engine,
        container.market,
        container.pipeline,
        config=config,
    )

    results = engine.run(
        symbols=config.symbols,
        start=window_start,
        end=window_end,
    )

    summary = BacktestReport().summarize(results)

    return {
        "window": name,
        "start": window_start,
        "end": window_end,
        "final_pnl": summary["final_pnl"],
        "win_rate": summary["win_rate"],
        "profit_factor": summary["profit_factor"],
        "max_drawdown": summary["max_drawdown"],
        "expectancy": summary["expectancy"],
        "closed_positions": summary["closed_positions"],
    }


def main():

    symbols = ["AAPL", "MSFT"]

    best_config = {
        "stop_loss_pct": -0.06,
        "take_profit_pct": 0.15,
        "max_holding_bars": 10,
        "min_call_score": 60.0,
        "min_put_score": 60.0,
        "min_option_price": 0.50,
        "min_abs_delta": 0.30,
        "max_abs_delta": 0.70,
        "initial_capital": 100000.0,
        "risk_per_trade_pct": 0.01,
        "max_contracts": 5,
    }

    windows = [
        ("Window-1", "2026-01-01", "2026-04-01"),
        ("Window-2", "2026-02-01", "2026-05-01"),
        ("Window-3", "2026-03-01", "2026-06-01"),
    ]

    rows = []

    for name, start, end in windows:
        rows.append(
            run_window(
                name=name,
                symbols=symbols,
                full_start="2026-01-01",
                full_end="2026-06-01",
                window_start=start,
                window_end=end,
                config_overrides=best_config,
            )
        )

    print()
    print("========== Walk Forward Results ==========")

    for r in rows:
        print(
            f"{r['window']:8} | "
            f"{r['start']} -> {r['end']} | "
            f"PnL={r['final_pnl']:>9.2f} | "
            f"Win={r['win_rate']:>6.2%} | "
            f"PF={r['profit_factor']:>5.2f} | "
            f"DD={r['max_drawdown']:>9.2f} | "
            f"Exp={r['expectancy']:>8.2f} | "
            f"Trades={r['closed_positions']}"
        )

    print("==========================================")
    print()


if __name__ == "__main__":
    main()
