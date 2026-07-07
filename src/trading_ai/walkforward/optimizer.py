import csv
from pathlib import Path

from trading_ai.optimization.strategy_scorer import StrategyScorer


class WalkForwardOptimizer:

    def __init__(
        self,
        summary_file="reports/backtest_experiments/summary.csv",
        profile="balanced",
        min_trades=10,
    ):
        self.summary_file = Path(summary_file)
        self.profile = profile
        self.min_trades = int(min_trades)
        self.scorer = StrategyScorer.from_profile(
            profile,
            min_trades=min_trades,
        )

    def _load_rows(self):

        if not self.summary_file.exists():
            raise FileNotFoundError(self.summary_file)

        with open(self.summary_file) as f:
            rows = list(csv.DictReader(f))

        if not rows:
            raise RuntimeError("No experiment results found.")

        return rows

    def ranked_runs(self):

        rows = self._load_rows()

        return self.scorer.score_rows(rows)

    def best_run(self):

        ranked = self.ranked_runs()

        return ranked[0]

    def best_parameters(self):

        best = self.best_run()

        return {
            "option_premium_pct": float(best.get("option_premium_pct", 0.10)),
            "take_profit": float(best.get("take_profit", 0.03)),
            "stop_loss": float(best.get("stop_loss", -0.02)),
            "max_hold": int(float(best.get("max_hold", 5))),
            "min_delta": float(best.get("min_delta", 0.0)),
            "max_delta": float(best.get("max_delta", 1.0)),
            "min_vega": float(best.get("min_vega", 0.0)),
            "max_vega": float(best.get("max_vega", 999.0)),
            "max_theta": float(best.get("max_theta", 999.0)),
        }
