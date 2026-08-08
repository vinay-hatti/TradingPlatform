from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
import json
from typing import Any

class Direction(str, Enum):
    STRONG_BULLISH='STRONG_BULLISH'; BULLISH='BULLISH'; WEAK_BULLISH='WEAK_BULLISH'; NEUTRAL='NEUTRAL'; WEAK_BEARISH='WEAK_BEARISH'; BEARISH='BEARISH'; STRONG_BEARISH='STRONG_BEARISH'
class Structure(str, Enum):
    TRENDING='TRENDING'; SIDEWAYS='SIDEWAYS'; COMPRESSION='COMPRESSION'; EXPANSION='EXPANSION'; EARLY_TREND='EARLY_TREND'; MATURE_TREND='MATURE_TREND'; EXHAUSTION='EXHAUSTION'; REVERSAL_ATTEMPT='REVERSAL_ATTEMPT'
class ParticipationState(str, Enum):
    ACCUMULATION='ACCUMULATION'; RE_ACCUMULATION='RE_ACCUMULATION'; DISTRIBUTION='DISTRIBUTION'; RE_DISTRIBUTION='RE_DISTRIBUTION'; NEUTRAL='NEUTRAL'; CAPITULATION='CAPITULATION'; SHORT_COVERING='SHORT_COVERING'
class BreakoutState(str, Enum):
    NONE='NONE'; BREAKOUT_SETUP='BREAKOUT_SETUP'; BREAKOUT_CONFIRMED='BREAKOUT_CONFIRMED'; BREAKOUT_CONTINUATION='BREAKOUT_CONTINUATION'; BREAKOUT_RETEST='BREAKOUT_RETEST'; FAILED_BREAKOUT='FAILED_BREAKOUT'; BREAKDOWN_SETUP='BREAKDOWN_SETUP'; BREAKDOWN_CONFIRMED='BREAKDOWN_CONFIRMED'; BREAKDOWN_RETEST='BREAKDOWN_RETEST'; FAILED_BREAKDOWN='FAILED_BREAKDOWN'

def stable_hash(value: Any)->str:
    return sha256(json.dumps(value,sort_keys=True,default=str,separators=(',',':')).encode()).hexdigest()
@dataclass
class TimeframeState:
    timeframe:str; direction:str; structure:str; trend_strength:float; momentum_score:float; confidence:float; close:float; atr:float=0.; realized_volatility:float=0.; efficiency_ratio:float=0.; evidence:dict[str,Any]=field(default_factory=dict)
@dataclass
class PriceLevel:
    level_type:str; price:float; timeframe:str; strength:float; confluence_score:float=0.; touch_count:int=1; holding_probability:float=.5; break_probability:float=.5; evidence:dict[str,Any]=field(default_factory=dict); contributing_timeframes:list[str]=field(default_factory=list)
    @property
    def primary_timeframe(self)->str:
        return self.timeframe
@dataclass
class PriceZone:
    zone_type:str; lower_bound:float; upper_bound:float; timeframe:str; strength:float; freshness:str='FRESH'; test_count:int=0; evidence:dict[str,Any]=field(default_factory=dict); contributing_timeframes:list[str]=field(default_factory=list)
    @property
    def primary_timeframe(self)->str:
        return self.timeframe
@dataclass
class InstitutionalStructureZone:
    zone_type:str; lower_bound:float; upper_bound:float; representative_price:float; strength:float; confluence_score:float=0.; holding_probability:float=.5; break_probability:float=.5; primary_timeframe:str='1d'; contributing_timeframes:list[str]=field(default_factory=list); components:list[str]=field(default_factory=list); touch_count:int=0; freshness:str='STRUCTURAL'; hierarchy:str='HISTORICAL_STRUCTURE'; status:str='UNKNOWN'; distance_pct:float=0.; relevance_score:float=0.; dealer_context:dict[str,Any]=field(default_factory=dict); evidence:dict[str,Any]=field(default_factory=dict)

@dataclass
class ParticipationProfile:
    state:str='NEUTRAL'; score:float=50.; conviction:float=0.; deterioration_risk:float=0.; evidence:dict[str,Any]=field(default_factory=dict)
@dataclass
class BreakoutProfile:
    state:str='NONE'; confirmation:float=0.; follow_through_probability:float=0.; failure_probability:float=50.; retest_quality:float=0.; evidence:dict[str,Any]=field(default_factory=dict)
@dataclass
class StockContextProfile:
    score:float=50.; adjustment:float=0.; confidence:float=0.; market_regime:str='UNKNOWN'; forecast_direction:str='UNKNOWN'; relative_strength_grade:str=''; dealer_positioning:str='UNKNOWN'; gamma_regime:str='UNKNOWN'; institutional_state:str='UNKNOWN'; evidence:dict[str,Any]=field(default_factory=dict)
@dataclass
class OpportunityScores:
    bullish:float=0.; bearish:float=0.; breakout:float=0.; breakdown:float=0.; accumulation:float=0.; distribution:float=0.; mean_reversion_long:float=0.; mean_reversion_short:float=0.; trend_continuation:float=0.; reversal:float=0.; options_suitability:float=0.; overall:float=0.; confidence:float=0.; freshness:float=100.; primary_category:str='NEUTRAL'; weights:dict[str,float]=field(default_factory=dict); warnings:list[str]=field(default_factory=list)
@dataclass
class DynamicUnderlyingTradePlan:
    entry_zone_low:float|None=None; entry_zone_high:float|None=None; confirmation_trigger:float|None=None; chase_limit:float|None=None; invalidation_level:float|None=None; targets:list[float]=field(default_factory=list); stop_policy:str='STRUCTURAL'; exit_policy:str='DYNAMIC'; rationale:list[str]=field(default_factory=list)
@dataclass
class StockIntelligenceProfile:
    symbol:str; snapshot_timestamp:str; provider:str='polygon'; primary_timeframe:str='1d'; timeframe_states:dict[str,TimeframeState]=field(default_factory=dict); direction:str='NEUTRAL'; structure:str='SIDEWAYS'; alignment_score:float=0.; confidence:float=0.; support_levels:list[PriceLevel]=field(default_factory=list); resistance_levels:list[PriceLevel]=field(default_factory=list); demand_zones:list[PriceZone]=field(default_factory=list); supply_zones:list[PriceZone]=field(default_factory=list); structure_zones:list[InstitutionalStructureZone]=field(default_factory=list); participation:ParticipationProfile|None=None; breakout:BreakoutProfile|None=None; context:StockContextProfile|None=None; scores:OpportunityScores|None=None; trade_plan:DynamicUnderlyingTradePlan|None=None; categories:list[str]=field(default_factory=list); warnings:list[str]=field(default_factory=list); metadata:dict[str,Any]=field(default_factory=dict); state_hash:str=''
    def finalize(self):
        if self.provider.lower()!='polygon': raise ValueError('Milestone 61 requires Polygon lineage')
        d=asdict(self); d.pop('state_hash',None); self.state_hash=stable_hash(d); return self

class EntryType(str, Enum):
    PULLBACK='PULLBACK'; BREAKOUT='BREAKOUT'; RETEST='RETEST'; DEMAND_BOUNCE='DEMAND_BOUNCE'; SUPPLY_REJECTION='SUPPLY_REJECTION'; STRUCTURE_BREAK='STRUCTURE_BREAK'; VWAP_RECLAIM='VWAP_RECLAIM'; MOMENTUM_CONTINUATION='MOMENTUM_CONTINUATION'; REVERSAL_CONFIRMATION='REVERSAL_CONFIRMATION'
class ExitAction(str, Enum):
    HOLD='HOLD'; TRAIL='TRAIL'; REDUCE='REDUCE'; EXIT='EXIT'; SCALE_IN='SCALE_IN'; NO_ACTION='NO_ACTION'
class ExitReason(str, Enum):
    UNDERLYING_STRUCTURE_INVALIDATED='UNDERLYING_STRUCTURE_INVALIDATED'; TARGET_ZONE_REACHED='TARGET_ZONE_REACHED'; TREND_DETERIORATION='TREND_DETERIORATION'; MOMENTUM_REVERSAL='MOMENTUM_REVERSAL'; DEALER_POSITIONING_CHANGED='DEALER_POSITIONING_CHANGED'; VOLATILITY_COLLAPSE='VOLATILITY_COLLAPSE'; THETA_RISK_EXCEEDED='THETA_RISK_EXCEEDED'; TIME_STOP_REACHED='TIME_STOP_REACHED'; OPTION_LIQUIDITY_DETERIORATED='OPTION_LIQUIDITY_DETERIORATED'; THESIS_HEALTHY='THESIS_HEALTHY'
@dataclass
class EntryProfile:
    entry_type:str='PULLBACK'; preferred_entry:float|None=None; zone_low:float|None=None; zone_high:float|None=None; confirmation_trigger:float|None=None; chase_limit:float|None=None; confidence:float=0.; fill_probability:float=0.; freshness:float=100.; rationale:list[str]=field(default_factory=list)
@dataclass
class StopCandidate:
    stop_type:str; price:float; confidence:float; reliability:float; distance_pct:float; false_stop_probability:float; rationale:list[str]=field(default_factory=list)
@dataclass
class StopProfile:
    recommended_stop:float|None=None; selected_type:str='STRUCTURAL'; confidence:float=0.; candidates:list[StopCandidate]=field(default_factory=list); emergency_stop:float|None=None; rationale:list[str]=field(default_factory=list)
@dataclass
class TargetLevel:
    target_type:str; price:float; probability:float; reward_risk:float=0.; rationale:list[str]=field(default_factory=list)
@dataclass
class TargetProfile:
    targets:list[TargetLevel]=field(default_factory=list); measured_move:float|None=None; expected_move_target:float|None=None; stretch_target:float|None=None; rationale:list[str]=field(default_factory=list); additional_targets:list[dict]=field(default_factory=list); rejected_targets:list[dict]=field(default_factory=list); ranking_version:str='M70-TARGET-RANKING-1.0'
@dataclass
class TrailingProfile:
    method:str='STRUCTURE'; activation_price:float|None=None; current_trail:float|None=None; step_pct:float=0.; confidence:float=0.; rationale:list[str]=field(default_factory=list)
@dataclass
class ExitIntelligence:
    action:str='HOLD'; reason:str='THESIS_HEALTHY'; thesis_integrity:float=100.; position_health:float=100.; opportunity_decay:str='STABLE'; reduce_fraction:float=0.; scale_in_allowed:bool=False; warnings:list[str]=field(default_factory=list); rationale:list[str]=field(default_factory=list)
@dataclass
class PositionIntelligenceProfile:
    entry:EntryProfile=field(default_factory=EntryProfile); stop:StopProfile=field(default_factory=StopProfile); targets:TargetProfile=field(default_factory=TargetProfile); trailing:TrailingProfile=field(default_factory=TrailingProfile); exit:ExitIntelligence=field(default_factory=ExitIntelligence); expected_hold_days:int=0; structural_reward_risk:float=0.; management_quality:float=0.; state_hash:str=''
    def finalize(self):
        d=asdict(self);d.pop('state_hash',None);self.state_hash=stable_hash(d);return self
