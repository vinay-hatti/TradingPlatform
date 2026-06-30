class BacktestReport:

    def summarize(self, results):

        open_positions = results.get("open_positions", {})
        closed_positions = results.get("closed_positions", [])
        equity_curve = results.get("equity_curve", [])

        wins = [p for p in closed_positions if p.pnl > 0]
        losses = [p for p in closed_positions if p.pnl <= 0]

        gross_profit = sum(p.pnl for p in wins)
        gross_loss = abs(sum(p.pnl for p in losses))

        win_rate = len(wins) / max(1, len(closed_positions))
        avg_win = gross_profit / max(1, len(wins))
        avg_loss = -gross_loss / max(1, len(losses))

        regime_stats = {}

        for p in closed_positions:
            regime = p.regime or "UNKNOWN"

            if regime not in regime_stats:
                regime_stats[regime] = {
                    "trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "pnl": 0.0,
                }

            regime_stats[regime]["trades"] += 1
            regime_stats[regime]["pnl"] += p.pnl
            if p.pnl > 0:
                regime_stats[regime]["wins"] += 1
            else:
                regime_stats[regime]["losses"] += 1


            strategy_stats = {}
            for p in closed_positions:
                strategy = p.strategy or "UNKNOWN"
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        "trades": 0,
                        "wins": 0,
                        "losses": 0,
                        "pnl": 0.0,
                    }
                strategy_stats[strategy]["trades"] += 1
                strategy_stats[strategy]["pnl"] += p.pnl
                if p.pnl > 0:
                    strategy_stats[strategy]["wins"] += 1
                else:
                    strategy_stats[strategy]["losses"] += 1

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else float("inf")
        )

        expectancy = (
            win_rate * avg_win
            + (1 - win_rate) * avg_loss
        )

        total_pnl = equity_curve[-1] if equity_curve else 0.0

        max_drawdown = self._max_drawdown(equity_curve)
        sharpe, sortino = self._sharpe_sortino(equity_curve)
 
        calmar = (
            total_pnl / max_drawdown
            if max_drawdown > 0
            else 0.0
        )

        exit_reasons = {}

        for p in closed_positions:
            reason = p.exit_reason or "UNKNOWN"
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

#        total_pnl = equity_curve[-1] if equity_curve else 0.0

        return {
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": win_rate,
            "final_pnl": total_pnl,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "max_drawdown": max_drawdown,
            "exit_reasons": exit_reasons,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "regime_stats": regime_stats,
            "strategy_stats": strategy_stats,
        }

    def _max_drawdown(self, equity_curve):

        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_dd = 0.0

        for value in equity_curve:
            peak = max(peak, value)
            drawdown = peak - value
            max_dd = max(max_dd, drawdown)

        return max_dd

    def print(self, results):

        summary = self.summarize(results)

        print()
        print("========== Backtest Summary ==========")
        print(f"Open Positions  : {summary['open_positions']}")
        print(f"Closed Positions: {summary['closed_positions']}")
        print(f"Wins            : {summary['wins']}")
        print(f"Losses          : {summary['losses']}")
        print(f"Win Rate        : {summary['win_rate']:.2%}")
        print(f"Average Win     : {summary['avg_win']:.2f}")
        print(f"Average Loss    : {summary['avg_loss']:.2f}")
        print(f"Gross Profit    : {summary['gross_profit']:.2f}")
        print(f"Gross Loss      : {summary['gross_loss']:.2f}")
        print(f"Profit Factor   : {summary['profit_factor']:.2f}")
        print(f"Expectancy      : {summary['expectancy']:.2f}")
        print(f"Max Drawdown    : {summary['max_drawdown']:.2f}")
        print(f"Final PnL       : {summary['final_pnl']:.2f}")
        print(f"Sharpe Ratio    : {summary['sharpe']:.2f}")
        print(f"Sortino Ratio   : {summary['sortino']:.2f}")
        print(f"Calmar Ratio    : {summary['calmar']:.2f}")

        print()
        print("Exit Reasons:")
        for reason, count in summary["exit_reasons"].items():
            print(f"  {reason:12}: {count}")

        print()
        print("Regime Stats:")
        for regime, stats in summary["regime_stats"].items():
            win_rate = stats["wins"] / max(1, stats["trades"])
            print(
                f"  {regime:12} | "
                f"Trades={stats['trades']:3} | "
                f"Win={win_rate:6.2%} | "
                f"PnL={stats['pnl']:10.2f}"
            )

        print()
        print("Strategy Stats:")
        for strategy, stats in summary["strategy_stats"].items():
            win_rate = stats["wins"] / max(1, stats["trades"])
            print(
                f"  {strategy:14} | "
                f"Trades={stats['trades']:3} | "
                f"Win={win_rate:6.2%} | "
                f"PnL={stats['pnl']:10.2f}"
            )

        print("======================================")
        print()

        self.print_closed_trades(results)

    def print_closed_trades(self, results):

        closed_positions = results.get("closed_positions", [])

        if not closed_positions:
            print("No closed trades.")
            return

        print("========== Closed Trades =============")

        for p in closed_positions:
            print(
                f"{p.symbol:5} | "
                f"{p.signal:4} | "
                f"Regime={p.regime:12} | "
                f"EntryIdx={p.entry_index:3} | "
                f"ExitIdx={p.exit_index:3} | "
                f"Reason={p.exit_reason:11} | "
                f"StockIn={p.stock_entry_price:8.2f} | "
                f"StockOut={p.stock_exit_price:8.2f} | "
                f"OptIn={p.option_entry_price:8.2f} | "
                f"OptOut={p.option_exit_price:8.2f} | "
                f"PnL={p.pnl:10.2f} | "
                f"Score={p.score:6.2f}"
            )

        print("======================================")
        print()

    def export_closed_trades_csv(self, results, path="reports/closed_trades.csv"):

        import csv
        from pathlib import Path

        closed_positions = results.get("closed_positions", [])

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)

            writer.writerow([
                "symbol",
                "signal",
                "strategy",
                "entry_index",
                "exit_index",
                "exit_reason",
                "stock_entry_price",
                "stock_exit_price",
                "option_entry_price",
                "option_exit_price",
                "strike",
                "expiry",
                "delta",
                "size",
                "score",
                "pnl",
            ])

            for p in closed_positions:
                writer.writerow([
                    p.symbol,
                    p.signal,
                    p.strategy,
                    p.entry_index,
                    p.exit_index,
                    p.exit_reason,
                    p.stock_entry_price,
                    p.stock_exit_price,
                    p.option_entry_price,
                    p.option_exit_price,
                    p.strike,
                    p.expiry,
                    p.delta,
                    p.size,
                    p.score,
                    p.pnl,
                ])

        print(f"Closed trades exported to {path}")

    def export_equity_curve_csv(self, results, path="reports/equity_curve.csv"):

        import csv
        from pathlib import Path

        equity_curve = results.get("equity_curve", [])

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="") as f:
            writer = csv.writer(f)

            writer.writerow([
                "step",
                "equity",
            ])

            for i, value in enumerate(equity_curve):
                writer.writerow([
                    i,
                    value,
                ])

        print(f"Equity curve exported to {path}")

    def export_equity_curve_chart(self, results, path="reports/equity_curve.png"):

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed; skipping chart export.")
            return

        from pathlib import Path

        equity_curve = results.get("equity_curve", [])

        if not equity_curve:
            print("No equity curve to chart.")
            return

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        plt.figure(figsize=(12, 6))
        plt.plot(equity_curve, linewidth=2)
        plt.title("Trading AI Equity Curve")
        plt.xlabel("Step")
        plt.ylabel("PnL")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(path, dpi=150)
        plt.close()

        print(f"Equity curve chart exported to {path}")

    def _returns(self, equity_curve):

        if len(equity_curve) < 2:
            return []

        returns = []

        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]
            curr = equity_curve[i]

            if prev == 0:
                returns.append(0.0)
            else:
                returns.append((curr - prev) / abs(prev))

        return returns

    def _sharpe_sortino(self, equity_curve):

        import math
        import statistics

        returns = self._returns(equity_curve)

        if len(returns) < 2:
            return 0.0, 0.0

        mean_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)

        sharpe = (
            mean_return / std_return * math.sqrt(252)
            if std_return > 0
            else 0.0
        )

        downside = [r for r in returns if r < 0]

        if len(downside) < 2:
            sortino = 0.0
        else:
            downside_std = statistics.stdev(downside)
            sortino = (
                mean_return / downside_std * math.sqrt(252)
                if downside_std > 0
                else 0.0
            )

        return sharpe, sortino

