#!/usr/bin/env python3
from __future__ import annotations

import argparse, contextlib, dataclasses, datetime as dt, hashlib, importlib.util, json, math
from collections import Counter
from pathlib import Path
from statistics import mean, median
from typing import Any, Mapping

VERSION="M77.19.6.5.2.3.1-MONTHLY-FORENSIC-PROBE-SEMANTIC-ADAPTER-REPAIR-1.0"
NATIVE_RUNNER_REL="scripts/run_m77_19_6_isolated_replay_engine_parity.py"
EXPECTED_NATIVE_RUNNER_SHA256="bcc5b49b87ddceba6ac417000d5af3d4a57efd14145595f4d712eb36ae81204b"
EXPECTED_522_REPORT_SHA256="704b6e70892247ed85e99d2ddc7c8a0ce2b5636c2e373c81398bd7b7755ab0d8"
EXPECTED_523_REPORT_SHA256=None  # deliberately not pinned: user-supplied forensic artifact is diagnosed structurally
NUMERIC_TOLERANCE=1e-9
MAX_SESSION_BACKTRACK=8

def load_json(p:Path): return json.loads(p.read_text())
def sha256_file(p:Path): return hashlib.sha256(p.read_bytes()).hexdigest()

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

def spy_sessions():
    from sqlalchemy import text
    with readonly_session() as s:
        rows=s.execute(text("SELECT date FROM public.price_history WHERE symbol='SPY' ORDER BY date")).all()
    out=[]
    for (v,) in rows:
        if isinstance(v,dt.datetime): v=v.date()
        elif not isinstance(v,dt.date): v=dt.date.fromisoformat(str(v)[:10])
        out.append(v)
    return sorted(set(out))

def import_native(root:Path):
    p=root/NATIVE_RUNNER_REL
    actual=sha256_file(p)
    if actual!=EXPECTED_NATIVE_RUNNER_SHA256:
        raise SystemExit(f"FAIL CLOSED: native runner SHA drift: {actual}")
    spec=importlib.util.spec_from_file_location("m77_native_5231",p)
    if spec is None or spec.loader is None: raise SystemExit("FAIL CLOSED: native runner import unavailable")
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    for name in ("call_profile","compare_profile","StockIntelligenceService"):
        if not hasattr(m,name): raise SystemExit(f"FAIL CLOSED: native runner missing {name}")
    return m

def require_522(root:Path):
    p=root/"reports/m77_19_6_5_2_2_native_compare_profile_parity_certification.json"
    if not p.exists(): raise SystemExit("FAIL CLOSED: M77.19.6.5.2.2 report missing")
    actual=sha256_file(p)
    if actual!=EXPECTED_522_REPORT_SHA256:
        raise SystemExit(f"FAIL CLOSED: M77.19.6.5.2.2 report SHA drift: {actual}")
    return p,load_json(p)

def require_523(root:Path):
    p=root/"reports/m77_19_6_5_2_3_monthly_context_parity_difference_forensics.json"
    if not p.exists(): raise SystemExit("FAIL CLOSED: M77.19.6.5.2.3 report missing")
    d=load_json(p)
    if d.get("baseline_summary",{}).get("comparison_count")!=0:
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.3 is not the diagnosed zero-comparison artifact")
    recs=d.get("records",[])
    if len(recs)!=48: raise SystemExit("FAIL CLOSED: expected 48 M77.19.6.5.2.3 records")
    nominal=[]
    for r in recs:
        c=next((x for x in r.get("candidates",[]) if x.get("session_backtrack")==0),None)
        if c: nominal.append((c.get("error"),c.get("message")))
    if len(nominal)!=48 or any(x!=("AttributeError","'OpportunityScores' object has no attribute 'overall_score'") for x in nominal):
        raise SystemExit("FAIL CLOSED: M77.19.6.5.2.3 failure signature differs from diagnosed adapter defect")
    return p,d

def find_monthly_summary(obj:Any):
    if isinstance(obj,Mapping):
        for k,v in obj.items():
            if str(k).upper()=="MONTHLY" and isinstance(v,Mapping) and "direction_match_pct" in v:
                return dict(v)
        for v in obj.values():
            got=find_monthly_summary(v)
            if got is not None: return got
    elif isinstance(obj,list):
        for v in obj:
            got=find_monthly_summary(v)
            if got is not None: return got
    return None

def normalize_rows(bundle):
    rows=[]
    for raw in bundle["price_history"]:
        low={str(k).lower():v for k,v in raw.items()}
        dv=low.get("date") or low.get("session_date") or low.get("price_date") or low.get("bar_date") or low.get("as_of")
        if dv is None: continue
        if isinstance(dv,dt.datetime): dv=dv.date()
        elif not isinstance(dv,dt.date): dv=dt.date.fromisoformat(str(dv)[:10])
        def f(n):
            v=low.get(n); return None if v in (None,"") else float(v)
        row={"date":dv,"open":f("open"),"high":f("high"),"low":f("low"),"close":f("close"),"volume":f("volume")}
        if row["close"] is not None: rows.append(row)
    rows.sort(key=lambda x:x["date"])
    return rows

def frozen_semantic(f):
    return {"direction":str(f["direction"]),"overall_score":float(f["overall_score"]),
            "confidence":float(f["confidence"]),"primary_category":str(f.get("primary_category",""))}

def to_mapping(obj):
    if dataclasses.is_dataclass(obj): return dataclasses.asdict(obj)
    if isinstance(obj,Mapping): return dict(obj)
    if hasattr(obj,"model_dump"):
        try: return obj.model_dump()
        except Exception: pass
    if hasattr(obj,"__dict__"): return {k:v for k,v in vars(obj).items() if not k.startswith("_")}
    return obj

def flatten(obj:Any,prefix=()):
    obj=to_mapping(obj)
    out={}
    if isinstance(obj,Mapping):
        for k,v in obj.items(): out.update(flatten(v,prefix+(str(k),)))
    elif isinstance(obj,(list,tuple)):
        for i,v in enumerate(obj): out.update(flatten(v,prefix+(str(i),)))
    elif isinstance(obj,(str,int,float,bool)) or obj is None:
        out[prefix]=obj
    return out

ALIASES={
    "direction":{"direction"},
    "confidence":{"confidence"},
    "primary_category":{"primary_category"},
    "overall_score":{"overall_score","total_score","composite_score","score"},
}

def terminal_candidates(flatmaps,field):
    common=None
    for fm in flatmaps:
        paths={p for p in fm if p and p[-1].lower() in ALIASES[field]}
        common=paths if common is None else common & paths
    return sorted(common or [])

def value_at(fm,path): return fm[path]

def aggregate_for_path(field,path,flatmaps,stored):
    vals=[value_at(fm,path) for fm in flatmaps]
    if field in ("direction","primary_category"):
        pct=100.0*sum(str(v)==str(s[field]) for v,s in zip(vals,stored))/len(vals)
        return {"match_pct":pct}
    diffs=[float(v)-float(s[field]) for v,s in zip(vals,stored)]
    return {"max_abs_error":max(abs(x) for x in diffs),"mean_signed_error":mean(diffs)}

def close(a,b,tol=1e-10): return abs(float(a)-float(b))<=tol

def certify_adapter(flatmaps,stored,m77_522_monthly):
    targets={
        "direction":("match_pct",float(m77_522_monthly["direction_match_pct"])),
        "primary_category":("match_pct",float(m77_522_monthly["primary_category_match_pct"])),
        "overall_score":("max_abs_error",float(m77_522_monthly["max_score_abs_error"])),
        "confidence":("max_abs_error",float(m77_522_monthly["max_confidence_abs_error"])),
    }
    adapter={}; evidence={}
    for field in ("direction","primary_category","overall_score","confidence"):
        candidates=terminal_candidates(flatmaps,field)
        qualified=[]
        for path in candidates:
            try: agg=aggregate_for_path(field,path,flatmaps,stored)
            except Exception: continue
            key,target=targets[field]
            if close(agg[key],target):
                qualified.append((path,agg))
        evidence[field]={
            "candidate_paths":[".".join(p) for p in candidates],
            "qualified_paths":[".".join(p) for p,_ in qualified],
            "target_metric":targets[field][0],
            "target_value":targets[field][1],
        }
        if len(qualified)!=1:
            raise RuntimeError(f"FAIL CLOSED: semantic adapter field {field} is ambiguous/unresolved: {evidence[field]}")
        adapter[field]=qualified[0][0]
        evidence[field]["certified_aggregate"]=qualified[0][1]
    return adapter,evidence

def semantic_from_flat(fm,adapter):
    return {k:(float(fm[p]) if k in ("overall_score","confidence") else str(fm[p])) for k,p in adapter.items()}

def err(iso,st):
    return {
        "direction_match":iso["direction"]==st["direction"],
        "primary_category_match":iso["primary_category"]==st["primary_category"],
        "score_signed_error":iso["overall_score"]-st["overall_score"],
        "score_abs_error":abs(iso["overall_score"]-st["overall_score"]),
        "confidence_signed_error":iso["confidence"]-st["confidence"],
        "confidence_abs_error":abs(iso["confidence"]-st["confidence"]),
    }

def exact(e):
    return e["direction_match"] and e["primary_category_match"] and e["score_abs_error"]<=NUMERIC_TOLERANCE and e["confidence_abs_error"]<=NUMERIC_TOLERANCE

def candidate_sessions(nominal,sessions):
    return list(reversed([s for s in sessions if s<=nominal][-(MAX_SESSION_BACKTRACK+1):]))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=".")
    ap.add_argument("--bundle-root",default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles")
    ap.add_argument("--output",default="reports/m77_19_6_5_2_3_1_monthly_forensic_probe_semantic_adapter_repair.json")
    a=ap.parse_args()
    root=Path(a.project_root).resolve()
    p522,d522=require_522(root); p523,d523=require_523(root)
    monthly_summary=find_monthly_summary(d522)
    if monthly_summary is None: raise SystemExit("FAIL CLOSED: MONTHLY summary not found in M77.19.6.5.2.2")
    native=import_native(root); svc=native.StockIntelligenceService()
    sessions=spy_sessions(); session_set=set(sessions)
    files=sorted((root/a.bundle_root/"monthly").glob("*.json"))
    if len(files)!=48: raise SystemExit(f"FAIL CLOSED: expected 48 monthly bundles, found {len(files)}")

    prepared=[]; nominal_profiles=[]; nominal_flats=[]; stored=[]
    for fp in files:
        b=load_json(fp); ident=b["prediction_identity"]; rows=normalize_rows(b)
        nominal=dt.date.fromisoformat(str(ident["as_of"])[:10])
        profile=native.call_profile(svc,str(ident["symbol"]),rows,nominal,session_set,300,750)
        if profile is None: raise SystemExit(f"FAIL CLOSED: nominal native profile ineligible for {ident['symbol']}")
        fm=flatten(profile)
        prepared.append((fp,b,ident,rows,nominal))
        nominal_profiles.append(profile); nominal_flats.append(fm); stored.append(frozen_semantic(b["frozen_output"]))

    adapter,evidence=certify_adapter(nominal_flats,stored,monthly_summary)

    records=[]
    for (fp,b,ident,rows,nominal),st in zip(prepared,stored):
        candidates=[]
        for rank,cutoff in enumerate(candidate_sessions(nominal,sessions)):
            cut_rows=[r for r in rows if r["date"]<=cutoff]
            if not cut_rows: continue
            try:
                # Preserve the MONTHLY evaluation date so native monthly eligibility remains valid.
                # Vary only the visible input-session cutoff.
                profile=native.call_profile(svc,str(ident["symbol"]),cut_rows,nominal,session_set,300,750)
                if profile is None: raise RuntimeError("native profile not eligible")
                sem=semantic_from_flat(flatten(profile),adapter)
                e=err(sem,st)
                candidates.append({"session_backtrack":rank,"candidate_input_cutoff":cutoff.isoformat(),
                    "evaluation_as_of":nominal.isoformat(),"input_row_count":len(cut_rows),
                    "input_last_date":cut_rows[-1]["date"].isoformat(),"isolated_semantic":sem,**e,
                    "exact_semantic_match":exact(e)})
            except Exception as exc:
                candidates.append({"session_backtrack":rank,"candidate_input_cutoff":cutoff.isoformat(),
                    "evaluation_as_of":nominal.isoformat(),"error":type(exc).__name__,"message":str(exc)[:1000],
                    "exact_semantic_match":False})
        valid=[c for c in candidates if "error" not in c]
        baseline=next((c for c in valid if c["session_backtrack"]==0),None)
        best=min(valid,key=lambda c:(0 if c["direction_match"] else 1,0 if c["primary_category_match"] else 1,
                                    c["confidence_abs_error"],c["score_abs_error"],c["session_backtrack"])) if valid else None
        records.append({"bundle":str(fp.relative_to(root)),"symbol":str(ident["symbol"]),
            "nominal_as_of":nominal.isoformat(),"stored_semantic":st,"baseline":baseline,"best_candidate":best,
            "exact_candidate_found":any(c.get("exact_semantic_match") for c in valid),"candidates":candidates})

    baselines=[r["baseline"] for r in records if r["baseline"]]
    if len(baselines)!=48: raise SystemExit(f"FAIL CLOSED: repaired baseline comparisons incomplete: {len(baselines)}/48")
    # Independent guard: repaired nominal aggregate MUST reproduce M77.19.6.5.2.2 monthly authority.
    got={
        "direction_match_pct":100*sum(c["direction_match"] for c in baselines)/48,
        "primary_category_match_pct":100*sum(c["primary_category_match"] for c in baselines)/48,
        "max_score_abs_error":max(c["score_abs_error"] for c in baselines),
        "max_confidence_abs_error":max(c["confidence_abs_error"] for c in baselines),
    }
    expected={k:float(monthly_summary[k]) for k in got}
    for k in got:
        if not close(got[k],expected[k],1e-9):
            raise SystemExit(f"FAIL CLOSED: repaired nominal aggregate does not reproduce 5.2.2 {k}: got={got[k]} expected={expected[k]}")

    exacts=[r for r in records if r["exact_candidate_found"]]
    bests=[r["best_candidate"] for r in records if r["best_candidate"]]
    all_exact=len(exacts)==48
    if all_exact:
        conclusion="MONTHLY_PARITY_ROOT_CAUSE_EXPLAINED_BY_INPUT_SESSION_CUTOFF_CONTEXT"
        next_step="BUILD_M77_19_6_5_2_4_GOVERNED_MONTHLY_CONTEXT_PARITY_CERTIFICATION"
    elif exacts:
        conclusion="MONTHLY_PARITY_PARTIALLY_EXPLAINED_BY_INPUT_SESSION_CUTOFF_CONTEXT"
        next_step="BUILD_M77_19_6_5_2_4_MONTHLY_FEATURE_CONFIDENCE_COMPONENT_FORENSICS"
    else:
        conclusion="MONTHLY_PARITY_NOT_EXPLAINED_BY_INPUT_SESSION_CUTOFF_CONTEXT"
        next_step="BUILD_M77_19_6_5_2_4_MONTHLY_FEATURE_CONFIDENCE_COMPONENT_FORENSICS"

    report={
        "version":VERSION,
        "governance":{"research_only":True,"forensic_probe_only":True,"database_mode":"READ_ONLY_SPY_SESSION_CALENDAR_ONLY",
            "production_database_writes":False,"parity_thresholds_relaxed":False,"numeric_tolerance":NUMERIC_TOLERANCE,
            "controlled_exact_input_parity_certified":False,"full_23_year_reconstruction_authorized":False,
            "production_authority_effect":False},
        "diagnosis_of_m77_19_6_5_2_3":{"valid_forensic_conclusion":False,
            "reason":"ZERO_BASELINE_COMPARISONS_CAUSED_BY_SEMANTIC_ADAPTER_ATTRIBUTEERROR",
            "observed_comparison_count":d523["baseline_summary"]["comparison_count"]},
        "source_522_report":str(p522),"source_523_report":str(p523),
        "native_semantic_adapter":{"certified":True,
            "paths":{k:".".join(v) for k,v in adapter.items()},"evidence":evidence},
        "repaired_nominal_authority_reproduction":{"expected":expected,"observed":got,"pass":True},
        "monthly_bundle_count":48,"records":records,
        "session_cutoff_forensics":{"exact_candidate_count":len(exacts),
            "exact_candidate_symbols":[r["symbol"] for r in exacts],
            "best_candidate_backtrack_distribution":dict(sorted(Counter(int(c["session_backtrack"]) for c in bests).items())),
            "all_monthly_exact_match_recovered_by_input_session_cutoff":all_exact},
        "forensic_conclusion":conclusion,
        "controlled_exact_input_parity_certified":False,
        "full_23_year_reconstruction_authorized":False,
        "production_authority_effect":False,
        "next_step":next_step,
    }
    out=root/a.output; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")
    print("=== M77.19.6.5.2.3.1 MONTHLY FORENSIC PROBE SEMANTIC ADAPTER REPAIR ===")
    print("m77_19_6_5_2_3_conclusion_valid: False")
    print("diagnosed_reason: ZERO_BASELINE_COMPARISONS_CAUSED_BY_SEMANTIC_ADAPTER_ATTRIBUTEERROR")
    print("native_semantic_adapter:",report["native_semantic_adapter"]["paths"])
    print("repaired_nominal_authority_reproduction:",report["repaired_nominal_authority_reproduction"])
    print("session_cutoff_forensics:",report["session_cutoff_forensics"])
    print("forensic_conclusion:",conclusion)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    print("next_step:",next_step)
    print("report:",out)

if __name__=="__main__": main()
