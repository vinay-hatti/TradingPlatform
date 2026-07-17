from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SecretGovernancePolicy:
    """Policy governing credential age, expiry, rotation and startup safety."""

    warning_age_days: int = 60
    maximum_age_days: int = 90
    expiry_warning_days: int = 14
    minimum_secret_length: int = 12
    minimum_health_score: float = 85.0
    fail_closed_in_production: bool = True
    require_rotation_owner: bool = True
    require_provider_resolution: bool = True
    reject_expired_secrets: bool = True
    reject_overdue_rotation: bool = True
    reject_reused_fingerprint: bool = True
    require_manual_production_rotation_approval: bool = True
    allowed_environments: tuple[str, ...] = (
        "development",
        "test",
        "paper",
        "production",
    )
    production_environment: str = "production"

    def validate(self) -> None:
        if self.warning_age_days < 0:
            raise ValueError("warning_age_days cannot be negative")
        if self.maximum_age_days <= 0:
            raise ValueError("maximum_age_days must be positive")
        if self.warning_age_days > self.maximum_age_days:
            raise ValueError("warning_age_days cannot exceed maximum_age_days")
        if self.expiry_warning_days < 0:
            raise ValueError("expiry_warning_days cannot be negative")
        if self.minimum_secret_length < 1:
            raise ValueError("minimum_secret_length must be positive")
        if not 0.0 <= self.minimum_health_score <= 100.0:
            raise ValueError("minimum_health_score must be between 0 and 100")
