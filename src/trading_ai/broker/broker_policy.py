from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerPolicy:
    """Governance policy for broker authentication and account readiness."""

    allowed_environments: tuple[str, ...] = (
        "development",
        "test",
        "paper",
        "production",
    )
    production_environment: str = "production"
    require_authenticated_session: bool = True
    require_account_profile: bool = True
    require_positive_net_liquidation: bool = True
    require_positive_buying_power: bool = True
    require_trading_permission: bool = True
    require_options_permission: bool = False
    require_market_data_permission: bool = False
    reject_live_broker_outside_production: bool = True
    require_manual_live_enablement: bool = True
    maximum_token_age_seconds: float = 3600.0
    token_expiry_warning_seconds: float = 300.0
    minimum_readiness_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        if not self.allowed_environments:
            raise ValueError("allowed_environments cannot be empty")
        if self.maximum_token_age_seconds <= 0:
            raise ValueError("maximum_token_age_seconds must be positive")
        if self.token_expiry_warning_seconds < 0:
            raise ValueError("token_expiry_warning_seconds cannot be negative")
        if not 0.0 <= self.minimum_readiness_score <= 100.0:
            raise ValueError("minimum_readiness_score must be between 0 and 100")
