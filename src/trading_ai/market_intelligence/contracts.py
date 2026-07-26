from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any

@dataclass
class MetricEvidence:
    name:str; value:Any; status:str="READY"; direction:str="NEUTRAL"; confidence:float=0.0
    provenance:str="COMPUTED"; source_tables:list[str]=field(default_factory=list); lookback:int|None=None
    sample_size:int=0; completeness:float=0.0; warnings:list[str]=field(default_factory=list)
    contribution:float=0.0

@dataclass
class MarketIntelligenceSnapshot:
    snapshot_timestamp:datetime; as_of_date:str; universe_name:str
    correlation:dict[str,Any]=field(default_factory=dict)
    sentiment:dict[str,Any]=field(default_factory=dict)
    sector_breadth:list[dict[str,Any]]=field(default_factory=list)
    dealer_ensemble:list[dict[str,Any]]=field(default_factory=list)
    market_internals:dict[str,Any]=field(default_factory=dict)
    volatility:dict[str,Any]=field(default_factory=dict)
    liquidity:dict[str,Any]=field(default_factory=dict)
    risk:dict[str,Any]=field(default_factory=dict)
    opportunities:list[dict[str,Any]]=field(default_factory=list)
    scanner_context:dict[str,Any]=field(default_factory=dict)
    governance:dict[str,Any]=field(default_factory=dict)
    warnings:list[str]=field(default_factory=list)
    def to_dict(self):
        d=asdict(self); d['snapshot_timestamp']=self.snapshot_timestamp.isoformat(); return d
