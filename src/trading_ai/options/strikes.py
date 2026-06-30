import pandas as pd


class StrikeSelector:

    def select_call_strike(self, calls: pd.DataFrame, price: float):

        # choose slightly OTM strike (delta proxy via moneyness)
        otm = calls[calls["strike"] > price]

        if otm.empty:
            return None

        return otm.iloc[0]

    def select_put_strike(self, puts: pd.DataFrame, price: float):

        itm = puts[puts["strike"] < price]

        if itm.empty:
            return None

        return itm.iloc[-1]
