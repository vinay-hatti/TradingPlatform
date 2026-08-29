#!/usr/bin/env python3
import argparse,csv,gzip,hashlib,importlib.util,json,math,sys
from bisect import bisect_right
from pathlib import Path
EXPECTED_CANONICAL_SHA="f1aa47fc78d7404f513aa1405e4401ca70ee2e06cb63a298063a3a068e2b891a"
EXPECTED_ADAPTER_SHA="9c24d993ca310b0f16f44a43b8e9a9f3d113626fee162576e2cf0603ca5fc9a4"
NUMERIC=("spy_close","spy_return_4w","spy_return_13w","spy_return_26w","spy_realized_vol_13w_annualized","spy_realized_vol_26w_annualized","spy_drawdown_from_52w_peak")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def loadj(p):return json.loads(Path(p).read_text())
def daily_map(root):
 out={}
 for p in Path(root).rglob("*.daily.csv.gz"):out[p.name[:-len(".daily.csv.gz")]]=p
 return out
def daily(path):
 out=[]
 with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
  r=csv.DictReader(f)
  for x in r:
   try:c=float(x["close"])
   except:continue
   d=str(x["session_date"])[:10]
   if d and c>0:out.append((d,c))
 out.sort();return out
def close(hist,d):
 ds=[x[0] for x in hist];i=bisect_right(ds,d)-1;return None if i<0 else hist[i][1]
def imp(path):
 s=importlib.util.spec_from_file_location("canon7416",str(path));m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);return m
def eq(a,b):
 if a in ("",None) and b in ("",None):return True
 try:
  x=float(a);y=float(b);return abs(x-y)<=1e-10*max(1.0,abs(x),abs(y))
 except:return a==b
def main():
 ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
 ap.add_argument("--protocol-json",default="reports/m77_19_8_7_10_7_5_non_outcome_dependent_final_holdout_protocol_preregistration_authority.json")
 ap.add_argument("--adapter-gate-json",default="reports/m77_19_8_7_10_7_6_0_exact_final_holdout_feature_adapter_certification_gate.json")
 ap.add_argument("--canonical-context-script",default="scripts/run_m77_19_7_4_16_point_in_time_regime_context_materialization_authority.py")
 ap.add_argument("--adapter-script",default="scripts/run_m77_19_7_4_16_final_holdout_daily_context_continuity_certified.py")
 ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
 ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
 ap.add_argument("--preholdout-context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
 ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_6_0_1_final_holdout_context_source_continuity_certification_gate.json")
 a=ap.parse_args();r=Path(a.project_root).resolve()
 protocol=loadj(r/a.protocol_json);gate=loadj(r/a.adapter_gate_json)
 if protocol.get("status")!="READY" or gate.get("status")!="READY":raise RuntimeError("upstream protocol/adapter gate invalid")
 if sha(r/a.canonical_context_script)!=EXPECTED_CANONICAL_SHA:raise RuntimeError("canonical context source SHA mismatch")
 if sha(r/a.adapter_script)!=EXPECTED_ADAPTER_SHA:raise RuntimeError("daily context adapter SHA mismatch")
 resolver=loadj(r/a.resolver_authority_json);dsa=resolver.get("frozen_daily_source_resolver") or {}
 if resolver.get("status")!="READY" or dsa.get("certified") is not True or dsa.get("date_field")!="session_date" or dsa.get("close_field")!="close":raise RuntimeError("daily resolver invalid")
 dm=daily_map(r/a.daily_materialization_root)
 hist=daily(dm["SPY"]);canon=imp(r/a.canonical_context_script)
 rows=list(csv.DictReader((r/a.preholdout_context_csv).open()))
 rows=[x for x in rows if str(x["as_of"])[:10]<"2023-01-01"];rows.sort(key=lambda x:x["as_of"])
 closes=[];mismatch=0;first=[]
 for x in rows:
  d=str(x["as_of"])[:10];c=close(hist,d)
  if c is None:raise RuntimeError(f"{d} daily close missing")
  closes.append(c)
  calc={"spy_close":c,"spy_return_4w":canon.rolling_return(closes,4),"spy_return_13w":canon.rolling_return(closes,13),"spy_return_26w":canon.rolling_return(closes,26),
  "spy_realized_vol_13w_annualized":canon.rolling_vol(closes,13),"spy_realized_vol_26w_annualized":canon.rolling_vol(closes,26),"spy_drawdown_from_52w_peak":canon.drawdown_from_peak(closes,52)}
  for k,v in calc.items():
   if not eq(x.get(k),v):
    mismatch+=1
    if len(first)<5:first.append((d,k,x.get(k),v))
 if mismatch:raise RuntimeError(f"preholdout daily-context parity mismatch count={mismatch} sample={first}")
 out={"version":"M77.19.8.7.10.7.6.0.1-FINAL-HOLDOUT-CONTEXT-SOURCE-CONTINUITY-CERTIFICATION-1.0","status":"READY",
 "preholdout_context_row_count":len(rows),"preholdout_daily_context_parity_mismatch_count":0,
 "frozen_daily_spy_close_parity_certified":True,"rolling_4w_13w_26w_52w_continuity_certified":True,
 "final_holdout_context_adapter_certified":True,"outcome_authority_required_for_final_holdout_context":False,
 "final_holdout_rows_read_by_this_step":False,"final_holdout_targets_opened":False,"final_holdout_outcomes_opened":False,
 "final_holdout_scoring_performed":False,"production_authority_effect":False,
 "next_step":"RUN_M77_19_8_7_10_7_6_1_FINAL_HOLDOUT_CONTEXT_AND_FEATURE_MATRIX_MATERIALIZATION"}
 (r/a.output_json).write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
 print("=== M77.19.8.7.10.7.6.0.1 FINAL HOLDOUT CONTEXT SOURCE & CONTINUITY CERTIFICATION ===")
 print("status: READY");print("preholdout_context_row_count:",len(rows));print("preholdout_daily_context_parity_mismatch_count: 0")
 print("frozen_daily_spy_close_parity_certified: True");print("rolling_4w_13w_26w_52w_continuity_certified: True")
 print("outcome_authority_required_for_final_holdout_context: False");print("final_holdout_rows_read_by_this_step: False")
 print("final_holdout_targets_opened: False");print("final_holdout_outcomes_opened: False");print("production_authority_effect: False")
 print("next_step:",out["next_step"]);print("report:",r/a.output_json)
if __name__=="__main__":main()
