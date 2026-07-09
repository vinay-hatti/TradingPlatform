class RiskAwareStrategyScorer:

    PROFILES = {
        "conservative": {
            "return_weight": 0.15,
            "pf_weight": 0.20,
            "win_weight": 0.15,
            "expectancy_weight": 0.10,
            "sharpe_weight": 0.15,
            "sortino_weight": 0.10,
            "drawdown_weight": 0.15,
            "max_allowed_drawdown": -0.25,
        },
        "balanced": {
            "return_weight": 0.20,
            "pf_weight": 0.20,
            "win_weight": 0.15,
            "expectancy_weight": 0.10,
            "sharpe_weight": 0.15,
            "sortino_weight": 0.10,
            "drawdown_weight": 0.10,
            "max_allowed_drawdown": -0.40,
        },
        "aggressive": {
            "return_weight": 0.30,
            "pf_weight": 0.20,
            "win_weight": 0.10,
            "expectancy_weight": 0.10,
            "sharpe_weight": 0.10,
            "sortino_weight": 0.05,
            "drawdown_weight": 0.15,
            "max_allowed_drawdown": -0.60,
        },
    }

    def __init__(self, profile="balanced", min_trades=10):
        self.profile_name = profile
        self.profile = self.PROFILES.get(profile, self.PROFILES["balanced"])
        self.min_trades = int(min_trades)

    def safe_float(self, value, default=0.0):
        try:
            if value in ("", None):
                return default
            return float(value)
        except Exception:
            return default

    def clamp(self, value, low=0.0, high=100.0):
        return max(low, min(float(value), high))

    def return_score(self, value):
        return self.clamp(self.safe_float(value) / 0.50 * 100.0)

    def profit_factor_score(self, value):
        return self.clamp(self.safe_float(value) / 3.0 * 100.0)

    def win_rate_score(self, value):
        return self.clamp(self.safe_float(value) / 0.70 * 100.0)

    def expectancy_score(self, value):
        return self.clamp(self.safe_float(value) / 2000.0 * 100.0)

    def sharpe_score(self, value):
        return self.clamp(max(self.safe_float(value), 0.0) / 2.0 * 100.0)

    def sortino_score(self, value):
        return self.clamp(max(self.safe_float(value), 0.0) / 3.0 * 100.0)

    def drawdown_score(self, value):
        drawdown = self.safe_float(value)

        if drawdown >= 0:
            return 100.0

        abs_dd = abs(drawdown)

        return self.clamp(100.0 - abs_dd * 100.0)

    def drawdown_penalty(self, value):
        drawdown = self.safe_float(value)
        max_allowed = self.profile["max_allowed_drawdown"]

        if drawdown >= max_allowed:
            return 0.0

        excess = abs(drawdown) - abs(max_allowed)

        return self.clamp(excess * 150.0, 0.0, 50.0)

    def low_trade_penalty(self, trades):
        trades = int(self.safe_float(trades))

        if trades >= self.min_trades:
            return 0.0

        missing = self.min_trades - trades

        return self.clamp(missing * 5.0, 0.0, 50.0)

    def score_row(self, row):
        trades = int(self.safe_float(row.get("trades", 0)))

        if trades <= 0:
            row["risk_score"] = 0.0
            row["risk_grade"] = "NO_TRADES"
            row["risk_reason"] = "No trades."
            return row

        return_score = self.return_score(row.get("return_pct", 0.0))
        pf_score = self.profit_factor_score(row.get("profit_factor", 0.0))
        win_score = self.win_rate_score(row.get("win_rate", 0.0))
        exp_score = self.expectancy_score(row.get("expectancy", 0.0))
        sharpe_score = self.sharpe_score(row.get("sharpe_ratio", 0.0))
        sortino_score = self.sortino_score(row.get("sortino_ratio", 0.0))
        drawdown_score = self.drawdown_score(row.get("max_drawdown_pct", 0.0))

        weighted = (
            return_score * self.profile["return_weight"]
            + pf_score * self.profile["pf_weight"]
            + win_score * self.profile["win_weight"]
            + exp_score * self.profile["expectancy_weight"]
            + sharpe_score * self.profile["sharpe_weight"]
            + sortino_score * self.profile["sortino_weight"]
            + drawdown_score * self.profile["drawdown_weight"]
        )

        penalties = (
            self.drawdown_penalty(row.get("max_drawdown_pct", 0.0))
            + self.low_trade_penalty(trades)
        )

        final_score = self.clamp(weighted - penalties)

        reasons = [
            f"Return={return_score:.1f}",
            f"PF={pf_score:.1f}",
            f"Win={win_score:.1f}",
            f"Sharpe={sharpe_score:.1f}",
            f"Sortino={sortino_score:.1f}",
            f"Drawdown={drawdown_score:.1f}",
        ]

        if penalties > 0:
            reasons.append(f"Penalty={penalties:.1f}")

        row["risk_score"] = final_score
        row["return_component"] = return_score
        row["pf_component"] = pf_score
        row["win_component"] = win_score
        row["expectancy_component"] = exp_score
        row["sharpe_component"] = sharpe_score
        row["sortino_component"] = sortino_score
        row["drawdown_component"] = drawdown_score
        row["risk_penalty"] = penalties
        row["risk_grade"] = self.grade(final_score)
        row["risk_reason"] = " | ".join(reasons)

        return row

    def grade(self, score):
        score = float(score)

        if score >= 80:
            return "A"

        if score >= 65:
            return "B"

        if score >= 50:
            return "C"

        if score >= 35:
            return "D"

        return "F"

    def score_rows(self, rows):
        scored = [
            self.score_row(dict(row))
            for row in rows
        ]

        return sorted(
            scored,
            key=lambda r: float(r.get("risk_score", 0.0)),
            reverse=True,
        )
