import pandas as pd


class LiquidityFilter:

    def score(self, option_row: pd.Series) -> float:

        volume = option_row.get("volume", 0)
        open_interest = option_row.get("openInterest", 0)
        bid = option_row.get("bid", 0)
        ask = option_row.get("ask", 0)

        spread = ask - bid

        score = 0

        if volume > 100:
            score += 30

        if open_interest > 500:
            score += 30

        if spread > 0:
            spread_pct = spread / ask if ask > 0 else 1
            if spread_pct < 0.05:
                score += 40

        return score
