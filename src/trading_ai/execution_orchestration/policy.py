from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass(frozen=True)
class ExecutionOrchestrationPolicy:
    require_risk_assessment: bool = True
    require_manual_approval_for_warning: bool = True
    allow_auto_release_when_risk_allows: bool = False
    maximum_orders_per_run: int = 50
    allowed_controls: tuple[str, ...] = ("ALLOW", "ALLOW_WITH_WARNING")
    hard_block_controls: tuple[str, ...] = ("BLOCK_NEW_RISK", "REDUCE_ONLY")
    terminal_statuses: tuple[str, ...] = ("FILLED", "CANCELED", "REJECTED", "EXPIRED")
    def validate(self) -> None:
        if self.maximum_orders_per_run < 1: raise ValueError('maximum_orders_per_run must be positive')
    def to_dict(self): return asdict(self)
