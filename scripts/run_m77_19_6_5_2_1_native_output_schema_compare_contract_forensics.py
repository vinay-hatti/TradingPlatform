#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import importlib.util
import inspect
import json
from pathlib import Path
from typing import Any, Mapping

VERSION = "M77.19.6.5.2.1-NATIVE-OUTPUT-SCHEMA-COMPARE-CONTRACT-FORENSICS-1.0"
CADENCES = ("DAILY","WEEKLY","MONTHLY")
NATIVE_RUNNER_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256 = "bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"

def load_json(path: Path) -> Any:
    return json.loads(path.read_text())

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def jsonable(v: Any) -> Any:
    if dataclasses.is_dataclass(v):
        return jsonable(dataclasses.asdict(v))
    if isinstance(v, Mapping):
        return {str(k):jsonable(x) for k,x in v.items()}
    if isinstance(v,(list,tuple,set)):
        return [jsonable(x) for x in v]
    if isinstance(v,(dt.date,dt.datetime)):
        return v.isoformat()
    if hasattr(v,"value") and not isinstance(v,(str,bytes,int,float,bool)):
        try: return jsonable(v.value)
        except Exception: pass
    if hasattr(v,"__dict__") and not isinstance(v,type):
        try: return jsonable(vars(v))
        except Exception: pass
    return v

def require_prior(root: Path, explicit: str|None):
    candidates=[Path(explicit)] if explicit else []
    candidates.append(root/"reports/m77_19_6_5_2_native_controlled_execution_parity_certification.json")
    for p in candidates:
        if not p.exists(): continue
        d=load_json(p)
        if d.get("next_step")!="FORENSIC_REVIEW_M77_19_6_5_2_NATIVE_PARITY_DIFFERENCES":
            raise SystemExit("FAIL CLOSED: prior report does not request 5.2 forensic review")
        if d.get("full_23_year_reconstruction_authorized") is True:
            raise SystemExit("FAIL CLOSED: unexpected 23-year authorization")
        return p,d
    raise SystemExit("FAIL CLOSED: M77.19.6.5.2 report not found")

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

def import_native(root: Path):
    p=root/NATIVE_RUNNER_REL
    actual=sha256_file(p)
    if actual!=EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")
    spec=importlib.util.spec_from_file_location("m77_native_521",p)
    if spec is None or spec.loader is None:
        raise SystemExit("FAIL CLOSED: native runner import unavailable")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("call_profile","compare_profile","StockIntelligenceService"):
        if not hasattr(mod,name):
            raise SystemExit(f"FAIL CLOSED: native runner missing {name}")
    return mod

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

def structural_shape(v: Any) -> dict[str,Any]:
    result={
        "python_type":f"{type(v).__module__}.{type(v).__qualname__}",
        "is_dataclass":dataclasses.is_dataclass(v),
        "has_dict":hasattr(v,"__dict__"),
    }
    if dataclasses.is_dataclass(v):
        result["dataclass_fields"]=[f.name for f in dataclasses.fields(v)]
    if hasattr(v,"__dict__"):
        result["dict_keys"]=sorted(vars(v).keys())
    j=jsonable(v)
    result["jsonable_type"]=type(j).__name__
    if isinstance(j,Mapping):
        result["jsonable_keys"]=sorted(str(k) for k in j.keys())
        result["jsonable_preview"]={str(k):j[k] for k in list(j)[:50]}
    else:
        result["jsonable_preview"]=j
    return result

def candidate_stored_rows(bundle):
    # Probe several governed shapes; native compare_profile is authoritative.
    frozen=bundle["frozen_output"]
    profile=bundle.get("frozen_profile")
    identity=bundle["prediction_identity"]
    base={
        "symbol":identity.get("symbol"),
        "as_of":identity.get("as_of"),
        "direction":frozen.get("direction"),
        "overall_score":frozen.get("overall_score"),
        "confidence":frozen.get("confidence"),
        "state_hash":frozen.get("state_hash"),
        "profile_json":profile,
        "profile":profile,
    }
    return [
        ("bundle_flattened",base),
        ("frozen_profile",profile if isinstance(profile,Mapping) else {}),
        ("frozen_output",dict(frozen)),
    ]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=".")
    ap.add_argument("--prior-report")
    ap.add_argument("--bundle-root",default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles")
    ap.add_argument("--output",default="reports/m77_19_6_5_2_1_native_output_schema_compare_contract_forensics.json")
    a=ap.parse_args()

    root=Path(a.project_root).resolve()
    prior_path,_=require_prior(root,a.prior_report)
    native=import_native(root)
    session_set=load_spy_session_set()
    svc=native.StockIntelligenceService()

    report={
        "version":VERSION,
        "prior_report":str(prior_path),
        "governance":{
            "research_only":True,
            "database_mode":"READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes":False,
            "parity_thresholds_relaxed":False,
            "forensic_probe_only":True,
            "controlled_exact_input_parity_certified":False,
            "full_23_year_reconstruction_authorized":False,
            "production_authority_effect":False,
        },
        "native_compare_profile_source":inspect.getsource(native.compare_profile),
        "native_call_profile_source":inspect.getsource(native.call_profile),
        "cadences":{},
        "blockers":[],
    }

    bundle_root=root/a.bundle_root
    for cadence in CADENCES:
        files=sorted((bundle_root/cadence.lower()).glob("*.json"))
        if not files:
            report["blockers"].append(f"{cadence}_NO_BUNDLE")
            continue
        bundle=load_json(files[0])
        rows=normalize_bundle_rows(bundle)
        as_of=dt.date.fromisoformat(str(bundle["prediction_identity"]["as_of"])[:10])
        symbol=str(bundle["prediction_identity"]["symbol"])
        first=native.call_profile(svc,symbol,rows,as_of,session_set,300,750)
        second=native.call_profile(svc,symbol,rows,as_of,session_set,300,750)
        if first is None:
            report["blockers"].append(f"{cadence}_PROFILE_NOT_ELIGIBLE")
            report["cadences"][cadence]={"bundle":str(files[0].relative_to(root)),"profile":None}
            continue

        compare_attempts=[]
        for label,stored in candidate_stored_rows(bundle):
            try:
                result=native.compare_profile(first,stored)
                compare_attempts.append({"shape":label,"success":True,"result":jsonable(result)})
            except Exception as exc:
                compare_attempts.append({"shape":label,"success":False,"error":type(exc).__name__,"message":str(exc)[:1000]})

        report["cadences"][cadence]={
            "bundle":str(files[0].relative_to(root)),
            "profile_shape":structural_shape(first),
            "repeat_profile_shape":structural_shape(second),
            "frozen_profile_shape":structural_shape(bundle.get("frozen_profile")),
            "frozen_output":bundle.get("frozen_output"),
            "native_compare_attempts":compare_attempts,
        }

    ready=all(
        c in report["cadences"] and report["cadences"][c].get("profile_shape")
        for c in CADENCES
    )
    report["native_output_schema_resolved"]=bool(ready)
    report["controlled_exact_input_parity_certified"]=False
    report["full_23_year_reconstruction_authorized"]=False
    report["production_authority_effect"]=False
    report["next_step"]="BUILD_M77_19_6_5_2_2_NATIVE_COMPARE_PROFILE_PARITY_CERTIFICATION" if ready else "RESOLVE_M77_19_6_5_2_1_OUTPUT_SCHEMA_BLOCKERS"

    out=root/a.output
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")

    print("=== M77.19.6.5.2.1 NATIVE OUTPUT SCHEMA & COMPARE-CONTRACT FORENSICS ===")
    print("database_mode: READ_ONLY_SPY_SESSION_CALENDAR_ONLY")
    print("parity_thresholds_relaxed: False")
    for cadence in CADENCES:
        c=report["cadences"].get(cadence,{})
        print(cadence,{
            "profile_type":c.get("profile_shape",{}).get("python_type"),
            "profile_keys":c.get("profile_shape",{}).get("jsonable_keys"),
            "compare_attempts":[{"shape":x["shape"],"success":x["success"],"message":x.get("message")} for x in c.get("native_compare_attempts",[])],
        })
    print("native_output_schema_resolved:",report["native_output_schema_resolved"])
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",out)

if __name__=="__main__":
    main()
