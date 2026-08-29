#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any, Mapping

VERSION = "M77.19.6.5.2.2-NATIVE-COMPARE-PROFILE-PARITY-CERTIFICATION-1.0"
CADENCES = ("DAILY","WEEKLY","MONTHLY")
NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
EXPECTED_FORENSIC_REPORT_SHA256 = "c4d7064429bd80df65f9d3b606317a479b2d131526a38b05ba9115dd00668964"
NUMERIC_TOLERANCE = 1e-9
REQUIRED_MATCH_PCT = 100.0

def load_json(path: Path) -> Any:
    return json.loads(path.read_text())

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def require_forensic(root: Path, explicit: str|None):
    candidates=[Path(explicit)] if explicit else []
    candidates.append(root/"reports/m77_19_6_5_2_1_native_output_schema_compare_contract_forensics.json")
    for p in candidates:
        if not p.exists():
            continue
        actual=sha256_file(p)
        if actual != EXPECTED_FORENSIC_REPORT_SHA256:
            raise SystemExit(f"FAIL CLOSED: forensic report SHA drift: {actual}")
        d=load_json(p)
        if d.get("native_output_schema_resolved") is not True:
            raise SystemExit("FAIL CLOSED: native output schema was not resolved")
        if d.get("next_step") != "BUILD_M77_19_6_5_2_2_NATIVE_COMPARE_PROFILE_PARITY_CERTIFICATION":
            raise SystemExit("FAIL CLOSED: forensic report does not authorize M77.19.6.5.2.2")
        if d.get("controlled_exact_input_parity_certified") is True:
            raise SystemExit("FAIL CLOSED: prior forensic report unexpectedly certified parity")
        return p,d
    raise SystemExit("FAIL CLOSED: M77.19.6.5.2.1 forensic report not found")

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

def load_spy_session_set():
    from sqlalchemy import text
    with readonly_session() as s:
        rows=s.execute(text("SELECT date FROM public.price_history WHERE symbol='SPY' ORDER BY date")).all()
    out=set()
    for (v,) in rows:
        if isinstance(v,dt.datetime): v=v.date()
        elif not isinstance(v,dt.date): v=dt.date.fromisoformat(str(v)[:10])
        out.add(v)
    return out

def import_native(root: Path, forensic: Mapping[str,Any]):
    p=root/NATIVE_RUNNER_REL
    actual=sha256_file(p)
    if actual != EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")
    spec=importlib.util.spec_from_file_location("m77_native_522",p)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("call_profile","compare_profile","StockIntelligenceService"):
        if not hasattr(mod,name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")
    import inspect
    if inspect.getsource(mod.compare_profile) != forensic.get("native_compare_profile_source"):
        raise SystemExit("FAIL CLOSED: native compare_profile source differs from certified forensic report")
    return mod

def normalize_bundle_rows(bundle):
    rows=[]
    for raw in bundle["price_history"]:
        low={str(k).lower():v for k,v in raw.items()}
        dv=low.get("date") or low.get("session_date") or low.get("price_date") or low.get("bar_date") or low.get("as_of")
        if dv is None:
            continue
        if isinstance(dv,dt.datetime): dv=dv.date()
        elif not isinstance(dv,dt.date): dv=dt.date.fromisoformat(str(dv)[:10])
        def f(name):
            v=low.get(name)
            return None if v in (None,"") else float(v)
        row={"date":dv,"open":f("open"),"high":f("high"),"low":f("low"),"close":f("close"),"volume":f("volume")}
        if row["close"] is not None:
            rows.append(row)
    rows.sort(key=lambda x:x["date"])
    return rows

def primary_category_from_profile(profile):
    scores=getattr(profile,"scores",None)
    return str(getattr(scores,"primary_category","") if scores else "")

def canonical_semantic_projection(direction, overall_score, confidence, primary_category):
    return {
        "confidence": round(float(confidence), 12),
        "direction": str(direction),
        "overall_score": round(float(overall_score), 12),
        "primary_category": str(primary_category),
    }

def semantic_hash(projection):
    raw=json.dumps(projection,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()

def pct(n,d):
    return 0.0 if d == 0 else 100.0*n/d

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=".")
    ap.add_argument("--forensic-report")
    ap.add_argument("--bundle-root",default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles")
    ap.add_argument("--output",default="reports/m77_19_6_5_2_2_native_compare_profile_parity_certification.json")
    a=ap.parse_args()

    root=Path(a.project_root).resolve()
    forensic_path,forensic=require_forensic(root,a.forensic_report)
    native=import_native(root,forensic)
    session_set=load_spy_session_set()
    svc=native.StockIntelligenceService()

    report={
        "version":VERSION,
        "forensic_report":str(forensic_path),
        "governance":{
            "research_only":True,
            "database_mode":"READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes":False,
            "native_compare_profile_invoked_directly":True,
            "numeric_tolerance":NUMERIC_TOLERANCE,
            "required_match_pct":REQUIRED_MATCH_PCT,
            "parity_thresholds_relaxed":False,
            "raw_state_hash_is_diagnostic_not_semantic_gate":True,
            "full_23_year_reconstruction_authorized":False,
            "production_authority_effect":False,
        },
        "cadences":{},
        "blockers":[],
    }

    bundle_root=root/a.bundle_root
    overall_records=[]
    for cadence in CADENCES:
        files=sorted((bundle_root/cadence.lower()).glob("*.json"))
        records=[]
        for fp in files:
            bundle=load_json(fp)
            rows=normalize_bundle_rows(bundle)
            identity=bundle["prediction_identity"]
            frozen=bundle["frozen_output"]
            as_of=dt.date.fromisoformat(str(identity["as_of"])[:10])
            symbol=str(identity["symbol"])
            try:
                first=native.call_profile(svc,symbol,rows,as_of,session_set,300,750)
                second=native.call_profile(svc,symbol,rows,as_of,session_set,300,750)
                if first is None or second is None:
                    raise RuntimeError("native profile not eligible")
                cmp1=native.compare_profile(first,frozen)
                cmp2=native.compare_profile(second,frozen)

                stored_proj=canonical_semantic_projection(
                    frozen["direction"], frozen["overall_score"], frozen["confidence"], frozen.get("primary_category","")
                )
                first_proj=canonical_semantic_projection(
                    cmp1["isolated"]["direction"], cmp1["isolated"]["overall_score"], cmp1["isolated"]["confidence"],
                    primary_category_from_profile(first)
                )
                second_proj=canonical_semantic_projection(
                    cmp2["isolated"]["direction"], cmp2["isolated"]["overall_score"], cmp2["isolated"]["confidence"],
                    primary_category_from_profile(second)
                )

                record={
                    "bundle":str(fp.relative_to(root)),
                    "symbol":symbol,
                    "as_of":str(identity["as_of"]),
                    "direction_match":bool(cmp1["direction_match"]),
                    "primary_category_match":first_proj["primary_category"] == stored_proj["primary_category"],
                    "score_abs_error":float(cmp1["score_abs_error"]),
                    "confidence_abs_error":float(cmp1["confidence_abs_error"]),
                    "raw_state_hash_match":bool(cmp1["state_hash_match"]),
                    "semantic_hash_match":semantic_hash(first_proj) == semantic_hash(stored_proj),
                    "deterministic_repeat_semantic_hash_match":semantic_hash(first_proj) == semantic_hash(second_proj),
                    "stored_semantic":stored_proj,
                    "isolated_semantic":first_proj,
                    "repeat_semantic":second_proj,
                    "stored_semantic_hash":semantic_hash(stored_proj),
                    "isolated_semantic_hash":semantic_hash(first_proj),
                    "repeat_semantic_hash":semantic_hash(second_proj),
                    "stored_state_hash":cmp1["stored"]["state_hash"],
                    "isolated_state_hash":cmp1["isolated"]["state_hash"],
                    "repeat_state_hash":cmp2["isolated"]["state_hash"],
                }
                record["pass"]=(
                    record["direction_match"]
                    and record["primary_category_match"]
                    and record["semantic_hash_match"]
                    and record["deterministic_repeat_semantic_hash_match"]
                    and record["score_abs_error"] <= NUMERIC_TOLERANCE
                    and record["confidence_abs_error"] <= NUMERIC_TOLERANCE
                )
            except Exception as exc:
                record={
                    "bundle":str(fp.relative_to(root)),
                    "symbol":str(identity.get("symbol")),
                    "as_of":str(identity.get("as_of")),
                    "error":type(exc).__name__,
                    "message":str(exc)[:1500],
                    "pass":False,
                }
            records.append(record)
            overall_records.append(record)

        n=len(records)
        ok=[r for r in records if "error" not in r]
        summary={
            "bundle_count":n,
            "comparisons":len(ok),
            "error_count":n-len(ok),
            "direction_match_pct":pct(sum(bool(r.get("direction_match")) for r in ok),len(ok)),
            "primary_category_match_pct":pct(sum(bool(r.get("primary_category_match")) for r in ok),len(ok)),
            "semantic_hash_match_pct":pct(sum(bool(r.get("semantic_hash_match")) for r in ok),len(ok)),
            "deterministic_repeat_pct":pct(sum(bool(r.get("deterministic_repeat_semantic_hash_match")) for r in ok),len(ok)),
            "raw_state_hash_match_pct":pct(sum(bool(r.get("raw_state_hash_match")) for r in ok),len(ok)),
            "max_score_abs_error":max((float(r["score_abs_error"]) for r in ok),default=None),
            "max_confidence_abs_error":max((float(r["confidence_abs_error"]) for r in ok),default=None),
            "failed_record_count":sum(not bool(r.get("pass")) for r in records),
            "records":records,
        }
        summary["pass"]=(
            n > 0 and summary["error_count"] == 0
            and summary["direction_match_pct"] == REQUIRED_MATCH_PCT
            and summary["primary_category_match_pct"] == REQUIRED_MATCH_PCT
            and summary["semantic_hash_match_pct"] == REQUIRED_MATCH_PCT
            and summary["deterministic_repeat_pct"] == REQUIRED_MATCH_PCT
            and summary["max_score_abs_error"] is not None
            and summary["max_score_abs_error"] <= NUMERIC_TOLERANCE
            and summary["max_confidence_abs_error"] is not None
            and summary["max_confidence_abs_error"] <= NUMERIC_TOLERANCE
        )
        report["cadences"][cadence]=summary
        if not summary["pass"]:
            report["blockers"].append(f"{cadence}_STRICT_PARITY_NOT_CERTIFIED")

    report["controlled_exact_input_parity_certified"]=all(report["cadences"].get(c,{}).get("pass") for c in CADENCES)
    report["full_23_year_reconstruction_authorized"]=False
    report["production_authority_effect"]=False
    report["next_step"]=(
        "SEPARATE_AUTHORIZATION_GATE_REQUIRED_FOR_FULL_23_YEAR_RECONSTRUCTION"
        if report["controlled_exact_input_parity_certified"]
        else "FORENSIC_REVIEW_M77_19_6_5_2_2_NATIVE_PARITY_DIFFERENCES"
    )

    out=root/a.output
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")

    print("=== M77.19.6.5.2.2 NATIVE compare_profile PARITY CERTIFICATION ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("native_compare_profile_invoked_directly: True")
    print("required_match_pct:",REQUIRED_MATCH_PCT)
    print("numeric_tolerance:",NUMERIC_TOLERANCE)
    print("parity_thresholds_relaxed: False")
    for cadence in CADENCES:
        s=report["cadences"][cadence]
        print(cadence,{k:s[k] for k in (
            "bundle_count","comparisons","error_count","direction_match_pct",
            "primary_category_match_pct","semantic_hash_match_pct","deterministic_repeat_pct",
            "raw_state_hash_match_pct","max_score_abs_error","max_confidence_abs_error",
            "failed_record_count","pass"
        )})
    print("controlled_exact_input_parity_certified:",report["controlled_exact_input_parity_certified"])
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    if report["blockers"]:
        print("blockers:")
        for b in report["blockers"]: print(" -",b)
    print("next_step:",report["next_step"])
    print("report:",out)

if __name__=="__main__":
    main()
