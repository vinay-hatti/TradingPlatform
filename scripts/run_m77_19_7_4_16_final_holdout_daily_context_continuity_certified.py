#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,importlib.util,json,math,sys
from bisect import bisect_right
from collections import Counter,defaultdict
from pathlib import Path

FINAL_HOLDOUT_START="2023-01-01"
DATE_FIELD="session_date";CLOSE_FIELD="close"
class ContextError(RuntimeError):pass

def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def iter_jsonl(path):
    op=gzip.open if str(path).endswith(".gz") else open
    with op(path,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def imp(path):
    spec=importlib.util.spec_from_file_location("m77_7416_canonical",str(path))
    m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m
def to_float(v):
    if v is None or isinstance(v,bool):return None
    try:
        x=float(v);return x if math.isfinite(x) else None
    except Exception:return None
def daily_file_map(root):
    out={}
    for p in sorted(Path(root).rglob("*.daily.csv.gz")):
        sym=p.name[:-len(".daily.csv.gz")]
        if sym in out:raise ContextError(f"ambiguous daily source for {sym}")
        out[sym]=p
    return out
def load_daily(path):
    rows=[]
    with gzip.open(path,"rt",encoding="utf-8",newline="") as f:
        r=csv.DictReader(f)
        if DATE_FIELD not in (r.fieldnames or []) or CLOSE_FIELD not in (r.fieldnames or []):raise ContextError("certified daily fields missing")
        for x in r:
            d=str(x.get(DATE_FIELD) or "")[:10];c=to_float(x.get(CLOSE_FIELD))
            if d and c is not None and c>0:rows.append((d,c))
    rows.sort();return rows
def close_on_or_before(hist,d):
    dates=[x[0] for x in hist];i=bisect_right(dates,d)-1
    return None if i<0 else hist[i][1]
def read_seed(path):
    rows=[]
    with Path(path).open("r",encoding="utf-8",newline="") as f:
        for r in csv.DictReader(f):
            if str(r["as_of"])[:10]<FINAL_HOLDOUT_START:rows.append(r)
    rows.sort(key=lambda x:x["as_of"])
    if not rows:raise ContextError("pre-holdout context seed empty")
    return rows
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--canonical-context-script",default="scripts/run_m77_19_7_4_16_point_in_time_regime_context_materialization_authority.py")
    ap.add_argument("--replay-authority-json",default="reports/m77_19_7_3_1_native_profile_schema_authority_repair.json")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--preholdout-context-csv",default="reports/m77_19_7_4_16_point_in_time_regime_context.csv")
    ap.add_argument("--partition-start",default="2023-01-01")
    ap.add_argument("--partition-end",required=True)
    ap.add_argument("--output-json",required=True);ap.add_argument("--output-csv",required=True)
    a=ap.parse_args();root=Path(a.project_root).resolve()
    canon=imp(resolve(root,a.canonical_context_script))
    ra=load_json(resolve(root,a.replay_authority_json));resolver=load_json(resolve(root,a.resolver_authority_json))
    dsa=resolver.get("frozen_daily_source_resolver") or {}
    if resolver.get("status")!="READY" or dsa.get("certified") is not True or dsa.get("date_field")!=DATE_FIELD or dsa.get("close_field")!=CLOSE_FIELD:raise ContextError("daily resolver authority invalid")
    replay_root=resolve(root,a.replay_root)
    files=sorted((replay_root/"weekly"/"profiles").glob("*.jsonl.gz"))
    if len(files)!=602:raise ContextError(f"expected 602 replay files, found {len(files)}")
    daily=daily_file_map(resolve(root,a.daily_materialization_root))
    if "SPY" not in daily:raise ContextError("SPY daily source missing")
    spy_hist=load_daily(daily["SPY"])
    seed=read_seed(resolve(root,a.preholdout_context_csv))
    closes=[float(r["spy_close"]) for r in seed]
    cross=defaultdict(Counter);spy_profile={}
    for f in files:
        sym=f.name[:-9]
        for row in iter_jsonl(f):
            d=str(row.get("as_of") or "")[:10]
            if d<a.partition_start or d>a.partition_end or row.get("status")!="REPLAYED":continue
            p=row.get("profile")
            if not isinstance(p,dict):raise ContextError(f"{sym} {d}: profile missing")
            direction=canon.classify_direction(p.get("direction"));c=cross[d];c["eligible"]+=1;c[f"direction_{direction}"]+=1
            bo=str(canon.get_path(p,"breakout.state") or "").upper()
            if bo:c[f"breakout_{bo}"]+=1
            part=str(canon.get_path(p,"participation.state") or "").upper()
            if part:c[f"participation_{part}"]+=1
            if sym=="SPY":
                spy_profile[d]={"spy_direction":str(p.get("direction") or ""),"spy_confidence":canon.num(p.get("confidence")),
                "spy_overall_score":canon.num(row.get("overall_score")),"spy_breakout_state":bo or None,"spy_participation_state":part or None}
    out=[]
    for d in sorted(cross):
        close=close_on_or_before(spy_hist,d)
        if close is None:raise ContextError(f"{d}: SPY daily close unavailable")
        closes.append(close);c=cross[d];n=c["eligible"]
        out.append({"as_of":d,"partition":"FINAL_HOLDOUT","cross_section_eligible_count":n,
        "breadth_bullish_fraction":c["direction_BULLISH"]/n,"breadth_bearish_fraction":c["direction_BEARISH"]/n,"breadth_neutral_fraction":c["direction_NEUTRAL"]/n,
        "breakdown_setup_fraction":c["breakout_BREAKDOWN_SETUP"]/n,"breakdown_confirmed_fraction":c["breakout_BREAKDOWN_CONFIRMED"]/n,
        "capitulation_fraction":c["participation_CAPITULATION"]/n,"spy_close":close,
        "spy_return_4w":canon.rolling_return(closes,4),"spy_return_13w":canon.rolling_return(closes,13),"spy_return_26w":canon.rolling_return(closes,26),
        "spy_realized_vol_13w_annualized":canon.rolling_vol(closes,13),"spy_realized_vol_26w_annualized":canon.rolling_vol(closes,26),
        "spy_drawdown_from_52w_peak":canon.drawdown_from_peak(closes,52),**(spy_profile.get(d) or {})})
    if not out:raise ContextError("no Final Holdout context rows materialized")
    op=resolve(root,a.output_csv);op.parent.mkdir(parents=True,exist_ok=True)
    fields=list(out[0])
    with op.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
    report={"version":"M77.19.7.4.16-FINAL-HOLDOUT-DAILY-CONTEXT-CONTINUITY-CERTIFIED-1.0","status":"READY",
    "partition_start":a.partition_start,"partition_end":a.partition_end,"row_count":len(out),"first_as_of":out[0]["as_of"],"last_as_of":out[-1]["as_of"],
    "spy_close_source":"FROZEN_DAILY_SOURCE_RESOLVER","preholdout_rolling_history_seeded_from_certified_context":True,
    "outcome_authority_read":False,"final_holdout_targets_opened":False,"final_holdout_outcomes_opened":False,"final_holdout_scoring_performed":False,"production_authority_effect":False}
    resolve(root,a.output_json).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("status: READY");print("row_count:",len(out));print("first_as_of:",out[0]["as_of"]);print("last_as_of:",out[-1]["as_of"])
    print("spy_close_source: FROZEN_DAILY_SOURCE_RESOLVER");print("preholdout_rolling_history_seeded_from_certified_context: True")
    print("outcome_authority_read: False");print("final_holdout_targets_opened: False");print("final_holdout_outcomes_opened: False");print("final_holdout_scoring_performed: False")
if __name__=="__main__":main()
