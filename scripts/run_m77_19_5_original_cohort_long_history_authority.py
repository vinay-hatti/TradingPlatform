#!/usr/bin/env python3
import argparse,csv,json,os,statistics
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import date,datetime,timezone
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.long_history_index_authority import fetch_polygon_daily,normalize_rows,continuity_audit,sha256_file,write_csv_atomic,write_json_atomic
ROOT=Path(__file__).resolve().parents[1];CFG=ROOT/"config/m77/m77_19_5_original_cohort_long_history.json";CONFIRM="MATERIALIZE_M77_19_5_ORIGINAL_601_SYMBOL_LONG_HISTORY_AUTHORITY";FIELDS=("symbol","polygon_ticker","date","open","high","low","close","volume","vwap","transactions","source_timestamp_ms")
def load():return json.loads(CFG.read_text())
def cohort():
 m=json.loads((ROOT/"reports/m77/m77_9_daily_model_replay_manifest.json").read_text());rid=m["replay_run_id"]
 with SessionLocal() as s: syms=[str(x) for x in s.execute(text("SELECT DISTINCT symbol FROM historical_underlying_replay_prediction WHERE replay_run_id=:r ORDER BY symbol"),{"r":rid}).scalars().all()]
 return rid,syms
def old(path):
 try:
  with path.open(newline="") as f:r=list(csv.DictReader(f))
  return r or None
 except:return None
def one(sym,c,end,force):
 raw=ROOT/c["storage_root"]/"raw"/sym.replace("/","_");out=ROOT/c["storage_root"]/"normalized"/f"{sym.replace('/','_')}_daily.csv"
 if not force:
  r=old(out)
  if r:return sym,{"status":"REUSED","path":str(out),"sha256":sha256_file(out),"audit":continuity_audit(r)}
 try:
  res,pages=fetch_polygon_daily(sym,c["requested_start"],end,os.environ[c["api_key_env"]],raw);r=normalize_rows(sym,sym,res)
  if not r:return sym,{"status":"NO_DATA"}
  write_csv_atomic(out,r,list(FIELDS));return sym,{"status":"READY","path":str(out),"sha256":sha256_file(out),"raw_pages":pages,"audit":continuity_audit(r)}
 except Exception as e:return sym,{"status":"ERROR","error":repr(e)}
def summary(t):
 ok=[v for v in t.values() if v["status"] in {"READY","REUSED"}];starts=[v["audit"]["first_date"] for v in ok if v["audit"]["first_date"]];rows=[v["audit"]["row_count"] for v in ok];yrs=sum((date.fromisoformat(v["audit"]["last_date"])-date.fromisoformat(v["audit"]["first_date"])).days/365.2425 for v in ok if v["audit"]["first_date"] and v["audit"]["last_date"])
 return {"cohort_count":len(t),"successful_symbols":len(ok),"success_pct":round(100*len(ok)/len(t),3),"no_data_symbols":sum(v["status"]=="NO_DATA" for v in t.values()),"error_symbols":sum(v["status"]=="ERROR" for v in t.values()),"earliest_start":min(starts) if starts else None,"symbols_starting_by_2004_01_31":sum(x<="2004-01-31" for x in starts),"median_rows":statistics.median(rows) if rows else 0,"aggregate_symbol_years":round(yrs,2)}
def main():
 a=argparse.ArgumentParser();a.add_argument("mode",choices=("preflight","materialize","certify"));a.add_argument("--confirm");a.add_argument("--workers",type=int);a.add_argument("--force",action="store_true");z=a.parse_args();c=load();rid,syms=cohort();manifest=ROOT/c["storage_root"]/"manifests/latest.json"
 if z.mode=="preflight":print(json.dumps({"version":c["version"],"status":"READY","replay_run_id":rid,"cohort_count":len(syms),"sample":syms[:25],"range":[c["requested_start"],c["requested_end"]],"api_key_present":bool(os.getenv(c["api_key_env"])),"cohort_semantics":c["cohort_semantics"],"important_limitation":c["important_limitation"],"production_authority_effect":False},indent=2));return
 if z.mode=="materialize":
  if z.confirm!=CONFIRM:raise SystemExit("confirmation required: "+CONFIRM)
  if not os.getenv(c["api_key_env"]):raise SystemExit("missing "+c["api_key_env"])
  t={};w=z.workers or c["workers"]
  with ThreadPoolExecutor(max_workers=w) as ex:
   fs={ex.submit(one,s,c,c["requested_end"],z.force):s for s in syms}
   for n,f in enumerate(as_completed(fs),1):
    s,v=f.result();t[s]=v
    if n%25==0 or n==len(syms):print(f"M77.19.5 progress {n}/{len(syms)}",flush=True)
  sm=summary(t);write_json_atomic(manifest,{"version":c["version"],"status":"READY","generated_at":datetime.now(timezone.utc).isoformat(),"provider":"POLYGON","replay_run_id":rid,"cohort_semantics":c["cohort_semantics"],"important_limitation":c["important_limitation"],"targets":dict(sorted(t.items())),"summary":sm,"production_authority_effect":False});print(json.dumps({"status":"READY","manifest":str(manifest),"summary":sm,"production_authority_effect":False},indent=2));return
 x=json.loads(manifest.read_text());sm=x["summary"];g=c["certification"];gates={"cohort_count":g["cohort_min"]<=sm["cohort_count"]<=g["cohort_max"],"success_pct":sm["success_pct"]>=g["success_pct"],"early_symbols":sm["symbols_starting_by_2004_01_31"]>=g["starts_by_2004"],"aggregate_symbol_years":sm["aggregate_symbol_years"]>=g["aggregate_symbol_years"],"median_rows":sm["median_rows"]>=g["median_rows"]};cert=all(gates.values());out={"version":c["version"],"status":"READY","summary":sm,"gates":gates,"certified_for_m77_19_6_reconstruction":cert,"authority_semantics":"FROZEN_COHORT_LONG_HISTORY_NOT_PIT_CONSTITUENT_AUTHORITY","survivorship_bias_explicit":True,"next_step":"BUILD_M77_19_6_ISOLATED_LONG_HISTORY_RECONSTRUCTION" if cert else "REVIEW_M77_19_5_COVERAGE_GAPS","database_writes":False,"production_authority_effect":False};write_json_atomic(ROOT/"reports/m77/m77_19_5_original_cohort_long_history_certification.json",out);print(json.dumps(out,indent=2))
if __name__=="__main__":main()
