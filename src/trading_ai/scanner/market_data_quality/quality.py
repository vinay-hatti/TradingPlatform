from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from math import isfinite
from typing import Mapping, Sequence
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

class QualityStatus(str, Enum):
    READY="READY"; DEGRADED="DEGRADED"; REVIEW="REVIEW"; FAILED="FAILED"

@dataclass(frozen=True)
class MarketDataQualityPolicy:
    lookback_rows:int=252
    extreme_return_threshold:float=0.50
    ready_score:float=99.0
    degraded_score:float=97.0
    review_score:float=90.0
    invalid_bar_penalty:float=5.0
    extreme_return_penalty:float=1.0
    zero_volume_penalty:float=0.25
    maximum_penalty:float=100.0
    def validate(self):
        if self.lookback_rows < 2: raise ValueError("lookback_rows must be at least 2")
        if self.extreme_return_threshold <= 0: raise ValueError("extreme_return_threshold must be positive")
        if not 0 <= self.review_score <= self.degraded_score <= self.ready_score <= 100:
            raise ValueError("invalid score thresholds")

@dataclass(frozen=True)
class PriceBar:
    symbol:str; trading_date:date; open:float|None; high:float|None
    low:float|None; close:float|None; volume:float|None

@dataclass(frozen=True)
class SymbolQualityProfile:
    symbol:str; evaluated_rows:int; invalid_price_rows:int; invalid_ohlc_rows:int
    negative_volume_rows:int; zero_volume_rows:int; non_finite_rows:int
    extreme_return_rows:int; maximum_absolute_return:float; quality_score:float
    status:QualityStatus; warnings:tuple[str,...]=(); rejection_reasons:tuple[str,...]=()
    metadata:Mapping[str,object]=field(default_factory=dict)

@dataclass(frozen=True)
class UniverseQualityProfile:
    as_of_date:date; canonical_symbol_count:int; evaluated_symbol_count:int
    ready_symbol_count:int; degraded_symbol_count:int; review_symbol_count:int
    failed_symbol_count:int; symbols_with_invalid_rows:int
    symbols_with_extreme_returns:int; total_invalid_price_rows:int
    total_invalid_ohlc_rows:int; total_negative_volume_rows:int
    total_zero_volume_rows:int; total_non_finite_rows:int
    total_extreme_return_rows:int; average_quality_score:float
    minimum_quality_score:float; status:QualityStatus
    symbol_profiles:tuple[SymbolQualityProfile,...]=()
    warnings:tuple[str,...]=(); rejection_reasons:tuple[str,...]=()
    metadata:Mapping[str,object]=field(default_factory=dict)

class MarketDataQualityEngine:
    def __init__(self, policy=None):
        self.policy=policy or MarketDataQualityPolicy(); self.policy.validate()
    def evaluate_symbol(self, symbol, bars):
        ordered=sorted(bars,key=lambda b:b.trading_date)
        ip=io=nv=zv=nf=er=0; maxret=0.0; prev=None
        for b in ordered:
            vals=[b.open,b.high,b.low,b.close,b.volume]
            if any(v is not None and not isfinite(float(v)) for v in vals):
                nf+=1; prev=None; continue
            prices=[b.open,b.high,b.low,b.close]
            if any(v is None or float(v)<=0 for v in prices): ip+=1
            elif not (float(b.low)<=float(b.open)<=float(b.high) and float(b.low)<=float(b.close)<=float(b.high)):
                io+=1
            if b.volume is not None:
                if float(b.volume)<0: nv+=1
                elif float(b.volume)==0: zv+=1
            if prev is not None and b.close is not None and float(b.close)>0:
                r=abs(float(b.close)/prev-1.0); maxret=max(maxret,r)
                if r>self.policy.extreme_return_threshold: er+=1
            prev=float(b.close) if b.close is not None and float(b.close)>0 else None
        penalty=(ip+io+nv+nf)*self.policy.invalid_bar_penalty+er*self.policy.extreme_return_penalty+zv*self.policy.zero_volume_penalty
        score=max(0.0,100.0-min(self.policy.maximum_penalty,penalty))
        status=self._status(score)
        warnings=[]
        if ip:warnings.append(f"{ip} rows contain missing or non-positive prices.")
        if io:warnings.append(f"{io} rows violate OHLC relationships.")
        if nv:warnings.append(f"{nv} rows contain negative volume.")
        if zv:warnings.append(f"{zv} rows contain zero volume.")
        if nf:warnings.append(f"{nf} rows contain non-finite values.")
        if er:warnings.append(f"{er} extreme close-to-close returns detected.")
        rejections=[]
        if not ordered: status=QualityStatus.FAILED; score=0.0; rejections.append("No price-history rows were available.")
        elif status is QualityStatus.FAILED: rejections.append("Market-data quality score violates production policy.")
        return SymbolQualityProfile(symbol.strip().upper(),len(ordered),ip,io,nv,zv,nf,er,round(maxret,8),round(score,6),status,tuple(warnings),tuple(rejections),{"lookback_rows":self.policy.lookback_rows})
    def evaluate_universe(self, profiles, canonical_symbol_count, as_of_date):
        counts={s:0 for s in QualityStatus}
        for p in profiles: counts[p.status]+=1
        scores=[p.quality_score for p in profiles]
        rank={QualityStatus.READY:0,QualityStatus.DEGRADED:1,QualityStatus.REVIEW:2,QualityStatus.FAILED:3}
        overall=QualityStatus.READY
        for p in profiles:
            if rank[p.status]>rank[overall]: overall=p.status
        if len(profiles)<canonical_symbol_count: overall=QualityStatus.FAILED
        invalid=lambda p: p.invalid_price_rows or p.invalid_ohlc_rows or p.negative_volume_rows or p.non_finite_rows
        warnings=[]
        if any(invalid(p) for p in profiles): warnings.append("One or more symbols contain invalid OHLCV rows.")
        if any(p.extreme_return_rows for p in profiles): warnings.append("One or more symbols contain extreme returns.")
        rejects=("Universe OHLCV quality is not production ready.",) if overall is QualityStatus.FAILED else ()
        return UniverseQualityProfile(as_of_date,canonical_symbol_count,len(profiles),counts[QualityStatus.READY],counts[QualityStatus.DEGRADED],counts[QualityStatus.REVIEW],counts[QualityStatus.FAILED],sum(bool(invalid(p)) for p in profiles),sum(p.extreme_return_rows>0 for p in profiles),sum(p.invalid_price_rows for p in profiles),sum(p.invalid_ohlc_rows for p in profiles),sum(p.negative_volume_rows for p in profiles),sum(p.zero_volume_rows for p in profiles),sum(p.non_finite_rows for p in profiles),sum(p.extreme_return_rows for p in profiles),round(sum(scores)/len(scores),6) if scores else 0.0,round(min(scores),6) if scores else 0.0,overall,tuple(profiles),tuple(warnings),rejects,{"policy":self.policy.__dict__.copy()})
    def _status(self,score):
        if score>=self.policy.ready_score:return QualityStatus.READY
        if score>=self.policy.degraded_score:return QualityStatus.DEGRADED
        if score>=self.policy.review_score:return QualityStatus.REVIEW
        return QualityStatus.FAILED

class MarketDataQualityRepository:
    def __init__(self,database): self.database=database
    def fetch_bars(self,symbols,as_of_date,lookback_rows):
        normalized=tuple(sorted({s.strip().upper() for s in symbols if s})); result={s:[] for s in normalized}
        if not normalized:return result
        stmt=text("""SELECT symbol,date,open,high,low,close,volume FROM (
        SELECT symbol,date,open,high,low,close,volume,
        ROW_NUMBER() OVER(PARTITION BY UPPER(symbol) ORDER BY date DESC) rn
        FROM price_history WHERE UPPER(symbol) IN :symbols AND date<=:as_of_date
        ) ranked WHERE rn<=:lookback_rows ORDER BY symbol,date""").bindparams(bindparam("symbols",expanding=True))
        params={"symbols":normalized,"as_of_date":as_of_date,"lookback_rows":lookback_rows}
        def consume(rows):
            for symbol,d,o,h,l,c,v in rows:
                if isinstance(d,str): d=date.fromisoformat(d)
                elif hasattr(d,"date") and not isinstance(d,date): d=d.date()
                key=str(symbol).strip().upper()
                result.setdefault(key,[]).append(PriceBar(key,d,float(o) if o is not None else None,float(h) if h is not None else None,float(l) if l is not None else None,float(c) if c is not None else None,float(v) if v is not None else None))
        if isinstance(self.database,Engine):
            with self.database.connect() as conn: consume(conn.execute(stmt,params))
        else: consume(self.database.execute(stmt,params))
        return result

class MarketDataQualityService:
    def __init__(self,database,policy=None):
        self.engine=MarketDataQualityEngine(policy); self.repository=MarketDataQualityRepository(database)
    def evaluate(self,symbols,as_of_date):
        normalized=tuple(sorted({s.strip().upper() for s in symbols if s}))
        bars=self.repository.fetch_bars(normalized,as_of_date,self.engine.policy.lookback_rows)
        profiles=[self.engine.evaluate_symbol(s,bars.get(s,())) for s in normalized]
        return self.engine.evaluate_universe(profiles,len(normalized),as_of_date)
