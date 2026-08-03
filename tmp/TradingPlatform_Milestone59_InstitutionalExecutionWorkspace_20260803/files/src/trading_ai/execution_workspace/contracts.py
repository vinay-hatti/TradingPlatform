from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

class ExecutionIntentState(str, Enum):
    PAPER_READY='PAPER_READY'; VALIDATED='VALIDATED'; APPROVED='APPROVED'; SUBMITTED='SUBMITTED'; ACKNOWLEDGED='ACKNOWLEDGED'; PARTIALLY_FILLED='PARTIALLY_FILLED'; FILLED='FILLED'; CANCEL_REQUESTED='CANCEL_REQUESTED'; CANCELLED='CANCELLED'; REJECTED='REJECTED'; EXPIRED='EXPIRED'

TERMINAL_STATES={ExecutionIntentState.FILLED.value,ExecutionIntentState.CANCELLED.value,ExecutionIntentState.REJECTED.value,ExecutionIntentState.EXPIRED.value}

@dataclass(frozen=True)
class ExecutionValidation:
    valid: bool
    checks: dict[str,bool]
    warnings: tuple[str,...]
    estimated_notional: float
    max_loss: float
    buying_power: float|None
    def to_dict(self): return asdict(self)

@dataclass(frozen=True)
class ExecutionIntent:
    execution_intent_id:str;trade_plan_id:str;trade_plan_version:int;opportunity_id:str;portfolio_id:str;account_id:str;symbol:str;strategy:str;state:ExecutionIntentState;version:int;legs:tuple[dict[str,Any],...];order_request:dict[str,Any];validation:dict[str,Any];broker:dict[str,Any];created_by:str;created_at:str;updated_at:str;submitted_at:str|None;terminal_at:str|None;metadata:dict[str,Any]
    def to_dict(self):
        d=asdict(self);d['state']=self.state.value;return d
