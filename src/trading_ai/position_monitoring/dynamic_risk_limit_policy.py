from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class DynamicRiskLimitPolicy:
    maximum_limit_profiles: int = 10000
    require_active_profile: bool = True
    account_profile_precedence: int = 100
    strategy_profile_precedence: int = 200
    underlying_profile_precedence: int = 300
    position_profile_precedence: int = 400
    breach_deduplication_window_seconds: int = 300
    acknowledgement_required_for_severe: bool = True
    acknowledgement_required_for_critical: bool = True
    severe_escalation_after_seconds: int = 900
    critical_escalation_after_seconds: int = 300
    maximum_escalation_level: int = 3
    persist_breaches: bool = True
    persist_alerts: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_limit_profiles <= 0:
            raise ValueError('maximum_limit_profiles must be positive')
        if self.breach_deduplication_window_seconds <= 0:
            raise ValueError('breach_deduplication_window_seconds must be positive')
        if self.severe_escalation_after_seconds <= 0:
            raise ValueError('severe_escalation_after_seconds must be positive')
        if self.critical_escalation_after_seconds <= 0:
            raise ValueError('critical_escalation_after_seconds must be positive')
        if self.maximum_escalation_level <= 0:
            raise ValueError('maximum_escalation_level must be positive')
