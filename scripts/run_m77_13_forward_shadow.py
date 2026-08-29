#!/usr/bin/env python3
from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect, text
from trading_ai.database.session import SessionLocal
from m77_13_completed_period_calendar import (
    completed_monthly_anchor,
    completed_weekly_anchor,
    is_actual_month_end_session,
)

VERSION="M77.13-MULTI-CADENCE-CERTIFIED-BASELINE-FORWARD-SHADOW-1.0"
CONFIRM="RUN_M77_13_FORWARD_SHADOW_CYCLE"

DAILY_CERT=Path("reports/m77/m77_9_daily_walk_forward_certification.json")
MONTHLY_CERT=Path("reports/m77/m77_10_monthly_walk_forward_certification.json")
PIT_SCRIPT=Path("scripts/run_m77_8_daily_pit_replay_authority.py")
PIT_ARTIFACT=Path("reports/m77/m77_8_daily_pit_regime_snapshots.json")
M77_1_CLI=Path("scripts/run_m77_1_historical_underlying_replay.py")

REQUIRED_TABLES={"m77_13_cadence_states","m77_13_forward_signals","m77_13_forward_outcomes"}

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def json_sha(path): return sha256_bytes(path.read_bytes())

def score_band(x):
    if x is None:return "S_UNKNOWN"
    x=float(x)
    if x<60:return "S_LT60"
    if x<70:return "S60_69"
    if x<80:return "S70_79"
    if x<90:return "S80_89"
    return "S90_100"

def conf_band(x):
    if x is None:return "C_UNKNOWN"
    x=float(x)
    if x<70:return "C_LT70"
    if x<80:return "C70_79"
    return "C80_100"

def direction_family(d):
    d=str(d or "").upper()
    if d in ("BULLISH","STRONG_BULLISH"): return "BULLISH"
    if d in ("BEARISH","STRONG_BEARISH"): return "BEARISH"
    return "NEUTRAL"

def frozen(path, directional_only=False):
    d=json.loads(path.read_text())
    rows=[]
    for x in d.get("cohort_certification",[]):
        if not x.get("certified"): continue
        if directional_only and direction_family(x.get("direction"))=="NEUTRAL": continue
        rows.append({
            "horizon_sessions":int(x["horizon_sessions"]),
            "regime":x.get("regime"),
            "direction":x.get("direction"),
            "score_band":x.get("score_band"),
            "confidence_band":x.get("confidence_band"),
        })
    return d,rows

def baseline_id(source,c):
    return f'{source}::{c["horizon_sessions"]}::{c["regime"]}::{c["direction"]}::{c["score_band"]}::{c["confidence_band"]}'

def matches(row,reg,c):
    return (
        reg==c["regime"]
        and row["direction"]==c["direction"]
        and score_band(row["overall_score"])==c["score_band"]
        and conf_band(row["confidence"])==c["confidence_band"]
    )

def check_tables(session):
    tables=set(inspect(session.get_bind()).get_table_names())
    missing=sorted(REQUIRED_TABLES-tables)
    if missing: raise RuntimeError("M77.13 schema missing: "+", ".join(missing))

def eligible_symbols(session):
    tables=set(inspect(session.get_bind()).get_table_names())
    table="historical_underlying_replay_authority"
    if table not in tables: raise RuntimeError("historical_underlying_replay_authority missing")
    rows=session.execute(text(
        f"SELECT symbol FROM {table} WHERE disposition='ELIGIBLE' ORDER BY symbol"
    )).scalars().all()
    out=sorted({str(x).strip().upper() for x in rows if str(x).strip()})
    if not out: raise RuntimeError("No ELIGIBLE M77.1 authority symbols")
    return out

def run_json(cmd):
    cp=subprocess.run(cmd,text=True,capture_output=True)
    if cp.returncode!=0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}")
    try:return json.loads(cp.stdout)
    except Exception as exc: raise RuntimeError(f"Command did not return JSON:\n{cp.stdout}") from exc

def refresh_pit():
    if not PIT_SCRIPT.exists(): raise RuntimeError(f"Missing {PIT_SCRIPT}")
    cp=subprocess.run([sys.executable,str(PIT_SCRIPT)],text=True,capture_output=True)
    if cp.returncode!=0:
        raise RuntimeError(f"M77.8 PIT refresh failed\nSTDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}")
    if not PIT_ARTIFACT.exists(): raise RuntimeError("M77.8 PIT artifact missing after refresh")

def market_calendar(session):
    ds=[str(x)[:10] for x in session.execute(text(
        "SELECT DISTINCT date FROM price_history WHERE symbol='SPY' ORDER BY date"
    )).scalars().all()]
    if not ds: raise RuntimeError("No SPY session calendar")
    return ds

def materialize_cadence(session,cadence,as_of,symbols,regimes):
    existing=session.execute(text("""
      SELECT count(*) FROM m77_13_cadence_states WHERE cadence=:c AND as_of=:d
    """),{"c":cadence,"d":as_of}).scalar_one()
    if existing>=len(symbols):
        return {"cadence":cadence,"as_of":as_of,"mode":"REUSED","states":existing}

    if not M77_1_CLI.exists(): raise RuntimeError(f"Missing {M77_1_CLI}")
    out=run_json([
        sys.executable,str(M77_1_CLI),"run-baseline",
        "--start",as_of,"--end",as_of,"--cadence",cadence,
        "--symbols",",".join(symbols),
    ])
    rid=out["replay_run_id"]
    rows=session.execute(text("""
      SELECT as_of,symbol,direction,overall_score,confidence,state_hash
      FROM historical_underlying_replay_prediction
      WHERE replay_run_id=:rid ORDER BY symbol
    """),{"rid":rid}).mappings().all()

    reg=regimes.get(as_of)
    if reg is None: raise RuntimeError(f"No exact M77.8 PIT regime for {as_of}")

    inserted=0
    for r in rows:
        session.execute(text("""
          INSERT INTO m77_13_cadence_states(
            state_id,cadence,as_of,symbol,direction,overall_score,confidence,regime,state_hash,source_replay_run_id,payload_json
          ) VALUES(
            :id,:c,:d,:s,:dir,:score,:conf,:reg,:hash,:rid,CAST(:payload AS jsonb)
          )
          ON CONFLICT ON CONSTRAINT uq_m77_13_cadence_state DO NOTHING
        """),{
            "id":"m77-13-state-"+uuid4().hex,"c":cadence,"d":as_of,"s":r["symbol"],
            "dir":r["direction"],"score":r["overall_score"],"conf":r["confidence"],
            "reg":reg,"hash":r["state_hash"],"rid":rid,
            "payload":json.dumps({"version":VERSION,"research_only":True,"production_effect":False})
        })
        inserted+=1
    session.commit()
    return {"cadence":cadence,"as_of":as_of,"mode":"MATERIALIZED","replay_run_id":rid,"states":len(rows),"attempted_inserts":inserted}

def state_map(session,cadence,as_of):
    rows=session.execute(text("""
      SELECT symbol,direction,overall_score,confidence,regime,state_hash
      FROM m77_13_cadence_states WHERE cadence=:c AND as_of=:d
    """),{"c":cadence,"d":as_of}).mappings().all()
    return {str(r["symbol"]):dict(r) for r in rows}

def close_map(session,dt,symbols):
    rows=session.execute(text("""
      SELECT symbol,close FROM price_history WHERE date=:d AND symbol = ANY(:symbols)
    """),{"d":dt,"symbols":symbols}).all()
    return {str(s):float(c) for s,c in rows if c is not None}

def capture_signals(session,source_date,weekly_anchor,monthly_anchor,daily_certs,monthly_certs,policy_sha,symbols):
    daily=state_map(session,"DAILY",source_date)
    weekly=state_map(session,"WEEKLY",weekly_anchor)
    monthly=state_map(session,"MONTHLY",monthly_anchor)
    prices=close_map(session,source_date,symbols)

    inserted=0; duplicates=0; by_source=defaultdict(int)
    def insert_signal(source,c,sym,state):
        nonlocal inserted,duplicates
        px=prices.get(sym)
        if px is None:return
        bid=baseline_id(source,c)
        fp=sha256_bytes(f"{source}|{bid}|{sym}|{source_date}".encode())
        exists=session.execute(text(
            "SELECT 1 FROM m77_13_forward_signals WHERE signal_fingerprint=:f"
        ),{"f":fp}).first()
        if exists:
            duplicates+=1;return
        payload={
            "version":VERSION,"research_only":True,"production_effect":False,
            "daily_context":daily.get(sym),"weekly_context":weekly.get(sym),"monthly_context":monthly.get(sym),
            "no_filtering_or_ranking_effect":True,
        }
        session.execute(text("""
          INSERT INTO m77_13_forward_signals(
            signal_id,signal_fingerprint,captured_at,source_as_of,symbol,baseline_source,baseline_id,horizon_sessions,
            direction,regime,score_band,confidence_band,reference_price,daily_state_as_of,weekly_state_as_of,monthly_state_as_of,
            policy_sha256,status,payload_json
          ) VALUES(
            :id,:fp,:now,:d,:sym,:src,:bid,:h,:dir,:reg,:sb,:cb,:px,:dd,:wd,:md,:sha,'OPEN',CAST(:payload AS jsonb)
          )
        """),{
            "id":"m77-13-signal-"+uuid4().hex,"fp":fp,"now":datetime.now(timezone.utc),"d":source_date,"sym":sym,
            "src":source,"bid":bid,"h":c["horizon_sessions"],"dir":c["direction"],"reg":c["regime"],
            "sb":c["score_band"],"cb":c["confidence_band"],"px":px,
            "dd":source_date,"wd":weekly_anchor,"md":monthly_anchor,"sha":policy_sha,
            "payload":json.dumps(payload,default=str)
        })
        inserted+=1;by_source[source]+=1

    for sym,state in daily.items():
        for c in daily_certs:
            if matches(state,state["regime"],c):
                insert_signal("DAILY",c,sym,state)

    # Monthly certified baseline signals are prospective only when source_date is the actual current month-end anchor.
    # This prevents backfilling a July signal on an August activation date.
    if is_actual_month_end_session(datetime.fromisoformat(source_date).date()):
        mprices=close_map(session,monthly_anchor,symbols)
        prices.update(mprices)
        for sym,state in monthly.items():
            for c in monthly_certs:
                if matches(state,state["regime"],c):
                    insert_signal("MONTHLY",c,sym,state)

    session.commit()
    return {"signals_inserted":inserted,"idempotent_duplicates":duplicates,"by_source":dict(by_source),
            "monthly_capture_armed":is_actual_month_end_session(datetime.fromisoformat(source_date).date())}

def mature(session,session_dates):
    idx={d:i for i,d in enumerate(session_dates)}
    open_rows=session.execute(text("""
      SELECT signal_id,source_as_of,symbol,horizon_sessions,direction,reference_price
      FROM m77_13_forward_signals WHERE status='OPEN' ORDER BY source_as_of,signal_id
    """)).mappings().all()
    matured=0;waiting=0
    for r in open_rows:
        d=str(r["source_as_of"])[:10]
        i=idx.get(d)
        if i is None or i+int(r["horizon_sessions"])>=len(session_dates):
            waiting+=1;continue
        target=session_dates[i+int(r["horizon_sessions"])]
        px=session.execute(text(
            "SELECT close FROM price_history WHERE symbol=:s AND date=:d"
        ),{"s":r["symbol"],"d":target}).scalar()
        if px is None:
            waiting+=1;continue
        raw=100*(float(px)/float(r["reference_price"])-1)
        thesis=-raw if direction_family(r["direction"])=="BEARISH" else raw
        hit=thesis>0
        session.execute(text("""
          INSERT INTO m77_13_forward_outcomes(
            outcome_id,signal_id,target_session_date,observed_at,target_close,raw_return_pct,thesis_return_pct,directional_hit,payload_json
          ) VALUES(:id,:sid,:td,:now,:px,:raw,:thesis,:hit,CAST(:payload AS jsonb))
          ON CONFLICT ON CONSTRAINT uq_m77_13_forward_outcome_signal DO NOTHING
        """),{
            "id":"m77-13-outcome-"+uuid4().hex,"sid":r["signal_id"],"td":target,"now":datetime.now(timezone.utc),
            "px":float(px),"raw":raw,"thesis":thesis,"hit":hit,
            "payload":json.dumps({"version":VERSION,"research_only":True,"production_effect":False})
        })
        session.execute(text(
            "UPDATE m77_13_forward_signals SET status='MATURED' WHERE signal_id=:id"
        ),{"id":r["signal_id"]})
        matured+=1
    session.commit()
    return {"open_examined":len(open_rows),"matured":matured,"waiting":waiting}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=["preflight","cycle"])
    ap.add_argument("--confirm")
    args=ap.parse_args()

    for p in (DAILY_CERT,MONTHLY_CERT,PIT_SCRIPT,M77_1_CLI):
        if not p.exists(): raise SystemExit(f"Missing required M77.13 dependency: {p}")

    dc,daily_certs=frozen(DAILY_CERT)
    mc,monthly_directional=frozen(MONTHLY_CERT,directional_only=True)
    monthly_neutral=[x for x in mc.get("cohort_certification",[]) if x.get("certified") and direction_family(x.get("direction"))=="NEUTRAL"]

    with SessionLocal() as s:
        check_tables(s)
        symbols=eligible_symbols(s)
        sessions=market_calendar(s)
        source_date=sessions[-1]
        weekly_anchor=completed_weekly_anchor(datetime.fromisoformat(source_date).date()).isoformat()
        monthly_anchor=completed_monthly_anchor(datetime.fromisoformat(source_date).date()).isoformat()

    pre={
        "version":VERSION,"status":"READY","mode":"PREFLIGHT","confirmation_required":CONFIRM,
        "source_session":source_date,"weekly_anchor":weekly_anchor,"monthly_anchor":monthly_anchor,
        "eligible_symbols":len(symbols),"frozen_daily_baselines":len(daily_certs),
        "frozen_monthly_directional_baselines":len(monthly_directional),
        "monthly_neutral_context_only":len(monthly_neutral),
        "schema_revision_required":"m77_004",
        "research_only":True,"production_authority_effect":False,
        "production_filter_or_ranking_effect":False,"automatic_shadow_promotion":False
    }
    if args.mode=="preflight":
        print(json.dumps(pre,indent=2));return
    if args.confirm!=CONFIRM:
        raise SystemExit(f"Confirmation required: --confirm {CONFIRM}")

    refresh_pit()
    pit=json.loads(PIT_ARTIFACT.read_text())
    regimes={str(x["as_of"])[:10]:x["regime"] for x in pit.get("snapshots",[])}

    policy_sha=sha256_bytes((DAILY_CERT.read_bytes()+MONTHLY_CERT.read_bytes()))

    with SessionLocal() as s:
        check_tables(s);symbols=eligible_symbols(s);sessions=market_calendar(s)
        source_date=sessions[-1]
        weekly_anchor=completed_weekly_anchor(datetime.fromisoformat(source_date).date()).isoformat()
        monthly_anchor=completed_monthly_anchor(datetime.fromisoformat(source_date).date()).isoformat()

        materialized=[]
        for cadence,dt in (("DAILY",source_date),("WEEKLY",weekly_anchor),("MONTHLY",monthly_anchor)):
            materialized.append(materialize_cadence(s,cadence,dt,symbols,regimes))

        capture=capture_signals(
            s,source_date,weekly_anchor,monthly_anchor,daily_certs,monthly_directional,policy_sha,symbols
        )
        maturity=mature(s,sessions)

    out={
        "version":VERSION,"status":"READY","mode":"PROSPECTIVE_CERTIFIED_BASELINE_FORWARD_SHADOW",
        "source_session":source_date,"weekly_anchor":weekly_anchor,"monthly_anchor":monthly_anchor,
        "cadence_state_materialization":materialized,"capture":capture,"maturity":maturity,
        "monthly_neutral_context_only":len(monthly_neutral),
        "policy_sha256":policy_sha,"production_authority_effect":False,
        "production_filter_or_ranking_effect":False
    }
    print(json.dumps(out,indent=2))

if __name__=="__main__":
    main()
