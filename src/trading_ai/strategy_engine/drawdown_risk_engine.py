import numpy as np


class DrawdownRiskEngine:
    """
    Calculates drawdown-path analytics from an ordered PnL series.
    """

    def analyze(
        self,
        pnl_values,
        confidence_level: float = 0.95,
        initial_capital: float = 0.0,
    ) -> dict:
        pnl = np.asarray(
            pnl_values,
            dtype=float,
        )

        if pnl.size == 0:
            return self._empty_result()

        capital = float(initial_capital or 0.0)

        if capital > 0:
            equity = capital + np.cumsum(pnl)
        else:
            equity = np.cumsum(pnl)

            minimum = float(
                np.min(equity)
            )

            if minimum <= 0:
                equity = equity + abs(minimum) + 1.0

        running_peak = np.maximum.accumulate(
            equity
        )

        drawdown_dollars = (
            equity - running_peak
        )

        drawdown_pct = np.divide(
            drawdown_dollars,
            running_peak,
            out=np.zeros_like(
                drawdown_dollars
            ),
            where=running_peak != 0,
        )

        losses = -drawdown_pct[
            drawdown_pct < 0
        ]

        maximum_drawdown = float(
            np.min(drawdown_dollars)
        )

        maximum_drawdown_pct = float(
            np.min(drawdown_pct)
        )

        average_drawdown_pct = (
            float(
                np.mean(
                    drawdown_pct[
                        drawdown_pct < 0
                    ]
                )
            )
            if np.any(drawdown_pct < 0)
            else 0.0
        )

        ulcer_index = float(
            np.sqrt(
                np.mean(
                    np.square(
                        drawdown_pct
                    )
                )
            )
        )

        pain_index = float(
            np.mean(
                np.abs(
                    drawdown_pct
                )
            )
        )

        if losses.size:
            drawdown_at_risk = float(
                np.quantile(
                    losses,
                    confidence_level,
                )
            )

            tail = losses[
                losses >= drawdown_at_risk
            ]

            expected_drawdown_shortfall = (
                float(np.mean(tail))
                if tail.size
                else drawdown_at_risk
            )
        else:
            drawdown_at_risk = 0.0
            expected_drawdown_shortfall = 0.0

        return {
            "maximum_drawdown":
                maximum_drawdown,
            "maximum_drawdown_pct":
                maximum_drawdown_pct,
            "average_drawdown_pct":
                average_drawdown_pct,
            "drawdown_at_risk":
                drawdown_at_risk,
            "expected_drawdown_shortfall":
                expected_drawdown_shortfall,
            "ulcer_index":
                ulcer_index,
            "pain_index":
                pain_index,
            "equity_curve":
                equity.tolist(),
            "drawdown_curve":
                drawdown_pct.tolist(),
        }

    def _empty_result(self) -> dict:
        return {
            "maximum_drawdown": 0.0,
            "maximum_drawdown_pct": 0.0,
            "average_drawdown_pct": 0.0,
            "drawdown_at_risk": 0.0,
            "expected_drawdown_shortfall": 0.0,
            "ulcer_index": 0.0,
            "pain_index": 0.0,
            "equity_curve": [],
            "drawdown_curve": [],
        }
