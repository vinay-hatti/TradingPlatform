import csv
from pathlib import Path


class WalkForwardOptimizer:

    def __init__(
        self,
        summary_file="reports/backtest_experiments/summary.csv",
    ):
        self.summary_file = Path(summary_file)

    def best_run(self):

        if not self.summary_file.exists():
            raise FileNotFoundError(self.summary_file)

        with open(self.summary_file) as f:
            rows = list(csv.DictReader(f))

        if not rows:
            raise RuntimeError("No experiment results found.")

        rows.sort(
            key=lambda r: (
                float(r["profit_factor"]),
                float(r["return_pct"]),
            ),
            reverse=True,
        )

        return rows[0]

    def best_parameters(self):

        best = self.best_run()

        return {
            "option_premium_pct": float(best["option_premium_pct"]),
            "take_profit": float(best["take_profit"]),
            "stop_loss": float(best["stop_loss"]),
            "max_hold": int(best["max_hold"]),
        }
