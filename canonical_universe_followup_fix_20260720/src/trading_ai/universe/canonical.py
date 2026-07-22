from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

CANONICAL_UNIVERSE_CSV = Path("data/universe/us_listed_equities_etfs.csv")


@dataclass(frozen=True)
class CanonicalUniverse:
    """Authoritative symbol allowlist backed by the canonical universe CSV."""

    path: Path = CANONICAL_UNIVERSE_CSV

    def symbols(self) -> tuple[str, ...]:
        if not self.path.is_file():
            raise FileNotFoundError(f"Canonical universe CSV not found: {self.path}")
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"Canonical universe CSV has no header: {self.path}")
            key = next((name for name in reader.fieldnames if name.strip().lower() == "symbol"), None)
            if key is None:
                raise ValueError(f"Canonical universe CSV must contain a symbol column: {self.path}")
            return tuple(dict.fromkeys(
                str(row.get(key, "")).strip().upper()
                for row in reader
                if str(row.get(key, "")).strip()
            ))


    def provider_symbol_map(self) -> dict[str, str]:
        """Return canonical-symbol -> provider-symbol mappings from the CSV.

        Provider symbols are used only at the external data-provider boundary.
        Database rows and all internal joins continue to use canonical symbols.
        """
        if not self.path.is_file():
            raise FileNotFoundError(f"Canonical universe CSV not found: {self.path}")
        output: dict[str, str] = {}
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"Canonical universe CSV has no header: {self.path}")
            symbol_key = next((name for name in reader.fieldnames if name.strip().lower() == "symbol"), None)
            provider_key = next((name for name in reader.fieldnames if name.strip().lower() == "provider_symbol"), None)
            if symbol_key is None:
                raise ValueError(f"Canonical universe CSV must contain a symbol column: {self.path}")
            for row in reader:
                canonical = str(row.get(symbol_key, "")).strip().upper()
                if not canonical:
                    continue
                provider = str(row.get(provider_key, "") if provider_key else "").strip().upper()
                output.setdefault(canonical, provider or canonical)
        return output

    def provider_symbol(self, symbol: str) -> str:
        canonical = self.require(symbol)
        return self.provider_symbol_map().get(canonical, canonical)

    def symbol_set(self) -> frozenset[str]:
        return frozenset(self.symbols())

    def require(self, symbol: str) -> str:
        normalized = str(symbol or "").strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        if normalized not in self.symbol_set():
            raise ValueError(
                f"Symbol {normalized} is not present in canonical universe {self.path}"
            )
        return normalized

    def filter(self, symbols: Iterable[str]) -> tuple[str, ...]:
        allowed = self.symbol_set()
        return tuple(dict.fromkeys(
            normalized
            for symbol in symbols
            if (normalized := str(symbol or "").strip().upper()) and normalized in allowed
        ))
