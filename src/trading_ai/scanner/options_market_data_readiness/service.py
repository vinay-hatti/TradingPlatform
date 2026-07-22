from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

from .contracts import (
    GovernanceStatus,
    OptionDataReadinessRunProfile,
)
from .engine import (
    CoverageInput,
    OptionDataReadinessEngine,
    QualityInput,
)
from .policy import OptionDataReadinessPolicy


class OptionDataReadinessService:
    def __init__(
        self,
        *,
        policy: OptionDataReadinessPolicy | None = None,
    ) -> None:
        self.policy = policy or OptionDataReadinessPolicy()
        self.engine = OptionDataReadinessEngine(self.policy)

    def run(
        self,
        *,
        as_of_date: date,
        coverage_report_path: str | Path,
        quality_report_path: str | Path,
    ) -> OptionDataReadinessRunProfile:
        coverage_path = Path(coverage_report_path)
        quality_path = Path(quality_report_path)

        coverage_payload = self._read_json(coverage_path)
        quality_payload = self._read_json(quality_path)

        self._validate_date(
            "coverage",
            coverage_payload,
            as_of_date,
        )
        self._validate_date(
            "quality",
            quality_payload,
            as_of_date,
        )

        quote_data_observed = bool(
            quality_payload.get("quote_data_observed", False)
        )

        coverage_rows = tuple(
            CoverageInput(
                symbol=item["symbol"],
                status=item["governance_status"],
                score=float(item["overall_coverage_score"]),
                contract_count=int(item["contract_count"]),
                expiration_count=int(item["expiration_count"]),
                distinct_strike_count=int(
                    item["distinct_strike_count"]
                ),
                reasons=tuple(item.get("governance_reasons") or ()),
            )
            for item in coverage_payload.get("profiles", ())
        )

        quality_rows = tuple(
            QualityInput(
                symbol=item["symbol"],
                status=item["governance_status"],
                score=float(item["overall_quality_score"]),
                quote_data_observed=quote_data_observed,
                reasons=tuple(item.get("governance_reasons") or ()),
                notes=tuple(item.get("informational_notes") or ()),
            )
            for item in quality_payload.get("profiles", ())
        )

        profiles = self.engine.evaluate(
            as_of_date=as_of_date,
            coverage_rows=coverage_rows,
            quality_rows=quality_rows,
        )

        scores = [item.readiness_score for item in profiles]

        return OptionDataReadinessRunProfile(
            as_of_date=as_of_date,
            generated_at=datetime.now(timezone.utc),
            symbols_evaluated=len(profiles),
            ready_symbols=sum(
                item.readiness_status == GovernanceStatus.READY
                for item in profiles
            ),
            review_symbols=sum(
                item.readiness_status == GovernanceStatus.REVIEW
                for item in profiles
            ),
            failed_symbols=sum(
                item.readiness_status == GovernanceStatus.FAILED
                for item in profiles
            ),
            average_readiness_score=(
                round(sum(scores) / len(scores), 6) if scores else 0.0
            ),
            minimum_readiness_score=(
                round(min(scores), 6) if scores else 0.0
            ),
            maximum_readiness_score=(
                round(max(scores), 6) if scores else 0.0
            ),
            coverage_report_path=str(coverage_path),
            quality_report_path=str(quality_path),
            profiles=profiles,
            metadata={
                "policy": self.policy.__dict__.copy(),
                "coverage_symbols": len(coverage_rows),
                "quality_symbols": len(quality_rows),
                "quote_data_observed": quote_data_observed,
                "phase": "Milestone 35 Phase 3",
                "step": 5,
            },
        )

    @staticmethod
    def _read_json(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError(f"{path} must contain a JSON object")
        return payload

    @staticmethod
    def _validate_date(
        label: str,
        payload: dict,
        expected: date,
    ) -> None:
        actual = payload.get("as_of_date")
        if actual != expected.isoformat():
            raise ValueError(
                f"{label} report date {actual!r} does not match "
                f"{expected.isoformat()!r}"
            )
