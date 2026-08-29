
from __future__ import annotations
import argparse, csv, hashlib, json, os, subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION="M77.41.0-RESEARCH-PROGRAM-CLOSURE-EVIDENCE-REGISTRY-PROSPECTIVE-GOVERNANCE-DASHBOARD-1.0"

PROSPECTIVE_TRACKS=(
    ("PSVE","M77.24.1","PSVE-CANDIDATE-001","data/positive_selection_shadow"),
    ("MGE","M77.26.2","MGE-CANDIDATE-001","data/management_geometry_shadow"),
    ("CQMI","M77.27.1","CQMI-CANDIDATE-001","data/candidate_quality_management_interaction_shadow"),
    ("CPRE","M77.30","CPRE-CANDIDATE-001","data/cross_sectional_capital_priority_shadow"),
    ("CACA","M77.40","CACA-CANDIDATE-001","data/capacity_aware_capital_allocation_shadow"),
)

REGISTRY=(
    ("M77.23","Certified Downside-Risk Veto Production Integration","PRODUCTION_CERTIFIED","DRVE downside-risk veto","Final-holdout PASS; production enforcement activated.","Monitor only; no automatic retraining."),
    ("M77.24","Positive Selection Edge Discovery","DEVELOPMENT_SURVIVOR","PROBABILITY_UP positive selection","Development survivor.","Prospective certification only."),
    ("M77.24.1","Frozen Prospective Positive Selection Shadow","PROSPECTIVE_CERTIFICATION_PENDING","PSVE","Frozen prospective shadow.","Accumulate/evaluate frozen gates."),
    ("M77.25","Entry Timing Path-Dependent Edge Discovery","REJECTED_DEVELOPMENT_HYPOTHESIS","Entry timing/path","0 development-ready timing configurations.","Closed; no post-hoc retuning."),
    ("M77.26.1","Executable Management Geometry Recalibration","DEVELOPMENT_SURVIVOR","NEXT_OPEN / 5ATR / 3ATR / 60d","Development-ready executable geometry.","Prospective certification only."),
    ("M77.26.2","Prospective Executable Management Geometry Shadow","PROSPECTIVE_CERTIFICATION_PENDING","MGE","Frozen prospective shadow.","Accumulate/evaluate frozen gates."),
    ("M77.27","Candidate Quality × Management Interaction","DEVELOPMENT_SURVIVOR","Candidate-quality × management","Development survivor.","Prospective certification only."),
    ("M77.27.1","Prospective Candidate Quality × Management Shadow","PROSPECTIVE_CERTIFICATION_PENDING","CQMI","Frozen prospective shadow.","Accumulate/evaluate frozen gates."),
    ("M77.28","Regime-Conditioned Edge Stability","FORENSIC_ONLY","Regime stability","Development-only stability forensics.","Reference only."),
    ("M77.29","Cross-Sectional Ranking & Opportunity Cost","DEVELOPMENT_SURVIVOR","PROBABILITY_UP ranking","Development-ready ranking evidence.","Prospective allocation testing only."),
    ("M77.29.1","Ranking Identity / Independence / Capacity Forensics","FORENSIC_ONLY","Ranking identity/capacity","Forensic decomposition.","Reference only."),
    ("M77.29.2","Ensemble Attribution / Capacity / Regime Neutralization","FORENSIC_ONLY","Ensemble/capacity neutralization","Forensic-only.","Reference only."),
    ("M77.29.3","Ensemble Payoff Distribution / Component Causality","FORENSIC_ONLY","Component causality","Forensic-only.","Reference only."),
    ("M77.30","Frozen Prospective Cross-Sectional Capital Priority Shadow","PROSPECTIVE_CERTIFICATION_PENDING","CPRE Top-3","Frozen prospective shadow.","Accumulate/evaluate frozen gates."),
    ("M77.31","Relative Strength / Persistence / Leadership","REJECTED_DEVELOPMENT_HYPOTHESIS","Leadership states","0 survivors.","Closed."),
    ("M77.32","Volatility Compression / Expansion Transition","REJECTED_DEVELOPMENT_HYPOTHESIS","Volatility transitions","0 survivors.","Closed."),
    ("M77.33","Participation / Accumulation Confirmation","REJECTED_DEVELOPMENT_HYPOTHESIS","Participation states","0 survivors.","Closed."),
    ("M77.34","Mean-Reversion / Extension State","REJECTED_DEVELOPMENT_HYPOTHESIS","Extension states","0 survivors.","Closed."),
    ("M77.35","Serial Dependence / Path Smoothness","REJECTED_DEVELOPMENT_HYPOTHESIS","Path states","0 survivors.","Closed."),
    ("M77.36","Cross-Sectional Dispersion / Relative Opportunity","REJECTED_DEVELOPMENT_HYPOTHESIS","Dispersion states","0 survivors.","Closed."),
    ("M77.37","Outcome Asymmetry / Conditional Tail Structure","REJECTED_DEVELOPMENT_HYPOTHESIS","Tail/asymmetry states","0 survivors.","Closed."),
    ("M77.38","Edge Interaction Necessity / Redundancy","NOT_IDENTIFIABLE","DRVE necessity in post-DRVE cohort","DRVE ablation not identifiable from conditioned panel.","Do not infer without pre-DRVE counterfactual."),
    ("M77.38.1","Capital-Priority Dependency / Incremental Value","FORENSIC_ONLY","CPRE semantic dependency","CPRE is definitionally PROBABILITY_UP-derived.","Architecture reference only."),
    ("M77.39","Capacity-Constrained Portfolio Utility","DEVELOPMENT_SURVIVOR","Capacity-aware ranked allocation","Primary Development certification PASS.","Prospective challenger only."),
    ("M77.40","Frozen Prospective Capacity-Aware Allocation Shadow","PROSPECTIVE_CERTIFICATION_PENDING","CACA","Frozen prospective challenger.","Accumulate/evaluate frozen gates."),
    ("M77.40.1","Governed Capacity Authority / CPRE Live Binding","FORENSIC_ONLY","Live authority binding","Read-only adapter; protocol unchanged.","Operational use only."),
    ("M77.40.2","Prospective Shadow Launchd Hardening","FORENSIC_ONLY","Operational automation","Daily record/update orchestration enabled.","Operational monitoring only."),
)

@dataclass(frozen=True)
class ClosureConfig:
    project_root:str
    output_dir:str="reports/m77/m77_41_research_program_closure"

def _sha(p:Path):
    if not p.exists(): return None
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def _read_json(p:Path):
    try: return json.loads(p.read_text()) if p.exists() else {}
    except Exception: return {}

def _track(root:Path,t):
    name,milestone,pid,base_s=t
    base=root/base_s
    protocol=base/"FROZEN_PROSPECTIVE_PROTOCOL.json"
    summary=base/"certification_summary.json"
    snaps=sorted((base/"snapshots").glob("*.json")) if (base/"snapshots").exists() else []
    matured=sorted((base/"matured").glob("*.json")) if (base/"matured").exists() else []
    s=_read_json(summary)
    return {
        "track":name,"milestone":milestone,"protocol_id":pid,
        "protocol_frozen":protocol.exists(),"protocol_sha256":_sha(protocol),
        "snapshot_count":len(snaps),"latest_snapshot":snaps[-1].stem if snaps else None,
        "matured_snapshot_count":len(matured),
        "certification_status":s.get("status","ACCUMULATING" if snaps else "NO_SNAPSHOTS"),
        "certification_verdict":s.get("certification_verdict","NOT_ENOUGH_PROSPECTIVE_EVIDENCE"),
        "production_authority_effect":bool(s.get("production_authority_effect",False)),
    }

def _launchd():
    label="com.tradingplatform.m77-6-shadow"
    try:
        r=subprocess.run(["launchctl","print",f"gui/{os.getuid()}/{label}"],text=True,capture_output=True,timeout=5)
    except Exception as e:
        return {"label":label,"available":False,"healthy":False,"reason":type(e).__name__}
    if r.returncode!=0:
        return {"label":label,"available":False,"healthy":False,"reason":(r.stderr or r.stdout).strip()}
    vals={}
    for line in r.stdout.splitlines():
        s=line.strip()
        for k in ("state","runs","last exit code"):
            if s.startswith(k+" ="): vals[k]=s.split("=",1)[1].strip()
    return {
        "label":label,"available":True,
        "state":vals.get("state"),"runs":vals.get("runs"),
        "last_exit_code":vals.get("last exit code"),
        "healthy":vals.get("last exit code") in (None,"0"),
    }

def run_closure(cfg:ClosureConfig):
    root=Path(cfg.project_root).expanduser().resolve()
    out=root/cfg.output_dir
    out.mkdir(parents=True,exist_ok=True)

    tracks=[_track(root,t) for t in PROSPECTIVE_TRACKS]
    launchd=_launchd()
    counts={}
    entries=[]
    for m,title,cls,mech,evidence,next_action in REGISTRY:
        counts[cls]=counts.get(cls,0)+1
        entries.append({
            "milestone":m,"title":title,"classification":cls,"mechanism":mech,
            "evidence":evidence,"next_permitted_action":next_action,
            "production_authority_effect":m=="M77.23",
        })

    pending=[t for t in tracks if t["certification_verdict"]=="NOT_ENOUGH_PROSPECTIVE_EVIDENCE"]
    healthy=(
        all(t["protocol_frozen"] and t["snapshot_count"]>0 and not t["production_authority_effect"] for t in tracks)
        and (launchd["healthy"] if launchd.get("available") else True)
    )
    result={
        "version":VERSION,
        "generated_at":datetime.now(timezone.utc).isoformat(),
        "historical_exploration_status":"COMPLETE",
        "research_program_phase":"PROSPECTIVE_EVIDENCE_ACCUMULATION",
        "classification_counts":dict(sorted(counts.items())),
        "production_certified_count":counts.get("PRODUCTION_CERTIFIED",0),
        "prospective_protocol_count":len(tracks),
        "prospective_pending_count":len(pending),
        "prospective_resolved_count":len(tracks)-len(pending),
        "production_changes_pending":"NONE",
        "automatic_production_promotion":False,
        "automatic_retraining":False,
        "new_historical_edge_discovery_permitted":False,
        "prospective_tracks":tracks,
        "launchd":launchd,
        "overall_operational_health":"HEALTHY" if healthy else "ATTENTION_REQUIRED",
        "next_step":"ALLOW FROZEN PROSPECTIVE EVIDENCE TO MATURE; EVALUATE ONLY AGAINST PREREGISTERED GATES; NO AUTOMATIC PRODUCTION PROMOTION",
    }
    (out/"M77_RESEARCH_PROGRAM_STATUS.json").write_text(json.dumps(result,indent=2,sort_keys=True))
    (out/"M77_EVIDENCE_REGISTRY.json").write_text(json.dumps({"version":VERSION,"entries":entries},indent=2,sort_keys=True))
    with (out/"M77_EVIDENCE_REGISTRY.csv").open("w",newline="") as f:
        fields=["milestone","title","classification","mechanism","evidence","next_permitted_action","production_authority_effect"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for e in entries:w.writerow(e)

    lines=[
        "# M77 Research Program Closure & Evidence Registry","",
        f"- Historical exploration: **{result['historical_exploration_status']}**",
        f"- Current phase: **{result['research_program_phase']}**",
        f"- Operational health: **{result['overall_operational_health']}**",
        f"- Prospective protocols: **{result['prospective_protocol_count']}**",
        f"- Pending certification: **{result['prospective_pending_count']}**","",
        "## Prospective tracks","",
        "| Track | Milestone | Frozen | Snapshots | Latest | Matured | Verdict |",
        "|---|---|---:|---:|---|---:|---|",
    ]
    for t in tracks:
        lines.append(f"| {t['track']} | {t['milestone']} | {'YES' if t['protocol_frozen'] else 'NO'} | {t['snapshot_count']} | {t['latest_snapshot'] or '-'} | {t['matured_snapshot_count']} | {t['certification_verdict']} |")
    lines += ["","## Evidence registry","",
              "| Milestone | Classification | Mechanism | Next permitted action |",
              "|---|---|---|---|"]
    for e in entries:
        lines.append(f"| {e['milestone']} | {e['classification']} | {e['mechanism']} | {e['next_permitted_action']} |")
    lines += ["","## Governance","",
              "- Historical edge discovery is closed.",
              "- Rejected Development hypotheses must not be reopened by post-hoc search.",
              "- Prospective protocols may only be evaluated against frozen gates.",
              "- No prospective PASS may automatically modify production."]
    (out/"M77_RESEARCH_PROGRAM_CLOSURE_REPORT.md").write_text("\n".join(lines))
    return result

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--project-root",required=True)
    p.add_argument("--output-dir",default=ClosureConfig.output_dir)
    a=p.parse_args(argv)
    print(json.dumps(run_closure(ClosureConfig(a.project_root,a.output_dir)),indent=2,sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
