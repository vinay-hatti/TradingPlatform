from datetime import datetime, date


class HistoricalDataSource:

    def __init__(self, market_provider):
        self.market_provider = market_provider

    def get_price_history(self, symbol, start, end):
        df = self.market_provider.get_history(
            symbol,
            start,
            end,
        )

        return df

    def _to_date(self, value):

        if isinstance(value, date):
            return value

        if hasattr(value, "date"):
            return value.date()

        if isinstance(value, (int, float)):
            # epoch milliseconds
            if value > 10_000_000_000:
                return datetime.fromtimestamp(value / 1000).date()

            # epoch seconds
            return datetime.fromtimestamp(value).date()

        try:
            return datetime.fromisoformat(str(value)).date()
        except Exception:
            return value

    def _row_date(self, row, fallback_index=None):

        value = row.get("time", fallback_index)

        return self._to_date(value)

    def get_next_days(self, df, entry_date, days=10):

        if df.empty:
            return []

        entry_date = self._to_date(entry_date)

        rows = []

        for idx, row in df.iterrows():

            row_date = self._row_date(row, idx)

            if row_date <= entry_date:
                continue

            rows.append({
                "date": row_date,
                "price": float(row["close"]),
            })

            if len(rows) >= days:
                break

        return rows

    def get_trading_dates(self, df):

        if df.empty:
            return []

        dates = []

        for idx, row in df.iterrows():
            dates.append(
                self._row_date(row, idx)
            )

        return dates
