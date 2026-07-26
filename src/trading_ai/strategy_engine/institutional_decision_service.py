from __future__ import annotations

import json
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from trading_ai.published_state.policy import PublishedStatePolicy
from trading_ai.lineage import DecisionRunLineage, LineagePersistenceService, new_run_id
from trading_ai.published_state.profile import PublishedMarketState
from trading_ai.published_state.service import PublishedMarketStateResolver
from trading_ai.strategy_engine.decision_serialization import decision_run_to_dict
from trading_ai.strategy_engine.institutional_decision_engine import InstitutionalDecisionEngine
from trading_ai.reporting import ReportingContext, write_report_manifest


class InstitutionalDecisionService:
    """Unified institutional-decision application service.

    Default production construction resolves and enforces the authoritative
    ``current_market_state`` publication before any decision work begins.
    Explicitly injected engines retain legacy isolated-test behaviour unless
    ``enforce_published_state=True`` is supplied.
    """

    def __init__(
        self,
        engine: InstitutionalDecisionEngine | None = None,
        *,
        published_state_resolver: PublishedMarketStateResolver | None = None,
        session_factory: Callable[[], Any] | None = None,
        published_state_policy: PublishedStatePolicy | None = None,
        enforce_published_state: bool | None = None,
        allow_unpublished_state: bool = False,
        lineage_persistence_service: LineagePersistenceService | None = None,
        persist_lineage: bool | None = None,
        decision_engine_version: str = "m47.phase6.v1",
        policy_version: str = "published-state.v1",
    ):
        injected_engine = engine is not None
        self.engine = engine or InstitutionalDecisionEngine()
        self.published_state_resolver = published_state_resolver
        self.session_factory = session_factory
        self.published_state_policy = published_state_policy or PublishedStatePolicy.for_consumer(
            "decision"
        )
        self.enforce_published_state = (
            not injected_engine if enforce_published_state is None else bool(enforce_published_state)
        )
        self.allow_unpublished_state = bool(allow_unpublished_state)
        self.lineage_persistence_service = lineage_persistence_service
        self.persist_lineage = (self.enforce_published_state and not self.allow_unpublished_state and published_state_resolver is None) if persist_lineage is None else bool(persist_lineage)
        self.decision_engine_version = str(decision_engine_version)
        self.policy_version = str(policy_version)

    def _resolve_published_state(self) -> PublishedMarketState | None:
        if not self.enforce_published_state:
            return None
        if self.allow_unpublished_state:
            return None
        if self.published_state_resolver is not None:
            return self.published_state_resolver.require()

        if self.session_factory is None:
            from trading_ai.database import SessionLocal
            session_factory = SessionLocal
        else:
            session_factory = self.session_factory
        session = session_factory()
        try:
            resolver = PublishedMarketStateResolver(
                session,
                policy=self.published_state_policy,
            )
            return resolver.require()
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _lineage(state: PublishedMarketState | None, *, bypassed: bool) -> dict[str, Any]:
        if state is None:
            return {
                "bypassed": bypassed,
                "publication_name": None,
                "ingestion_run_id": None,
                "publication_status": "BYPASSED" if bypassed else "NOT_ENFORCED",
                "published_at": None,
                "market_as_of_date": None,
                "market_intelligence_snapshot_timestamp": None,
                "option_snapshot_timestamp": None,
                "option_snapshot_id": None,
                "option_snapshot_completeness_pct": None,
                "published_state_degraded": False,
            }

        completeness = state.details.get("option_snapshot_completeness_pct")
        if completeness is None:
            checks = state.details.get("checks", [])
            for check in checks if isinstance(checks, list) else []:
                if isinstance(check, dict) and check.get("name") == "option_snapshot_completeness":
                    completeness = check.get("latest_value")
                    break
        try:
            completeness = float(completeness) if completeness is not None else None
        except (TypeError, ValueError):
            completeness = None

        return {
            "bypassed": False,
            "publication_name": state.publication_name,
            "ingestion_run_id": state.run_id,
            "publication_status": state.readiness_status,
            "published_at": state.published_at.isoformat(),
            "market_as_of_date": state.as_of_date.isoformat(),
            "market_intelligence_snapshot_timestamp": state.market_intelligence_timestamp.isoformat(),
            "option_snapshot_timestamp": (
                state.option_snapshot_timestamp.isoformat()
                if state.option_snapshot_timestamp is not None else None
            ),
            "option_snapshot_id": state.option_snapshot_id,
            "option_snapshot_completeness_pct": completeness,
            "published_state_degraded": state.degraded,
        }

    @staticmethod
    def _apply_lineage(result: Any, lineage: dict[str, Any]) -> None:
        metadata = getattr(result, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            try:
                setattr(result, "metadata", metadata)
            except Exception:
                pass
        metadata["published_market_state"] = dict(lineage)

        for decision in getattr(result, "decisions", []) or []:
            for key, value in lineage.items():
                if key == "bypassed":
                    continue
                try:
                    setattr(decision, key, value)
                except Exception:
                    pass

        warnings = getattr(result, "warnings", None)
        if isinstance(warnings, list):
            if lineage.get("published_state_degraded"):
                warnings.append(
                    "Institutional decision consumed a DEGRADED but decision-ready published market state."
                )
            if lineage.get("bypassed"):
                warnings.append(
                    "Published-state governance was explicitly bypassed for this decision run."
                )

    def run(self, request):
        started_at = datetime.now(timezone.utc)
        decision_run_id = new_run_id("decision")
        state = self._resolve_published_state()
        result = self.engine.run(request)
        lineage = self._lineage(
            state,
            bypassed=self.enforce_published_state and self.allow_unpublished_state,
        )
        lineage["decision_run_id"] = decision_run_id
        lineage["decision_engine_version"] = self.decision_engine_version
        lineage["policy_version"] = self.policy_version
        self._apply_lineage(result, lineage)
        metadata = getattr(result, "metadata", None)
        if isinstance(metadata, dict):
            metadata["decision_run_id"] = decision_run_id
            metadata["decision_engine_version"] = self.decision_engine_version
            metadata["policy_version"] = self.policy_version
        if self.persist_lineage:
            service = self.lineage_persistence_service or LineagePersistenceService(self.session_factory)
            profile = DecisionRunLineage(
                decision_run_id=decision_run_id,
                publication_name=lineage.get("publication_name"),
                ingestion_run_id=lineage.get("ingestion_run_id"),
                publication_status=str(lineage.get("publication_status") or "UNKNOWN"),
                market_intelligence_snapshot_timestamp=lineage.get("market_intelligence_snapshot_timestamp"),
                option_snapshot_timestamp=lineage.get("option_snapshot_timestamp"),
                option_snapshot_id=lineage.get("option_snapshot_id"),
                published_state_degraded=bool(lineage.get("published_state_degraded", False)),
                decision_engine_version=self.decision_engine_version,
                policy_version=self.policy_version,
                started_at=started_at,
            )
            summary = service.persist_decision_run(
                profile,
                result,
                metadata={"published_market_state": lineage},
            )
            if isinstance(metadata, dict):
                metadata["lineage_persistence"] = {
                    "status": summary.status,
                    "decision_rows": summary.item_rows,
                    **summary.metadata,
                }
        return result

    def run_and_export(self, request, output_file):
        result = self.run(request)
        path = Path(output_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        metadata = getattr(result, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}
            try:
                setattr(result, "metadata", metadata)
            except Exception:
                pass
        published = metadata.get("published_market_state") or {}
        reporting_metadata = dict(metadata)
        reporting_metadata["published_state"] = published
        context = ReportingContext.from_metadata(reporting_metadata)
        metadata["report_version"] = context.report_version
        metadata["reporting_context"] = context.to_dict()

        path.write_text(
            json.dumps(decision_run_to_dict(result), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        manifest = write_report_manifest(
            path.with_name(f"{path.stem}_manifest.json"),
            context=context,
            artifacts=[path],
            report_type="institutional_decision",
            extra={"decision_count": len(getattr(result, "decisions", []) or [])},
        )
        metadata["report_manifest"] = str(manifest)
        return result, path
