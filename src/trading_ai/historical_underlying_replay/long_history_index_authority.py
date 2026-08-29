from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

POLYGON_BASE="https://api.polygon.io"
DEFAULT_START="2000-01-01"

def sha256_bytes(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def write_json_atomic(path:Path,payload:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def write_csv_atomic(path:Path,rows:list[dict[str,Any]],fields:list[str])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    with tmp.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)

def _http_json(url:str,timeout:int=60)->tuple[dict[str,Any],bytes]:
    req=urllib.request.Request(url,headers={"User-Agent":"TradingPlatform-M77.15.6-Research/1.0"})
    with urllib.request.urlopen(req,timeout=timeout) as resp:
        b=resp.read()
    return json.loads(b.decode("utf-8")),b

def _page_url(ticker:str,start:str,end:str,api_key:str)->str:
    path=f"/v2/aggs/ticker/{urllib.parse.quote(ticker,safe=':')}/range/1/day/{start}/{end}"
    q=urllib.parse.urlencode({
        "adjusted":"true",
        "sort":"asc",
        "limit":"50000",
        "apiKey":api_key,
    })
    return POLYGON_BASE+path+"?"+q

def fetch_polygon_daily(
    ticker:str,
    start:str,
    end:str,
    api_key:str,
    raw_dir:Path,
    pause_seconds:float=0.25,
)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    url=_page_url(ticker,start,end,api_key)
    all_rows=[]
    pages=[]
    page_no=0
    while url:
        page_no+=1
        payload,raw=_http_json(url)
        status=payload.get("status")
        if status not in ("OK","DELAYED"):
            raise RuntimeError(f"Polygon response status={status!r} ticker={ticker}")
        raw_dir.mkdir(parents=True,exist_ok=True)
        raw_path=raw_dir/f"{ticker.replace(':','_')}_page_{page_no:03d}.json"
        raw_path.write_bytes(raw)
        pages.append({
            "page":page_no,
            "raw_path":str(raw_path),
            "raw_sha256":sha256_bytes(raw),
            "results_count":len(payload.get("results") or []),
        })
        all_rows.extend(payload.get("results") or [])
        next_url=payload.get("next_url")
        if next_url:
            sep="&" if "?" in next_url else "?"
            url=next_url+sep+urllib.parse.urlencode({"apiKey":api_key})
            time.sleep(pause_seconds)
        else:
            url=None
    return all_rows,pages

def normalize_rows(logical_symbol:str,polygon_ticker:str,results:list[dict[str,Any]])->list[dict[str,Any]]:
    out=[]
    for r in results:
        ts=r.get("t")
        if ts is None:
            continue
        d=datetime.fromtimestamp(float(ts)/1000.0,tz=timezone.utc).date().isoformat()
        out.append({
            "symbol":logical_symbol,
            "polygon_ticker":polygon_ticker,
            "date":d,
            "open":r.get("o"),
            "high":r.get("h"),
            "low":r.get("l"),
            "close":r.get("c"),
            "volume":r.get("v"),
            "vwap":r.get("vw"),
            "transactions":r.get("n"),
            "source_timestamp_ms":ts,
        })
    out.sort(key=lambda x:x["date"])
    return out

def continuity_audit(rows:list[dict[str,Any]])->dict[str,Any]:
    dates=[r["date"] for r in rows]
    duplicates=sorted({d for d in dates if dates.count(d)>1})
    ohlc_violations=[]
    nonpositive=[]
    extreme_daily_moves=[]
    prior=None
    for r in rows:
        vals=[r.get("open"),r.get("high"),r.get("low"),r.get("close")]
        if any(v is None for v in vals):
            ohlc_violations.append({"date":r["date"],"reason":"MISSING_OHLC"})
            continue
        o,h,l,c=map(float,vals)
        if min(o,h,l,c)<=0:
            nonpositive.append(r["date"])
        if h < max(o,c,l) or l > min(o,c,h):
            ohlc_violations.append({"date":r["date"],"reason":"OHLC_INVARIANT"})
        if prior and prior>0:
            ret=c/prior-1.0
            if abs(ret)>=0.20:
                extreme_daily_moves.append({"date":r["date"],"return":ret})
        prior=c
    calendar_gaps=[]
    parsed=[date.fromisoformat(d) for d in dates]
    for a,b in zip(parsed,parsed[1:]):
        gap=(b-a).days
        if gap>4:
            calendar_gaps.append({"from":a.isoformat(),"to":b.isoformat(),"calendar_days":gap})
    return {
        "row_count":len(rows),
        "first_date":dates[0] if dates else None,
        "last_date":dates[-1] if dates else None,
        "duplicate_dates":duplicates,
        "ohlc_violation_count":len(ohlc_violations),
        "ohlc_violations":ohlc_violations[:50],
        "nonpositive_price_count":len(nonpositive),
        "nonpositive_price_dates":nonpositive[:50],
        "extreme_daily_move_count":len(extreme_daily_moves),
        "extreme_daily_moves":extreme_daily_moves[:100],
        "calendar_gap_gt4d_count":len(calendar_gaps),
        "calendar_gaps_gt4d":calendar_gaps[:100],
    }

def cross_symbol_session_audit(series:dict[str,list[dict[str,Any]]])->dict[str,Any]:
    sets={k:{r["date"] for r in v} for k,v in series.items()}
    union=set().union(*sets.values()) if sets else set()
    common=set.intersection(*sets.values()) if sets else set()
    missing={}
    for sym,s in sets.items():
        missing[sym]=sorted(union-s)
    return {
        "union_session_count":len(union),
        "common_session_count":len(common),
        "union_first_date":min(union) if union else None,
        "union_last_date":max(union) if union else None,
        "per_symbol_missing_vs_union":{
            k:{"count":len(v),"sample":v[:100]} for k,v in missing.items()
        },
    }
