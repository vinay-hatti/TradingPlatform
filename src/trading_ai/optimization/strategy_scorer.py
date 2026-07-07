import csv
from pathlib import Path


class StrategyScorer:

    def __init__(
        self,
        profit_factor_weight=0.40,
        return_weight=0.30,
        win_rate_weight=0.15,
        trade_count_weight=0.10,
        expectancy_weight=0.05,
        min_trades=10,
    ):
        self.profit_factor_weight = float(profit_factor_weight)
        self.return_weight = float(return_weight)
        self.win_rate_weight = float(win_rate_weight)
        self.trade_count_weight = float(trade_count_weight)
        self.expectancy_weight = float(expectancy_weight)
        self.min_trades = int(min_trades)

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    def _safe_int(self, value, default=0):
        try:
            return int(float(value))
        except Exception:
            return default

    @classmethod
    def from_profile(cls, profile, min_trades=10):

        profile = str(profile).lower()

        if profile == "conservative":
            return cls(
                profit_factor_weight=0.55,
                return_weight=0.15,
                win_rate_weight=0.15,
                trade_count_weight=0.05,
                expectancy_weight=0.10,
                min_trades=min_trades,
            )

        if profile == "aggressive":
            return cls(
                profit_factor_weight=0.20,
                return_weight=0.50,
                win_rate_weight=0.10,
                trade_count_weight=0.10,
                expectancy_weight=0.10,
                min_trades=min_trades,
            )

        return cls(
            profit_factor_weight=0.40,
            return_weight=0.30,
            win_rate_weight=0.15,
            trade_count_weight=0.10,
            expectancy_weight=0.05,
            min_trades=min_trades,
        )

    def score_row(self, row):

        trades = self._safe_int(row.get("trades", 0))
        profit_factor = self._safe_float(row.get("profit_factor", 0.0))
        return_pct = self._safe_float(row.get("return_pct", 0.0))
        win_rate = self._safe_float(row.get("win_rate", 0.0))
        expectancy = self._safe_float(row.get("expectancy", 0.0))

        if trades < self.min_trades:
            return 0.0

        pf_score = min(profit_factor / 3.0, 1.0) * 100.0
        return_score = max(min(return_pct / 0.50, 1.0), -1.0) * 100.0
        win_score = win_rate * 100.0
        trade_score = min(trades / 100.0, 1.0) * 100.0
        expectancy_score = max(min(expectancy / 1000.0, 1.0), -1.0) * 100.0

        total = (
            pf_score * self.profit_factor_weight
            + return_score * self.return_weight
            + win_score * self.win_rate_weight
            + trade_score * self.trade_count_weight
            + expectancy_score * self.expectancy_weight
        )

        return total

    def score_rows(self, rows):

        scored = []

        for row in rows:
            scored_row = dict(row)
            scored_row["strategy_score"] = self.score_row(row)
            scored.append(scored_row)

        return sorted(
            scored,
            key=lambda r: float(r["strategy_score"]),
            reverse=True,
        )

    def load_summary(self, path):

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(path)

        with open(path, "r") as f:
            return list(csv.DictReader(f))

    def rank_file(self, path):
        rows = self.load_summary(path)
        return self.score_rows(rows)
