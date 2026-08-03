from __future__ import annotations

"""Governed scanner universe registry.

The registry is backed by the canonical active U.S. equity/ETF dataset and the
latest persisted liquidity metrics. The broad scanner universe is capped at
700 symbols and ranked by average daily dollar volume when metrics are present.
Stable named subsets are derived from canonical membership metadata.
"""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_UNIVERSE_CSV = REPOSITORY_ROOT / "data" / "universe" / "us_listed_equities_etfs.csv"
LIQUIDITY_METRICS_CSV = REPOSITORY_ROOT / "data" / "market" / "liquidity_metrics.csv"
FULL_UNIVERSE_LIMIT = 700


@dataclass(frozen=True)
class UniverseDefinition:
    universe_id: str
    label: str
    description: str
    symbols: tuple[str, ...]
    source: str
    as_of_date: str | None = None
    maximum_symbols: int | None = None

    def metadata(self) -> dict[str, object]:
        return {
            "id": self.universe_id,
            "label": self.label,
            "description": self.description,
            "symbol_count": len(self.symbols),
            "source": self.source,
            "as_of_date": self.as_of_date,
            "maximum_symbols": self.maximum_symbols,
            "active": True,
        }


def _normalize_symbol(value: object) -> str:
    return str(value or "").strip().upper()


def _load_canonical_rows(path: Path = CANONICAL_UNIVERSE_CSV) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Canonical universe CSV not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    active: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        symbol = _normalize_symbol(row.get("symbol"))
        if not symbol or symbol in seen:
            continue
        active_value = str(row.get("active", "true")).strip().lower()
        if active_value not in {"1", "true", "yes", "y"}:
            continue
        asset_type = str(row.get("asset_type", "")).strip().upper()
        if asset_type not in {"EQUITY", "ETF"}:
            continue
        seen.add(symbol)
        normalized = dict(row)
        normalized["symbol"] = symbol
        normalized["asset_type"] = asset_type
        active.append(normalized)
    return active


def _load_liquidity_scores(path: Path = LIQUIDITY_METRICS_CSV) -> dict[str, float]:
    if not path.is_file():
        return {}
    scores: dict[str, float] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            symbol = _normalize_symbol(row.get("symbol"))
            if not symbol:
                continue
            try:
                scores[symbol] = float(row.get("average_daily_dollar_volume") or 0.0)
            except (TypeError, ValueError):
                scores[symbol] = 0.0
    return scores


def _as_of_date(rows: Iterable[dict[str, str]]) -> str | None:
    values = sorted({str(row.get("as_of_date", "")).strip() for row in rows if str(row.get("as_of_date", "")).strip()})
    return values[-1] if values else None


def _membership_contains(row: dict[str, str], name: str) -> bool:
    memberships = {item.strip().lower() for item in str(row.get("membership", "")).split("|") if item.strip()}
    return name.lower() in memberships


def _ranked_symbols(rows: list[dict[str, str]], limit: int | None = None) -> tuple[str, ...]:
    liquidity = _load_liquidity_scores()
    ranked = sorted(
        rows,
        key=lambda row: (-liquidity.get(row["symbol"], 0.0), row["symbol"]),
    )
    symbols = tuple(row["symbol"] for row in ranked)
    return symbols[:limit] if limit is not None else symbols


def build_universe_registry() -> dict[str, UniverseDefinition]:
    rows = _load_canonical_rows()
    source_date = _as_of_date(rows)
    source = str(CANONICAL_UNIVERSE_CSV.relative_to(REPOSITORY_ROOT))

    sp500_rows = [row for row in rows if _membership_contains(row, "S&P 500")]
    nasdaq_rows = [row for row in rows if _membership_contains(row, "NASDAQ-100")]
    etf_rows = [row for row in rows if row.get("asset_type") == "ETF"]

    liquid_symbols = _ranked_symbols(rows, FULL_UNIVERSE_LIMIT)
    sp500_symbols = _ranked_symbols(sp500_rows)
    nasdaq_symbols = _ranked_symbols(nasdaq_rows)
    etf_symbols = _ranked_symbols(etf_rows)
    top100_symbols = tuple(symbol for symbol in liquid_symbols if symbol in set(sp500_symbols))[:100]

    registry = {
        "liquid-us-700": UniverseDefinition(
            universe_id="liquid-us-700",
            label="Highly Liquid U.S. Equities & ETFs",
            description="Liquidity-ranked active U.S. equities and ETFs, capped at 700 symbols.",
            symbols=liquid_symbols,
            source=source,
            as_of_date=source_date,
            maximum_symbols=FULL_UNIVERSE_LIMIT,
        ),
        "sp500-top100": UniverseDefinition(
            universe_id="sp500-top100",
            label="S&P 500 Top 100 Liquid",
            description="The 100 most liquid canonical S&P 500 constituents.",
            symbols=top100_symbols,
            source=source,
            as_of_date=source_date,
            maximum_symbols=100,
        ),
        "sp500": UniverseDefinition(
            universe_id="sp500",
            label="S&P 500",
            description="Active canonical S&P 500 constituents, liquidity ranked.",
            symbols=sp500_symbols,
            source=source,
            as_of_date=source_date,
        ),
        "nasdaq100": UniverseDefinition(
            universe_id="nasdaq100",
            label="Nasdaq 100",
            description="Active canonical Nasdaq-100 constituents, liquidity ranked.",
            symbols=nasdaq_symbols,
            source=source,
            as_of_date=source_date,
        ),
        "major-etfs": UniverseDefinition(
            universe_id="major-etfs",
            label="Major ETFs",
            description="Active canonical major ETFs, liquidity ranked.",
            symbols=etf_symbols,
            source=source,
            as_of_date=source_date,
        ),
    }
    for definition in registry.values():
        validate_universe(definition.symbols, maximum=definition.maximum_symbols)
    return registry


def list_universes() -> tuple[dict[str, object], ...]:
    return tuple(definition.metadata() for definition in build_universe_registry().values())


def get_universe(name: str = "liquid-us-700") -> tuple[str, ...]:
    normalized = name.strip().lower().replace("_", "-")
    aliases = {
        "top100": "sp500-top100",
        "top-100": "sp500-top100",
        "large-cap-100": "sp500-top100",
        "full": "liquid-us-700",
        "full-liquid": "liquid-us-700",
        "liquid-700": "liquid-us-700",
    }
    normalized = aliases.get(normalized, normalized)
    registry = build_universe_registry()
    if normalized not in registry:
        raise ValueError(
            f"Unsupported universe '{name}'. Supported: {', '.join(registry)}"
        )
    return registry[normalized].symbols


def validate_universe(symbols: tuple[str, ...], maximum: int | None = None) -> None:
    if maximum is not None and len(symbols) > maximum:
        raise ValueError(f"Universe exceeds maximum size {maximum}; got {len(symbols)}")
    if len(set(symbols)) != len(symbols):
        raise ValueError("Universe contains duplicate symbols")
    invalid = [symbol for symbol in symbols if not symbol or symbol != symbol.upper() or " " in symbol]
    if invalid:
        raise ValueError(f"Invalid universe symbols: {invalid}")


# Backward-compatible exports used by existing ingestion and scan code.
SP500_TOP_100: tuple[str, ...] = get_universe("sp500-top100")
SP500 = list(get_universe("sp500"))
