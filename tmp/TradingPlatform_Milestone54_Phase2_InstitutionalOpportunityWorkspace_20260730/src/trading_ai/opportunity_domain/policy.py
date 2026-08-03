from __future__ import annotations

from .profile import WorkflowState

_ALLOWED: dict[WorkflowState, frozenset[WorkflowState]] = {
    WorkflowState.STAGED: frozenset({WorkflowState.UNDER_REVIEW, WorkflowState.REJECTED, WorkflowState.ARCHIVED}),
    WorkflowState.UNDER_REVIEW: frozenset({WorkflowState.APPROVED, WorkflowState.REJECTED, WorkflowState.ARCHIVED}),
    WorkflowState.APPROVED: frozenset({WorkflowState.TRADE_BUILT, WorkflowState.ARCHIVED}),
    WorkflowState.TRADE_BUILT: frozenset({WorkflowState.PAPER_SUBMITTED, WorkflowState.ARCHIVED}),
    WorkflowState.REJECTED: frozenset({WorkflowState.ARCHIVED}),
    WorkflowState.PAPER_SUBMITTED: frozenset({WorkflowState.ARCHIVED}),
    WorkflowState.ARCHIVED: frozenset(),
}


def validate_transition(current: WorkflowState, target: WorkflowState) -> None:
    if target not in _ALLOWED[current]:
        raise ValueError(f"Invalid opportunity transition: {current.value} -> {target.value}")
