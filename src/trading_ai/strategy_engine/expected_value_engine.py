import numpy as np


class ExpectedValueEngine:
    def calculate(
        self,
        pnl_values,
        capital_required: float = 0.0,
        maximum_loss: float = 0.0,
    ) -> dict:
        pnl = np.asarray(
            pnl_values,
            dtype=float,
        )

        if pnl.size == 0:
            return {
                "expected_value": 0.0,
                "average_profit": 0.0,
                "average_loss": 0.0,
                "expected_return_on_capital": 0.0,
                "expected_return_on_risk": 0.0,
                "median_pnl": 0.0,
                "pnl_standard_deviation": 0.0,
                "value_at_risk_95": 0.0,
                "conditional_value_at_risk_95": 0.0,
            }

        profitable = pnl[pnl > 0]
        losing = pnl[pnl < 0]

        expected_value = float(
            np.mean(pnl)
        )

        average_profit = (
            float(np.mean(profitable))
            if profitable.size
            else 0.0
        )

        average_loss = (
            float(np.mean(losing))
            if losing.size
            else 0.0
        )

        capital = float(
            capital_required or 0.0
        )

        risk = float(
            maximum_loss or 0.0
        )

        expected_return_on_capital = (
            expected_value / capital
            if capital > 0
            else 0.0
        )

        expected_return_on_risk = (
            expected_value / risk
            if risk > 0
            else 0.0
        )

        percentile_5 = float(
            np.percentile(pnl, 5)
        )

        tail = pnl[pnl <= percentile_5]

        cvar_95 = (
            float(np.mean(tail))
            if tail.size
            else percentile_5
        )

        return {
            "expected_value": expected_value,
            "average_profit": average_profit,
            "average_loss": average_loss,
            "expected_return_on_capital":
                expected_return_on_capital,
            "expected_return_on_risk":
                expected_return_on_risk,
            "median_pnl": float(
                np.median(pnl)
            ),
            "pnl_standard_deviation": float(
                np.std(pnl)
            ),
            "value_at_risk_95": percentile_5,
            "conditional_value_at_risk_95":
                cvar_95,
        }
