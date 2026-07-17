from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperTradingAutomationPolicy:
    """Governance for automated paper-trading sessions."""

    allowed_environments: tuple[str, ...] = ("paper", "simulation")
    allowed_session_states: tuple[str, ...] = (
        "CREATED",
        "READY",
        "RUNNING",
        "PAUSED",
        "STOPPING",
        "STOPPED",
        "FAILED",
        "COMPLETED",
    )
    maximum_orders_per_cycle: int = 20
    maximum_orders_per_session: int = 500
    maximum_open_positions: int = 100
    maximum_cycles_per_session: int = 10000
    minimum_cycle_interval_seconds: int = 5
    maximum_cycle_interval_seconds: int = 3600
    default_cycle_interval_seconds: int = 60
    require_risk_gateway_approval: bool = True
    require_market_data_readiness: bool = True
    require_broker_readiness: bool = True
    require_persistent_runtime_state: bool = True
    require_unique_session_id: bool = True
    allow_restart_recovery: bool = True
    allow_pause_resume: bool = True
    allow_manual_stop: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if not self.allowed_environments:
            raise ValueError("allowed_environments cannot be empty")
        if self.maximum_orders_per_cycle <= 0:
            raise ValueError("maximum_orders_per_cycle must be positive")
        if self.maximum_orders_per_session <= 0:
            raise ValueError("maximum_orders_per_session must be positive")
        if self.maximum_open_positions <= 0:
            raise ValueError("maximum_open_positions must be positive")
        if self.maximum_cycles_per_session <= 0:
            raise ValueError("maximum_cycles_per_session must be positive")
        if self.minimum_cycle_interval_seconds <= 0:
            raise ValueError("minimum_cycle_interval_seconds must be positive")
        if self.maximum_cycle_interval_seconds < self.minimum_cycle_interval_seconds:
            raise ValueError(
                "maximum_cycle_interval_seconds cannot be below minimum"
            )
        if not (
            self.minimum_cycle_interval_seconds
            <= self.default_cycle_interval_seconds
            <= self.maximum_cycle_interval_seconds
        ):
            raise ValueError(
                "default_cycle_interval_seconds must be within bounds"
            )
