from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any


def stable_hash(value: Any) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class BarrierOutcomeLabel:
    status: str
    candidate_id: str
    scanner_run_id: str
    symbol: str
    as_of: str
    horizon_end: str | None
    entry_triggered: int | None
    target_1_before_stop: int | None
    target_2_before_stop: int | None
    target_3_before_stop: int | None
    profitable_at_horizon: int | None
    thesis_invalidation: int | None
    maximum_favorable_excursion_pct: float | None
    maximum_adverse_excursion_pct: float | None
    realized_return_pct: float | None
    days_to_target_1: int | None
    days_to_target_2: int | None
    days_to_stop: int | None
    entry_date: str | None
    entry_price: float | None
    ambiguous_targets: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OutcomeProbabilityAssessment:
    version: str = "M77.0-OUTCOME-PROBABILITY-1.0"
    status: str = "SHADOW_NOT_READY"
    mode: str = "SHADOW"
    authority_effect: bool = False
    model_id: str | None = None
    model_version: str | None = None
    calibration_status: str = "NOT_AVAILABLE"
    target_1_before_stop: float | None = None
    target_2_before_stop: float | None = None
    target_3_before_stop: float | None = None
    profitable_at_horizon: float | None = None
    thesis_invalidation: float | None = None
    expected_mfe_pct: float | None = None
    expected_mae_pct: float | None = None
    expected_days_to_target_1: float | None = None
    expected_days_to_stop: float | None = None
    expected_value_r: float | None = None
    model_confidence: float = 0.0
    epistemic_uncertainty: float = 1.0
    out_of_distribution_score: float = 1.0
    recommended_disposition: str = "ABSTAIN"
    analog_evidence: dict[str, Any] = field(default_factory=dict)
    feature_contributions: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    lineage: dict[str, Any] = field(default_factory=dict)
    state_hash: str = ""

    def finalize(self) -> "OutcomeProbabilityAssessment":
        payload = asdict(self)
        payload.pop("state_hash", None)
        self.state_hash = stable_hash(payload)
        return self

    def to_dict(self) -> dict[str, Any]:
        if not self.state_hash:
            self.finalize()
        return asdict(self)
