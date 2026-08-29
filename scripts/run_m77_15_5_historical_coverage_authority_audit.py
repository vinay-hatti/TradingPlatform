#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text
from trading_ai.database.session import SessionLocal

ROOT=Path(__file__).resolve().parents[1]
EVENTS=ROOT/"data/m77/m77_15_4_astronomical_event_registry_2000_2040.csv"
PIT=ROOT/"reports/m77/m77_8_daily_pit_regime_snapshots.json"
OUT=ROOT/"reports/m77/m77_15_5_historical_coverage_authority_audit.json"

VERSION="M77.15.5-HISTORICAL-COVERAGE-LONG-HORIZON-RESEARCH-AUTHORITY-AUDIT-1.0"
CONFIRM="RUN_M77_15_5_HISTORICAL_COVERAGE_AUDIT"

TARGETS=("SPX","NDX","RUT")
PROXIES={"SPX":"SPY","NDX":"QQQ","RUT":"IWM"}

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def resolve_symbol(session,target):
    for sym in (target,PROXIES[target],"I:"+target):
        if session.execute(text("SELECT 1 FROM price_history WHERE symbol=:s LIMIT 1"),{"s":sym}).scalar():
            return sym
    return None

def price_coverage(session,sym):
    if not sym:
        return {"symbol":None,"row_count":0,"first_date":None,"last_date":None}
    row=session.execute(text("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM price_history
        WHERE symbol=:s AND close IS NOT NULL
    """),{"s":sym}).one()
    return {
        "symbol":sym,
        "row_count":int(row[0] or 0),
        "first_date":str(row[1])[:10] if row[1] else None,
        "last_date":str(row[2])[:10] if row[2] else None,
    }

def load_pit():
    if not PIT.exists():
        return {"rows":0,"first_date":None,"last_date":None,"dates":set()}
    x=json.loads(PIT.read_text())
    rows=x if isinstance(x,list) else x.get("snapshots") or x.get("rows") or []
    dates=sorted({str(r.get("as_of"))[:10] for r in rows if r.get("as_of")})
    return {
        "rows":len(rows),
        "first_date":dates[0] if dates else None,
        "last_date":dates[-1] if dates else None,
        "dates":set(dates),
    }

def load_events():
    with EVENTS.open() as f:
        return list(csv.DictReader(f))

def between(d,start,end):
    return bool(start and end and start <= d <= end)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run"))
    ap.add_argument("--confirm")
    a=ap.parse_args()

    events=load_events()
    pit=load_pit()

    with SessionLocal() as s:
        resolved={t:resolve_symbol(s,t) for t in TARGETS}
        coverage={t:price_coverage(s,resolved[t]) for t in TARGETS}

    if a.mode=="preflight":
        print(json.dumps({
            "version":VERSION,
            "status":"READY",
            "confirmation_required":CONFIRM,
            "targets":resolved,
            "event_registry_rows":len(events),
            "pit_source_present":PIT.exists(),
            "governance":{
                "database_read_only":True,
                "production_authority_effect":False,
                "historical_replay_mutation":False,
                "no_fabricated_pit_regimes":True,
                "audit_only":True
            }
        },indent=2))
        return

    if a.confirm!=CONFIRM:
        raise SystemExit(f"confirmation required: {CONFIRM}")

    family_counts=defaultdict(int)
    for e in events:
        family_counts[e["event_family"]]+=1

    target_details={}
    for target,cov in coverage.items():
        pstart,pstop=cov["first_date"],cov["last_date"]
        family={}
        for fam,total in sorted(family_counts.items()):
            fam_events=[e for e in events if e["event_family"]==fam]
            price_overlap=[e for e in fam_events if between(e["event_date"],pstart,pstop)]
            pit_overlap=[e for e in price_overlap if e["event_date"] in pit["dates"]]
            family[fam]={
                "astronomical_event_count":total,
                "price_overlap_event_count":len(price_overlap),
                "pit_exact_date_overlap_event_count":len(pit_overlap),
            }
        target_details[target]={
            "price_coverage":cov,
            "event_family_coverage":family,
        }

    # Overall date-overlap diagnostics.
    overall={
        "event_registry":{
            "rows":len(events),
            "first_date":min(e["event_date"] for e in events) if events else None,
            "last_date":max(e["event_date"] for e in events) if events else None,
            "family_counts":dict(sorted(family_counts.items())),
        },
        "pit_regime_coverage":{
            "rows":pit["rows"],
            "first_date":pit["first_date"],
            "last_date":pit["last_date"],
        },
        "targets":target_details,
    }

    # Governance recommendation is descriptive only.
    earliest_price=min((v["first_date"] for v in coverage.values() if v["first_date"]),default=None)
    latest_price=max((v["last_date"] for v in coverage.values() if v["last_date"]),default=None)
    price_history_years=None
    if earliest_price and latest_price:
        from datetime import date
        a0=date.fromisoformat(earliest_price); a1=date.fromisoformat(latest_price)
        price_history_years=round((a1-a0).days/365.2425,2)

    recommendation={
        "price_history_span_years_across_targets":price_history_years,
        "full_pit_control_available_from":pit["first_date"],
        "full_pit_control_available_through":pit["last_date"],
        "long_history_mode_definition":"PRICE_PLUS_CALENDAR_CONTROLS_ONLY",
        "recent_pit_mode_definition":"PRICE_PLUS_CALENDAR_PLUS_PIT_REGIME_CONTROLS",
        "promotion_rule":"NO_CANDIDATE_MAY_ADVANCE_UNLESS_IT_SURVIVES_LONG_HISTORY_AND_RECENT_PIT_MODES_IN_SAME_DIRECTION",
        "fabricated_historical_pit_regimes":"PROHIBITED",
    }

    out={
        "version":VERSION,
        "status":"READY",
        "audit":overall,
        "recommendation":recommendation,
        "next_step":"BUILD_DUAL_CONTROL_LONG_HISTORY_RESEARCH_HARNESS_IF_PRICE_HISTORY_IS_MATERIALLY_LONGER_THAN_PIT_HISTORY",
        "production_authority_effect":False,
        "database_writes":False,
    }
    write_json_atomic(OUT,out)

    print(json.dumps({
        "version":VERSION,
        "status":"READY",
        "targets":coverage,
        "pit_regime_coverage":{
            "rows":pit["rows"],
            "first_date":pit["first_date"],
            "last_date":pit["last_date"],
        },
        "event_registry_rows":len(events),
        "next_step":out["next_step"],
        "production_authority_effect":False
    },indent=2))

if __name__=="__main__":
    main()
