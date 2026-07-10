import csv
from datetime import datetime

from trading_ai.options.contract import OptionContract


class OptionChainCSVImporter:

    def parse_date(self, value):
        if hasattr(value, "date"):
            return value.date()

        return datetime.fromisoformat(str(value)).date()

    def safe_float(self, row, key, default=0.0):
        value = row.get(key, default)

        try:
            if value in ("", None):
                return default
            return float(value)
        except Exception:
            return default

    def safe_int(self, row, key, default=0):
        value = row.get(key, default)

        try:
            if value in ("", None):
                return default
            return int(float(value))
        except Exception:
            return default

    def load(self, path):
        contracts = []

        with open(path, "r") as f:
            reader = csv.DictReader(f)

            for row in reader:
                bid = self.safe_float(row, "bid")
                ask = self.safe_float(row, "ask")
                mid = self.safe_float(row, "mid")

                if mid <= 0 and bid > 0 and ask > 0:
                    mid = (bid + ask) / 2.0

                contracts.append(
                    OptionContract(
                        underlying_symbol=row["underlying_symbol"].upper(),
                        option_symbol=row.get("option_symbol", ""),
                        quote_date=self.parse_date(row["quote_date"]),
                        expiry=self.parse_date(row["expiry"]),
                        option_type=row["option_type"].upper(),
                        strike=self.safe_float(row, "strike"),
                        bid=bid,
                        ask=ask,
                        mid=mid,
                        last=self.safe_float(row, "last"),
                        volume=self.safe_int(row, "volume"),
                        open_interest=self.safe_int(row, "open_interest"),
                        implied_volatility=self.safe_float(row, "implied_volatility"),
                        delta=self.safe_float(row, "delta"),
                        gamma=self.safe_float(row, "gamma"),
                        theta=self.safe_float(row, "theta"),
                        vega=self.safe_float(row, "vega"),
                        rho=self.safe_float(row, "rho"),
                    )
                )

        return contracts
