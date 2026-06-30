import numpy as np
from datetime import datetime


class TermStructureBuilder:

    def build(self, option_chain, spot_date=None):

        spot_date = spot_date or datetime.utcnow().date()

        buckets = {}

        for opt in option_chain:

            try:
                expiry = datetime.strptime(opt.expiry, "%Y-%m-%d").date()
                dte = (expiry - spot_date).days

                if dte <= 0:
                    continue

                if opt.implied_volatility <= 0:
                    continue

                if dte not in buckets:
                    buckets[dte] = []

                buckets[dte].append(opt.implied_volatility)

            except Exception:
                continue

        return {
            dte: float(np.mean(vals))
            for dte, vals in buckets.items()
        }
