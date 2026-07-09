import math
from collections import defaultdict


class ReportingAnalytics:

    def _pnl(self, trade):
        value = getattr(trade, "net_pnl", None)
        if value in (None, 0.0):
            value = getattr(trade, "pnl", 0.0)
        return float(value)

    def _safe_div(self, a, b):
        return a / b if b else 0.0

    def trade_pnls(self, trades):
        return [self._pnl(t) for t in trades]

    def returns_from_equity(self, equity_curve):
        returns = []
        for i in range(1, len(equity_curve)):
            prev = float(equity_curve[i - 1]["equity"])
            curr = float(equity_curve[i]["equity"])
            if prev > 0:
                returns.append((curr - prev) / prev)
        return returns

    def drawdown_curve(self, equity_curve):
        rows = []
        peak = None

        for point in equity_curve:
            equity = float(point["equity"])

            if peak is None or equity > peak:
                peak = equity

            dd_dollars = equity - peak
            dd_pct = self._safe_div(dd_dollars, peak)

            rows.append({
                "date": point.get("date", ""),
                "equity": equity,
                "peak_equity": peak,
                "drawdown_dollars": dd_dollars,
                "drawdown_pct": dd_pct,
            })

        return rows

    def drawdown_duration(self, equity_curve):
        curve = self.drawdown_curve(equity_curve)

        current = 0
        longest = 0

        for row in curve:
            if float(row["drawdown_pct"]) < 0:
                current += 1
                longest = max(longest, current)
            else:
                current = 0

        return {
            "longest_drawdown_duration": longest,
            "current_drawdown_duration": current,
        }

    def streaks(self, trades):
        max_win = 0
        max_loss = 0
        current_win = 0
        current_loss = 0

        for trade in trades:
            pnl = self._pnl(trade)

            if pnl > 0:
                current_win += 1
                current_loss = 0
            elif pnl < 0:
                current_loss += 1
                current_win = 0
            else:
                current_win = 0
                current_loss = 0

            max_win = max(max_win, current_win)
            max_loss = max(max_loss, current_loss)

        return {
            "longest_win_streak": max_win,
            "longest_loss_streak": max_loss,
        }

    def monthly_heatmap(self, trades, initial_capital=100000):
        grouped = defaultdict(float)

        for trade in trades:
            exit_date = str(getattr(trade, "exit_date", ""))[:10]
            if not exit_date:
                continue

            year = exit_date[:4]
            month = exit_date[5:7]
            grouped[(year, month)] += self._pnl(trade)

        years = sorted(set(y for y, _ in grouped.keys()))
        months = ["01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"]

        rows = []
        for year in years:
            row = {"year": year}
            for month in months:
                pnl = grouped.get((year, month), 0.0)
                row[month] = pnl / float(initial_capital)
                row[f"{month}_pnl"] = pnl
            rows.append(row)

        return rows

    def rolling_metrics(self, equity_curve, window=20):
        returns = self.returns_from_equity(equity_curve)
        dates = [p.get("date", "") for p in equity_curve][1:]

        rows = []

        for i in range(len(returns)):
            subset = returns[max(0, i - window + 1): i + 1]

            if len(subset) < 2:
                sharpe = 0.0
                vol = 0.0
            else:
                mean = sum(subset) / len(subset)
                variance = sum((r - mean) ** 2 for r in subset) / len(subset)
                std = math.sqrt(variance)
                vol = std * math.sqrt(252)
                sharpe = (mean / std * math.sqrt(252)) if std else 0.0

            rows.append({
                "date": dates[i],
                "rolling_return": sum(subset),
                "rolling_sharpe": sharpe,
                "rolling_volatility": vol,
            })

        return rows

    def var_cvar(self, trades, confidence=0.95):
        pnls = sorted(self.trade_pnls(trades))

        if not pnls:
            return {
                "var_95": 0.0,
                "cvar_95": 0.0,
            }

        index = int((1.0 - confidence) * len(pnls))
        index = max(0, min(index, len(pnls) - 1))

        var = pnls[index]
        tail = pnls[: index + 1]
        cvar = sum(tail) / len(tail) if tail else 0.0

        return {
            "var_95": var,
            "cvar_95": cvar,
        }

    def kelly(self, trades):
        pnls = self.trade_pnls(trades)

        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]

        if not pnls or not wins or not losses:
            return {
                "kelly_fraction": 0.0,
                "half_kelly": 0.0,
            }

        win_rate = len(wins) / len(pnls)
        loss_rate = 1.0 - win_rate

        avg_win = sum(wins) / len(wins)
        avg_loss = sum(losses) / len(losses)

        b = self._safe_div(avg_win, avg_loss)

        if b <= 0:
            kelly = 0.0
        else:
            kelly = win_rate - (loss_rate / b)

        return {
            "kelly_fraction": kelly,
            "half_kelly": kelly / 2.0,
        }

    def ulcer_index(self, equity_curve):
        curve = self.drawdown_curve(equity_curve)

        if not curve:
            return 0.0

        squares = [
            (float(r["drawdown_pct"]) * 100.0) ** 2
            for r in curve
        ]

        return math.sqrt(sum(squares) / len(squares))

    def omega_ratio(self, trades, threshold=0.0):
        pnls = self.trade_pnls(trades)

        gains = [p - threshold for p in pnls if p > threshold]
        losses = [threshold - p for p in pnls if p < threshold]

        return self._safe_div(sum(gains), sum(losses))

    def tail_ratio(self, trades):
        pnls = sorted(self.trade_pnls(trades))

        if len(pnls) < 10:
            return 0.0

        p95 = pnls[int(0.95 * (len(pnls) - 1))]
        p05 = pnls[int(0.05 * (len(pnls) - 1))]

        return self._safe_div(abs(p95), abs(p05))

    def recovery_factor(self, total_pnl, max_drawdown_dollars):
        return self._safe_div(float(total_pnl), abs(float(max_drawdown_dollars)))

    def time_in_market(self, trades, equity_curve):
        if not equity_curve:
            return 0.0

        active_days = set()

        for trade in trades:
            entry = str(getattr(trade, "entry_date", ""))[:10]
            exit_ = str(getattr(trade, "exit_date", ""))[:10]
            if entry:
                active_days.add(entry)
            if exit_:
                active_days.add(exit_)

        total_days = len(set(str(p.get("date", ""))[:10] for p in equity_curve))

#        return self._safe_div(len(active_days), total_days)
        return min(
            1.0,
            self._safe_div(len(active_days), total_days),
        )

    def regime_performance(self, trades):
        return self._grouped_performance(
            trades,
            lambda t: getattr(t, "market_regime", getattr(t, "regime", "UNKNOWN")),
            "regime",
        )

    def greek_bucket_performance(self, trades):
        return {
            "gamma": self._bucketed(trades, "entry_gamma", [0.02, 0.04, 0.06, 0.08]),
            "theta": self._bucketed_abs(trades, "entry_theta", [0.03, 0.05, 0.08, 0.12]),
            "vega": self._bucketed(trades, "entry_vega", [0.20, 0.30, 0.40, 0.60]),
            "volatility": self._bucketed(trades, "entry_volatility", [0.10, 0.20, 0.30, 0.45]),
        }

    def score_calibration(self, trades):
        def bucket(t):
            score = float(getattr(t, "rank_score", getattr(t, "option_score", 0.0)))
            low = int(score // 5 * 5)
            high = low + 5
            return f"{low}-{high}"

        return self._grouped_performance(trades, bucket, "score_bucket")

    def trade_distribution(self, trades):
        buckets = {
            "< -10000": [],
            "-10000 to -5000": [],
            "-5000 to -1000": [],
            "-1000 to 0": [],
            "0 to 1000": [],
            "1000 to 5000": [],
            "5000 to 10000": [],
            "> 10000": [],
        }

        for trade in trades:
            pnl = self._pnl(trade)

            if pnl < -10000:
                key = "< -10000"
            elif pnl < -5000:
                key = "-10000 to -5000"
            elif pnl < -1000:
                key = "-5000 to -1000"
            elif pnl < 0:
                key = "-1000 to 0"
            elif pnl < 1000:
                key = "0 to 1000"
            elif pnl < 5000:
                key = "1000 to 5000"
            elif pnl < 10000:
                key = "5000 to 10000"
            else:
                key = "> 10000"

            buckets[key].append(pnl)

        rows = []

        for key, values in buckets.items():
            rows.append({
                "bucket": key,
                "trades": len(values),
                "net_pnl": sum(values),
                "avg_pnl": sum(values) / len(values) if values else 0.0,
            })

        return rows

    def _bucketed(self, trades, field, cuts):
        def bucket(t):
            value = float(getattr(t, field, 0.0))

            prev = 0.0
            for cut in cuts:
                if value < cut:
                    return f"{prev:.2f}-{cut:.2f}"
                prev = cut

            return f"{cuts[-1]:.2f}+"

        return self._grouped_performance(trades, bucket, f"{field}_bucket")

    def _bucketed_abs(self, trades, field, cuts):
        def bucket(t):
            value = abs(float(getattr(t, field, 0.0)))

            prev = 0.0
            for cut in cuts:
                if value < cut:
                    return f"{prev:.2f}-{cut:.2f}"
                prev = cut

            return f"{cuts[-1]:.2f}+"

        return self._grouped_performance(trades, bucket, f"{field}_bucket")

    def _grouped_performance(self, trades, key_fn, key_name):
        grouped = defaultdict(list)

        for trade in trades:
            grouped[str(key_fn(trade))].append(self._pnl(trade))

        rows = []

        for key, pnls in sorted(grouped.items()):
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]

            gross_profit = sum(wins)
            gross_loss = abs(sum(losses))

            rows.append({
                key_name: key,
                "trades": len(pnls),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": self._safe_div(len(wins), len(pnls)),
                "net_pnl": sum(pnls),
                "avg_pnl": self._safe_div(sum(pnls), len(pnls)),
                "profit_factor": self._safe_div(gross_profit, gross_loss),
                "expectancy": self._safe_div(sum(pnls), len(pnls)),
            })

        return sorted(rows, key=lambda r: r["net_pnl"], reverse=True)
