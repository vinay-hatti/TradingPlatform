#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,os,tempfile
from collections import Counter
from pathlib import Path
VERSION="M77.19.8.7.10.7.3.4-TARGET-STATUS-ELIGIBILITY-DIRECTION-LABEL-BINDING-AUTHORITY-1.1"
HORIZONS=(5,10,20);ELIGIBLE_STATUS="MATURED";ELIGIBLE_LABELS=("UP","DOWN","ZERO")
KNOWN_INELIGIBLE_STATUSES=("SOURCE_SESSION_MISSING","NOT_MATURED","PURGED_PARTITION_OVERLAP","SYMBOL_TARGET_SESSION_MISSING")
class AuthorityError(RuntimeError):pass
def resolve(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():yield json.loads(line)
def norm(v):
    if v=="<NULL>":return None
    if isinstance(v,str) and len(v)>=2 and v[0]=="'" and v[-1]=="'":return v[1:-1]
    return v
def dev_expected(a85,h):
    x=((a85.get("target_matrix") or {}).get("horizon_summary") or {}).get(str(h))
    if not isinstance(x,dict):raise AuthorityError(f"8.5 missing h{h}")
    return {"MATURED":int(x.get("matured",0)),"SOURCE_SESSION_MISSING":int(x.get("source_session_missing",0)),"NOT_MATURED":int(x.get("not_matured",0)),"PURGED_PARTITION_OVERLAP":int(x.get("purged_partition_overlap",0)),"SYMBOL_TARGET_SESSION_MISSING":int(x.get("symbol_target_session_missing",0)),"labels":{k:int(v) for k,v in (x.get("direction_labels") or {}).items()}}
def val_expected(a106,h):
    rows=a106.get("target_horizon_summary")
    if not isinstance(rows,list):raise AuthorityError("10.6 target_horizon_summary must be list")
    found=[x for x in rows if int(x.get("horizon",-1))==h]
    if len(found)!=1:raise AuthorityError(f"10.6 h{h} summary count={len(found)}")
    x=found[0];return {"matured":int(x["matured"]),"labels":{k:int(x[k]) for k in ("UP","DOWN","ZERO")}}
def scan_val(root,h):
    hp=Path(root)/f"h{h}";files=sorted(hp.glob("*.jsonl.gz"))
    if not files:raise AuthorityError(f"Validation target directory empty: {hp}")
    labels=Counter();rows=0
    for p in files:
        for r in iter_jsonl_gz(p):
            rows+=1
            if int(r.get("horizon_sessions",-1))!=h or r.get("partition")!="VALIDATION":raise AuthorityError(f"{p}: target contract mismatch")
            lab=r.get("T_DIRECTION")
            if lab not in ELIGIBLE_LABELS:raise AuthorityError(f"{p}: bad T_DIRECTION {lab!r}")
            labels[lab]+=1
    return {"file_count":len(files),"row_count":rows,"labels":dict(labels)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--census-json",default="reports/m77_19_8_7_10_7_3_3_nested_target_label_status_census_forensics.json")
    ap.add_argument("--development-target-authority-json",default="reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    ap.add_argument("--validation-target-authority-json",default="reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
    ap.add_argument("--validation-target-root",default="research_data/m77_19_8_7_10_6/validation_target_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_3_4_target_status_eligibility_direction_label_binding_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_3_4_target_eligibility_binding_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve();census=load_json(resolve(root,a.census_json));a85=load_json(resolve(root,a.development_target_authority_json));a106=load_json(resolve(root,a.validation_target_authority_json))
    if census.get("status")!="READY" or a85.get("status")!="READY" or a106.get("status")!="READY" or a106.get("validation_targets_materialized") is not True:raise AuthorityError("upstream authority invalid")
    pairs=census["development"]["status_label_pairs"];dev={};val={};rows=[]
    for h in HORIZONS:
        ex=dev_expected(a85,h);sc=Counter();lc=Counter()
        for r in pairs[str(h)]:
            s=norm(r["status"]);lab=norm(r["direction_label"]);n=int(r["count"])
            if s=="MATURED":
                if lab not in ELIGIBLE_LABELS:raise AuthorityError(f"h{h}: bad matured label")
                sc[s]+=n;lc[lab]+=n
            elif s in KNOWN_INELIGIBLE_STATUSES:
                if lab is not None:raise AuthorityError(f"h{h}: ineligible row labeled")
                sc[s]+=n
            else:raise AuthorityError(f"h{h}: unknown status {s!r}")
        if sc["MATURED"]!=ex["MATURED"] or dict(lc)!=ex["labels"]:raise AuthorityError(f"h{h}: Development census disagrees with 8.5")
        for s in KNOWN_INELIGIBLE_STATUSES:
            if sc[s]!=ex[s]:raise AuthorityError(f"h{h}: Development {s} disagrees with 8.5")
        dev[str(h)]={"status_counts":dict(sc),"label_counts":dict(lc),"matured":ex["MATURED"]}
        ve=val_expected(a106,h);vs=scan_val(resolve(root,a.validation_target_root),h)
        if vs["row_count"]!=ve["matured"] or vs["labels"]!=ve["labels"]:raise AuthorityError(f"h{h}: Validation files disagree with 10.6")
        val[str(h)]={"representation":"HORIZON_SUBDIRECTORY_FLAT_MATURED_ONLY","file_count":vs["file_count"],"matured":vs["row_count"],"label_counts":vs["labels"]}
        for lab,n in lc.items():rows.append({"partition":"DEVELOPMENT","horizon":h,"status":"MATURED","direction_label":lab,"eligibility":"TARGET_MATERIALIZED","count":n})
        for lab,n in vs["labels"].items():rows.append({"partition":"VALIDATION","horizon":h,"status":"MATURED_BY_10_6_AUTHORITY","direction_label":lab,"eligibility":"TARGET_MATERIALIZED","count":n})
    report={"version":VERSION,"status":"READY","development_target_status_label_binding":dev,"validation_target_representation_binding":val,"development_score_eligible_rule":"status == MATURED AND direction_label IN {UP,DOWN}","validation_score_eligible_rule":"ROW_PRESENT_IN_10_6_HORIZON_SUBDIRECTORY_AND_T_DIRECTION_IN_{UP,DOWN}","zero_label_policy":"EXCLUDE_FROM_BINARY_DIRECTION_SCORING_WITHOUT_REMAPPING","target_status_eligibility_binding_certified":True,"validation_flat_matured_only_representation_certified":True,"validation_scoring_execution_authorized":True,"validation_scoring_performed":False,"validation_preprocessor_refit_performed":False,"validation_model_refit_performed":False,"validation_model_retuning_performed":False,"model_family_champion_selected":False,"final_holdout_opened":False,"production_authority_effect":False,"next_step":"RUN_M77_19_8_7_10_7_3_5_REPO_GROUNDED_FROZEN_VALIDATION_SCORING"}
    atomic_json(resolve(root,a.output_json),report)
    with resolve(root,a.output_csv).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["partition","horizon","status","direction_label","eligibility","count"]);w.writeheader();w.writerows(rows)
    print("=== M77.19.8.7.10.7.3.4 TARGET STATUS ELIGIBILITY & DIRECTION LABEL BINDING AUTHORITY ===");print("status: READY")
    for h in HORIZONS:print(f"Development h{h}: matured={dev[str(h)]['matured']} labels={dev[str(h)]['label_counts']}");print(f"Validation h{h}: matured={val[str(h)]['matured']} labels={val[str(h)]['label_counts']} files={val[str(h)]['file_count']}")
    print("target_status_eligibility_binding_certified: True");print("validation_scoring_execution_authorized: True");print("validation_scoring_performed: False");print("final_holdout_opened: False");print("production_authority_effect: False");print("next_step:",report["next_step"]);print("report:",resolve(root,a.output_json));print("csv:",resolve(root,a.output_csv));return 0
if __name__=="__main__":raise SystemExit(main())
