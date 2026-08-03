from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any

class TradePlanState(str, Enum):
    DRAFT='DRAFT'; VALIDATED='VALIDATED'; APPROVED='APPROVED'; PAPER_READY='PAPER_READY'; CANCELLED='CANCELLED'
class LegSide(str, Enum): BUY='BUY'; SELL='SELL'
class OptionRight(str, Enum): CALL='CALL'; PUT='PUT'

@dataclass(frozen=True)
class TradeLeg:
    side: LegSide; quantity: int; option_right: OptionRight; strike: float; expiry: str
    limit_price: float; delta: float|None=None; gamma: float|None=None; theta: float|None=None; vega: float|None=None
    option_symbol: str|None=None
@dataclass(frozen=True)
class BuildTradePlanRequest:
    opportunity_id: str; expected_opportunity_version: int; account_id: str; strategy: str
    capital: float; risk_budget_pct: float; legs: tuple[TradeLeg,...]; actor: str
    entry_debit: float|None=None; max_profit: float|None=None; notes: str=''
@dataclass(frozen=True)
class TradePlan:
    trade_plan_id: str; opportunity_id: str; opportunity_version: int; intelligence_id: str|None
    account_id: str; symbol: str; direction: str; strategy: str; state: TradePlanState; version: int
    capital: float; risk_budget_pct: float; risk_budget_amount: float; estimated_debit: float
    estimated_credit: float; max_loss: float; max_profit: float|None; reward_risk_ratio: float|None
    net_greeks: dict[str,float]; validation: dict[str,Any]; legs: tuple[TradeLeg,...]
    created_by: str; created_at: str; updated_at: str; notes: str=''
    def to_dict(self): return asdict(self)
