#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,shutil
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CFG=ROOT/"config/m77/m77_17_2_astrology_research_closure.json"
OUT=ROOT/"reports/m77/m77_17_2_astrology_research_closure.json"
CONFIRM="CLOSE_M77_ASTROLOGY_RESEARCH_AND_RETIRE_SHADOW"

def write_json_atomic(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    t=p.with_suffix(p.suffix+".tmp")
    t.write_text(json.dumps(x,indent=2,default=str)+"\n")
    json.loads(t.read_text()); t.replace(p)

def discover(cfg):
    hits=[]
    roots=[ROOT/"scripts",ROOT/"config",ROOT/"ops",ROOT/"launchd"]
    markers=tuple(cfg["known_shadow_markers"])
    for base in roots:
        if not base.exists(): continue
        for p in base.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in (".py",".sh",".json",".plist",".yaml",".yml",".toml"): continue
            try: txt=p.read_text(errors="ignore")
            except Exception: continue
            if any(m in txt for m in markers):
                hits.append({"path":str(p.relative_to(ROOT)),"markers":[m for m in markers if m in txt]})
    return hits

def safe_retire_file(path,markers,backup_root):
    txt=path.read_text()
    original=txt
    # Only retire executable invocation lines that explicitly name the M77.14 lunar shadow.
    lines=[]
    changed=False
    for line in txt.splitlines(True):
        if any(m in line for m in markers) and not line.lstrip().startswith("#"):
            # Never rewrite Python source semantics automatically.
            if path.suffix==".sh":
                lines.append("# M77.17.2 RETIRED_ASTROLOGY_SHADOW: "+line)
                changed=True
            else:
                lines.append(line)
        else:
            lines.append(line)
    if changed:
        rel=path.relative_to(ROOT)
        bp=backup_root/rel
        bp.parent.mkdir(parents=True,exist_ok=True)
        bp.write_text(original)
        tmp=path.with_suffix(path.suffix+".m77172tmp")
        tmp.write_text("".join(lines)); tmp.replace(path)
    return changed

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("preflight","close"))
    ap.add_argument("--confirm")
    a=ap.parse_args()
    cfg=json.loads(CFG.read_text())

    evidence=ROOT/cfg["closure"]["M77_14"]["evidence"]
    if not evidence.exists(): raise SystemExit("M77.17.2 blocked: M77.17 long-history evidence missing")
    ev=json.loads(evidence.read_text())
    if ev.get("primary_replication_pass") is not False:
        raise SystemExit("M77.17.2 blocked: expected failed primary lunar replication")
    if ev.get("disposition")!="TERMINATE_M77_14_PROSPECTIVE_SHADOW_AND_CLOSE_LUNAR_RESEARCH":
        raise SystemExit("M77.17.2 blocked: M77.17 disposition does not authorize closure")

    hits=discover(cfg)
    if a.mode=="preflight":
        print(json.dumps({
          "version":cfg["version"],"status":"READY","confirmation_required":CONFIRM,
          "m77_17_primary_replication_pass":ev["primary_replication_pass"],
          "m77_17_disposition":ev["disposition"],
          "discovered_shadow_references":hits,
          "retirement_policy":cfg["retirement"],
          "production_authority_effect":False
        },indent=2)); return

    if a.confirm!=CONFIRM: raise SystemExit(f"confirmation required: {CONFIRM}")

    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root=ROOT/"backups"/f"m77_17_2_astrology_shadow_retirement_{stamp}"
    changed=[]
    reviewed=[]
    for h in hits:
        p=ROOT/h["path"]
        reviewed.append(h["path"])
        if safe_retire_file(p,cfg["known_shadow_markers"],backup_root):
            changed.append(h["path"])

    # Create a durable retirement sentinel consumed by future orchestration.
    sentinel=ROOT/"config/m77/M77_ASTROLOGY_RESEARCH_RETIRED.json"
    sentinel_payload={
      "version":cfg["version"],
      "status":"RETIRED",
      "retired_at":datetime.now(timezone.utc).isoformat(),
      "M77_14":"CLOSED_UNSUPPORTED_LONG_HISTORY_REPLICATION_FAILURE",
      "M77_15":"CLOSED_UNSUPPORTED",
      "M77_16":"CLOSED_UNSUPPORTED",
      "lunar_prospective_shadow_enabled":False,
      "production_authority_effect":False,
      "reopen_rule":cfg["governance"]["reopen_rule"]
    }
    write_json_atomic(sentinel,sentinel_payload)

    out={
      "version":cfg["version"],"status":"READY",
      "closure":cfg["closure"],
      "m77_17_evidence":{
        "primary_replication_pass":ev["primary_replication_pass"],
        "all_three_same_framework_pass":ev["all_three_same_framework_pass"],
        "disposition":ev["disposition"]
      },
      "retirement":{
        "sentinel":str(sentinel),
        "shadow_references_reviewed":reviewed,
        "shell_orchestration_files_modified":changed,
        "backup_root":str(backup_root) if changed else None,
        "historical_artifacts_preserved":True,
        "research_data_deleted":False,
        "logs_deleted":False
      },
      "certification":{
        "astrology_research_closed":True,
        "m77_14_shadow_enabled":False,
        "m77_15_closed":True,
        "m77_16_closed":True,
        "production_model_change":False,
        "production_ranking_change":False,
        "production_decision_change":False,
        "database_writes":False,
        "production_authority_effect":False
      },
      "next_step":"ASTROLOGY_RESEARCH_COMPLETE_RETURN_TO_CORE_TRADING_PLATFORM_ROADMAP",
      "production_authority_effect":False
    }
    write_json_atomic(OUT,out)
    print(json.dumps(out,indent=2))

if __name__=="__main__": main()
