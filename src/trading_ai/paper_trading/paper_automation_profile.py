from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

def utc_now_iso(): return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class PaperAutomationCheckpoint:
    checkpoint_id: str
    session_id: str
    cycle_id: str
    stage: str
    completed_stages: tuple[str,...]=()
    pending_stages: tuple[str,...]=()
    candidate_ids: tuple[str,...]=()
    order_draft_ids: tuple[str,...]=()
    execution_keys: tuple[str,...]=()
    position_ids: tuple[str,...]=()
    retry_count: int=0
    recoverable: bool=True
    last_error: str|None=None
    state: str='IN_PROGRESS'
    created_at: str=field(default_factory=utc_now_iso)
    updated_at: str=field(default_factory=utc_now_iso)
    metadata: dict[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class PaperAutomationCycleResult:
    valid: bool
    allowed: bool
    session_id: str
    cycle_id: str|None
    recommendation: str
    scan_result: Any=None
    execution_decisions: tuple[Any,...]=()
    position_decisions: tuple[Any,...]=()
    checkpoint: PaperAutomationCheckpoint|None=None
    errors: tuple[str,...]=()
    warnings: tuple[str,...]=()
    metadata: dict[str,Any]=field(default_factory=dict)
    def to_dict(self): return asdict(self)
