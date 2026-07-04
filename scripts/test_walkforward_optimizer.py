from trading_ai.walkforward.optimizer import WalkForwardOptimizer


def main():

    optimizer = WalkForwardOptimizer()

    best = optimizer.best_run()

    print()
    print("========== Walk-Forward Optimizer ==========")

    print("Best Run")
    print("--------------------------------------------")

    for key in [
        "run",
        "option_premium_pct",
        "take_profit",
        "stop_loss",
        "max_hold",
        "profit_factor",
        "return_pct",
        "net_pnl",
    ]:
        print(f"{key:22}: {best[key]}")

    print("--------------------------------------------")

    print()
    print("Best Parameters")

    for k, v in optimizer.best_parameters().items():
        print(f"{k:22}: {v}")

    print("============================================")
    print()


if __name__ == "__main__":
    main()
