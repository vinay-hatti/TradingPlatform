from __future__ import annotations
from dataclasses import dataclass,asdict,field
from enum import Enum
from typing import Any
class LearningPolicyState(str,Enum):
 DRAFT='DRAFT';REVIEW='REVIEW';APPROVED='APPROVED';ACTIVE='ACTIVE';RETIRED='RETIRED'
@dataclass(frozen=True)
class PerformanceMetrics:
 sample_size:int;wins:int;losses:int;flats:int;win_rate:float;average_return_pct:float;median_return_pct:float;profit_factor:float;expectancy_pct:float;max_drawdown_pct:float
 def to_dict(self):return asdict(self)
@dataclass(frozen=True)
class CalibrationBucket:
 lower:float;upper:float;count:int;predicted:float;observed:float;calibration_error:float
 def to_dict(self):return asdict(self)
@dataclass(frozen=True)
class DecisionQuality:
 alignment_rate:float;override_rate:float;profitable_alignment_rate:float;avoidable_loss_rate:float;sample_size:int
 def to_dict(self):return asdict(self)
@dataclass(frozen=True)
class LearningRecommendation:
 category:str;target:str;current_value:float;proposed_value:float;confidence:float;sample_size:int;reason:str;evidence:dict[str,Any]=field(default_factory=dict)
 def to_dict(self):return asdict(self)
@dataclass(frozen=True)
class LearningReport:
 report_id:str;portfolio_id:str;generated_at:str;window_start:str|None;window_end:str|None;overall:PerformanceMetrics;by_strategy:dict[str,PerformanceMetrics];by_direction:dict[str,PerformanceMetrics];calibration:tuple[CalibrationBucket,...];decision_quality:DecisionQuality;recommendations:tuple[LearningRecommendation,...];governance:dict[str,Any]
 def to_dict(self):return asdict(self)
