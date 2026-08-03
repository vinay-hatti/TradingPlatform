from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from .models import OpportunityAuditEventModel, OpportunityModel
from .policy import validate_transition
from .profile import OpportunityCreate, OpportunityRecord, OpportunityTransition, WorkflowState
from .repository import OpportunityRepository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OpportunityService:
    def __init__(self, session: Session):
        self.session = session
        self.repo = OpportunityRepository(session)

    def create(self, request: OpportunityCreate) -> OpportunityRecord:
        existing = self.repo.find_by_source(request.scanner_run_id, request.snapshot_id, request.symbol.upper(), request.strategy)
        if existing:
            return self._record(existing)
        now = _now()
        model = OpportunityModel(
            opportunity_id=f"opp-{uuid4().hex}", scanner_run_id=request.scanner_run_id,
            snapshot_id=request.snapshot_id, snapshot_timestamp=request.snapshot_timestamp,
            symbol=request.symbol.upper(), direction=request.direction.upper(), strategy=request.strategy,
            workflow_state=WorkflowState.STAGED.value, version=1,
            source_payload_json=dict(request.source_payload), created_by=request.created_by,
            created_at=now, updated_at=now, metadata_json=dict(request.metadata),
        )
        self.repo.add(model)
        self.repo.add_event(OpportunityAuditEventModel(
            event_id=f"oppevt-{uuid4().hex}", opportunity_id=model.opportunity_id,
            opportunity_version=1, event_type="OPPORTUNITY_CREATED", previous_state=None,
            new_state=WorkflowState.STAGED.value, actor=request.created_by,
            reason="Opportunity staged from persisted scanner result", event_timestamp=now,
            metadata_json={"scanner_run_id": request.scanner_run_id, "snapshot_id": request.snapshot_id},
        ))
        self.session.commit()
        return self._record(model)

    def transition(self, opportunity_id: str, request: OpportunityTransition) -> OpportunityRecord:
        model = self.repo.get(opportunity_id)
        if model is None:
            raise KeyError(f"Opportunity not found: {opportunity_id}")
        if model.version != request.expected_version:
            raise RuntimeError(f"Opportunity version conflict: expected {request.expected_version}, actual {model.version}")
        current = WorkflowState(model.workflow_state)
        validate_transition(current, request.new_state)
        now = _now()
        model.version += 1
        model.workflow_state = request.new_state.value
        model.updated_at = now
        self.repo.add_event(OpportunityAuditEventModel(
            event_id=f"oppevt-{uuid4().hex}", opportunity_id=model.opportunity_id,
            opportunity_version=model.version, event_type="WORKFLOW_TRANSITIONED",
            previous_state=current.value, new_state=request.new_state.value,
            actor=request.actor, reason=request.reason, event_timestamp=now,
            metadata_json=dict(request.metadata),
        ))
        self.session.commit()
        return self._record(model)


    def designate_preferred(self, opportunity_id: str, *, expected_version: int, actor: str, reason: str) -> OpportunityRecord:
        model = self.repo.get(opportunity_id)
        if model is None:
            raise KeyError(f"Opportunity not found: {opportunity_id}")
        if model.version != expected_version:
            raise RuntimeError(f"Opportunity version conflict: expected {expected_version}, actual {model.version}")
        now = _now()
        cohort = self.repo.list_cohort(model.scanner_run_id, model.snapshot_id)
        for item in cohort:
            metadata = dict(item.metadata_json or {})
            was_preferred = bool(metadata.get("preferred"))
            should_prefer = item.opportunity_id == model.opportunity_id
            if was_preferred == should_prefer:
                continue
            item.version += 1
            item.updated_at = now
            metadata["preferred"] = should_prefer
            metadata["preferred_at"] = now if should_prefer else None
            metadata["preferred_by"] = actor if should_prefer else None
            item.metadata_json = metadata
            self.repo.add_event(OpportunityAuditEventModel(
                event_id=f"oppevt-{uuid4().hex}", opportunity_id=item.opportunity_id,
                opportunity_version=item.version, event_type="PREFERRED_DESIGNATION_CHANGED",
                previous_state=item.workflow_state, new_state=item.workflow_state, actor=actor,
                reason=reason if should_prefer else f"Superseded by preferred opportunity {model.opportunity_id}",
                event_timestamp=now, metadata_json={"preferred": should_prefer, "cohort_scanner_run_id": model.scanner_run_id, "cohort_snapshot_id": model.snapshot_id},
            ))
        self.session.commit()
        refreshed = self.repo.get(opportunity_id)
        assert refreshed is not None
        return self._record(refreshed)

    @staticmethod
    def _record(model: OpportunityModel) -> OpportunityRecord:
        return OpportunityRecord(
            opportunity_id=model.opportunity_id, scanner_run_id=model.scanner_run_id,
            snapshot_id=model.snapshot_id, snapshot_timestamp=model.snapshot_timestamp,
            symbol=model.symbol, direction=model.direction, strategy=model.strategy,
            workflow_state=WorkflowState(model.workflow_state), version=model.version,
            source_payload=dict(model.source_payload_json), created_by=model.created_by,
            created_at=model.created_at, updated_at=model.updated_at,
            metadata=dict(model.metadata_json or {}),
        )
