#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, hashlib, subprocess, sys
from pathlib import Path
from sqlalchemy import inspect, text
from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.service import HistoricalUnderlyingReplayService

VERSION="M77.10.2-MONTHLY-MODEL-REPLAY-1.0"
CONFIRM="RUN_M77_10_MONTHLY_MODEL_REPLAY"
AUTH=Path("reports/m77/m77_8_daily_pit_replay_authority.json")
OUT=Path("reports/m77/m77_10_monthly_model_replay_manifest.json")
START="2022-08-31"
END="2026-05-29"
M77_1_CLI=Path("scripts/run_m77_1_historical_underlying_replay.py")

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def discover_authority_table(session):
    insp=inspect(session.get_bind()); tables=set(insp.get_table_names())
    for table in ("historical_underlying_replay_authority","historical_underlying_replay_symbol_authority"):
        if table in tables:
            cols={c["name"] for c in insp.get_columns(table)}
            if {"symbol","disposition"}.issubset(cols): return table
    for table in sorted(tables):
        if "historical_underlying_replay" in table and "authority" in table:
            cols={c["name"] for c in insp.get_columns(table)}
            if {"symbol","disposition"}.issubset(cols): return table
    raise RuntimeError("Persisted M77.1 replay authority table not found")

def eligible_authority_symbols(session):
    table=discover_authority_table(session)
    rows=session.execute(text(f"SELECT symbol FROM {table} WHERE disposition='ELIGIBLE' ORDER BY symbol")).scalars().all()
    symbols=sorted({str(x).strip().upper() for x in rows if str(x).strip()})
    if not symbols: raise RuntimeError(f"No ELIGIBLE symbols in {table}")
    return table,symbols

def run_m77_1_cli(symbols):
    if not M77_1_CLI.exists():
        raise RuntimeError(f"Installed M77.1 CLI missing: {M77_1_CLI}")
    cmd=[
        sys.executable,str(M77_1_CLI),"run-baseline",
        "--start",START,"--end",END,"--cadence","MONTHLY",
        "--symbols",",".join(symbols),
    ]
    cp=subprocess.run(cmd,text=True,capture_output=True)
    if cp.returncode!=0:
        raise RuntimeError(
            "M77.1 monthly replay CLI failed\n"
            f"STDOUT:\n{cp.stdout}\nSTDERR:\n{cp.stderr}"
        )
    try:
        return json.loads(cp.stdout)
    except Exception as exc:
        raise RuntimeError(f"M77.1 CLI did not return JSON: {cp.stdout}") from exc

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("mode",choices=["preflight","run"]); ap.add_argument("--confirm"); args=ap.parse_args()
    if not AUTH.exists(): raise SystemExit(f"Missing M77.8 authority: {AUTH}")
    if not M77_1_CLI.exists(): raise SystemExit(f"Missing M77.1 CLI: {M77_1_CLI}")
    a=json.loads(AUTH.read_text())
    if not a.get("acceptance",{}).get("daily_pit_replay_authority_ready"):
        raise SystemExit("FAIL_CLOSED: M77.8 authority not READY")
    if a.get("production_authority_effect") is not False:
        raise SystemExit("FAIL_CLOSED: M77.8 production authority effect must be false")

    with SessionLocal() as s:
        summary=HistoricalUnderlyingReplayService(s).materialize_authority()
        table,eligible=eligible_authority_symbols(s)

    pre={"version":VERSION,"status":"READY","mode":"PREFLIGHT","confirmation_required":CONFIRM,
         "start":START,"end":END,"cadence":"MONTHLY","authority_table":table,
         "authority_summary_status":summary.get("status"),"authority_summary_symbols":summary.get("symbols"),
         "eligible_authority_symbols":len(eligible),"monthly_horizons":[60,120,180,252],
         "replay_execution_contract":"INSTALLED_M77_1_CLI_RUN_BASELINE",
         "long_horizon_outcomes_contract":"CERTIFICATION_COMPUTES_FROM_PRICE_HISTORY; M77.1 replay rows remain unmodified",
         "production_authority_effect":False,"existing_weekly_m77_mutation":False,"existing_daily_m77_mutation":False}
    if args.mode=="preflight":
        print(json.dumps(pre,indent=2)); return
    if args.confirm!=CONFIRM: raise SystemExit(f"Confirmation required: --confirm {CONFIRM}")

    out=run_m77_1_cli(eligible)
    manifest={"version":VERSION,"status":out.get("status","UNKNOWN"),"replay_run_id":out["replay_run_id"],
              "start":START,"end":END,"cadence":"MONTHLY","authority_table":table,"eligible_symbol_scope":len(eligible),
              "prediction_count":out.get("prediction_count",0),"failure_count":out.get("failure_count",0),
              "replay_execution_contract":"INSTALLED_M77_1_CLI_RUN_BASELINE",
              "long_horizon_outcomes_contract":"COMPUTE_FROM_PRICE_HISTORY_DURING_CERTIFICATION",
              "m77_8_authority":str(AUTH),"m77_8_sha256":sha(AUTH),
              "production_authority_effect":False,"existing_weekly_m77_mutation":False,"existing_daily_m77_mutation":False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(manifest,indent=2))
if __name__=="__main__": main()
