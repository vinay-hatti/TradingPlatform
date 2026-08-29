from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json

from trading_ai.stock_intelligence.models import StockScannerPublicationModel

from .models import (
    ExecutionRecommendationModel,
    InstitutionalDecisionSnapshotModel,
    InstitutionalOpportunityModel,
    StrategyComparisonModel,
)
from .publication_scope import latest_stock_intelligence_publication
from .trade_builder_authority import (
    classify_trade_builder_authority,
    readiness_integrity_report,
)


AUTHORITY_KEY = "institutional_options_advancement_authority"
AUTHORITY_VERSION = "M68.2.1.15-INSTITUTIONAL-OPTIONS-ADVANCEMENT-1.0"


class InstitutionalOptionsAuthorityIncompleteError(RuntimeError):
    """M64 cannot publish while options advancement is incomplete or stale."""

    def __init__(self, details: dict):
        self.details = dict(details)
        reasons = ", ".join(self.details.get("reasons") or ()) or "UNKNOWN"
        super().__init__(
            "Institutional Options advancement authority is incomplete; "
            f"reasons={reasons}"
        )

    def as_dict(self) -> dict:
        return dict(self.details)


def _canonical_payload(session, stock_scanner_run_id: str) -> dict:
    opportunities = (
        session.query(InstitutionalOpportunityModel)
        .filter(
            InstitutionalOpportunityModel.stock_scanner_run_id
            == stock_scanner_run_id
        )
        .order_by(InstitutionalOpportunityModel.opportunity_id)
        .all()
    )
    opportunity_ids = [str(row.opportunity_id) for row in opportunities]
    comparisons = {
        str(row.opportunity_id): str(row.selected_strategy_candidate_id or "")
        for row in (
            session.query(StrategyComparisonModel)
            .filter(StrategyComparisonModel.opportunity_id.in_(opportunity_ids))
            .all()
            if opportunity_ids
            else ()
        )
    }
    decisions = {
        str(row.opportunity_id): str(row.state_hash or "")
        for row in (
            session.query(InstitutionalDecisionSnapshotModel)
            .filter(InstitutionalDecisionSnapshotModel.opportunity_id.in_(opportunity_ids))
            .all()
            if opportunity_ids
            else ()
        )
    }
    executions = {
        str(row.opportunity_id): classify_trade_builder_authority(
            row.payload_json,
            row.ready_for_trade_builder,
        )
        for row in (
            session.query(ExecutionRecommendationModel)
            .filter(ExecutionRecommendationModel.opportunity_id.in_(opportunity_ids))
            .all()
            if opportunity_ids
            else ()
        )
    }
    rows = [
        {
            "opportunity_id": str(row.opportunity_id),
            "state": str(row.state),
            "version": int(row.version or 0),
            "option_snapshot_id": str(row.option_snapshot_id or ""),
            "selected_strategy_candidate_id": comparisons.get(
                str(row.opportunity_id), ""
            ),
            "decision_state_hash": decisions.get(str(row.opportunity_id), ""),
            "trade_builder_authority": executions.get(
                str(row.opportunity_id),
                classify_trade_builder_authority(None, None),
            ),
        }
        for row in opportunities
    ]
    return {
        "stock_scanner_run_id": stock_scanner_run_id,
        "opportunity_count": len(rows),
        "state_counts": dict(sorted(Counter(row["state"] for row in rows).items())),
        "rows": rows,
    }


def advancement_fingerprint(session, stock_scanner_run_id: str) -> tuple[str, dict]:
    payload = _canonical_payload(session, stock_scanner_run_id)
    encoded = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return sha256(encoded).hexdigest(), payload


def persist_advancement_authority(
    session_factory,
    *,
    stock_scanner_run_id: str,
    advancement: dict,
) -> dict:
    unexpected = list(advancement.get("unexpected_failures") or ())
    if unexpected or str(advancement.get("status") or "") == "FAILED":
        raise InstitutionalOptionsAuthorityIncompleteError({
            "status": "BLOCKED_INCOMPLETE_ADVANCEMENT",
            "stock_scanner_run_id": stock_scanner_run_id,
            "reasons": ["UNEXPECTED_ADVANCEMENT_FAILURES"],
            "unexpected_failures": unexpected,
        })
    with session_factory() as session:
        publication = (
            session.query(StockScannerPublicationModel)
            .filter_by(
                publication_name="current_stock_intelligence",
                scanner_run_id=stock_scanner_run_id,
            )
            .one_or_none()
        )
        if publication is None:
            raise RuntimeError(
                "Cannot persist advancement authority without its exact Stock "
                f"publication: {stock_scanner_run_id}"
            )
        fingerprint, canonical = advancement_fingerprint(
            session, stock_scanner_run_id
        )
        integrity = readiness_integrity_report(
            session,
            stock_scanner_run_id=stock_scanner_run_id,
        )
        if integrity["invalid_readiness_count"]:
            raise InstitutionalOptionsAuthorityIncompleteError({
                "status": "BLOCKED_INCOMPLETE_ADVANCEMENT",
                "stock_scanner_run_id": stock_scanner_run_id,
                "reasons": ["INVALID_TRADE_BUILDER_READINESS"],
                "readiness_integrity": integrity,
            })
        governed = sum(
            int((advancement.get("summary") or {}).get(key) or 0)
            for key in (
                "governed_no_strategy",
                "governed_no_contract",
                "missing_option_data",
                "governed_not_ready",
            )
        )
        marker = {
            "version": AUTHORITY_VERSION,
            "status": (
                "COMPLETE_WITH_GOVERNED_EXCLUSIONS"
                if governed
                else "COMPLETE"
            ),
            "stock_scanner_run_id": stock_scanner_run_id,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": fingerprint,
            "opportunity_count": canonical["opportunity_count"],
            "state_counts": canonical["state_counts"],
            "unexpected_failure_count": 0,
            "governed_exclusion_count": governed,
            "summary": dict(advancement.get("summary") or {}),
            "readiness_integrity": {
                key: value for key, value in integrity.items()
                if key not in {
                    "certified_opportunity_ids",
                    "invalid_opportunity_ids",
                }
            },
        }
        payload = dict(publication.payload_json or {})
        payload.pop("institutional_options_advancement_in_progress", None)
        payload[AUTHORITY_KEY] = marker
        publication.payload_json = payload
        session.commit()
        return marker


def invalidate_advancement_authority(
    session_factory,
    *,
    stock_scanner_run_id: str,
    reason: str,
) -> None:
    """Remove a same-run completion marker before mutating downstream state."""

    with session_factory() as session:
        publication = (
            session.query(StockScannerPublicationModel)
            .filter_by(
                publication_name="current_stock_intelligence",
                scanner_run_id=stock_scanner_run_id,
            )
            .one_or_none()
        )
        if publication is None:
            return
        payload = dict(publication.payload_json or {})
        payload.pop(AUTHORITY_KEY, None)
        payload["institutional_options_advancement_in_progress"] = {
            "version": AUTHORITY_VERSION,
            "stock_scanner_run_id": stock_scanner_run_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }
        publication.payload_json = payload
        session.commit()


def validate_current_advancement_authority(session_factory) -> dict:
    reasons: list[str] = []
    with session_factory() as session:
        publication = latest_stock_intelligence_publication(
            session,
            "current_stock_intelligence",
            require_materialized=True,
        )
        if publication is None:
            raise InstitutionalOptionsAuthorityIncompleteError({
                "status": "BLOCKED_INCOMPLETE_ADVANCEMENT",
                "reasons": ["NO_MATERIALIZED_STOCK_PUBLICATION"],
            })
        run_id = str(publication.scanner_run_id)
        marker = dict((publication.payload_json or {}).get(AUTHORITY_KEY) or {})
        if marker.get("version") != AUTHORITY_VERSION:
            reasons.append("MISSING_OR_UNSUPPORTED_AUTHORITY_MARKER")
        if marker.get("status") not in {
            "COMPLETE", "COMPLETE_WITH_GOVERNED_EXCLUSIONS"
        }:
            reasons.append("ADVANCEMENT_NOT_COMPLETE")
        if str(marker.get("stock_scanner_run_id") or "") != run_id:
            reasons.append("STOCK_RUN_LINEAGE_MISMATCH")
        if int(marker.get("unexpected_failure_count") or 0) != 0:
            reasons.append("UNEXPECTED_ADVANCEMENT_FAILURES")
        fingerprint, canonical = advancement_fingerprint(session, run_id)
        if str(marker.get("fingerprint") or "") != fingerprint:
            reasons.append("ADVANCEMENT_FINGERPRINT_STALE")
        if int(marker.get("opportunity_count") or 0) != int(
            canonical["opportunity_count"]
        ):
            reasons.append("OPPORTUNITY_COUNT_MISMATCH")
        if canonical["opportunity_count"] <= 0:
            reasons.append("NO_MATERIALIZED_OPPORTUNITIES")
        integrity = readiness_integrity_report(
            session,
            stock_scanner_run_id=run_id,
        )
        if integrity["invalid_readiness_count"]:
            reasons.append("INVALID_TRADE_BUILDER_READINESS")
        details = {
            "status": (
                "READY" if not reasons else "BLOCKED_INCOMPLETE_ADVANCEMENT"
            ),
            "version": AUTHORITY_VERSION,
            "stock_scanner_run_id": run_id,
            "opportunity_count": canonical["opportunity_count"],
            "state_counts": canonical["state_counts"],
            "fingerprint": fingerprint,
            "reasons": reasons,
            "marker": marker,
            "readiness_integrity": integrity,
        }
        if reasons:
            raise InstitutionalOptionsAuthorityIncompleteError(details)
        return details
