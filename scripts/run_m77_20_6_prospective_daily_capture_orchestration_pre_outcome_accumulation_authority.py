#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,hashlib,json,os,subprocess,tempfile
from datetime import datetime,timezone
from pathlib import Path

VERSION="M77.20.6-PROSPECTIVE-DAILY-CAPTURE-ORCHESTRATION-PRE-OUTCOME-ACCUMULATION-AUTHORITY-1.0"
class OrchestrationError(RuntimeError):pass

def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:Path(tmp).write_bytes(data);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def run(cmd):
    print("RUN:"," ".join(str(x) for x in cmd),flush=True)
    p=subprocess.run(cmd,text=True)
    if p.returncode!=0:raise OrchestrationError(f"child step failed returncode={p.returncode}: {cmd[1]}")

def validate_existing_baseline_seed(root, authority_path, capture_date):
    if not authority_path.exists():
        return None
    d=J(authority_path)
    if d.get("status")!="READY" or d.get("capture_date")!=capture_date:
        return None
    if d.get("prospective_outcomes_opened") is not False:
        raise OrchestrationError("existing baseline seed has prospective outcomes opened")
    if d.get("prospective_scoring_performed") is not False:
        raise OrchestrationError("existing baseline seed has scoring performed")
    if d.get("production_authority_effect") is not False:
        raise OrchestrationError("existing baseline seed has production effect")
    if int(d.get("frozen_baseline_feature_column_count") or 0)!=99:
        raise OrchestrationError("existing baseline seed is not certified 99-column baseline")
    sp=R(root,d.get("baseline_snapshot_file"))
    if not sp.exists():
        raise OrchestrationError(f"existing baseline seed snapshot missing: {sp}")
    snap=J(sp)
    ah=d.get("baseline_snapshot_semantic_sha256")
    sh=snap.get("baseline_snapshot_semantic_sha256")
    if not ah or ah!=sh:
        raise OrchestrationError("existing baseline seed authority/snapshot semantic hash mismatch")
    if snap.get("capture_date")!=capture_date:
        raise OrchestrationError("existing baseline seed snapshot capture date mismatch")
    if snap.get("effective_observation_session")!=d.get("effective_observation_session"):
        raise OrchestrationError("existing baseline seed effective-session mismatch")
    return d

def bootstrap_baseline_manifest(root, baseline_authority):
    outroot=R(root,"research_data/m77_20_5/prospective_baseline_shadow")
    manifest_path=outroot/"manifest.json"
    manifest={"version":"M77.20.5-PROSPECTIVE-BASELINE-SHADOW-MANIFEST-1.0","snapshots":[]}
    if manifest_path.exists():
        manifest=J(manifest_path)
    entries={str(x.get("capture_date") or x.get("snapshot_date")):x for x in (manifest.get("snapshots") or [])}
    capture_date=baseline_authority["capture_date"]
    ent={
        "capture_date":capture_date,
        "snapshot_file":baseline_authority["baseline_snapshot_file"],
        "baseline_snapshot_semantic_sha256":baseline_authority["baseline_snapshot_semantic_sha256"],
        "effective_observation_session":baseline_authority["effective_observation_session"],
        "paired_observation_eligible_count":int(baseline_authority["paired_observation_eligible_count"]),
    }
    if capture_date in entries and entries[capture_date]!=ent:
        raise OrchestrationError("baseline seed manifest immutability violation")
    mode="EXISTING_BASELINE_MANIFEST_ENTRY_REUSED" if capture_date in entries else "IMMUTABLE_BASELINE_SEED_MANIFEST_BOOTSTRAPPED"
    entries[capture_date]=ent
    manifest["snapshots"]=[entries[k] for k in sorted(entries)]
    manifest["latest_capture_date"]=max(entries)
    atomic(manifest_path,json.dumps(manifest,indent=2,sort_keys=True).encode()+b"\n")
    return mode,manifest_path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--snapshot-date",default=None)
    ap.add_argument("--design-gate-json",default="reports/m77_20_2_external_historical_pit_sector_source_decision_prospective_only_research_design_gate.json")
    ap.add_argument("--canonical-csv",default="data/universe/us_listed_equities_etfs.csv")
    ap.add_argument("--benchmark-source",default="src/trading_ai/market_intelligence/engine.py")
    ap.add_argument("--training-gate-json",default="reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    ap.add_argument("--development-helper-script",default="scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    ap.add_argument("--development-evaluation-json",default="reports/m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.json")
    ap.add_argument("--accumulation-root",default="research_data/m77_20_6/pre_outcome_accumulation")
    ap.add_argument("--output-json",default="reports/m77_20_6_prospective_daily_capture_orchestration_pre_outcome_accumulation_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_20_6_pre_outcome_accumulation_registry.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    py=str(root/".venv/bin/python3")
    if not Path(py).exists():py=os.sys.executable
    sd=a.snapshot_date or datetime.now(timezone.utc).date().isoformat()

    s3=root/"scripts/run_m77_20_3_prospective_sector_membership_benchmark_snapshot_capture_authority.py"
    s4=root/"scripts/run_m77_20_4_prospective_f071_feature_materialization_immutable_shadow_capture_authority.py"
    s5=root/"scripts/run_m77_20_5_prospective_baseline_feature_shadow_capture_paired_observation_authority.py"
    for p in (s3,s4,s5):
        if not p.exists():raise OrchestrationError(f"required child runner missing: {p}")

    r3="reports/m77_20_3_prospective_sector_membership_benchmark_snapshot_capture_authority.json"
    r4="reports/m77_20_4_prospective_f071_feature_materialization_immutable_shadow_capture_authority.json"
    r5="reports/m77_20_5_prospective_baseline_feature_shadow_capture_paired_observation_authority.json"

    run([py,str(s3),"--project-root",str(root),"--design-gate-json",a.design_gate_json,
         "--canonical-csv",a.canonical_csv,"--benchmark-source",a.benchmark_source,
         "--snapshot-date",sd,"--output-root","research_data/m77_20_3/prospective_sector_snapshots",
         "--output-json",r3,"--output-csv","reports/m77_20_3_latest_snapshot_summary.csv"])
    d3=J(root/r3)
    if d3.get("status")!="READY" or d3.get("prospective_outcomes_opened") is not False:
        raise OrchestrationError("20.3 authority invalid after child run")

    run([py,str(s4),"--project-root",str(root),"--snapshot-authority-json",r3,
         "--output-root","research_data/m77_20_4/prospective_f071_shadow",
         "--output-json",r4,"--output-csv","reports/m77_20_4_f071_coverage_summary.csv"])
    d4=J(root/r4)
    if d4.get("status")!="READY" or d4.get("prospective_outcomes_opened") is not False:
        raise OrchestrationError("20.4 authority invalid after child run")

    existing_seed=validate_existing_baseline_seed(root,root/r5,sd)
    if existing_seed is not None:
        d5=existing_seed
        baseline_execution_mode="ADOPTED_EXISTING_IMMUTABLE_BASELINE_SEED"
        baseline_manifest_mode,baseline_manifest_path=bootstrap_baseline_manifest(root,d5)
        print("BASELINE:",baseline_execution_mode,flush=True)
        print("BASELINE_MANIFEST:",baseline_manifest_mode,flush=True)
    else:
        run([py,str(s5),"--project-root",str(root),"--f071-authority-json",r4,
             "--training-gate-json",a.training_gate_json,"--development-helper-script",a.development_helper_script,
             "--development-evaluation-json",a.development_evaluation_json,
             "--output-root","research_data/m77_20_5/prospective_baseline_shadow",
             "--output-json",r5,"--output-csv","reports/m77_20_5_paired_observation_summary.csv"])
        d5=J(root/r5)
        if d5.get("status")!="READY" or d5.get("prospective_outcomes_opened") is not False:
            raise OrchestrationError("20.5 authority invalid after child run")
        baseline_execution_mode="NEW_OR_IDEMPOTENT_BASELINE_CHILD_EXECUTION"
        baseline_manifest_mode,baseline_manifest_path=bootstrap_baseline_manifest(root,d5)

    if not (d3["snapshot_date"]==d4["snapshot_date"]==d5["capture_date"]==sd):
        raise OrchestrationError("capture-date lineage mismatch")
    effective=d5["effective_observation_session"]
    paired=int(d5["paired_observation_eligible_count"])
    if int(d5["frozen_baseline_feature_column_count"])!=99:
        raise OrchestrationError("baseline feature registry no longer 99 columns")

    accroot=R(root,a.accumulation_root);manifest_path=accroot/"manifest.json"
    manifest={"version":"M77.20.6-PRE-OUTCOME-ACCUMULATION-MANIFEST-1.0","observations":[]}
    if manifest_path.exists():manifest=J(manifest_path)
    obs=manifest.get("observations") or []
    prior_sessions=sorted({x["effective_observation_session"] for x in obs})
    prior_latest=max(prior_sessions) if prior_sessions else None

    if effective in prior_sessions:
        accumulation_mode="NO_NEW_EFFECTIVE_MARKET_SESSION_IDEMPOTENT"
        new_statistical_observation=False
    elif prior_latest is not None and effective<prior_latest:
        raise OrchestrationError(f"OUT_OF_ORDER_EFFECTIVE_SESSION current={effective} prior_latest={prior_latest}")
    else:
        accumulation_mode="NEW_EFFECTIVE_MARKET_SESSION_ACCUMULATED"
        new_statistical_observation=True
        ent={"capture_date":sd,"effective_observation_session":effective,
             "paired_observation_eligible_count":paired,
             "sector_snapshot_semantic_sha256":d3["snapshot_semantic_sha256"],
             "f071_snapshot_semantic_sha256":d4["feature_snapshot_semantic_sha256"],
             "baseline_snapshot_semantic_sha256":d5["baseline_snapshot_semantic_sha256"],
             "sector_authority_json":r3,"f071_authority_json":r4,"baseline_authority_json":r5}
        obs.append(ent)
        obs.sort(key=lambda x:x["effective_observation_session"])
        manifest["observations"]=obs
        manifest["latest_effective_observation_session"]=effective
        manifest["statistical_session_count"]=len(obs)
        manifest["cumulative_paired_observation_rows"]=sum(int(x["paired_observation_eligible_count"]) for x in obs)
        atomic(manifest_path,json.dumps(manifest,indent=2,sort_keys=True).encode()+b"\n")

    session_count=len(manifest.get("observations") or [])
    cumulative=sum(int(x["paired_observation_eligible_count"]) for x in (manifest.get("observations") or []))
    minimum=10000
    report={"version":VERSION,"status":"READY","capture_date":sd,
      "effective_observation_session":effective,"accumulation_mode":accumulation_mode,
      "new_statistical_observation_accumulated":new_statistical_observation,
      "paired_observation_eligible_count_this_session":paired,
      "baseline_execution_mode":baseline_execution_mode,
      "baseline_manifest_mode":baseline_manifest_mode,
      "baseline_manifest_file":str(baseline_manifest_path.relative_to(root)),
      "existing_immutable_baseline_recomputed":False if baseline_execution_mode=="ADOPTED_EXISTING_IMMUTABLE_BASELINE_SEED" else None,
      "statistical_effective_session_count":session_count,
      "cumulative_paired_observation_rows":cumulative,
      "preregistered_minimum_matured_binary_rows_per_horizon":minimum,
      "pre_outcome_accumulation_only":True,
      "target_materialization_authorized":False,
      "prospective_outcomes_opened":False,
      "prospective_scoring_authorized":False,
      "prospective_scoring_performed":False,
      "effective_session_deduplication_enforced":True,
      "out_of_order_effective_session_authorized":False,
      "sector_snapshot_immutability_certified":d3["snapshot_immutability_certified"],
      "f071_snapshot_immutability_certified":d4["feature_snapshot_immutability_certified"],
      "baseline_snapshot_immutability_certified":d5["baseline_snapshot_immutability_certified"],
      "production_authority_effect":False,
      "manifest_file":str(manifest_path.relative_to(root)),
      "next_step":"CONTINUE_DAILY_M77_20_6_CAPTURE_UNTIL_PRE_OUTCOME_SAMPLE_MATURITY_GATE_CAN_BE_PREREGISTERED_AND_MET"}
    oj,oc=R(root,a.output_json),R(root,a.output_csv);oj.parent.mkdir(parents=True,exist_ok=True)
    atomic(oj,json.dumps(report,indent=2,sort_keys=True).encode()+b"\n")
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=["capture_date","effective_observation_session","accumulation_mode",
          "new_statistical_observation_accumulated","paired_observation_eligible_count_this_session",
          "statistical_effective_session_count","cumulative_paired_observation_rows"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow({k:report[k] for k in fields})

    print("=== M77.20.6 PROSPECTIVE DAILY CAPTURE ORCHESTRATION & PRE-OUTCOME ACCUMULATION AUTHORITY ===")
    print("status: READY");print("capture_date:",sd);print("effective_observation_session:",effective)
    print("accumulation_mode:",accumulation_mode);print("new_statistical_observation_accumulated:",new_statistical_observation)
    print("paired_observation_eligible_count_this_session:",paired)
    print("baseline_execution_mode:",baseline_execution_mode)
    print("baseline_manifest_mode:",baseline_manifest_mode)
    print("existing_immutable_baseline_recomputed:",False if baseline_execution_mode=="ADOPTED_EXISTING_IMMUTABLE_BASELINE_SEED" else None)
    print("statistical_effective_session_count:",session_count);print("cumulative_paired_observation_rows:",cumulative)
    print("effective_session_deduplication_enforced: True");print("out_of_order_effective_session_authorized: False")
    print("pre_outcome_accumulation_only: True");print("target_materialization_authorized: False")
    print("prospective_outcomes_opened: False");print("prospective_scoring_authorized: False")
    print("prospective_scoring_performed: False");print("production_authority_effect: False")
    print("next_step:",report["next_step"]);print("report:",oj);print("csv:",oc);print("manifest:",manifest_path)

if __name__=="__main__":main()
