from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationRecoveryPolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    kill_switch_active: bool = False
    permit_monitor_replay: bool = True
    permit_report_rebuild: bool = True
    permit_submit_replay: bool = False
    require_exact_confirmation: bool = True
    require_phase_order: bool = True
    require_control_plane_revalidation: bool = True
    require_post_recovery_observability: bool = True
    confirmation_template: str = (
        "RECOVER PAPER AUTOMATION {portfolio_id} {run_key}"
    )

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("recovery must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if self.permit_submit_replay:
            raise ValueError("automatic submit replay is not permitted")
