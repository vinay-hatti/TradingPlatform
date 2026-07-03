import csv
import json
from pathlib import Path


class BacktestExporter:

    def export_trades(self, trades, path):

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "symbol",
            "entry_date",
            "exit_date",
            "strategy",
            "signal",
            "strike",
            "expiry",
            "entry_price",
            "exit_price",
            "contracts",
            "pnl",
            "pnl_pct",
            "max_profit",
            "max_drawdown",
            "days_held",
            "exit_reason",
            "rank_score",
            "option_score",
            "pop",
            "liquidity",
            "atm_score",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for t in trades:
                writer.writerow({
                    "symbol": t.symbol,
                    "entry_date": t.entry_date,
                    "exit_date": t.exit_date,
                    "strategy": t.strategy,
                    "signal": t.signal,
                    "strike": t.strike,
                    "expiry": t.expiry,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "contracts": t.contracts,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "max_profit": t.max_profit,
                    "max_drawdown": t.max_drawdown,
                    "days_held": t.days_held,
                    "exit_reason": t.exit_reason,
                    "rank_score": t.rank_score,
                    "option_score": t.option_score,
                    "pop": t.pop,
                    "liquidity": t.liquidity,
                    "atm_score": t.atm_score,
                })

    def export_equity(self, equity_curve, path):

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "date",
            "equity",
            "pnl",
            "symbol",
            "exit_reason",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(equity_curve)

    def export_metrics(self, metrics, path):

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(metrics, f, indent=2)

    def export_rejected(self, rejected, path):

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "symbol",
            "entry_date",
            "signal",
            "strategy",
            "entry_price",
            "contracts",
            "reason",
            "rank_score",
            "option_score",
        ]

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for item in rejected:
                trade = item["trade"]

                writer.writerow({
                    "symbol": trade.symbol,
                    "entry_date": trade.entry_date,
                    "signal": trade.signal,
                    "strategy": trade.strategy,
                    "entry_price": trade.entry_price,
                    "contracts": trade.contracts,
                    "reason": item["reason"],
                    "rank_score": trade.rank_score,
                    "option_score": trade.option_score,
                })
