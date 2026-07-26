from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from .exceptions import (
    PublishedStateNotReadyError,
    PublishedStateStaleError,
    PublishedStateUnavailableError,
)
from .governance import (
    PublishedStateFailureCode,
    PublishedStateFinding,
    PublishedStateSeverity,
)
from .policy import PublishedStatePolicy
from .profile import PublishedMarketState, PublishedStateResolution


class PublishedMarketStateResolver:
    """Single authoritative reader and governor for a published ingestion state.

    Consumers never fall back to independently selected latest rows.
    """

    def __init__(self, session: Session, policy: PublishedStatePolicy | None = None) -> None:
        self.session = session
        self.policy = policy or PublishedStatePolicy()
        self.policy.validate()

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    def _details(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
            return parsed if isinstance(parsed, dict) else {"value": parsed}
        except (TypeError, ValueError, json.JSONDecodeError):
            return {"raw": str(value)}

    @staticmethod
    def _finding(code: PublishedStateFailureCode, message: str, *, blocking: bool, severity: PublishedStateSeverity) -> PublishedStateFinding:
        return PublishedStateFinding(
            code=code.value,
            severity=severity.value,
            message=message,
            blocking=blocking,
        )

    def resolve(self, *, now: datetime | None = None) -> PublishedStateResolution:
        row = self.session.execute(text("""
            SELECT publication_name, run_id, published_at, as_of_date,
                   market_intelligence_timestamp, option_snapshot_timestamp,
                   option_snapshot_id, readiness_status, scanner_ready,
                   decision_context_ready, details_json
              FROM market_ingestion_publication
             WHERE publication_name = :name
             LIMIT 1
        """), {"name": self.policy.publication_name}).mappings().one_or_none()

        if row is None:
            finding = self._finding(
                PublishedStateFailureCode.PUBLICATION_MISSING,
                f"No publication named {self.policy.publication_name!r} exists.",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            )
            return PublishedStateResolution(
                status="UNAVAILABLE",
                state=None,
                errors=(finding.message,),
                findings=(finding,),
                consumer=self.policy.consumer,
            )

        findings: list[PublishedStateFinding] = []
        try:
            published_at = self._utc(row["published_at"])
            market_intelligence_timestamp = (
                self._utc(row["market_intelligence_timestamp"])
                if row["market_intelligence_timestamp"] is not None else None
            )
        except Exception as exc:
            finding = self._finding(
                PublishedStateFailureCode.INVALID_PUBLICATION_RECORD,
                f"Published state contains invalid timestamps: {exc}",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            )
            return PublishedStateResolution(
                status="REJECTED",
                state=None,
                errors=(finding.message,),
                findings=(finding,),
                consumer=self.policy.consumer,
            )

        current = self._utc(now or datetime.now(timezone.utc))
        age_seconds = max(0.0, (current - published_at).total_seconds())
        readiness_status = str(row["readiness_status"] or "UNKNOWN").upper()

        if readiness_status == "DEGRADED":
            if self.policy.allow_degraded:
                findings.append(self._finding(
                    PublishedStateFailureCode.STATUS_NOT_READY,
                    "Published state is DEGRADED but permitted by policy.",
                    blocking=False,
                    severity=PublishedStateSeverity.WARNING,
                ))
            else:
                findings.append(self._finding(
                    PublishedStateFailureCode.DEGRADED_NOT_ALLOWED,
                    "Published state is DEGRADED and policy requires READY.",
                    blocking=True,
                    severity=PublishedStateSeverity.ERROR,
                ))
        elif readiness_status != "READY":
            findings.append(self._finding(
                PublishedStateFailureCode.STATUS_NOT_READY,
                f"Published state status is {readiness_status}, not READY.",
                blocking=True,
                severity=PublishedStateSeverity.ERROR,
            ))

        if age_seconds > self.policy.maximum_age_seconds:
            findings.append(self._finding(
                PublishedStateFailureCode.PUBLICATION_STALE,
                f"Published state is stale: age={age_seconds:.0f}s exceeds maximum={self.policy.maximum_age_seconds}s.",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            ))
        elif (
            self.policy.warning_age_seconds is not None
            and self.policy.warning_age_seconds < self.policy.maximum_age_seconds
            and age_seconds > self.policy.warning_age_seconds
        ):
            findings.append(self._finding(
                PublishedStateFailureCode.PUBLICATION_STALE,
                f"Published state is approaching staleness: age={age_seconds:.0f}s exceeds warning={self.policy.warning_age_seconds}s.",
                blocking=False,
                severity=PublishedStateSeverity.WARNING,
            ))

        if self.policy.require_scanner_ready and not bool(row["scanner_ready"]):
            findings.append(self._finding(
                PublishedStateFailureCode.SCANNER_NOT_READY,
                "Published state is not scanner-ready.",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            ))
        if self.policy.require_decision_context_ready and not bool(row["decision_context_ready"]):
            findings.append(self._finding(
                PublishedStateFailureCode.DECISION_CONTEXT_NOT_READY,
                "Published state is not decision-context-ready.",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            ))
        if self.policy.require_option_snapshot and not row["option_snapshot_id"]:
            findings.append(self._finding(
                PublishedStateFailureCode.OPTION_SNAPSHOT_MISSING,
                "Published state does not reference an option snapshot ID.",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            ))
        if self.policy.require_option_snapshot_timestamp and row["option_snapshot_timestamp"] is None:
            findings.append(self._finding(
                PublishedStateFailureCode.OPTION_SNAPSHOT_TIMESTAMP_MISSING,
                "Published state does not reference an option snapshot timestamp.",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            ))
        if self.policy.require_market_intelligence_timestamp and market_intelligence_timestamp is None:
            findings.append(self._finding(
                PublishedStateFailureCode.MARKET_INTELLIGENCE_TIMESTAMP_MISSING,
                "Published state does not reference a Market Intelligence timestamp.",
                blocking=True,
                severity=PublishedStateSeverity.CRITICAL,
            ))

        option_snapshot_timestamp = (
            self._utc(row["option_snapshot_timestamp"])
            if row["option_snapshot_timestamp"] is not None else None
        )
        state = PublishedMarketState(
            publication_name=str(row["publication_name"]),
            run_id=str(row["run_id"]),
            published_at=published_at,
            as_of_date=row["as_of_date"],
            market_intelligence_timestamp=market_intelligence_timestamp or published_at,
            option_snapshot_timestamp=option_snapshot_timestamp,
            option_snapshot_id=str(row["option_snapshot_id"]) if row["option_snapshot_id"] else None,
            readiness_status=readiness_status,
            scanner_ready=bool(row["scanner_ready"]),
            decision_context_ready=bool(row["decision_context_ready"]),
            details=self._details(row["details_json"]),
            age_seconds=age_seconds,
            degraded=readiness_status == "DEGRADED",
        )
        blocking = tuple(item for item in findings if item.blocking)
        warning = tuple(item for item in findings if not item.blocking)
        return PublishedStateResolution(
            status="REJECTED" if blocking else readiness_status,
            state=state,
            warnings=tuple(item.message for item in warning),
            errors=tuple(item.message for item in blocking),
            findings=tuple(findings),
            consumer=self.policy.consumer,
        )

    def require(self, *, now: datetime | None = None) -> PublishedMarketState:
        result = self.resolve(now=now)
        if result.usable and result.state is not None:
            return result.state
        message = "; ".join(result.errors) or "Published market state is unavailable."
        codes = result.failure_codes
        if result.status == "UNAVAILABLE" or PublishedStateFailureCode.PUBLICATION_MISSING.value in codes:
            raise PublishedStateUnavailableError(message, codes=codes)
        if PublishedStateFailureCode.PUBLICATION_STALE.value in codes:
            raise PublishedStateStaleError(message, codes=codes)
        raise PublishedStateNotReadyError(message, codes=codes)
