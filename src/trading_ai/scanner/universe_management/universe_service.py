from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .universe_engine import UniverseEngine
from .universe_profile import SecurityProfile, UniverseBuildResult


class UniverseService:
    def __init__(self, engine: UniverseEngine | None = None) -> None:
        self.engine = engine or UniverseEngine()

    @staticmethod
    def _as_bool(value: object, default: bool = False) -> bool:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _as_float(value: object) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    def load_csv(self, path: str | Path, *, source: str = "CSV") -> tuple[SecurityProfile, ...]:
        source_path = Path(path)
        if not source_path.exists():
            raise FileNotFoundError(f"Universe source file not found: {source_path}")

        securities: list[SecurityProfile] = []
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"symbol", "exchange", "asset_type"}
            missing = required.difference(reader.fieldnames or ())
            if missing:
                raise ValueError(
                    "Universe CSV missing required column(s): " + ", ".join(sorted(missing))
                )
            for row in reader:
                securities.append(
                    SecurityProfile(
                        symbol=row.get("symbol", ""),
                        name=row.get("name", ""),
                        exchange=row.get("exchange", ""),
                        asset_type=row.get("asset_type", "EQUITY"),
                        active=self._as_bool(row.get("active"), True),
                        tradable=self._as_bool(row.get("tradable"), True),
                        options_eligible=self._as_bool(row.get("options_eligible"), False),
                        sector=row.get("sector", ""),
                        industry=row.get("industry", ""),
                        market_cap=self._as_float(row.get("market_cap")),
                        average_daily_volume=self._as_float(
                            row.get("average_daily_volume")
                        ),
                        source=row.get("source", "") or source,
                    )
                )
        return tuple(securities)

    def build(self, securities: Iterable[SecurityProfile], **kwargs) -> UniverseBuildResult:
        return self.engine.build(securities, **kwargs)

    def build_from_csv(self, path: str | Path, **kwargs) -> UniverseBuildResult:
        securities = self.load_csv(path)
        return self.build(securities, **kwargs)
