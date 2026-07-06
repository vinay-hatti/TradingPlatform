from trading_ai.walkforward.optimizer import WalkForwardOptimizer
from trading_ai.walkforward.validator import WalkForwardValidator


def main():

    optimizer = WalkForwardOptimizer()

    params = optimizer.best_parameters()

    validator = WalkForwardValidator(
        symbols="AAPL,MSFT,AMZN",
    )

    result = validator.validate(
        start="2026-05-01",
        end="2026-06-01",
        params=params,
    )

    metrics = result["metrics"]

    print()
    print("========== Walk-Forward Validator ==========")
    print(f"Test Window : {result['start']} -> {result['end']}")
    print(f"Run Dir     : {result['run_dir']}")
    print()
    print("Parameters")
    print("--------------------------------------------")

    for k, v in result["params"].items():
        print(f"{k:22}: {v}")

    print()
    print("Out-of-Sample Metrics")
    print("--------------------------------------------")
    print(f"Trades       : {metrics['trades']}")
    print(f"Win Rate     : {metrics['win_rate']:.2%}")
    print(f"Return       : {metrics['return_pct']:.2%}")
    print(f"ProfitFactor : {metrics['profit_factor']:.2f}")
    print(f"Net PnL      : ${metrics['net_pnl']:,.2f}")
    print("============================================")
    print()


if __name__ == "__main__":
    main()
