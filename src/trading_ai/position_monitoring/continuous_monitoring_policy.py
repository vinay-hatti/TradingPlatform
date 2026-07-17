from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ContinuousMonitoringPolicy:
    cycle_interval_seconds: int = 15
    maximum_cycle_duration_seconds: int = 60
    maximum_consecutive_cycle_failures: int = 3
    reconciliation_quantity_tolerance: float = 0.000001
    reconciliation_cost_tolerance_pct: float = 0.01
    activate_kill_switch_on_critical_breach: bool = True
    activate_kill_switch_on_reconciliation_failure: bool = True
    activate_kill_switch_on_monitoring_failure: bool = True
    add_account_halt_on_kill_switch: bool = True
    allow_reduce_only_after_activation: bool = True
    require_position_snapshot: bool = True
    require_greeks_snapshot_for_options: bool = True
    require_dynamic_limit_evaluation: bool = True
    require_broker_reconciliation: bool = True
    persist_cycle_state: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.cycle_interval_seconds <= 0: raise ValueError('cycle_interval_seconds must be positive')
        if self.maximum_cycle_duration_seconds <= 0: raise ValueError('maximum_cycle_duration_seconds must be positive')
        if self.maximum_consecutive_cycle_failures <= 0: raise ValueError('maximum_consecutive_cycle_failures must be positive')
        if self.reconciliation_quantity_tolerance < 0: raise ValueError('reconciliation_quantity_tolerance cannot be negative')
        if self.reconciliation_cost_tolerance_pct < 0: raise ValueError('reconciliation_cost_tolerance_pct cannot be negative')
