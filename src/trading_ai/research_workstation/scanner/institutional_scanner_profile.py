from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class InstitutionalScannerDecisionProfile:
    symbol: str
    available: bool
    allowed: bool
    selected: bool
    action: str
    readiness: str
    strategy: str
    decision_confidence: float
    probability_of_profit: float
    calibrated_probability: float
    expected_return: float
    expected_profit: float
    maximum_loss: float
    risk_score: float
    reward_risk_ratio: float
    regime_confidence: float
    execution_quality: float
    tail_risk_score: float
    tail_risk_grade: str
    recommended_position_size_pct: float
    stop_loss_pct: float
    take_profit_pct: float
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class InstitutionalScannerRunProfile:
    decisions_by_symbol: dict[str, InstitutionalScannerDecisionProfile]
    total_symbols: int
    processed_symbols: int
    selected_count: int
    valid: bool
    overall_readiness: str
    overall_action: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
