from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

class IntelligenceCategory(str, Enum):
    MARKET='MARKET'; TREND='TREND'; TRANSITION='TRANSITION'; DEALER='DEALER'; INSTITUTIONAL='INSTITUTIONAL'; LIQUIDITY='LIQUIDITY'; RISK='RISK'; PROBABILITY='PROBABILITY'; AI='AI'

class Severity(str, Enum):
    POSITIVE='POSITIVE'; NEUTRAL='NEUTRAL'; WATCH='WATCH'; NEGATIVE='NEGATIVE'; CRITICAL='CRITICAL'

@dataclass(frozen=True)
class Evidence:
    source: str; title: str; description: str; score: float; weight: float; contribution: float; confidence: float; severity: Severity; timestamp: str|None=None; metadata: dict[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class IntelligenceRisk:
    category: str; description: str; probability: float; impact: float; severity: Severity; mitigation: str

@dataclass(frozen=True)
class Recommendation:
    title: str; priority: int; action: str; reason: str; confidence: float; evidence_titles: tuple[str,...]=()

@dataclass(frozen=True)
class IntelligenceScore:
    category: IntelligenceCategory; name: str; overall_score: float; confidence: float; percentile: float; trend: str; status: str; severity: Severity; evidence: tuple[Evidence,...]=(); risks: tuple[IntelligenceRisk,...]=(); recommendations: tuple[Recommendation,...]=(); metrics: dict[str,Any]=field(default_factory=dict)

@dataclass(frozen=True)
class Explanation:
    summary: str; confidence: float; positive_drivers: tuple[Evidence,...]; negative_drivers: tuple[Evidence,...]; invalidation_conditions: tuple[str,...]; checklist: tuple[dict[str,Any],...]

@dataclass(frozen=True)
class TradePlaybook:
    preferred_strategy: str; alternative_strategy: str; entry: float|None; stop: float|None; targets: tuple[float,...]; expected_hold_days: int; probability: float; position_size_pct: float; contracts: int|None; greeks: dict[str,Any]; risk_notes: tuple[str,...]

@dataclass(frozen=True)
class OpportunityHealth:
    score: float; direction: str; baseline_score: float; drivers: tuple[dict[str,Any],...]; recommended_action: str

@dataclass(frozen=True)
class IntelligenceBundle:
    opportunity_id: str; snapshot_id: str; snapshot_timestamp: str; analytics_version: str; generated_at: str; scores: tuple[IntelligenceScore,...]; explanation: Explanation; recommendations: tuple[Recommendation,...]; playbook: TradePlaybook; health: OpportunityHealth; profile: dict[str,Any]
    def to_dict(self)->dict[str,Any]: return asdict(self)
