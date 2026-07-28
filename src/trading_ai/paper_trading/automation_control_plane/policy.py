from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationControlPlanePolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    kill_switch_active: bool = False
    paper_routing_enabled: bool = True
    require_phase1: bool = True
    require_phase2: bool = True
    require_phase3: bool = True
    require_phase4: bool = True
    maximum_cycle_errors: int = 0
    maximum_cycle_warnings: int = 20
    minimum_portfolio_health_score: float = 70.0
    block_new_entries_on_risk_breach: bool = True
    block_new_entries_on_low_health: bool = True
    allow_position_exits_during_kill_switch: bool = True
    submit_confirmation_template: str = (
        "RUN AUTOMATED PAPER TRADING CYCLE {portfolio_id}"
    )
    kill_switch_confirmation_template: str = (
        "ACTIVATE PAPER TRADING KILL SWITCH {portfolio_id}"
    )
    resume_confirmation_template: str = (
        "RESUME PAPER TRADING AUTOMATION {portfolio_id}"
    )

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("automation control plane must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if self.maximum_cycle_errors < 0:
            raise ValueError("maximum_cycle_errors cannot be negative")
        if self.maximum_cycle_warnings < 0:
            raise ValueError("maximum_cycle_warnings cannot be negative")
        if not 0.0 <= self.minimum_portfolio_health_score <= 100.0:
            raise ValueError(
                "minimum_portfolio_health_score must be within [0, 100]"
            )
