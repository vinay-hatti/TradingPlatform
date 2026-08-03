from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
class ManagedPositionState(str,Enum):
 OPEN='OPEN';PARTIAL='PARTIAL';HEDGED='HEDGED';ROLLED='ROLLED';CLOSED='CLOSED';CANCELLED='CANCELLED'
class PositionAction(str,Enum):
 HOLD='HOLD';SCALE_IN='SCALE_IN';SCALE_OUT='SCALE_OUT';ROLL='ROLL';HEDGE='HEDGE';CLOSE='CLOSE'
@dataclass(frozen=True)
class PositionMark:
 mark_price:float;quantity:float;market_value:float;unrealized_pnl:float;unrealized_return_pct:float
 delta:float=0;gamma:float=0;theta:float=0;vega:float=0;days_to_expiry:int|None=None
@dataclass(frozen=True)
class HealthDriver:
 category:str;score:float;direction:str;contribution:float;reason:str
@dataclass(frozen=True)
class PositionHealth:
 score:float;direction:str;confidence:float;drivers:tuple[HealthDriver,...];alerts:tuple[str,...]
 def to_dict(self):return asdict(self)
@dataclass(frozen=True)
class PositionDecision:
 action:PositionAction;confidence:float;priority:str;reason:str;expected_benefit:str;risk_impact:str;alternatives:tuple[str,...]=()
 def to_dict(self):
  d=asdict(self);d['action']=self.action.value;return d
@dataclass(frozen=True)
class PortfolioSnapshot:
 portfolio_id:str;snapshot_timestamp:str;net_liquidation:float;cash:float;buying_power:float;market_value:float;unrealized_pnl:float;realized_pnl:float;open_risk:float;health_score:float;position_count:int;greeks:dict[str,float];sector_exposure:dict[str,float];strategy_exposure:dict[str,float];concentration:dict[str,float]
 def to_dict(self):return asdict(self)
@dataclass(frozen=True)
class ManagedPosition:
 position_id:str;portfolio_id:str;trade_plan_id:str;opportunity_id:str;intelligence_id:str|None;execution_id:str|None;symbol:str;strategy:str;direction:str;state:ManagedPositionState;version:int;opened_at:str;closed_at:str|None;entry_value:float;realized_pnl:float;mark:PositionMark;health:PositionHealth;decision:PositionDecision;metadata:dict[str,Any]=field(default_factory=dict)
 def to_dict(self):
  d=asdict(self);d['state']=self.state.value;d['decision']['action']=self.decision.action.value;return d
