from __future__ import annotations
import csv,json,math
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any
from sqlalchemy import text

_KEYS=("expected_move_pct","forecast_move_pct","expected_absolute_return_pct","predicted_move_pct","expected_return_pct","expected_move_1d")

def _obj(v):
    if isinstance(v,dict): return v
    if isinstance(v,str):
        try:return json.loads(v)
        except Exception:return {}
    return {}

def _find_numeric(payload:Any):
    if isinstance(payload,dict):
        for k in _KEYS:
            v=payload.get(k)
            if isinstance(v,(int,float)):
                value=abs(float(v))
                if k=="expected_move_1d": return value,k,1
                return value,k,None
        for k,v in payload.items():
            found=_find_numeric(v)
            if found:return found[0],f"{k}.{found[1]}",found[2]
    elif isinstance(payload,list):
        for i,v in enumerate(payload):
            found=_find_numeric(v)
            if found:return found[0],f"[{i}].{found[1]}",found[2]
    return None

def _canonical_symbols(path:Path=Path("data/universe/us_listed_equities_etfs.csv")):
    if not path.is_file(): return set()
    with path.open(encoding="utf-8-sig",newline="") as h:
        reader=csv.DictReader(h); key=next((x for x in (reader.fieldnames or []) if x.strip().lower()=="symbol"),None)
        return {str(r.get(key,"")).strip().upper() for r in reader if key and str(r.get(key,"")).strip()}

class GovernedForecastResolver:
    def __init__(self,universe_file:Path=Path("data/universe/us_listed_equities_etfs.csv")):
        self.universe_file=universe_file
    def _trend(self,session,symbol,dte):
        rows=session.execute(text("""
          WITH latest_date AS (
            SELECT MAX(as_of_date) d FROM stock_trend_forecast_snapshot
            WHERE UPPER(symbol)=:s AND status='READY' AND as_of_date<=CURRENT_DATE
          )
          SELECT payload_json,horizon_days,as_of_date,snapshot_timestamp
          FROM stock_trend_forecast_snapshot,latest_date
          WHERE UPPER(symbol)=:s AND status='READY' AND as_of_date=latest_date.d
          ORDER BY ABS(horizon_days-:d),horizon_days,snapshot_timestamp DESC LIMIT 12
        """),{"s":symbol,"d":dte}).mappings().all()
        for row in rows:
            found=_find_numeric(_obj(row['payload_json']))
            if not found:continue
            raw,key,forced_horizon=found; horizon=max(1,int(forced_horizon or row['horizon_days'] or 1)); scaled=raw*math.sqrt(dte/horizon)
            return round(scaled,4),{"source":"stock_trend_forecast_snapshot","source_key":key,"raw_value_pct":raw,"source_horizon_days":horizon,"target_horizon_days":dte,"scaling":"SQRT_TIME","as_of_date":str(row['as_of_date']),"eligibility":"ELIGIBLE"}
        return None
    def _stock_fallback(self,session,symbol,dte):
        row=session.execute(text("""
          SELECT c.payload_json,c.snapshot_timestamp FROM stock_scanner_candidates c
          JOIN stock_scanner_publications p ON p.scanner_run_id=c.scanner_run_id
          WHERE UPPER(c.symbol)=:s AND p.publication_name='current_stock_intelligence' AND p.status IN ('READY','DEGRADED')
          ORDER BY p.snapshot_timestamp DESC,c.snapshot_timestamp DESC LIMIT 1
        """),{"s":symbol}).mappings().first()
        if not row:return None
        payload=_obj(row['payload_json']); plan=payload.get('trade_plan') or {}; entry=plan.get('entry') or {}; targets=((plan.get('targets') or {}).get('targets') or [])
        mid=None
        lo=entry.get('zone_low'); hi=entry.get('zone_high')
        if isinstance(lo,(int,float)) and isinstance(hi,(int,float)) and (lo+hi)>0:mid=(lo+hi)/2
        prices=[float(x.get('price')) for x in targets if isinstance(x,dict) and isinstance(x.get('price'),(int,float))]
        if mid and prices:
            raw=abs(prices[0]-mid)/mid*100; scaled=raw*math.sqrt(max(1,dte)/10)
            return round(scaled,4),{"source":"current_stock_intelligence","source_key":"trade_plan.first_target","raw_value_pct":round(raw,4),"source_horizon_days":10,"target_horizon_days":dte,"scaling":"SQRT_TIME","snapshot_timestamp":str(row['snapshot_timestamp']),"eligibility":"ELIGIBLE","fallback":True}
        return None
    def resolve(self,session,*,symbol:str,event_date:date):
        raw_symbol=symbol.upper(); dte=max(1,(event_date-date.today()).days)
        canonical=_canonical_symbols(self.universe_file)
        if raw_symbol in ('*','ALL'):
            values=[]; evidence=[]
            for proxy in ('SPY','QQQ','IWM'):
                found=self._trend(session,proxy,dte) or self._stock_fallback(session,proxy,dte)
                if found:values.append(found[0]); evidence.append({"proxy":proxy,**found[1]})
            if values:return round(median(values),4),{"source":"MACRO_PROXY_ENSEMBLE","proxies":evidence,"target_horizon_days":dte,"eligibility":"ELIGIBLE"}
            return None,{"reason":"NO_MACRO_PROXY_FORECAST","eligibility":"ELIGIBLE","target_horizon_days":dte}
        if raw_symbol not in canonical:
            return None,{"reason":"NON_CANONICAL_EVENT_SYMBOL","eligibility":"NOT_ELIGIBLE","symbol":raw_symbol,"target_horizon_days":dte}
        found=self._trend(session,raw_symbol,dte) or self._stock_fallback(session,raw_symbol,dte)
        if found:return found
        return None,{"reason":"NO_GOVERNED_FORECAST","eligibility":"ELIGIBLE","symbol":raw_symbol,"target_horizon_days":dte}
