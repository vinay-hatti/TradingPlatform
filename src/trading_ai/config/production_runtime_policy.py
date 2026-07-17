from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductionRuntimePolicy:
    allowed_environments: tuple[str, ...] = (
        "development",
        "test",
        "paper",
        "production",
    )
    production_environment: str = "production"
    minimum_startup_score: float = 85.0
    fail_closed: bool = True
    reject_debug_in_production: bool = True
    reject_plaintext_secrets_in_production: bool = True
    require_database_in_production: bool = True
    require_broker_in_production: bool = True
    require_market_data_in_production: bool = True
    require_kill_switch_in_production: bool = True
    allow_live_trading_only_in_production: bool = True
    require_writable_directories: bool = True
    required_directories: tuple[str, ...] = (
        "data_directory",
        "reports_directory",
        "logs_directory",
        "audit_directory",
    )
    sensitive_key_fragments: tuple[str, ...] = (
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "database_url",
    )
    required_feature_flags: dict[str, bool] = field(default_factory=dict)

    def validate(self) -> None:
        if not 0.0 <= self.minimum_startup_score <= 100.0:
            raise ValueError("minimum_startup_score must be between 0 and 100")
        if not self.allowed_environments:
            raise ValueError("allowed_environments cannot be empty")
