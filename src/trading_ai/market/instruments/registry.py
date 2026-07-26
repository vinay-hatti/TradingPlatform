from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

_ACTIVE_VALUES = {"1", "true", "yes", "y", "active"}


@dataclass(frozen=True)
class CanonicalInstrument:
    canonical_symbol: str
    name: str
    asset_class: str
    provider: str
    price_ticker: str
    options_snapshot_ticker: str
    options_reference_ticker: str
    options_eligible: bool = True
    active: bool = True
    source_registry: str = ""

    def __post_init__(self) -> None:
        symbol = self.canonical_symbol.strip().upper()
        asset_class = self.asset_class.strip().upper()
        provider = self.provider.strip().upper()
        if not symbol:
            raise ValueError("canonical_symbol is required")
        if asset_class not in {"EQUITY", "ETF", "INDEX"}:
            raise ValueError(f"Unsupported asset_class: {asset_class}")
        if not self.price_ticker.strip():
            raise ValueError(f"price_ticker is required for {symbol}")
        object.__setattr__(self, "canonical_symbol", symbol)
        object.__setattr__(self, "asset_class", asset_class)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "price_ticker", self.price_ticker.strip().upper())
        object.__setattr__(self, "options_snapshot_ticker", self.options_snapshot_ticker.strip().upper())
        object.__setattr__(self, "options_reference_ticker", self.options_reference_ticker.strip().upper())

    @property
    def volume_applicable(self) -> bool:
        return self.asset_class != "INDEX"


class CanonicalInstrumentRegistry:
    """Loads every approved asset-class registry into one canonical namespace."""

    def __init__(self, instruments: Iterable[CanonicalInstrument]) -> None:
        by_symbol: dict[str, CanonicalInstrument] = {}
        for instrument in instruments:
            existing = by_symbol.get(instrument.canonical_symbol)
            if existing is not None and existing != instrument:
                raise ValueError(f"Conflicting canonical instrument definition: {instrument.canonical_symbol}")
            by_symbol[instrument.canonical_symbol] = instrument
        if not by_symbol:
            raise ValueError("At least one canonical instrument is required")
        self._by_symbol = by_symbol

    @classmethod
    def from_files(cls, paths: Sequence[str | Path]) -> "CanonicalInstrumentRegistry":
        instruments: list[CanonicalInstrument] = []
        for path_value in paths:
            path = Path(path_value).expanduser()
            if not path.is_file():
                raise FileNotFoundError(f"Canonical registry not found: {path}")
            instruments.extend(_read_registry(path))
        return cls(instruments)

    def get(self, symbol: str) -> CanonicalInstrument:
        key = symbol.strip().upper()
        try:
            return self._by_symbol[key]
        except KeyError as exc:
            raise KeyError(f"Symbol is not present in an approved canonical registry: {key}") from exc

    def select(
        self,
        *,
        symbols: Iterable[str] | None = None,
        asset_classes: Iterable[str] | None = None,
    ) -> tuple[CanonicalInstrument, ...]:
        allowed_classes = {value.strip().upper() for value in (asset_classes or ()) if value.strip()}
        if allowed_classes - {"EQUITY", "ETF", "INDEX"}:
            raise ValueError(f"Unsupported asset classes: {sorted(allowed_classes)}")
        if symbols is None:
            selected = tuple(self._by_symbol.values())
        else:
            selected = tuple(self.get(symbol) for symbol in symbols)
        return tuple(
            instrument
            for instrument in selected
            if instrument.active and (not allowed_classes or instrument.asset_class in allowed_classes)
        )

    def price_ticker(self, symbol: str) -> str:
        return self.get(symbol).price_ticker

    def options_snapshot_ticker(self, symbol: str) -> str:
        return self.get(symbol).options_snapshot_ticker

    def options_reference_ticker(self, symbol: str) -> str:
        return self.get(symbol).options_reference_ticker


def _truthy(value: str | None, *, default: bool) -> bool:
    if value is None or not str(value).strip():
        return default
    return str(value).strip().lower() in _ACTIVE_VALUES


def _read_registry(path: Path) -> list[CanonicalInstrument]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"Canonical registry has no header: {path}")
        rows = list(reader)

    instruments: list[CanonicalInstrument] = []
    for row in rows:
        symbol = (row.get("canonical_symbol") or row.get("symbol") or row.get("ticker") or "").strip().upper()
        if not symbol:
            continue
        asset_class = (row.get("asset_class") or row.get("asset_type") or "EQUITY").strip().upper()
        provider_symbol = (row.get("provider_symbol") or symbol).strip().upper()
        is_index = asset_class == "INDEX"
        instruments.append(
            CanonicalInstrument(
                canonical_symbol=symbol,
                name=(row.get("name") or row.get("security") or symbol).strip(),
                asset_class=asset_class,
                provider=(row.get("provider") or ("POLYGON" if is_index else "YAHOO")).strip(),
                price_ticker=(row.get("price_ticker") or provider_symbol).strip(),
                options_snapshot_ticker=(row.get("options_snapshot_ticker") or provider_symbol).strip(),
                options_reference_ticker=(row.get("options_reference_ticker") or symbol).strip(),
                options_eligible=_truthy(row.get("options_eligible"), default=True),
                active=_truthy(row.get("active"), default=True),
                source_registry=str(path),
            )
        )
    return instruments
