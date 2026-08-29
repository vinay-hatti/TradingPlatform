#!/usr/bin/env python3
from __future__ import annotations

import ast,csv,json,re
from pathlib import Path
from collections import defaultdict

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_18_1_semantic_replication_backlog.json"
OUT=ROOT/"reports/m77/m77_18_1_semantic_replication_backlog_refinement.json"

def write_json_atomic(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(x,indent=2,default=str)+"\n")
    json.loads(t.read_text()); t.replace(p)

def safe_text(p):
    try:return p.read_text(errors="ignore")
    except Exception:return ""

def extract_json_semantics(p):
    try:x=json.loads(p.read_text())
    except Exception:return {}
    out={}
    keys=("version","status","first_date","last_date","start_date","end_date","sample_size","row_count",
          "targets","horizons","outcomes","hypothesis","prediction","disposition","next_step",
          "production_authority_effect")
    def walk(v,path=""):
        if isinstance(v,dict):
            for k,val in v.items():
                kp=f"{path}.{k}" if path else k
                if k in keys and not isinstance(val,(dict,list)):
                    out[kp]=val
                elif k in ("targets","horizons","outcomes","hypotheses","predictions","acceptance","gates","controls"):
                    out[kp]=val
                walk(val,kp)
        elif isinstance(v,list):
            for i,z in enumerate(v[:50]): walk(z,f"{path}[{i}]")
    walk(x)
    return out

def extract_python_constants(p):
    txt=safe_text(p)
    out={}
    try: tree=ast.parse(txt)
    except Exception:return out
    for node in tree.body:
        if isinstance(node,(ast.Assign,ast.AnnAssign)):
            targets=node.targets if isinstance(node,ast.Assign) else [node.target]
            value=node.value
            for t in targets:
                if isinstance(t,ast.Name):
                    name=t.id
                    if any(k in name.lower() for k in ("horizon","outcome","hypothesis","threshold","window","label","feature","target","start","end","minimum","maximum","confirm")):
                        try: out[name]=ast.literal_eval(value)
                        except Exception: pass
    return out

def marker_counts(txt,groups):
    low=txt.lower()
    return {g:{m:low.count(m.lower()) for m in ms if m.lower() in low} for g,ms in groups.items()}

def empirical_or_runtime(txt):
    low=txt.lower()
    empirical=sum(low.count(k) for k in ("empirical_p","permutation","bootstrap","bh_q","incremental","forward_return","realized_volatility","backtest","calibration"))
    runtime=sum(low.count(k) for k in ("repository","service","api","persist","sessionlocal","endpoint","request","response"))
    return "EMPIRICAL" if empirical>runtime and empirical>0 else ("RUNTIME_OR_STRUCTURAL" if runtime>0 else "AMBIGUOUS")

def analyze_family(fid,meta,cfg):
    files=[]
    missing=[]
    for rel in meta["expected_files"]:
        p=ROOT/rel
        if not p.exists():
            missing.append(rel); continue
        txt=safe_text(p)
        files.append({
          "path":rel,
          "kind":p.suffix.lower(),
          "semantic_type":empirical_or_runtime(txt),
          "marker_counts":marker_counts(txt,cfg["semantic_markers"]),
          "python_constants":extract_python_constants(p) if p.suffix==".py" else {},
          "json_semantics":extract_json_semantics(p) if p.suffix==".json" else {}
        })
    empirical_files=[f for f in files if f["semantic_type"]=="EMPIRICAL"]
    runtime_files=[f for f in files if f["semantic_type"]=="RUNTIME_OR_STRUCTURAL"]

    frozen_recoverable=bool(empirical_files)
    action="REVIEW_MANUALLY"
    if fid in ("M77.3","M77.11","M77.12"):
        action="BUILD_23_YEAR_FROZEN_REPLICATION" if frozen_recoverable else "BLOCK_MISSING_EMPIRICAL_DEFINITION"
    elif fid=="M77.0_OUTCOME_PROBABILITY":
        action="REPLICATE_ONLY_EMPIRICAL_CALIBRATION_COMPONENTS" if empirical_files else "NO_HISTORICAL_REPLICATION_RUNTIME_ONLY"
    elif fid in ("M77.6","M77.13"):
        action="TRACE_TO_UPSTREAM_FROZEN_HYPOTHESIS" if files else "BLOCK_MISSING_FILES"

    return {
      "family_id":fid,
      "name":meta["name"],
      "priority":meta["priority"],
      "condition":meta.get("condition"),
      "files_found":len(files),
      "files_missing":missing,
      "empirical_file_count":len(empirical_files),
      "runtime_or_structural_file_count":len(runtime_files),
      "frozen_hypothesis_recoverable":frozen_recoverable,
      "recommended_action":action,
      "files":files
    }

def main():
    cfg=json.loads(CFG.read_text())
    src=ROOT/cfg["source_audit"]
    if not src.exists(): raise SystemExit("M77.18.1 blocked: M77.18 audit artifact missing")
    audit=json.loads(src.read_text())

    families=[analyze_family(fid,meta,cfg) for fid,meta in cfg["candidate_families"].items()]

    # Explicit correction of heuristic false positives from M77.18.
    excluded=[]
    for row in audit.get("replication_backlog",[]):
        ms=row.get("milestone","")
        if any(ms==x or ms.startswith(x+".") for x in cfg["hard_exclusions"]["closed_astrology"]):
            excluded.append({"milestone":ms,"reason":"CLOSED_RESEARCH_ALREADY_LONG_HISTORY_RESOLVED"})
        elif any(ms==x or ms.startswith(x+".") for x in cfg["hard_exclusions"]["pure_structural_prefixes"]):
            excluded.append({"milestone":ms,"reason":"STRUCTURAL_OR_RECOVERY_TOOLING_NOT_STANDALONE_EMPIRICAL_HYPOTHESIS"})

    p0=[f for f in families if f["priority"]=="P0" and f["recommended_action"]=="BUILD_23_YEAR_FROZEN_REPLICATION"]
    p1=[f for f in families if f["priority"].startswith("P1")]

    out={
      "version":cfg["version"],"status":"READY","mode":"READ_ONLY_SEMANTIC_REFINEMENT",
      "source_audit_summary":{
        "files_examined":audit.get("files_examined"),
        "milestones_found":audit.get("milestones_found"),
        "heuristic_backlog_count":len(audit.get("replication_backlog",[]))
      },
      "long_history_authority":cfg["long_history_authority"],
      "false_positive_exclusions":excluded,
      "families":families,
      "p0_frozen_replication_families":[f["family_id"] for f in p0],
      "p1_review_families":[f["family_id"] for f in p1],
      "recommended_execution_order":[
        "M77.3",
        "M77.11",
        "M77.12",
        "M77.0_OUTCOME_PROBABILITY",
        "M77.6",
        "M77.13"
      ],
      "next_step":"BUILD_CUMULATIVE_M77_19_LONG_HISTORY_REPLICATION_FOR_P0_FAMILIES_THEN_CONDITIONAL_P1",
      "governance":cfg["governance"],
      "production_authority_effect":False
    }
    write_json_atomic(OUT,out)
    print(json.dumps({
      "version":out["version"],"status":"READY",
      "p0_frozen_replication_families":out["p0_frozen_replication_families"],
      "p1_review_families":out["p1_review_families"],
      "false_positive_exclusion_count":len(out["false_positive_exclusions"]),
      "next_step":out["next_step"],
      "production_authority_effect":False
    },indent=2))

if __name__=="__main__": main()
