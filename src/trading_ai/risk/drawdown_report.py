import csv
from pathlib import Path

from trading_ai.risk.metrics import RiskMetricsEngine


class DrawdownReporter:

    def export_csv(
        self,
        equity_curve,
        path,
    ):
        rows = RiskMetricsEngine().drawdown_curve(
            equity_curve,
        )

        fieldnames = [
            "date",
            "equity",
            "peak_equity",
            "drawdown_dollars",
            "drawdown_pct",
        ]

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames,
            )

            writer.writeheader()
            writer.writerows(rows)

        return path
