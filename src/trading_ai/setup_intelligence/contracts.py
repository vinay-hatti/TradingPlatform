from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import json
from typing import Any


class SetupFamily(str, Enum):
    TREND = "TREND"
    BREAKOUT = "BREAKOUT"
    FAILURE = "FAILURE"
    STRUCTURAL_REVERSAL = "STRUCTURAL_REVERSAL"
    EVENT = "EVENT"


class SetupType(str, Enum):
    TREND_PULLBACK = "TREND_PULLBACK"
    TREND_CONTINUATION = "TREND_CONTINUATION"
    MOMENTUM_ACCELERATION = "MOMENTUM_ACCELERATION"
    BREAKOUT_SETUP = "BREAKOUT_SETUP"
    BREAKOUT_CONFIRMED = "BREAKOUT_CONFIRMED"
    BREAKOUT_RETEST = "BREAKOUT_RETEST"
    BREAKOUT_CONTINUATION = "BREAKOUT_CONTINUATION"
    BREAKDOWN_SETUP = "BREAKDOWN_SETUP"
    BREAKDOWN_CONFIRMED = "BREAKDOWN_CONFIRMED"
    BREAKDOWN_RETEST = "BREAKDOWN_RETEST"
    BREAKDOWN_CONTINUATION = "BREAKDOWN_CONTINUATION"
    FAILED_BREAKOUT_REVERSAL = "FAILED_BREAKOUT_REVERSAL"
    FAILED_BREAKDOWN_REVERSAL = "FAILED_BREAKDOWN_REVERSAL"
    SUPPORT_REVERSAL = "SUPPORT_REVERSAL"
    RESISTANCE_REVERSAL = "RESISTANCE_REVERSAL"
    POST_EARNINGS_DRIFT_LONG = "POST_EARNINGS_DRIFT_LONG"
    POST_EARNINGS_DRIFT_SHORT = "POST_EARNINGS_DRIFT_SHORT"


class SetupStage(str, Enum):
    WATCH = "WATCH"
    ARMED = "ARMED"
    TRIGGERED = "TRIGGERED"
    CONFIRMED = "CONFIRMED"
    RETESTING = "RETESTING"
    RETEST_HELD = "RETEST_HELD"
    CONTINUATION = "CONTINUATION"
    FAILED = "FAILED"
    EXHAUSTED = "EXHAUSTED"


class SetupDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


def stable_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class SetupEvidence:
    values: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


@dataclass
class SetupSnapshot:
    setup_id: str
    candidate_id: str
    scanner_run_id: str
    symbol: str
    as_of: str
    setup_type: str
    setup_family: str
    stage: str
    direction: str
    quality: float
    confidence: float
    invalidation_level: float | None
    entry_reference: float | None
    source_state_hash: str | None
    context: dict[str, Any] = field(default_factory=dict)
    evidence: SetupEvidence = field(default_factory=SetupEvidence)
    lineage: dict[str, Any] = field(default_factory=dict)
    authority_effect: bool = False
    state_hash: str = ""

    def finalize(self) -> "SetupSnapshot":
        payload = asdict(self)
        payload.pop("state_hash", None)
        self.state_hash = stable_hash(payload)
        return self


@dataclass(frozen=True)
class ConditionalProbability:
    status: str
    setup_type: str
    observation_count: int
    target_1_probability: float | None = None
    target_2_probability: float | None = None
    target_3_probability: float | None = None
    stop_probability: float | None = None
    profitable_probability: float | None = None
    expected_mfe_pct: float | None = None
    expected_mae_pct: float | None = None
    expected_return_pct: float | None = None
    expected_holding_days: float | None = None
    confidence: float = 0.0
    comparable_population: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExpectedValueAssessment:
    status: str
    setup_type: str
    expected_r: float | None
    expected_return_pct: float | None
    capital_efficiency: float | None
    time_efficiency: float | None
    quality_adjusted_utility: float | None
    inputs: dict[str, Any] = field(default_factory=dict)
