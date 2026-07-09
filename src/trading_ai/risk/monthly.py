from collections import defaultdict


class MonthlyReturnAnalyzer:

    def analyze(self, trades):

        grouped = defaultdict(list)

        for trade in trades:
            exit_date = getattr(trade, "exit_date", None)

            if exit_date is None:
                continue

            month = str(exit_date)[:7]
            pnl = float(
                getattr(
                    trade,
                    "net_pnl",
                    getattr(trade, "pnl", 0.0),
                )
            )

            grouped[month].append(pnl)

        rows = []

        for month, pnls in sorted(grouped.items()):
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]

            rows.append({
                "month": month,
                "trades": len(pnls),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": len(wins) / len(pnls) if pnls else 0.0,
                "net_pnl": sum(pnls),
                "avg_pnl": sum(pnls) / len(pnls) if pnls else 0.0,
            })

        return rows
