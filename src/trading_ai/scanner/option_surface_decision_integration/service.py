from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import (
    SurfaceDecisionPolicy,
    SurfaceDecisionRunProfile,
    SurfaceDecisionStatus,
)
from .engine import OptionSurfaceDecisionEngine
from .serialization import read_csv_rows, write_jsonl_atomic


class OptionSurfaceDecisionIntegrationService:
    def __init__(
        self,
        policy: SurfaceDecisionPolicy | None = None,
    ) -> None:
        self.policy = policy or SurfaceDecisionPolicy()
        self.engine = OptionSurfaceDecisionEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        symbol_surface_csv_path: str | Path,
        output_path: str | Path,
    ) -> SurfaceDecisionRunProfile:
        rows = read_csv_rows(symbol_surface_csv_path)

        mismatched = [
            row
            for row in rows
            if str(row.get("quote_date")) != as_of_date.isoformat()
        ]
        if mismatched:
            raise ValueError(
                f"{len(mismatched)} symbol surface records do not match "
                f"as-of date {as_of_date.isoformat()}"
            )

        profiles = tuple(
            self.engine.evaluate(row)
            for row in rows
        )
        write_jsonl_atomic(output_path, profiles)

        return SurfaceDecisionRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            input_path=str(symbol_surface_csv_path),
            output_path=str(output_path),
            records_read=len(rows),
            records_generated=len(profiles),
            eligible_count=sum(
                profile.decision_status
                == SurfaceDecisionStatus.ELIGIBLE
                for profile in profiles
            ),
            review_count=sum(
                profile.decision_status
                == SurfaceDecisionStatus.REVIEW
                for profile in profiles
            ),
            blocked_count=sum(
                profile.decision_status
                == SurfaceDecisionStatus.BLOCKED
                for profile in profiles
            ),
            metadata={
                "policy": self.policy.__dict__.copy(),
                "feature_version": "m35.phase4.step4.v1",
            },
        )
