#!/usr/bin/env python3
from __future__ import annotations
import argparse,ast,csv,hashlib,json,os,tempfile
from datetime import date,datetime,timezone
from pathlib import Path

VERSION="M77.20.3-PROSPECTIVE-SECTOR-MEMBERSHIP-BENCHMARK-SNAPSHOT-CAPTURE-AUTHORITY-1.0"
EARLIEST_AUTHORIZED_CAPTURE_DATE=date.fromisoformat("2026-08-24")
class CaptureError(RuntimeError):pass

def R(root,p):
    p=Path(p).expanduser();return p.resolve() if p.is_absolute() else (root/p).resolve()
def J(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def H(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()
def semantic_hash(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        Path(tmp).write_bytes(data);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def sector_etfs(path):
    tree=ast.parse(path.read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="SECTOR_ETFS" for t in n.targets):
            x=ast.literal_eval(n.value)
            if isinstance(x,dict):return {str(k):str(v) for k,v in x.items()}
    raise CaptureError("SECTOR_ETFS assignment not found")
def memberships(path):
    out=[]
    with path.open("r",encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if str(r.get("active","True")).strip().lower() not in {"true","1","yes"}:continue
            sym=(r.get("symbol") or "").strip();sec=(r.get("sector") or "").strip()
            if not sym or not sec:continue
            out.append({"symbol":sym,"asset_type":(r.get("asset_type") or "").strip() or None,
                        "sector":sec,"company_name":(r.get("security") or sym).strip(),
                        "source_identity":(r.get("source") or "canonical_universe").strip(),
                        "source_as_of_date":(r.get("as_of_date") or "").strip() or None})
    out.sort(key=lambda x:(x["symbol"],x["sector"]))
    if not out:raise CaptureError("no active symbol-sector memberships found")
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--design-gate-json",default="reports/m77_20_2_external_historical_pit_sector_source_decision_prospective_only_research_design_gate.json")
    ap.add_argument("--canonical-csv",default="data/universe/us_listed_equities_etfs.csv")
    ap.add_argument("--benchmark-source",default="src/trading_ai/market_intelligence/engine.py")
    ap.add_argument("--snapshot-date",default=None)
    ap.add_argument("--output-root",default="research_data/m77_20_3/prospective_sector_snapshots")
    ap.add_argument("--output-json",default="reports/m77_20_3_prospective_sector_membership_benchmark_snapshot_capture_authority.json")
    ap.add_argument("--output-csv",default="reports/m77_20_3_latest_snapshot_summary.csv")
    a=ap.parse_args();root=Path(a.project_root).resolve()
    gp,cp,bp=R(root,a.design_gate_json),R(root,a.canonical_csv),R(root,a.benchmark_source)
    for p in (gp,cp,bp):
        if not p.exists():raise CaptureError(f"required source missing: {p}")
    gate=J(gp)
    if gate.get("status")!="READY":raise CaptureError("M77.20.2 design gate invalid")
    if (gate.get("decision") or {}).get("prospective_only_route_selected") is not True:raise CaptureError("prospective-only route not certified")
    con=gate.get("prospective_capture_contract") or {}
    if con.get("snapshot_immutability_required") is not True or con.get("historical_rewrite_authorized") is not False:raise CaptureError("snapshot immutability contract invalid")
    if con.get("prospective_outcomes_opened") is not False:raise CaptureError("prospective outcomes already opened")

    sd=date.fromisoformat(a.snapshot_date) if a.snapshot_date else datetime.now(timezone.utc).date()
    if sd<EARLIEST_AUTHORIZED_CAPTURE_DATE:raise CaptureError(f"snapshot date {sd} precedes earliest authorized capture date {EARLIEST_AUTHORIZED_CAPTURE_DATE}")

    mem=memberships(cp);mapping=sector_etfs(bp);secs=sorted({x["sector"] for x in mem})
    mapped=sorted(s for s in secs if mapping.get(s));unmapped=sorted(s for s in secs if not mapping.get(s))
    source_hashes={"canonical_csv_sha256":H(cp),"benchmark_source_sha256":H(bp),"design_gate_sha256":H(gp)}

    mrows=[]
    for x in mem:
        r=dict(x);r["snapshot_date"]=sd.isoformat();r["source_record_identity_or_snapshot_hash"]=source_hashes["canonical_csv_sha256"];mrows.append(r)
    brows=[]
    for sec in secs:
        sym=mapping.get(sec)
        brows.append({"sector":sec,"benchmark_symbol":sym or None,"benchmark_status":"AVAILABLE" if sym else "MISSING_NO_GOVERNED_MAPPING",
                      "snapshot_date":sd.isoformat(),"source_identity":"trading_ai.market_intelligence.engine.SECTOR_ETFS",
                      "source_record_identity_or_snapshot_hash":source_hashes["benchmark_source_sha256"]})
    available_symbols=sum(1 for x in mem if mapping.get(x["sector"]))
    missing_symbols=len(mem)-available_symbols

    payload={"version":VERSION,"snapshot_date":sd.isoformat(),"captured_at_utc":datetime.now(timezone.utc).isoformat(),
             "membership_records":mrows,"benchmark_records":brows,"source_hashes":source_hashes,
             "governance":{"prospective_only":True,"retroactive_sector_reclassification_authorized":False,
                           "retroactive_benchmark_substitution_authorized":False,"benchmark_fallback_to_SPY_authorized":False,
                           "unmapped_sector_policy":"EXPLICIT_MISSING_F071_NO_INFERENCE","outcomes_read":False,
                           "F071_materialized":False,"production_authority_effect":False}}
    sh=semantic_hash({k:v for k,v in payload.items() if k!="captured_at_utc"});payload["snapshot_semantic_sha256"]=sh

    outroot=R(root,a.output_root);snap=outroot/sd.isoformat()/"sector_membership_benchmark_snapshot.json"
    if snap.exists():
        old=J(snap)
        if old.get("snapshot_semantic_sha256")!=sh:raise CaptureError(f"IMMUTABILITY_VIOLATION_EXISTING_SNAPSHOT_DIFFERS date={sd}")
        mode="IDEMPOTENT_EXISTING_SNAPSHOT_REUSED";payload=old
    else:
        atomic(snap,json.dumps(payload,indent=2,sort_keys=True).encode()+b"\n");mode="NEW_IMMUTABLE_SNAPSHOT_CAPTURED"

    manifest_path=outroot/"manifest.json"
    manifest={"version":"M77.20.3-PROSPECTIVE-SECTOR-SNAPSHOT-MANIFEST-1.0","snapshots":[]}
    if manifest_path.exists():manifest=J(manifest_path)
    entries={x["snapshot_date"]:x for x in manifest.get("snapshots") or []}
    ent={"snapshot_date":sd.isoformat(),"snapshot_file":str(snap.relative_to(root)),"snapshot_semantic_sha256":payload["snapshot_semantic_sha256"],
         "membership_count":len(mrows),"benchmark_classification_count":len(brows),"benchmark_available_classification_count":len(mapped),
         "benchmark_missing_classification_count":len(unmapped)}
    if sd.isoformat() in entries and entries[sd.isoformat()]!=ent:raise CaptureError("manifest immutability violation")
    entries[sd.isoformat()]=ent;manifest["snapshots"]=[entries[k] for k in sorted(entries)];manifest["latest_snapshot_date"]=max(entries)
    atomic(manifest_path,json.dumps(manifest,indent=2,sort_keys=True).encode()+b"\n")

    srcdates=sorted({x["source_as_of_date"] for x in mrows if x.get("source_as_of_date")})
    report={"version":VERSION,"status":"READY","execution_mode":mode,"snapshot_date":sd.isoformat(),
            "earliest_authorized_capture_date":EARLIEST_AUTHORIZED_CAPTURE_DATE.isoformat(),
            "snapshot_semantic_sha256":payload["snapshot_semantic_sha256"],"membership_count":len(mrows),
            "sector_classification_count":len(secs),"benchmark_available_classification_count":len(mapped),
            "benchmark_missing_classification_count":len(unmapped),"benchmark_available_symbol_membership_count":available_symbols,
            "benchmark_missing_symbol_membership_count":missing_symbols,"benchmark_available_classifications":mapped,
            "benchmark_missing_classifications":unmapped,"membership_source_as_of_dates":srcdates,
            "retroactive_snapshots_materialized":False,"snapshot_immutability_certified":True,
            "idempotent_same_content_rerun_allowed":True,"different_content_same_date_rewrite_authorized":False,
            "unmapped_sector_policy":"EXPLICIT_MISSING_F071_NO_INFERENCE","benchmark_fallback_to_SPY_performed":False,
            "prospective_membership_snapshot_capture_started":True,"prospective_benchmark_snapshot_capture_started":True,
            "prospective_membership_snapshot_capture_certified":True,"prospective_benchmark_snapshot_capture_certified":True,
            "prospective_F071_materialized":False,"prospective_outcomes_opened":False,"prospective_scoring_performed":False,
            "production_authority_effect":False,"snapshot_file":str(snap.relative_to(root)),"manifest_file":str(manifest_path.relative_to(root)),
            "next_step":"BUILD_M77_20_4_PROSPECTIVE_F071_FEATURE_MATERIALIZATION_AND_IMMUTABLE_SHADOW_CAPTURE_AUTHORITY"}
    oj,oc=R(root,a.output_json),R(root,a.output_csv);oj.parent.mkdir(parents=True,exist_ok=True)
    atomic(oj,json.dumps(report,indent=2,sort_keys=True).encode()+b"\n")
    with oc.open("w",encoding="utf-8",newline="") as f:
        fields=["snapshot_date","membership_count","sector_classification_count","benchmark_available_classification_count",
                "benchmark_missing_classification_count","benchmark_available_symbol_membership_count","benchmark_missing_symbol_membership_count",
                "snapshot_semantic_sha256","execution_mode"]
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerow({k:report[k] for k in fields})

    print("=== M77.20.3 PROSPECTIVE SECTOR MEMBERSHIP & BENCHMARK SNAPSHOT CAPTURE AUTHORITY ===")
    print("status: READY");print("execution_mode:",mode);print("snapshot_date:",sd.isoformat())
    print("earliest_authorized_capture_date:",EARLIEST_AUTHORIZED_CAPTURE_DATE.isoformat())
    print("membership_count:",len(mrows));print("sector_classification_count:",len(secs))
    print("benchmark_available_classification_count:",len(mapped));print("benchmark_missing_classification_count:",len(unmapped))
    print("benchmark_available_symbol_membership_count:",available_symbols);print("benchmark_missing_symbol_membership_count:",missing_symbols)
    print("membership_source_as_of_dates:",srcdates);print("retroactive_snapshots_materialized: False")
    print("snapshot_immutability_certified: True");print("unmapped_sector_policy: EXPLICIT_MISSING_F071_NO_INFERENCE")
    print("benchmark_fallback_to_SPY_performed: False");print("prospective_membership_snapshot_capture_certified: True")
    print("prospective_benchmark_snapshot_capture_certified: True");print("prospective_F071_materialized: False")
    print("prospective_outcomes_opened: False");print("production_authority_effect: False");print("next_step:",report["next_step"])
    print("report:",oj);print("csv:",oc);print("snapshot:",snap);print("manifest:",manifest_path)
if __name__=="__main__":main()
