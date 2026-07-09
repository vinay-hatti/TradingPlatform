from collections import defaultdict


class StrategyPerformanceAnalyzer:

    def analyze(self, trades):

        grouped = defaultdict(list)

        for trade in trades:
            strategy = getattr(trade, "strategy", "UNKNOWN")
            signal = getattr(trade, "signal", "UNKNOWN")
            key = f"{strategy}/{signal}"

            pnl = float(
                getattr(
                    trade,
                    "net_pnl",
                    getattr(trade, "pnl", 0.0),
                )
            )

            grouped[key].append(pnl)

        rows = []

        for key, pnls in sorted(grouped.items()):
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]

            gross_profit = sum(wins)
            gross_loss = abs(sum(losses))

            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else 0.0
            )

            rows.append({
                "strategy_signal": key,
                "trades": len(pnls),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(pnls) if pnls else 0.0,
                "net_pnl": sum(pnls),
                "avg_pnl": sum(pnls) / len(pnls) if pnls else 0.0,
                "profit_factor": profit_factor,
            })

        return sorted(
            rows,
            key=lambda r: r["net_pnl"],
            reverse=True,
        )
