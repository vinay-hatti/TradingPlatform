import json
import subprocess
from pathlib import Path


class WalkForwardValidator:

    def __init__(
        self,
        symbols,
        capital=100000.0,
        max_position_pct=0.05,
        risk_per_trade_pct=0.05,
        sizer_max_position_pct=0.05,
    ):
        self.symbols = symbols
        self.capital = capital
        self.max_position_pct = max_position_pct
        self.risk_per_trade_pct = risk_per_trade_pct
        self.sizer_max_position_pct = sizer_max_position_pct

    def latest_backtest_dir(self):

        dirs = sorted(
            Path("reports/backtests").glob("*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        return dirs[0] if dirs else None

    def validate(
        self,
        start,
        end,
        params,
    ):
        cmd = [
            "uv",
            "run",
            "python",
            "-m",
            "trading_ai",
            "backtest",
            "--symbols",
            self.symbols,
            "--start",
            str(start),
            "--end",
            str(end),
            "--capital",
            str(self.capital),
            "--max-position-pct",
            str(self.max_position_pct),
            "--risk-per-trade-pct",
            str(self.risk_per_trade_pct),
            "--sizer-max-position-pct",
            str(self.sizer_max_position_pct),
            "--option-premium-pct",
            str(params["option_premium_pct"]),
            "--take-profit",
            str(params["take_profit"]),
            "--stop-loss",
            str(params["stop_loss"]),
            "--max-hold",
            str(params["max_hold"]),
        ]

        subprocess.run(
            cmd,
            check=True,
        )

        run_dir = self.latest_backtest_dir()

        metrics_path = run_dir / "metrics.json"

        with open(metrics_path, "r") as f:
            metrics = json.load(f)

        return {
            "start": str(start),
            "end": str(end),
            "params": params,
            "run_dir": str(run_dir),
            "metrics": metrics,
        }
