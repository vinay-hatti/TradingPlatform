#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping

VERSION = "M77.19.6.5.2.3-MONTHLY-CONTEXT-PARITY-DIFFERENCE-FORENSICS-1.0"
NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
EXPECTED_522_REPORT_SHA256 = "704b6e70892247ed85e99d2ddc7c8a0ce2b5636c2e373c81398bd7b7755ab0d8"
NUMERIC_TOLERANCE = 1e-9
MAX_SESSION_BACKTRACK = 8

def load_json(path: Path) -> Any:
    return json.loads(path.read_text())

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

@contextlib.contextmanager
def readonly_session():
    from trading_ai.database.session import SessionLocal
    from sqlalchemy import text
    s=SessionLocal()
    try:
        s.execute(text("SET TRANSACTION READ ONLY"))
        yield s
        s.rollback()
    finally:
        s.close()

def load_spy_sessions():
    from sqlalchemy import text
    with readonly_session() as s:
        rows=s.execute(text("SELECT date FROM public.price_history WHERE symbol='SPY' ORDER BY date")).all()
    out=[]
    for (v,) in rows:
        if isinstance(v,dt.datetime): v=v.date()
        elif not isinstance(v,dt.date): v=dt.date.fromisoformat(str(v)[:10])
        out.append(v)
    return sorted(set(out))

def import_native(root: Path):
    p=root/NATIVE_RUNNER_REL
    actual=sha256_file(p)
    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")
    spec=importlib.util.spec_from_file_location("m77_native_523",p)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("call_profile","compare_profile","StockIntelligenceService"):
        if not hasattr(mod,name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")
    return mod

def require_522(root: Path, explicit: str|None):
    paths=[Path(explicit)] if explicit else []
    paths.append(root/"reports/m77_19_6_5_2_2_native_compare_profile_parity_certification.json")
    for p in paths:
        if not p.exists(): continue
        actual=sha256_file(p)
        if actual != EXPECTED_522_REPORT_SHA256:
            raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.2 report SHA drift: {actual}")
        d=load_json(p)
        if d.get("controlled_exact_input_parity_certified") is not False:
            raise SystemExit("FAIL CLOSED: expected failed controlled parity")
        if d.get("blockers") != ["MONTHLY_STRICT_PARITY_NOT_CERTIFIED"]:
            raise SystemExit("FAIL CLOSED: expected isolated monthly blocker")
        if d.get("next_step") != "FORENSIC_REVIEW_M77_19_6_5_2_2_NATIVE_PARITY_DIFFERENCES":
            raise SystemExit("FAIL CLOSED: M77.19.6.5.2.2 did not authorize this forensic review")
        return p,d
    raise SystemExit("FAIL CLOSED: M77.19.6.5.2.2 report not found")

def normalize_bundle_rows(bundle):
    rows=[]
    for raw in bundle["price_history"]:
        low={str(k).lower():v for k,v in raw.items()}
        dv=low.get("date") or low.get("session_date") or low.get("price_date") or low.get("bar_date") or low.get("as_of")
        if dv is None: continue
        if isinstance(dv,dt.datetime): dv=dv.date()
        elif not isinstance(dv,dt.date): dv=dt.date.fromisoformat(str(dv)[:10])
        def f(name):
            v=low.get(name)
            return None if v in (None,"") else float(v)
        row={"date":dv,"open":f("open"),"high":f("high"),"low":f("low"),"close":f("close"),"volume":f("volume")}
        if row["close"] is not None: rows.append(row)
    rows.sort(key=lambda x:x["date"])
    return rows

def category(profile):
    scores=getattr(profile,"scores",None)
    return str(getattr(scores,"primary_category","") if scores else "")

def sem_from_profile(profile):
    scores=getattr(profile,"scores",None)
    return {
        "direction":str(getattr(profile,"direction","")),
        "overall_score":float(getattr(scores,"overall_score")),
        "confidence":float(getattr(profile,"confidence")),
        "primary_category":category(profile),
    }

def sem_from_frozen(frozen):
    return {
        "direction":str(frozen["direction"]),
        "overall_score":float(frozen["overall_score"]),
        "confidence":float(frozen["confidence"]),
        "primary_category":str(frozen.get("primary_category","")),
    }

def errors(iso, stored):
    return {
        "direction_match": iso["direction"] == stored["direction"],
        "primary_category_match": iso["primary_category"] == stored["primary_category"],
        "score_signed_error": iso["overall_score"] - stored["overall_score"],
        "score_abs_error": abs(iso["overall_score"] - stored["overall_score"]),
        "confidence_signed_error": iso["confidence"] - stored["confidence"],
        "confidence_abs_error": abs(iso["confidence"] - stored["confidence"]),
    }

def exact(e):
    return (
        e["direction_match"] and e["primary_category_match"]
        and e["score_abs_error"] <= NUMERIC_TOLERANCE
        and e["confidence_abs_error"] <= NUMERIC_TOLERANCE
    )

def candidate_sessions(as_of, sessions):
    eligible=[s for s in sessions if s <= as_of]
    return list(reversed(eligible[-(MAX_SESSION_BACKTRACK+1):]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=".")
    ap.add_argument("--certification-report")
    ap.add_argument("--bundle-root",default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles")
    ap.add_argument("--output",default="reports/m77_19_6_5_2_3_monthly_context_parity_difference_forensics.json")
    a=ap.parse_args()

    root=Path(a.project_root).resolve()
    prior_path,prior=require_522(root,a.certification_report)
    native=import_native(root)
    sessions=load_spy_sessions()
    session_set=set(sessions)
    svc=native.StockIntelligenceService()

    monthly_files=sorted((root/a.bundle_root/"monthly").glob("*.json"))
    report={
        "version":VERSION,
        "source_certification_report":str(prior_path),
        "governance":{
            "research_only":True,
            "forensic_probe_only":True,
            "database_mode":"READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes":False,
            "parity_thresholds_relaxed":False,
            "numeric_tolerance":NUMERIC_TOLERANCE,
            "production_authority_effect":False,
            "controlled_exact_input_parity_certified":False,
            "full_23_year_reconstruction_authorized":False,
        },
        "monthly_bundle_count":len(monthly_files),
        "records":[],
    }

    for fp in monthly_files:
        bundle=load_json(fp)
        identity=bundle["prediction_identity"]
        frozen=bundle["frozen_output"]
        stored=sem_from_frozen(frozen)
        rows=normalize_bundle_rows(bundle)
        nominal=dt.date.fromisoformat(str(identity["as_of"])[:10])
        candidates=[]
        for rank,cutoff in enumerate(candidate_sessions(nominal,sessions)):
            cut_rows=[r for r in rows if r["date"] <= cutoff]
            if not cut_rows: continue
            try:
                profile=native.call_profile(svc,str(identity["symbol"]),cut_rows,cutoff,session_set,300,750)
                if profile is None: raise RuntimeError("native profile not eligible")
                sem=sem_from_profile(profile)
                e=errors(sem,stored)
                candidates.append({
                    "session_backtrack":rank,
                    "candidate_as_of":cutoff.isoformat(),
                    "input_row_count":len(cut_rows),
                    "input_last_date":cut_rows[-1]["date"].isoformat(),
                    "isolated_semantic":sem,
                    **e,
                    "exact_semantic_match":exact(e),
                })
            except Exception as exc:
                candidates.append({
                    "session_backtrack":rank,
                    "candidate_as_of":cutoff.isoformat(),
                    "error":type(exc).__name__,
                    "message":str(exc)[:1000],
                    "exact_semantic_match":False,
                })

        valid=[c for c in candidates if "error" not in c]
        best=min(valid,key=lambda c:(
            0 if c["direction_match"] else 1,
            0 if c["primary_category_match"] else 1,
            c["confidence_abs_error"],
            c["score_abs_error"],
            c["session_backtrack"],
        )) if valid else None

        baseline=next((c for c in valid if c["session_backtrack"]==0),None)
        rec={
            "bundle":str(fp.relative_to(root)),
            "symbol":str(identity["symbol"]),
            "nominal_as_of":nominal.isoformat(),
            "stored_semantic":stored,
            "price_history_row_count":len(rows),
            "price_history_first_date":rows[0]["date"].isoformat() if rows else None,
            "price_history_last_date":rows[-1]["date"].isoformat() if rows else None,
            "baseline":baseline,
            "best_candidate":best,
            "exact_candidate_found":any(c.get("exact_semantic_match") for c in valid),
            "candidates":candidates,
        }
        report["records"].append(rec)

    baselines=[r["baseline"] for r in report["records"] if r["baseline"]]
    bests=[r["best_candidate"] for r in report["records"] if r["best_candidate"]]
    exacts=[r for r in report["records"] if r["exact_candidate_found"]]
    category_mismatch=[
        r for r in report["records"]
        if r["baseline"] and not r["baseline"]["primary_category_match"]
    ]

    signed_scores=[c["score_signed_error"] for c in baselines]
    signed_conf=[c["confidence_signed_error"] for c in baselines]
    report["baseline_summary"]={
        "comparison_count":len(baselines),
        "direction_match_pct":100.0*sum(c["direction_match"] for c in baselines)/len(baselines) if baselines else 0.0,
        "primary_category_match_pct":100.0*sum(c["primary_category_match"] for c in baselines)/len(baselines) if baselines else 0.0,
        "max_score_abs_error":max((c["score_abs_error"] for c in baselines),default=None),
        "max_confidence_abs_error":max((c["confidence_abs_error"] for c in baselines),default=None),
        "mean_score_signed_error":mean(signed_scores) if signed_scores else None,
        "median_score_signed_error":median(signed_scores) if signed_scores else None,
        "unique_confidence_signed_errors":sorted(set(round(x,12) for x in signed_conf)),
        "score_signed_error_distribution_2dp":dict(sorted(Counter(round(x,2) for x in signed_scores).items())),
        "category_mismatches":[{
            "symbol":r["symbol"],
            "stored":r["stored_semantic"]["primary_category"],
            "isolated":r["baseline"]["isolated_semantic"]["primary_category"],
            "stored_score":r["stored_semantic"]["overall_score"],
            "isolated_score":r["baseline"]["isolated_semantic"]["overall_score"],
        } for r in category_mismatch],
    }
    report["session_cutoff_forensics"]={
        "exact_candidate_count":len(exacts),
        "exact_candidate_symbols":[r["symbol"] for r in exacts],
        "best_candidate_backtrack_distribution":dict(sorted(Counter(
            int(c["session_backtrack"]) for c in bests
        ).items())),
        "all_monthly_exact_match_recovered_by_session_cutoff":len(exacts)==len(report["records"]) and len(report["records"])>0,
    }

    if report["session_cutoff_forensics"]["all_monthly_exact_match_recovered_by_session_cutoff"]:
        conclusion="MONTHLY_PARITY_ROOT_CAUSE_IS_SESSION_CUTOFF_CONTEXT"
        next_step="BUILD_M77_19_6_5_2_4_GOVERNED_MONTHLY_SESSION_CONTEXT_REPLAY_CERTIFICATION"
    elif len(exacts)>0:
        conclusion="MONTHLY_PARITY_PARTIALLY_EXPLAINED_BY_SESSION_CUTOFF_CONTEXT"
        next_step="DECOMPOSE_REMAINING_MONTHLY_FEATURE_AND_CONFIDENCE_CONTEXT"
    else:
        conclusion="MONTHLY_PARITY_NOT_EXPLAINED_BY_SIMPLE_SESSION_CUTOFF_CONTEXT"
        next_step="BUILD_M77_19_6_5_2_4_MONTHLY_FEATURE_CONFIDENCE_COMPONENT_FORENSICS"

    report["forensic_conclusion"]=conclusion
    report["controlled_exact_input_parity_certified"]=False
    report["full_23_year_reconstruction_authorized"]=False
    report["production_authority_effect"]=False
    report["next_step"]=next_step

    out=root/a.output
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")

    print("=== M77.19.6.5.2.3 MONTHLY CONTEXT PARITY DIFFERENCE FORENSICS ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("forensic_probe_only: True")
    print("monthly_bundle_count:",len(monthly_files))
    print("baseline_summary:",report["baseline_summary"])
    print("session_cutoff_forensics:",report["session_cutoff_forensics"])
    print("forensic_conclusion:",report["forensic_conclusion"])
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",out)

if __name__=="__main__":
    main()
