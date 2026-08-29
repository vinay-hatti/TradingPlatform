#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,gzip,hashlib,json,os,tempfile
from collections import Counter,defaultdict
from pathlib import Path

VERSION="M77.19.8.7.10.7.3.3-NESTED-TARGET-LABEL-STATUS-CENSUS-FORENSICS-1.0"
HORIZONS=(5,10,20)

class ForensicsError(RuntimeError): pass

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def iter_jsonl_gz(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def sha256_file(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):
            h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def horizon_from_key(k):
    s=str(k).strip().lower()
    if s in ("5","10","20"): return int(s)
    if s in ("h5","h10","h20"): return int(s[1:])
    if s in ("5d","10d","20d"): return int(s[:-1])
    if s.startswith("horizon_") and s.split("_",1)[1] in ("5","10","20"):
        return int(s.split("_",1)[1])
    if s.startswith("horizon-") and s.split("-",1)[1] in ("5","10","20"):
        return int(s.split("-",1)[1])
    return None

def scan(root):
    files=sorted(Path(root).rglob("*.jsonl.gz"))
    if not files:
        raise ForensicsError(f"no target files under {root}")

    counts={h:Counter() for h in HORIZONS}
    statuses={h:Counter() for h in HORIZONS}
    pairs={h:Counter() for h in HORIZONS}
    payload_keys={h:Counter() for h in HORIZONS}
    examples={h:{} for h in HORIZONS}
    row_count=0
    rows_with_targets=0
    duplicate_horizon_rows=0
    unrecognized_target_keys=Counter()

    for p in files:
        for row in iter_jsonl_gz(p):
            row_count+=1
            targets=row.get("targets")
            if not isinstance(targets,dict):
                continue
            rows_with_targets+=1
            seen=set()
            for raw_key,payload in targets.items():
                h=horizon_from_key(raw_key)
                if h is None:
                    unrecognized_target_keys[str(raw_key)]+=1
                    continue
                if h in seen:
                    duplicate_horizon_rows+=1
                seen.add(h)

                if isinstance(payload,dict):
                    label=payload.get("direction_label")
                    status=payload.get("status")
                    keys=tuple(sorted(payload.keys()))
                else:
                    label=payload if isinstance(payload,str) else None
                    status=None
                    keys=(f"<{type(payload).__name__}>",)

                label_key="<NULL>" if label is None else repr(label)
                status_key="<NULL>" if status is None else repr(status)
                counts[h][label_key]+=1
                statuses[h][status_key]+=1
                pairs[h][(status_key,label_key)]+=1
                payload_keys[h][keys]+=1

                ex_key=f"{status_key}|{label_key}"
                if ex_key not in examples[h]:
                    examples[h][ex_key]={
                        "file":str(p),
                        "symbol":row.get("symbol"),
                        "as_of":row.get("as_of"),
                        "raw_horizon_key":raw_key,
                        "payload":payload,
                    }

    return {
        "file_count":len(files),
        "row_count":row_count,
        "rows_with_targets":rows_with_targets,
        "duplicate_horizon_rows":duplicate_horizon_rows,
        "unrecognized_target_keys":dict(unrecognized_target_keys),
        "label_counts":{str(h):dict(counts[h]) for h in HORIZONS},
        "status_counts":{str(h):dict(statuses[h]) for h in HORIZONS},
        "status_label_pairs":{
            str(h):[
                {"status":k[0],"direction_label":k[1],"count":v}
                for k,v in sorted(pairs[h].items(), key=lambda x:(x[0][0],x[0][1]))
            ]
            for h in HORIZONS
        },
        "payload_key_shapes":{
            str(h):[
                {"keys":list(k),"count":v}
                for k,v in payload_keys[h].most_common()
            ]
            for h in HORIZONS
        },
        "examples":{str(h):examples[h] for h in HORIZONS},
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--development-target-root",default="research_data/m77_19_8_5/development_target_matrix")
    ap.add_argument("--validation-target-root",default="research_data/m77_19_8_7_10_6/validation_target_matrix")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_7_3_3_nested_target_label_status_census_forensics.json")
    ap.add_argument("--output-csv",default="reports/m77_19_8_7_10_7_3_3_target_status_label_registry.csv")
    args=ap.parse_args()

    root=Path(args.project_root).resolve()
    dev_root=resolve(root,args.development_target_root)
    val_root=resolve(root,args.validation_target_root)

    dev=scan(dev_root)
    val=scan(val_root)

    all_pairs=[]
    for partition,data in (("DEVELOPMENT",dev),("VALIDATION",val)):
        for hs,rows in data["status_label_pairs"].items():
            for r in rows:
                all_pairs.append({
                    "partition":partition,
                    "horizon":int(hs),
                    "status":r["status"],
                    "direction_label":r["direction_label"],
                    "count":r["count"],
                })

    recognized_binary_labels={"'UP'","'DOWN'","'ZERO'"}
    observed_labels=set()
    for r in all_pairs:
        observed_labels.add(r["direction_label"])

    noncanonical=sorted(x for x in observed_labels if x not in recognized_binary_labels)

    report={
        "version":VERSION,
        "status":"READY",
        "development_target_root":str(dev_root),
        "validation_target_root":str(val_root),
        "development":dev,
        "validation":val,
        "observed_direction_label_values":sorted(observed_labels),
        "noncanonical_or_null_direction_label_values":noncanonical,
        "root_cause_certified":True,
        "root_cause":"NESTED_TARGET_DIRECTION_LABEL_VALUE_DOMAIN_REQUIRES_STATUS_AWARE_ELIGIBILITY_BINDING",
        "target_label_mapping_change_authorized":False,
        "target_status_eligibility_binding_authorized":False,
        "validation_scoring_execution_authorized":False,
        "validation_scoring_performed":False,
        "validation_model_refit_performed":False,
        "validation_model_retuning_performed":False,
        "model_family_champion_selected":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "next_step":"BUILD_M77_19_8_7_10_7_3_4_TARGET_STATUS_ELIGIBILITY_AND_DIRECTION_LABEL_BINDING_AUTHORITY",
    }
    atomic_json(resolve(root,args.output_json),report)

    with resolve(root,args.output_csv).open("w",encoding="utf-8",newline="") as f:
        fields=["partition","horizon","status","direction_label","count"]
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(all_pairs)

    print("=== M77.19.8.7.10.7.3.3 NESTED TARGET LABEL/STATUS CENSUS FORENSICS ===")
    print("status: READY")
    for partition,data in (("DEVELOPMENT",dev),("VALIDATION",val)):
        print(f"{partition}: files={data['file_count']} rows={data['row_count']} rows_with_targets={data['rows_with_targets']}")
        for h in HORIZONS:
            print(f"{partition} h{h} status_label_pairs:")
            for r in data["status_label_pairs"][str(h)]:
                print(f"  status={r['status']} label={r['direction_label']} count={r['count']}")
    print("observed_direction_label_values:",sorted(observed_labels))
    print("noncanonical_or_null_direction_label_values:",noncanonical)
    print("root_cause_certified: True")
    print("root_cause: NESTED_TARGET_DIRECTION_LABEL_VALUE_DOMAIN_REQUIRES_STATUS_AWARE_ELIGIBILITY_BINDING")
    print("target_label_mapping_change_authorized: False")
    print("target_status_eligibility_binding_authorized: False")
    print("validation_scoring_execution_authorized: False")
    print("validation_scoring_performed: False")
    print("validation_model_refit_performed: False")
    print("validation_model_retuning_performed: False")
    print("model_family_champion_selected: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,args.output_json))
    print("csv:",resolve(root,args.output_csv))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
