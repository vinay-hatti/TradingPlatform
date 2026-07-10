import csv
import json
from pathlib import Path


class BacktestExporter:

    def _get(self, obj, name, default=""):
        return getattr(obj, name, default)

    def export_trades(self, trades, path):

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "symbol",
            "entry_date",
            "exit_date",
            "strategy",
            "signal",
            "pricing_source",
            "option_symbol",
            "strike",
            "expiry",
            "entry_price",
            "exit_price",
            "entry_delta",
            "entry_gamma",
            "entry_theta",
            "entry_vega",
            "entry_rho",
            "entry_volatility",
            "entry_dte",
            "option_volume",
            "option_open_interest",
            "option_spread_pct",
            "contracts",
            "pnl",
            "pnl_pct",
            "gross_pnl",
            "fees",
            "net_pnl",
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
                    "symbol": self._get(t, "symbol"),
                    "entry_date": self._get(t, "entry_date"),
                    "exit_date": self._get(t, "exit_date"),
                    "strategy": self._get(t, "strategy"),
                    "signal": self._get(t, "signal"),
                    "pricing_source": self._get(t, "pricing_source", "black_scholes_proxy"),
                    "option_symbol": self._get(t, "option_symbol", ""),
                    "strike": self._get(t, "strike"),
                    "expiry": self._get(t, "expiry"),
                    "entry_price": self._get(t, "entry_price", 0.0),
                    "exit_price": self._get(t, "exit_price", 0.0),
                    "entry_delta": self._get(t, "entry_delta", 0.0),
                    "entry_gamma": self._get(t, "entry_gamma", 0.0),
                    "entry_theta": self._get(t, "entry_theta", 0.0),
                    "entry_vega": self._get(t, "entry_vega", 0.0),
                    "entry_rho": self._get(t, "entry_rho", 0.0),
                    "entry_volatility": self._get(t, "entry_volatility", 0.0),
                    "entry_dte": self._get(t, "entry_dte", 0),
                    "option_volume": self._get(t, "option_volume", 0),
                    "option_open_interest": self._get(t, "option_open_interest", 0),
                    "option_spread_pct": self._get(t, "option_spread_pct", 0.0),
                    "contracts": self._get(t, "contracts", 0),
                    "pnl": self._get(t, "pnl", 0.0),
                    "pnl_pct": self._get(t, "pnl_pct", 0.0),
                    "gross_pnl": self._get(t, "gross_pnl", 0.0),
                    "fees": self._get(t, "fees", 0.0),
                    "net_pnl": self._get(t, "net_pnl", self._get(t, "pnl", 0.0)),
                    "max_profit": self._get(t, "max_profit", 0.0),
                    "max_drawdown": self._get(t, "max_drawdown", 0.0),
                    "days_held": self._get(t, "days_held", 0),
                    "exit_reason": self._get(t, "exit_reason", ""),
                    "rank_score": self._get(t, "rank_score", 0.0),
                    "option_score": self._get(t, "option_score", 0.0),
                    "pop": self._get(t, "pop", 0.0),
                    "liquidity": self._get(t, "liquidity", 0.0),
                    "atm_score": self._get(t, "atm_score", 0.0),
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
            "pricing_source",
            "option_symbol",
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
                trade = item.get("trade")

                writer.writerow({
                    "symbol": self._get(trade, "symbol"),
                    "entry_date": self._get(trade, "entry_date"),
                    "signal": self._get(trade, "signal"),
                    "strategy": self._get(trade, "strategy"),
                    "pricing_source": self._get(trade, "pricing_source", ""),
                    "option_symbol": self._get(trade, "option_symbol", ""),
                    "entry_price": self._get(trade, "entry_price", 0.0),
                    "contracts": self._get(trade, "contracts", 0),
                    "reason": item.get("reason", ""),
                    "rank_score": self._get(trade, "rank_score", 0.0),
                    "option_score": self._get(trade, "option_score", 0.0),
                })
