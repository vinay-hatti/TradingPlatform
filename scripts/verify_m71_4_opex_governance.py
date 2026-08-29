from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from trading_ai.opex_intelligence.models import (
    OpexForecastPublicationModel,
    OpexForecastSnapshotModel,
)
from trading_ai.opex_intelligence.service import OpexIntelligenceService


VERSION = "M71.4.2-GOVERNED-OPEX-VERIFICATION-1.0"
ROOT = Path(__file__).resolve().parents[1]


def _method_block(source: str, signature: str) -> str:
    start = source.find(signature)
    if start < 0:
        return ""
    end = source.find("\n    def ", start + len(signature))
    return source[start:] if end < 0 else source[start:end]


def static_checks() -> dict[str, bool]:
    service = (ROOT / "src/trading_ai/opex_intelligence/service.py").read_text()
    governance = (ROOT / "src/trading_ai/opex_intelligence/governance.py").read_text()
    models = (ROOT / "src/trading_ai/opex_intelligence/models.py").read_text()
    ui = (ROOT / "ui/workstation/src/OpexIntelligencePage.tsx").read_text()
    migration = (ROOT / "migrations/versions/m71_004_governed_opex_authority.py").read_text()
    learning = (ROOT / "src/trading_ai/performance_learning/continuous_learning.py").read_text()
    management = (ROOT / "src/trading_ai/autonomous_position_management/service.py").read_text()
    management_intelligence = _method_block(management, "    def _intelligence(")
    cleanup = (ROOT / "scripts/run_m71_4_opex_cleanup.py").read_text()
    downstream_patch = (ROOT / "scripts/apply_m71_4_downstream_governance.py").read_text()
    return {
        "exact_publication_authority": "forecast_id.in_(forecast_ids)" in service,
        "serialized_publication": "pg_try_advisory_xact_lock" in service,
        "semantic_noop": "NOOP_UNCHANGED_AUTHORITY" in service and "input_fingerprint" in models,
        "atomic_complete_coverage": "EXACT_COVERAGE_GATE_FAILED" in service and "AUTHORITY_PRESERVED" in service,
        "point_in_time_prices": "PriceHistory.date <= snap.as_of_date" in service,
        "index_scoped_events": "OptionValuationEventModel.symbol.in_" in service,
        "event_double_count_guard": "event_risk_embedded_in_surface" in service,
        "holiday_aware_calendar": "monthly_opex_date" in governance and "Good Friday" in governance,
        "coherent_time_bases": "TRADING_SESSIONS_252" in service and "ACT_365_CALENDAR" in service,
        "full_paths": "trading_sessions(start,end,include_start=True)" in service and "len(days)<22" not in service and "len(flow_dates)<16" not in service,
        "official_settlement_truth": all(token in governance for token in ('"SET"', '"XQO"', '"RLS"')) and "opex_settlement_values" in migration,
        "independent_calibration": "sample_group_key" in service and "expected_calibration_error" in service,
        "shadow_governance": "HEURISTIC_EVIDENCE_ONLY" in service and "DISABLED — EVIDENCE ONLY" in ui,
        "current_only_learning": "published_forecast_ids" in learning,
        "scenario_overlap_fixed": learning.find('if not observed.in_90') < learning.find('elif resistance is not None'),
        "management_fail_closed": (
            (
                "opex_score" not in management_intelligence
                or (
                    "opex_governance_status" in management_intelligence
                    and "HUMAN_APPROVED" in management_intelligence
                )
            )
            and "NOOP_NO_OPEX_COUPLING" in downstream_patch
            and "Expected exactly one recognized OPEX score assignment" in downstream_patch
        ),
        "bounded_cleanup": "PURGE_NONAUTHORITATIVE_OPEX_DUPLICATES" in cleanup and "authority_preservation" in cleanup,
        "ui_provenance": all(token in ui for token in ("Authority fingerprint", "Input fingerprint", "Independent-cycle forecast calibration")),
    }


def runtime_checks() -> tuple[dict[str, bool], dict]:
    from trading_ai.database.session import SessionLocal

    with SessionLocal() as session:
        publication = session.scalar(
            select(OpexForecastPublicationModel).where(
                OpexForecastPublicationModel.publication_name
                == "current_opex_intelligence"
            )
        )
        if publication is None:
            return {"runtime_publication": False}, {}
        forecast_ids = list((publication.payload_json or {}).get("forecast_ids") or [])
        rows = list(
            session.scalars(
                select(OpexForecastSnapshotModel).where(
                    OpexForecastSnapshotModel.forecast_id.in_(forecast_ids)
                )
            )
        ) if forecast_ids else []
        duplicate_fingerprints = session.scalar(
            select(func.count())
            .select_from(
                select(OpexForecastSnapshotModel.input_fingerprint)
                .where(OpexForecastSnapshotModel.input_fingerprint.is_not(None))
                .group_by(OpexForecastSnapshotModel.input_fingerprint)
                .having(func.count() > 1)
                .subquery()
            )
        )
        calibration = OpexIntelligenceService(lambda: session)._calibration(session)
        checks = {
            "runtime_publication": publication.status == "READY",
            "runtime_m714_authority": str((publication.payload_json or {}).get("version", "")).startswith("M71.4"),
            "runtime_exact_ids": len(forecast_ids) == publication.forecast_count == len(rows) == 9,
            "runtime_unique_ids": len(set(forecast_ids)) == len(forecast_ids),
            "runtime_complete_coverage": publication.coverage_status == "COMPLETE",
            "runtime_authority_fingerprint": bool(publication.authority_input_fingerprint),
            "runtime_forecast_fingerprints": all(row.input_fingerprint for row in rows),
            "runtime_no_duplicate_fingerprints": int(duplicate_fingerprints or 0) == 0,
            "runtime_full_paths": all((row.payload_json or {}).get("path_completeness", {}).get("status") == "COMPLETE" for row in rows),
            "runtime_shadow_only": calibration.get("governance", {}).get("authority_effect") is False and calibration.get("governance", {}).get("automatic_activation") is False,
        }
        details = {
            "publication_id": publication.publication_id,
            "forecast_count": publication.forecast_count,
            "authority_input_fingerprint": publication.authority_input_fingerprint,
            "calibration": calibration,
        }
        return checks, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    checks = static_checks()
    details = {}
    if not args.static_only:
        runtime, details = runtime_checks()
        checks.update(runtime)
    status = "PASSED" if all(checks.values()) else "FAILED"
    print(json.dumps({"version": VERSION, "status": status, "checks": checks, "details": details}, indent=2, sort_keys=True, default=str))
    return 0 if status == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
