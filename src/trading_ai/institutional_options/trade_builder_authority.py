from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


FINAL_CERTIFICATION_SCOPE = "INSTITUTIONAL_OPTIONS_FINAL_PLAN"
READY_EXECUTION_DISPOSITION = "READY_NOW"
AUTHORITY_VERSION = "M68.2.1.15.3-CERTIFIED-TRADE-BUILDER-AUTHORITY-1.0"


def classify_trade_builder_authority(
    execution_payload: dict[str, Any] | None,
    ready_for_trade_builder: bool | None,
) -> dict[str, Any]:
    """Return the canonical final-plan readiness classification.

    The denormalized SQL boolean is never sufficient authority.  It must agree
    with the persisted final certification object and its execution
    disposition.  Missing lineage fields are reported for diagnostics but the
    blocking contract intentionally matches the Trade Builder handoff contract.
    """

    payload = dict(execution_payload or {})
    raw = payload.get("trade_plan_certification")
    certification = dict(raw) if isinstance(raw, dict) else {}
    entry_execution = dict(
        certification.get("entry_execution") or {}
    ) if certification else {}
    blocking_reasons: list[str] = []
    entry_reason_codes: list[str] = []
    if not certification:
        blocking_reasons.append("FINAL_CERTIFICATION_MISSING")
    else:
        if str(certification.get("status") or "").upper() != "PASS":
            blocking_reasons.append("FINAL_CERTIFICATION_NOT_PASS")
        if certification.get("certification_scope") != FINAL_CERTIFICATION_SCOPE:
            blocking_reasons.append("FINAL_CERTIFICATION_SCOPE_INVALID")
        if certification.get("execution_disposition") != READY_EXECUTION_DISPOSITION:
            blocking_reasons.append("EXECUTION_DISPOSITION_NOT_READY_NOW")
        if certification.get("trade_builder_ready") is not True:
            blocking_reasons.append("CERTIFICATION_TRADE_BUILDER_READY_FALSE")
        blocking_reasons.extend(
            str(code) for code in certification.get("failure_codes") or ()
            if str(code)
        )
        # Entry reason codes explain *why* a disposition was reached.  They are
        # not themselves certification failures.  In particular,
        # REFERENCE_PRICE_WITHIN_GOVERNED_ENTRY_RANGE is affirmative evidence
        # for READY_NOW and must never invalidate an otherwise passing plan.
        entry_reason_codes.extend(
            str(code) for code in entry_execution.get("reason_codes") or ()
            if str(code)
        )

    certification_valid = not blocking_reasons
    column_ready = ready_for_trade_builder is True
    column_consistent = column_ready == certification_valid
    if column_ready and not certification_valid:
        blocking_reasons.append("READY_FLAG_WITHOUT_VALID_CERTIFICATION")
    elif certification_valid and not column_ready:
        blocking_reasons.append("VALID_CERTIFICATION_WITH_READY_FLAG_FALSE")

    blocking_reasons = list(dict.fromkeys(blocking_reasons))
    entry_reason_codes = list(dict.fromkeys(entry_reason_codes))
    diagnostic_reasons = list(dict.fromkeys(
        blocking_reasons + entry_reason_codes
    ))

    warnings: list[str] = []
    if certification and not certification.get("certification_id"):
        warnings.append("CERTIFICATION_ID_MISSING")
    if certification and not certification.get("plan_fingerprint"):
        warnings.append("PLAN_FINGERPRINT_MISSING")

    return {
        "version": AUTHORITY_VERSION,
        "authorized": bool(certification_valid and column_ready),
        "certification_present": bool(certification),
        "certification_valid": certification_valid,
        "ready_flag": column_ready,
        "column_consistent": column_consistent,
        "certification_status": certification.get("status"),
        "certification_scope": certification.get("certification_scope"),
        "execution_disposition": certification.get("execution_disposition"),
        "entry_execution": entry_execution,
        "certification_id": certification.get("certification_id"),
        "plan_fingerprint": certification.get("plan_fingerprint"),
        "blocking_reason_codes": blocking_reasons,
        "entry_reason_codes": entry_reason_codes,
        "reason_codes": diagnostic_reasons,
        "warning_codes": warnings,
    }


def certified_ready_opportunity_ids(
    session,
    *,
    stock_scanner_run_id: str,
    opportunity_ids: Iterable[str] | None = None,
) -> set[str]:
    """Resolve final-certification-authorized current opportunity identities."""

    from .models import (
        ExecutionRecommendationModel,
        InstitutionalOpportunityModel,
    )

    query = (
        session.query(
            InstitutionalOpportunityModel.opportunity_id,
            ExecutionRecommendationModel.ready_for_trade_builder,
            ExecutionRecommendationModel.payload_json,
        )
        .outerjoin(
            ExecutionRecommendationModel,
            ExecutionRecommendationModel.opportunity_id
            == InstitutionalOpportunityModel.opportunity_id,
        )
        .filter(
            InstitutionalOpportunityModel.stock_scanner_run_id
            == stock_scanner_run_id,
            InstitutionalOpportunityModel.state == "READY_FOR_EXECUTION",
        )
    )
    requested = tuple(str(item) for item in (opportunity_ids or ()) if item)
    if requested:
        query = query.filter(
            InstitutionalOpportunityModel.opportunity_id.in_(requested)
        )
    authorized: set[str] = set()
    for opportunity_id, ready_flag, payload in query.all():
        authority = classify_trade_builder_authority(payload, ready_flag)
        if authority["authorized"]:
            authorized.add(str(opportunity_id))
    return authorized


def readiness_integrity_report(
    session,
    *,
    stock_scanner_run_id: str,
) -> dict[str, Any]:
    """Audit lifecycle, SQL flag, and certification coherence for one run."""

    from .models import (
        ExecutionRecommendationModel,
        InstitutionalOpportunityModel,
    )

    rows = (
        session.query(InstitutionalOpportunityModel, ExecutionRecommendationModel)
        .outerjoin(
            ExecutionRecommendationModel,
            ExecutionRecommendationModel.opportunity_id
            == InstitutionalOpportunityModel.opportunity_id,
        )
        .filter(
            InstitutionalOpportunityModel.stock_scanner_run_id
            == stock_scanner_run_id
        )
        .all()
    )
    reason_counts: Counter[str] = Counter()
    invalid_ids: list[str] = []
    certified_ids: list[str] = []
    ready_state_count = 0
    ready_flag_count = 0
    for opportunity, execution in rows:
        state_ready = str(opportunity.state) == "READY_FOR_EXECUTION"
        if state_ready:
            ready_state_count += 1
        authority = classify_trade_builder_authority(
            None if execution is None else execution.payload_json,
            None if execution is None else execution.ready_for_trade_builder,
        )
        if authority["ready_flag"]:
            ready_flag_count += 1
        if authority["authorized"]:
            certified_ids.append(str(opportunity.opportunity_id))
        if state_ready != authority["authorized"]:
            invalid_ids.append(str(opportunity.opportunity_id))
            reason_counts[
                "READY_STATE_WITHOUT_CERTIFIED_EXECUTION"
                if state_ready
                else "CERTIFIED_EXECUTION_OUTSIDE_READY_STATE"
            ] += 1
        if not authority["column_consistent"]:
            invalid_ids.append(str(opportunity.opportunity_id))
        # Do not describe every pre-execution opportunity as a certification
        # failure.  Certification is only expected once an execution row or
        # READY lifecycle claim exists.  This keeps the attrition ledger
        # focused on real invariant failures rather than normal early stages.
        if (
            not authority["authorized"]
            and (state_ready or execution is not None or authority["ready_flag"])
        ):
            reason_counts.update(authority["reason_codes"])
    return {
        "version": AUTHORITY_VERSION,
        "stock_scanner_run_id": stock_scanner_run_id,
        "opportunity_count": len(rows),
        "ready_state_count": ready_state_count,
        "ready_flag_count": ready_flag_count,
        "certified_ready_count": len(certified_ids),
        "invalid_readiness_count": len(set(invalid_ids)),
        "invalid_opportunity_ids": sorted(set(invalid_ids)),
        "reason_counts": dict(sorted(reason_counts.items())),
        "certified_opportunity_ids": sorted(certified_ids),
    }
