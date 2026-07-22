from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import SectorLeadershipRunProfile
from .engine import SectorLeadershipEngine
from .policy import SectorLeadershipPolicy
from .serialization import load_jsonl, write_json_atomic


class SectorLeadershipService:
    def __init__(
        self,
        policy: SectorLeadershipPolicy | None = None,
    ) -> None:
        self.policy = policy or SectorLeadershipPolicy()
        self.engine = SectorLeadershipEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        input_path: str | Path,
        output_path: str | Path,
    ) -> SectorLeadershipRunProfile:
        records = load_jsonl(input_path)

        features_by_symbol = {
            str(record["symbol"]).strip().upper(): record
            for record in records
            if record.get("symbol")
        }

        profile = self.engine.evaluate(
            as_of_date=as_of_date,
            features_by_symbol=features_by_symbol,
        )

        write_json_atomic(output_path, profile)

        expected_sectors = {
            "XLF", "XLK", "XLE", "XLI", "XLV", "XLY",
            "XLP", "XLU", "XLB", "XLRE", "XLC",
        }
        available_sectors = expected_sectors & set(features_by_symbol)

        return SectorLeadershipRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            input_path=str(input_path),
            output_path=str(output_path),
            records_read=len(records),
            sectors_available=len(available_sectors),
            sectors_missing=len(expected_sectors - available_sectors),
            rotation_state=profile.rotation_state,
            leadership_state=profile.leadership_state,
            confidence=profile.confidence,
            governance_status=profile.governance_status.value,
            metadata={
                "feature_version": profile.feature_version,
                "leaders": list(profile.leaders),
                "laggards": list(profile.laggards),
                "expected_sectors": sorted(expected_sectors),
                "available_sectors": sorted(available_sectors),
                "missing_sectors": sorted(
                    expected_sectors - available_sectors
                ),
                "policy": self.policy.__dict__.copy(),
            },
        )
