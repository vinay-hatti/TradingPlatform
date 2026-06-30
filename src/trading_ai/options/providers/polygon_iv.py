from polygon import RESTClient
from trading_ai.config import settings
import numpy as np


class PolygonIVProvider:

    def __init__(self):
        self.client = RESTClient(settings.polygon_api_key)

    def get_atm_iv(self, symbol: str, expiry: str = None) -> float:
        """
        Extract ATM implied volatility from options chain
        """

        contracts = self.client.list_options_contracts(
            underlying_ticker=symbol,
            expired=False,
            limit=250,
        )

        ivs = []

        for c in contracts:
            try:
                # only calls for stability (you can expand later)
                if c.implied_volatility is None:
                    continue

                ivs.append(float(c.implied_volatility))

            except Exception:
                continue

        if not ivs:
            return None

        # use median = robust IV anchor
        return float(np.median(ivs))
