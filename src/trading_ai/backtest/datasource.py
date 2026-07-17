from datetime import datetime, date


class HistoricalDataSource:
    def __init__(self, market_provider, *, cache_only=False):
        self.market_provider = market_provider
        self.cache_only = bool(cache_only)

    def get_price_history(self, symbol, start, end):
        try:
            return self.market_provider.get_history(symbol, start, end, cache_only=self.cache_only)
        except TypeError as exc:
            if "cache_only" not in str(exc):
                raise
            return self.market_provider.get_history(symbol, start, end)

    def _to_date(self, value):
        if isinstance(value, date):
            return value
        if hasattr(value, "date"):
            return value.date()
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value).date()
        try:
            return datetime.fromisoformat(str(value)).date()
        except Exception:
            return value

    def _row_date(self, row, fallback_index=None):
        return self._to_date(row.get("time", fallback_index))

    def get_next_days(self, df, entry_date, days=10):
        if df.empty:
            return []
        entry_date = self._to_date(entry_date)
        rows = []
        for idx, row in df.iterrows():
            row_date = self._row_date(row, idx)
            if row_date <= entry_date:
                continue
            rows.append({"date": row_date, "price": float(row["close"])})
            if len(rows) >= days:
                break
        return rows

    def get_trading_dates(self, df):
        return [] if df.empty else [self._row_date(row, idx) for idx, row in df.iterrows()]
