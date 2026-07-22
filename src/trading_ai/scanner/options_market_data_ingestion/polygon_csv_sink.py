from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Sequence
from datetime import date

from .contracts import OptionHistoryProvider, ProviderBatch


FIELDS = (
    "underlying_symbol", "expiry", "quote_date", "strike", "option_type",
    "bid", "ask", "last", "volume", "open_interest", "implied_volatility",
    "delta", "gamma", "theta", "vega",
)


class CsvRecordingOptionHistoryProvider:
    """Decorator that streams provider records into the canonical historical CSV."""

    def __init__(self, provider: OptionHistoryProvider, output_path: str | Path, *, append: bool = True) -> None:
        self.provider = provider
        self.output_path = Path(output_path)
        self.append = append

    @property
    def source_name(self) -> str:
        return self.provider.source_name

    def iter_batches(self, *, symbols: Sequence[str] | None = None, start_date: date | None = None, end_date: date | None = None, batch_size: int = 5_000) -> Iterable[ProviderBatch]:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if self.append and self.output_path.exists() else "w"
        write_header = mode == "w" or self.output_path.stat().st_size == 0
        with self.output_path.open(mode, newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if write_header:
                writer.writeheader()
            for batch in self.provider.iter_batches(symbols=symbols, start_date=start_date, end_date=end_date, batch_size=batch_size):
                for record in batch.records:
                    writer.writerow({
                        "underlying_symbol": record.identity.underlying_symbol,
                        "expiry": record.identity.expiration_date.isoformat(),
                        "quote_date": record.quote_date.isoformat(),
                        "strike": record.identity.strike,
                        "option_type": record.identity.option_side.value,
                        "bid": record.bid,
                        "ask": record.ask,
                        "last": record.last,
                        "volume": record.volume,
                        "open_interest": record.open_interest,
                        "implied_volatility": record.implied_volatility,
                        "delta": record.delta,
                        "gamma": record.gamma,
                        "theta": record.theta,
                        "vega": record.vega,
                    })
                handle.flush()
                yield batch
