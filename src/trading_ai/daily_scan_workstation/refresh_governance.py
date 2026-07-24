from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RefreshGovernanceDecision:
    status: str
    eligible_to_continue: bool
    coverage_pct: float
    failed_symbol_count: int


def evaluate_refresh_governance(
    *,
    requested_symbol_count: int,
    covered_symbol_count: int,
    minimum_coverage_pct: float,
    maximum_failed_symbols: int,
    continue_on_degraded: bool,
) -> RefreshGovernanceDecision:
    coverage_pct = (
        covered_symbol_count / requested_symbol_count * 100.0
        if requested_symbol_count
        else 0.0
    )
    failed_symbol_count = max(0, requested_symbol_count - covered_symbol_count)
    fully_ready = failed_symbol_count == 0
    degraded_eligible = (
        continue_on_degraded
        and coverage_pct >= minimum_coverage_pct
        and failed_symbol_count <= maximum_failed_symbols
    )
    eligible = fully_ready or degraded_eligible
    status = "READY" if fully_ready else ("DEGRADED" if eligible else "FAILED")
    return RefreshGovernanceDecision(
        status=status,
        eligible_to_continue=eligible,
        coverage_pct=coverage_pct,
        failed_symbol_count=failed_symbol_count,
    )
