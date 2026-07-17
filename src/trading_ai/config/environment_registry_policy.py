from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvironmentRegistryPolicy:
    allowed_promotion_paths: tuple[tuple[str, str], ...] = (
        ("development", "test"),
        ("test", "paper"),
        ("paper", "production"),
    )
    minimum_source_runtime_score: float = 85.0
    minimum_target_runtime_score: float = 90.0
    require_source_allowed: bool = True
    require_target_validation: bool = True
    require_hash_change_for_new_version: bool = False
    block_debug_in_production: bool = True
    block_live_trading_before_production: bool = True
    require_kill_switch_for_production: bool = True
    require_manual_production_promotion: bool = True

    def validate(self) -> None:
        for value in (self.minimum_source_runtime_score, self.minimum_target_runtime_score):
            if not 0.0 <= value <= 100.0:
                raise ValueError("promotion scores must be between 0 and 100")
