#!/usr/bin/env python3
from __future__ import annotations
import argparse,bisect,csv,hashlib,importlib.util,json,math,os,tempfile
from collections import Counter
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

VERSION="M77.20.5-PROSPECTIVE-BASELINE-FEATURE-SHADOW-CAPTURE-PAIRED-OBSERVATION-AUTHORITY-1.0"
class BaselineError(RuntimeError):pass

def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def sh(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:Path(tmp).write_bytes(data);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def imp(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def fl(v):
    if v is None or isinstance(v,bool):return None
    try:
        x=float(v);return x if math.isfinite(x) else None
    except Exception:return None
def atr1d(p):
    one=(p.get("timeframe_states") or {}).get("1d")
    if not isinstance(one,dict):return None
    hits=[]
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if "atr" in str(k).lower():
                    q=fl(v)
                    if q is not None:hits.append(q)
                if isinstance(v,dict):walk(v)
    walk(one);u=sorted(set(round(x,14) for x in hits))
    return float(u[0]) if len(u)==1 else None
def level_price(x):
    if isinstance(x,(int,float)):return fl(x)
    if not isinstance(x,dict):return None
    for k in ("price","level","value"):
        q=fl(x.get(k))
        if q is not None:return q
    return None
def nearest(levels,ref):
    vals=[q for q in (level_price(x) for x in (levels or [])) if q is not None]
    if not vals or not ref:return None
    q=min(vals,key=lambda x:abs(x-ref));return (q-ref)/ref
def hist(rows):
    out={}
    for r in rows:
        s=str(r["symbol"]).upper();out.setdefault(s,[]).append((str(r["date"])[:10],float(r["close"])))
    for s in out:
        out[s].sort()
    return out
def idx(h,d):
    ds=[x[0] for x in h];i=bisect.bisect_right(ds,d)-1;return i if i>=0 else None
def tr(h,d,n):
    i=idx(h,d)
    if i is None or i-n<0:return None
    b=h[i-n][1];return None if not b else h[i][1]/b-1
def loc52(h,d):
    i=idx(h,d)
    if i is None:return (None,None)
    w=h[max(0,i-251):i+1]
    if len(w)<2:return (None,None)
    c=h[i][1];hi=max(x[1] for x in w);lo=min(x[1] for x in w)
    return (None if not hi else c/hi-1,None if not lo else c/lo-1)
def weekly_closes(h,d):
    # Week-ending closes, matching the historical context's weekly rolling semantics.
    rows=[x for x in h if x[0]<=d];b={}
    from datetime import date
    for ds,c in rows:
        z=date.fromisoformat(ds);iso=z.isocalendar();b[(iso.year,iso.week)]=(ds,c)
    return [b[k][1] for k in sorted(b)]
def wret(c,n):
    return None if len(c)<=n or not c[-1-n] else c[-1]/c[-1-n]-1
def wvol(c,n):
    if len(c)<=n:return None
    rs=[c[i]/c[i-1]-1 for i in range(len(c)-n,len(c)) if c[i-1]]
    if len(rs)<2:return None
    import statistics
    return statistics.stdev(rs)*(52.0**0.5)
def wdd(c,n):
    if not c:return None
    w=c[-n:] if len(c)>=n else c
    p=max(w);return None if not p else c[-1]/p-1
def publication_asof(pub):
    p=dict(pub.get("payload_json") or {});lin=dict(p.get("lineage") or {})
    return str(lin.get("market_as_of_date") or lin.get("source_as_of_date") or pub["snapshot_timestamp"])[:10]

def prior_baseline_state(root, output_root, current_capture_date):
    outroot=R(root,output_root)
    manifest_path=outroot/"manifest.json"
    if not manifest_path.exists():
        return {},None
    manifest=J(manifest_path)
    prior=[x for x in (manifest.get("snapshots") or []) if str(x.get("capture_date") or x.get("snapshot_date") or "") < current_capture_date]
    if not prior:
        return {},None
    prior.sort(key=lambda x:str(x.get("capture_date") or x.get("snapshot_date") or ""))
    ent=prior[-1]
    p=R(root,ent["snapshot_file"])
    snap=J(p)
    state={}
    for r in snap.get("records") or []:
        if not r.get("baseline_available") or not isinstance(r.get("baseline_features"),dict):
            continue
        f=r["baseline_features"]
        state[r["symbol"]]={
            "direction":f.get("F003"),
            "direction_age":f.get("F090"),
            "effective_observation_session":snap.get("effective_observation_session"),
        }
    return state,snap.get("capture_date")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--f071-authority-json",default="reports/m77_20_4_prospective_f071_feature_materialization_immutable_shadow_capture_authority.json")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--development-helper-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    ap.add_argument("--development-evaluation-json",default="reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json")
    ap.add_argument("--output-root",default="research_data/m77_20_5/prospective_baseline_shadow")
    ap.add_argument("--output-json",default="reports/m77_20_5_prospective_baseline_feature_shadow_capture_paired_observation_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_20_5_paired_observation_summary.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    fp,gp,hp,dep=R(root,a.f071_authority_json),R(root,a.training_gate_json),R(root,a.development_helper_script),R(root,a.development_evaluation_json)
    for p in (fp,gp,hp,dep):
        if not p.exists():raise BaselineError(f"required authority/source missing: {p}")
    fa,gate,dev_eval=J(fp),J(gp),J(dep)
    if fa.get("status")!="READY" or fa.get("prospective_F071_materialized") is not True:raise BaselineError("M77.20.4 authority invalid")
    if fa.get("prospective_outcomes_opened") is not False:raise BaselineError("outcomes already opened")
    fpath=R(root,fa["feature_snapshot_file"]);fs=J(fpath)
    if fs.get("feature_snapshot_semantic_sha256")!=fa.get("feature_snapshot_semantic_sha256"):raise BaselineError("F071 snapshot hash mismatch")
    helper=imp("m77_frozen_structured_helper",hp)
    structured_cols=[x["column_name"] for x in gate.get("structured_columns") or []]
    if len(structured_cols)!=72:raise BaselineError(f"expected 72 frozen structured columns, got {len(structured_cols)}")
    certified_feature_cols=dev_eval.get("training_feature_columns") or []
    if len(certified_feature_cols)!=99 or len(set(certified_feature_cols))!=99:
        raise BaselineError(f"certified Development training feature registry invalid: {len(certified_feature_cols)} columns")
    if "F012" not in certified_feature_cols or "F051" not in certified_feature_cols or "F071" in certified_feature_cols:
        raise BaselineError("certified Development root/blocked feature registry changed")

    frows={x["symbol"]:x for x in fs.get("records") or []}
    symbols=sorted(frows)
    prior_state,prior_capture_date=prior_baseline_state(root,a.output_root,fa["snapshot_date"])
    with SessionLocal() as s:
        pub=s.execute(text("""SELECT scanner_run_id,status,snapshot_timestamp,payload_json
          FROM stock_scanner_publications WHERE publication_name='current_stock_intelligence'
          AND status IN ('READY','DEGRADED') ORDER BY snapshot_timestamp DESC LIMIT 1""")).mappings().first()
        if not pub:raise BaselineError("no READY/DEGRADED current_stock_intelligence publication")
        pub=dict(pub);asof=publication_asof(pub)
        candidates=[dict(x) for x in s.execute(text("""SELECT symbol,score,payload_json,snapshot_timestamp
          FROM stock_scanner_candidates WHERE scanner_run_id=:r ORDER BY symbol"""),{"r":pub["scanner_run_id"]}).mappings()]
        needed=sorted(set(symbols+["SPY"]))
        prices=list(s.execute(text("""SELECT symbol,date,close FROM price_history
          WHERE UPPER(symbol)=ANY(:symbols) AND date<=:d AND close>0 ORDER BY symbol,date"""),
          {"symbols":needed,"d":asof}).mappings())
    ph=hist(prices);spy=ph.get("SPY") or [];wc=weekly_closes(spy,asof)
    cmap={str(x["symbol"]).upper():x for x in candidates}
    dirs=[str((dict(x.get("payload_json") or {}).get("direction") or "")).upper() for x in candidates]
    n=len(dirs);bull=sum(x=="BULLISH" for x in dirs);bear=sum(x=="BEARISH" for x in dirs)
    ctx={"F060":None if not n else bull/n,"F061":None if not n else bear/n,
         "F062":wret(wc,13),"F063":wret(wc,26),"F064":wvol(wc,26),"F065":wdd(wc,52)}
    records=[];reasons=Counter();feature_cols=set()
    for sym in symbols:
        fr=frows[sym];c=cmap.get(sym)
        base={"symbol":sym,"capture_date":fa["snapshot_date"],"effective_observation_session":asof,
              "stock_scanner_run_id":pub["scanner_run_id"],"stock_publication_snapshot_timestamp":str(pub["snapshot_timestamp"])}
        if not c:
            records.append({**base,"baseline_available":False,"baseline_missing_reason":"NO_CURRENT_STOCK_INTELLIGENCE_CANDIDATE",
                            "baseline_features":None});reasons["NO_CURRENT_STOCK_INTELLIGENCE_CANDIDATE"]+=1;continue
        p=dict(c.get("payload_json") or {});h=ph.get(sym) or [];i=idx(h,asof);ref=None if i is None else h[i][1]
        atr=atr1d(p);rs13=tr(h,asof,65);sp13=tr(spy,asof,65);rs26=tr(h,asof,130);sp26=tr(spy,asof,130);dd,dl=loc52(h,asof)
        vals={"F001":fl(c.get("score")),"F002":fl(p.get("confidence")),"F003":p.get("direction"),
              "F010":fl(p.get("alignment_score")),"F011":p.get("primary_timeframe"),
              "F020":atr,"F021":None if atr is None or not ref else atr/ref,
              "F030":None if not ref else nearest(p.get("support_levels"),ref),
              "F031":None if not ref else nearest(p.get("resistance_levels"),ref),
              "F032":len(p.get("support_levels") or []),"F033":len(p.get("resistance_levels") or []),
              "F040":(p.get("breakout") or {}).get("state"),"F050":(p.get("participation") or {}).get("state"),
              # Certified Development matrix retained these governed root columns
              # as explicit missing values in addition to their structured children.
              "F012":None,"F051":None,
              **ctx,"F070":{"rs_13w":None if rs13 is None or sp13 is None else rs13-sp13,
                            "rs_26w":None if rs26 is None or sp26 is None else rs26-sp26},
              "F080":dd,"F081":dl}
        prev=prior_state.get(sym)
        cur_dir=vals.get("F003")
        if prev is None:
            vals["F090"]=None
            vals["F091"]=None
            state_mode="FIRST_PROSPECTIVE_OBSERVATION_NO_PRIOR_IMMUTABLE_STATE"
        else:
            changed=(prev.get("direction") is not None and cur_dir!=prev.get("direction"))
            prev_age=prev.get("direction_age")
            if changed:
                age=1
            elif prev_age is None:
                # Prior capture was the first prospective observation. We now have
                # two immutable prospective observations with unchanged direction.
                age=2
            else:
                age=int(prev_age)+1
            vals["F090"]=age
            vals["F091"]=bool(changed)
            state_mode="DERIVED_FROM_PRIOR_IMMUTABLE_PROSPECTIVE_BASELINE"
        flat=helper.flatten_base_features(vals);flat.update(helper.build_structured(p,gate))
        feature_cols.update(flat)
        endpoint=None if i is None else h[i][0]
        f071_end=set()
        for x in (fr.get("component_endpoint_session") or {}).values():
            if isinstance(x,dict) and x.get("symbol"):f071_end.add(str(x["symbol"]))
        session_match=(not f071_end) or (f071_end=={asof})
        f071_complete=not fr.get("F071_missing") and fr.get("F071",{}).get("rs_sector_13w") is not None and fr.get("F071",{}).get("rs_sector_26w") is not None
        paired=f071_complete and session_match and endpoint==asof
        if not paired:
            if not f071_complete:r="F071_NOT_FULLY_AVAILABLE"
            elif not session_match:r="F071_EFFECTIVE_SESSION_MISMATCH"
            else:r="BASELINE_PRICE_ENDPOINT_MISMATCH"
            reasons[r]+=1
        records.append({**base,"baseline_available":True,"baseline_price_endpoint_session":endpoint,
                        "baseline_feature_count":len(flat),"baseline_features":flat,
                        "F090_F091_state_mode":state_mode,
                        "f071_full_available":f071_complete,"f071_effective_sessions":sorted(f071_end),
                        "paired_observation_eligible":paired,"paired_ineligibility_reason":None if paired else r})
    records.sort(key=lambda x:x["symbol"])
    prospective_feature_cols=sorted(feature_cols)
    if prospective_feature_cols!=certified_feature_cols:
        missing=sorted(set(certified_feature_cols)-set(prospective_feature_cols))
        extra=sorted(set(prospective_feature_cols)-set(certified_feature_cols))
        raise BaselineError(
            f"frozen prospective baseline exact column registry mismatch: "
            f"actual={len(prospective_feature_cols)} expected={len(certified_feature_cols)} "
            f"missing={missing} extra={extra}"
        )
    paired=sum(1 for x in records if x.get("paired_observation_eligible"))
    payload={"version":VERSION,"capture_date":fa["snapshot_date"],"effective_observation_session":asof,
             "stock_scanner_run_id":pub["scanner_run_id"],"stock_publication_snapshot_timestamp":str(pub["snapshot_timestamp"]),
             "feature_columns":certified_feature_cols,"feature_column_count":len(certified_feature_cols),
             "records":records,"market_context_features":ctx,
             "governance":{"prospective_only":True,"first_capture_state_history_missing_by_design":True,
                           "historical_state_history_backfill_performed":False,"outcomes_read":False,
                           "consumed_final_holdout_opened":False,"scoring_performed":False,"production_authority_effect":False}}
    bh=sh(payload);payload["baseline_snapshot_semantic_sha256"]=bh
    outroot=R(root,a.output_root);op=outroot/fa["snapshot_date"]/"baseline_feature_shadow_snapshot.json"
    if op.exists():
        old=J(op)
        if old.get("baseline_snapshot_semantic_sha256")!=bh:raise BaselineError("IMMUTABILITY_VIOLATION_EXISTING_BASELINE_SNAPSHOT_DIFFERS")
        mode="IDEMPOTENT_EXISTING_BASELINE_SNAPSHOT_REUSED";payload=old
    else:
        atomic(op,json.dumps(payload,indent=2,sort_keys=True).encode()+b"\n");mode="NEW_IMMUTABLE_BASELINE_SHADOW_SNAPSHOT_CAPTURED"
    manifest_path=outroot/"manifest.json"
    manifest={"version":"M77.20.5-PROSPECTIVE-BASELINE-SHADOW-MANIFEST-1.0","snapshots":[]}
    if manifest_path.exists():
        manifest=J(manifest_path)
    entries={str(x.get("capture_date") or x.get("snapshot_date")):x for x in (manifest.get("snapshots") or [])}
    ent={"capture_date":fa["snapshot_date"],"snapshot_file":str(op.relative_to(root)),
         "baseline_snapshot_semantic_sha256":payload["baseline_snapshot_semantic_sha256"],
         "effective_observation_session":asof,"paired_observation_eligible_count":paired}
    if fa["snapshot_date"] in entries and entries[fa["snapshot_date"]]!=ent:
        raise BaselineError("baseline manifest immutability violation")
    entries[fa["snapshot_date"]]=ent
    manifest["snapshots"]=[entries[k] for k in sorted(entries)]
    manifest["latest_capture_date"]=max(entries)
    atomic(manifest_path,json.dumps(manifest,indent=2,sort_keys=True).encode()+b"\n")

    report={"version":VERSION,"status":"READY","execution_mode":mode,"capture_date":fa["snapshot_date"],
      "effective_observation_session":asof,"stock_scanner_run_id":pub["scanner_run_id"],
      "F071_observation_count":len(frows),"baseline_observation_count":len(records),"frozen_baseline_feature_column_count":len(certified_feature_cols),
      "paired_observation_eligible_count":paired,"paired_observation_ineligible_count":len(records)-paired,
      "paired_ineligibility_reason_counts":dict(sorted(reasons.items())),
      "prior_prospective_baseline_capture_date":prior_capture_date,
      "prospective_state_history_mode":"FIRST_CAPTURE_MISSING" if prior_capture_date is None else "DERIVED_FROM_PRIOR_IMMUTABLE_CAPTURE",
      "historical_state_history_backfill_performed":False,
      "baseline_snapshot_immutability_certified":True,"paired_same_effective_session_required":True,
      "prospective_baseline_materialized":True,"prospective_F071_already_materialized":True,
      "prospective_outcomes_opened":False,"prospective_scoring_performed":False,"production_authority_effect":False,
      "baseline_snapshot_semantic_sha256":payload["baseline_snapshot_semantic_sha256"],
      "baseline_snapshot_file":str(op.relative_to(root)),"baseline_manifest_file":str(manifest_path.relative_to(root)),
      "next_step":"BUILD_M77_20_6_PROSPECTIVE_DAILY_CAPTURE_ORCHESTRATION_AND_PRE_OUTCOME_ACCUMULATION_AUTHORITY"}
    oj,oc=R(root,a.output_json),R(root,a.output_csv);oj.parent.mkdir(parents=True,exist_ok=True)
    atomic(oj,json.dumps(report,indent=2,sort_keys=True).encode()+b"\n")
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=["capture_date","effective_observation_session","F071_observation_count","baseline_observation_count",
                "frozen_baseline_feature_column_count","paired_observation_eligible_count","paired_observation_ineligible_count","execution_mode"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow({k:report[k] for k in fields})
    print("=== M77.20.5 PROSPECTIVE BASELINE FEATURE SHADOW CAPTURE & PAIRED OBSERVATION AUTHORITY ===")
    print("status: READY");print("execution_mode:",mode);print("capture_date:",fa["snapshot_date"])
    print("effective_observation_session:",asof);print("stock_scanner_run_id:",pub["scanner_run_id"])
    print("F071_observation_count:",len(frows));print("baseline_observation_count:",len(records))
    print("frozen_baseline_feature_column_count:",len(certified_feature_cols));print("paired_observation_eligible_count:",paired)
    print("paired_observation_ineligible_count:",len(records)-paired);print("paired_ineligibility_reason_counts:",dict(sorted(reasons.items())))
    print("prior_prospective_baseline_capture_date:",prior_capture_date)
    print("prospective_state_history_mode:","FIRST_CAPTURE_MISSING" if prior_capture_date is None else "DERIVED_FROM_PRIOR_IMMUTABLE_CAPTURE")
    print("historical_state_history_backfill_performed: False")
    print("baseline_snapshot_immutability_certified: True");print("paired_same_effective_session_required: True")
    print("prospective_outcomes_opened: False");print("prospective_scoring_performed: False");print("production_authority_effect: False")
    print("next_step:",report["next_step"]);print("report:",oj);print("csv:",oc);print("baseline_snapshot:",op)
if __name__=="__main__":main()
