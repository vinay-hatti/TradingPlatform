#!/usr/bin/env python3
from __future__ import annotations

import argparse,json,re
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_18_historical_depth_audit.json"
OUT=ROOT/"reports/m77/m77_18_historical_depth_replication_authority_audit.json"

TEXT_SUFFIXES={".py",".sh",".json",".md",".txt",".yaml",".yml",".toml"}

def write_json_atomic(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(payload,indent=2,default=str)+"\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def safe_read(path):
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""

def milestone_from(path,txt):
    s=str(path)
    pats=[
      r"(?i)m77[._-](\d+)(?:[._-](\d+))?(?:[._-](\d+))?",
      r"(?i)M77\.(\d+)(?:\.(\d+))?(?:\.(\d+))?"
    ]
    for p in pats:
        m=re.search(p,s)
        if not m: m=re.search(p,txt[:5000])
        if m:
            bits=[x for x in m.groups() if x is not None]
            return "M77."+ ".".join(bits)
    return "M77.UNKNOWN"

def date_range_from_json(path):
    if path.suffix.lower()!=".json": return None
    try: x=json.loads(path.read_text())
    except Exception: return None
    candidates=[]
    def walk(v):
        if isinstance(v,dict):
            for k,val in v.items():
                lk=str(k).lower()
                if lk in ("first_date","start_date","common_start","from","period_start") and isinstance(val,str):
                    candidates.append(("start",val))
                if lk in ("last_date","end_date","common_end","through","period_end") and isinstance(val,str):
                    candidates.append(("end",val))
                walk(val)
        elif isinstance(v,list):
            for z in v: walk(z)
    walk(x)
    starts=[v for k,v in candidates if k=="start" and re.match(r"\d{4}-\d{2}-\d{2}",v)]
    ends=[v for k,v in candidates if k=="end" and re.match(r"\d{4}-\d{2}-\d{2}",v)]
    if starts or ends:
        return {"first_date":min(starts) if starts else None,"last_date":max(ends) if ends else None}
    return None

def classify(ms,txt,cfg,path):
    low=txt.lower()
    closed=cfg["known_closed_branches"]
    for prefix,disp in closed.items():
        if ms==prefix or ms.startswith(prefix+"."):
            return "CLOSED_SUPERSEDED",["KNOWN_CLOSED_BRANCH:"+disp]

    long_hits=[m for m in cfg["known_long_history_markers"] if m.lower() in low]
    empirical_hits=[m for m in cfg["empirical_markers"] if m.lower() in low]
    prospective_hits=[m for m in cfg["prospective_markers"] if m.lower() in low]
    structural_hits=[m for m in cfg["structural_markers"] if m.lower() in low]

    dr=date_range_from_json(path)
    if long_hits and empirical_hits:
        return "LONG_HISTORY_ALREADY_CERTIFIED",["LONG_HISTORY_MARKERS",*long_hits[:4],*empirical_hits[:4]]
    if prospective_hits and not empirical_hits:
        return "PROSPECTIVE_ONLY",["PROSPECTIVE_MARKERS",*prospective_hits[:4]]
    if empirical_hits:
        # If report proves a short modern sample, explicitly flag.
        if dr and dr.get("first_date") and dr["first_date"]>"2005-01-01":
            return "SHORT_HISTORY_EMPIRICAL_REPLICATION_REQUIRED",["EMPIRICAL_MARKERS","SHORT_DATE_RANGE",*empirical_hits[:5]]
        if "descriptive_only" in low:
            return "DESCRIPTIVE_ONLY",["DESCRIPTIVE_ONLY_MARKER",*empirical_hits[:4]]
        if not long_hits:
            return "SHORT_HISTORY_EMPIRICAL_REPLICATION_REQUIRED",["EMPIRICAL_WITHOUT_LONG_HISTORY_MARKER",*empirical_hits[:5]]
    if structural_hits:
        return "STRUCTURAL_ENGINEERING",["STRUCTURAL_MARKERS",*structural_hits[:5]]
    return "UNKNOWN_REVIEW_REQUIRED",[]

def summarize_milestone(entries):
    classes=defaultdict(int)
    files=[]
    ranges=[]
    for e in entries:
        classes[e["classification"]]+=1
        files.append(e["path"])
        if e.get("date_range"): ranges.append(e["date_range"])
    # Priority classification at milestone level.
    priority=[
      "SHORT_HISTORY_EMPIRICAL_REPLICATION_REQUIRED",
      "DESCRIPTIVE_ONLY",
      "PROSPECTIVE_ONLY",
      "LONG_HISTORY_ALREADY_CERTIFIED",
      "STRUCTURAL_ENGINEERING",
      "CLOSED_SUPERSEDED",
      "UNKNOWN_REVIEW_REQUIRED"
    ]
    overall=next((c for c in priority if classes.get(c)), "UNKNOWN_REVIEW_REQUIRED")
    return {
      "classification":overall,
      "file_count":len(entries),
      "class_counts":dict(classes),
      "sample_files":files[:12],
      "date_ranges":ranges[:12]
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","run"))
    a=ap.parse_args()
    cfg=json.loads(CFG.read_text())

    cert=ROOT/cfg["long_history_authority"]["certification"]
    cert_ok=False
    cert_summary=None
    if cert.exists():
        try:
            cx=json.loads(cert.read_text())
            cert_ok=bool(cx.get("certified_for_m77_15_7_long_history_replication")) and cx.get("common_authority",{}).get("session_count",0)>=cfg["long_history_authority"]["expected_common_sessions"]
            cert_summary={
              "certified":cert_ok,
              "common_start":cx.get("common_authority",{}).get("first_date"),
              "common_end":cx.get("common_authority",{}).get("last_date"),
              "common_sessions":cx.get("common_authority",{}).get("session_count")
            }
        except Exception:
            cert_summary={"certified":False}

    if a.mode=="preflight":
        print(json.dumps({
          "version":cfg["version"],"status":"READY","mode":"READ_ONLY_AUDIT",
          "long_history_authority":cert_summary,
          "scan_roots":cfg["scope"]["roots"],
          "classification_policy":cfg["classification_policy"],
          "production_authority_effect":False
        },indent=2))
        return

    regex=re.compile(cfg["scope"]["m77_name_regex"])
    entries=[]
    seen=set()
    for rel in cfg["scope"]["roots"]:
        base=ROOT/rel
        if not base.exists(): continue
        for p in base.rglob("*"):
            if not p.is_file(): continue
            if p.suffix.lower() not in TEXT_SUFFIXES: continue
            rp=str(p.relative_to(ROOT))
            if rp in seen: continue
            txt=safe_read(p)
            if not regex.search(rp) and not regex.search(txt[:10000]):
                continue
            seen.add(rp)
            ms=milestone_from(rp,txt)
            cl,reasons=classify(ms,txt,cfg,p)
            entries.append({
              "path":rp,
              "milestone":ms,
              "classification":cl,
              "reasons":reasons,
              "date_range":date_range_from_json(p)
            })

    by_ms=defaultdict(list)
    for e in entries: by_ms[e["milestone"]].append(e)
    milestone_summary={ms:summarize_milestone(v) for ms,v in sorted(by_ms.items())}

    backlog=[]
    for ms,s in milestone_summary.items():
        if s["classification"] in ("SHORT_HISTORY_EMPIRICAL_REPLICATION_REQUIRED","DESCRIPTIVE_ONLY"):
            backlog.append({
              "milestone":ms,
              "classification":s["classification"],
              "priority":"HIGH" if s["classification"]=="SHORT_HISTORY_EMPIRICAL_REPLICATION_REQUIRED" else "MEDIUM",
              "recommended_action":"RECOVER_FROZEN_HYPOTHESIS_AND_REPLICATE_ON_5773_SESSION_AUTHORITY",
              "sample_files":s["sample_files"][:6]
            })

    # Explicitly surface cycle/seasonality evidence if found anywhere.
    cycle_hits=[e for e in entries if any(k in safe_read(ROOT/e["path"]).lower() for k in ("seasonality","cyclical","cycle"))]
    cycle_milestones=sorted(set(e["milestone"] for e in cycle_hits))

    out={
      "version":cfg["version"],"status":"READY","mode":"READ_ONLY_AUDIT",
      "long_history_authority":cert_summary,
      "files_examined":len(entries),
      "milestones_found":len(milestone_summary),
      "milestone_summary":milestone_summary,
      "replication_backlog":backlog,
      "cycle_seasonality_findings":{
        "milestones":cycle_milestones,
        "file_count":len(cycle_hits),
        "sample_files":[e["path"] for e in cycle_hits[:20]]
      },
      "closed_branches":cfg["known_closed_branches"],
      "governance":{
        "database_writes":False,
        "production_authority_effect":False,
        "source_files_mutated":False,
        "reports_mutated":False,
        "historical_artifacts_deleted":False
      },
      "next_step":"REVIEW_REPLICATION_BACKLOG_THEN_BUILD_FROZEN_LONG_HISTORY_REPLICATIONS_ONLY",
      "production_authority_effect":False
    }
    write_json_atomic(OUT,out)
    print(json.dumps({
      "version":out["version"],"status":"READY",
      "files_examined":out["files_examined"],
      "milestones_found":out["milestones_found"],
      "replication_backlog_count":len(backlog),
      "cycle_seasonality_milestones":cycle_milestones,
      "long_history_authority":cert_summary,
      "next_step":out["next_step"],
      "production_authority_effect":False
    },indent=2))

if __name__=="__main__":
    main()
