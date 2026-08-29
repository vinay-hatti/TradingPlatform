#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,hashlib,json,os,shutil,subprocess,tempfile
from pathlib import Path

VERSION="M77.19.8.7.10.4.2-EXACT-MAIN-DEVELOPMENT-REPLAY-PARITY-HARNESS-1.0"
EXPECTED_ROWS=303689
REQUIRED_FEATURE_IDS=("F020","F021","F030","F031","F070","F080","F081")

class ParityError(RuntimeError): pass

def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)

def resolve(root,p):
    p=Path(p).expanduser()
    return p.resolve() if p.is_absolute() else (root/p).resolve()

def sha256_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""):h.update(c)
    return h.hexdigest()

def atomic_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp");os.close(fd)
    try:
        with open(tmp,"w",encoding="utf-8") as f:
            json.dump(obj,f,indent=2,sort_keys=True);f.write("\n")
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def iter_rows(path):
    with gzip.open(path,"rt",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            if not line.strip():continue
            try:yield json.loads(line)
            except Exception as exc:raise ParityError(f"{path}:{i}: invalid JSONL") from exc

def canonical_row_hash(row):
    b=json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(b).hexdigest()

def compare_symbol_files(expected,actual):
    exp=list(iter_rows(expected));act=list(iter_rows(actual))
    if len(exp)!=len(act):
        return {"equal":False,"expected_rows":len(exp),"actual_rows":len(act),"first_mismatch":"ROW_COUNT"}
    for i,(a,b) in enumerate(zip(exp,act),1):
        if canonical_row_hash(a)!=canonical_row_hash(b):
            return {
                "equal":False,"expected_rows":len(exp),"actual_rows":len(act),
                "first_mismatch":i,
                "expected_identity":{"symbol":a.get("symbol"),"as_of":a.get("as_of")},
                "actual_identity":{"symbol":b.get("symbol"),"as_of":b.get("as_of")},
                "expected_feature_values":a.get("feature_values"),
                "actual_feature_values":b.get("feature_values"),
            }
    return {"equal":True,"expected_rows":len(exp),"actual_rows":len(act),"first_mismatch":None}

# M77.19.8.7.10.4.2.1-PARITY-COVERAGE-EVIDENCE-NORMALIZATION-REPAIR

def _coverage_from_materialized_matrix(files):
    coverage={fid:{"present":0,"missing":0} for fid in REQUIRED_FEATURE_IDS}
    row_count=0
    for p in files:
        for row in iter_rows(p):
            row_count+=1
            values=row.get("feature_values") or {}
            for fid in REQUIRED_FEATURE_IDS:
                v=values.get(fid)
                missing=(v is None)
                if not missing:
                    try:
                        fv=float(v)
                        missing=not (fv==fv and abs(fv)!=float("inf"))
                    except Exception:
                        missing=False
                if missing:
                    coverage[fid]["missing"]+=1
                else:
                    coverage[fid]["present"]+=1
    summary=[]
    for fid in REQUIRED_FEATURE_IDS:
        p=coverage[fid]["present"]
        m=coverage[fid]["missing"]
        den=p+m
        summary.append({
            "feature_id":fid,
            "present":p,
            "missing":m,
            "coverage_pct":(p/den if den else None),
        })
    return row_count,summary

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform")
    ap.add_argument("--call-graph-authority-json",default="reports/m77_19_8_7_10_4_1_exact_callable_invocation_contract_development_parity_authority.json")
    ap.add_argument("--development-backfill-script",default="scripts/run_m77_19_8_4_3_certified_source_resolver_development_feature_backfill_repair.py")
    ap.add_argument("--resolver-authority-json",default="reports/m77_19_8_4_2_reference_price_frozen_daily_source_resolver_authority.json")
    ap.add_argument("--backfill-authority-json",default="reports/m77_19_8_4_blocked_feature_schema_census_development_feature_backfill_authority.json")
    ap.add_argument("--matrix-root",default="research_data/m77_19_8_2/development_only_feature_matrix")
    ap.add_argument("--replay-root",default="research_data/m77_19_7_3_1/point_in_time_stock_intelligence_replay")
    ap.add_argument("--daily-materialization-root",default="research_data/m77_19_7_2/symbol_specific_polygon_replay_materialization")
    ap.add_argument("--certified-development-root",default="research_data/m77_19_8_4_3/development_feature_matrix_certified_backfill")
    ap.add_argument("--output-json",default="reports/m77_19_8_7_10_4_2_exact_main_development_replay_parity_harness.json")
    ap.add_argument("--keep-parity-output",action="store_true")
    a=ap.parse_args();root=Path(a.project_root).resolve()

    cg_p=resolve(root,a.call_graph_authority_json);script=resolve(root,a.development_backfill_script)
    cg=load_json(cg_p)
    if cg.get("status")!="BLOCKED_NO_NON_MAIN_FULL_ROW_CALLABLE":
        raise ParityError("10.4.1 must be BLOCKED_NO_NON_MAIN_FULL_ROW_CALLABLE")
    if cg.get("development_feature_row_count")!=EXPECTED_ROWS:
        raise ParityError("10.4.1 Development row authority changed")
    if cg.get("validation_feature_matrix_materialized") is not False:
        raise ParityError("10.4.1 unexpectedly materialized Validation")
    if cg.get("validation_outcomes_opened") is not False or cg.get("final_holdout_opened") is not False:
        raise ParityError("partition governance violated")
    if sha256_file(script)!=cg.get("development_backfill_script_sha256"):
        raise ParityError("8.4.3 implementation SHA changed after 10.4.1")

    certified_root=resolve(root,a.certified_development_root)
    expected_files=sorted(certified_root.glob("*.jsonl.gz"))
    if not expected_files:raise ParityError("certified Development matrix missing")
    expected_symbols={p.name:p for p in expected_files}

    # Exact invocation contract: rerun the SHA-pinned 8.4.3 CLI main() with the
    # same Development-only input authorities and source roots used originally.
    # Only output destinations are redirected to an isolated temporary directory.
    tmp_base=Path(tempfile.mkdtemp(prefix="m77_19_8_7_10_4_2_",dir=str(root/"research_data")))
    parity_root=tmp_base/"development_feature_matrix_certified_backfill"
    parity_report=tmp_base/"m77_19_8_4_3_parity_report.json"
    parity_csv=tmp_base/"m77_19_8_4_3_parity_coverage.csv"

    cmd=[
        str(root/".venv/bin/python") if (root/".venv/bin/python").exists() else "python",
        str(script),
        "--project-root",str(root),
        "--resolver-authority-json",str(resolve(root,a.resolver_authority_json)),
        "--backfill-authority-json",str(resolve(root,a.backfill_authority_json)),
        "--matrix-root",str(resolve(root,a.matrix_root)),
        "--replay-root",str(resolve(root,a.replay_root)),
        "--daily-materialization-root",str(resolve(root,a.daily_materialization_root)),
        "--output-root",str(parity_root),
        "--output-json",str(parity_report),
        "--output-csv",str(parity_csv),
    ]

    proc=subprocess.run(cmd,cwd=root,text=True,capture_output=True)
    if proc.returncode!=0:
        report={
            "version":VERSION,"status":"BLOCKED_EXACT_MAIN_REPLAY_EXECUTION_FAILED",
            "development_backfill_script_sha256":sha256_file(script),
            "command_without_output_paths":[x for x in cmd if str(tmp_base) not in x],
            "returncode":proc.returncode,
            "stdout_tail":proc.stdout[-8000:],
            "stderr_tail":proc.stderr[-8000:],
            "development_parity_certified":False,
            "validation_data_opened":False,"final_holdout_opened":False,
            "production_authority_effect":False,
            "next_step":"REVIEW_M77_19_8_7_10_4_2_EXACT_MAIN_REPLAY_EXECUTION_FAILURE",
        }
        atomic_json(resolve(root,a.output_json),report)
        if not a.keep_parity_output:shutil.rmtree(tmp_base,ignore_errors=True)
        print("=== M77.19.8.7.10.4.2 EXACT MAIN DEVELOPMENT REPLAY PARITY HARNESS ===")
        print("status: BLOCKED_EXACT_MAIN_REPLAY_EXECUTION_FAILED")
        print("returncode:",proc.returncode)
        print("development_parity_certified: False")
        print("validation_data_opened: False")
        print("final_holdout_opened: False")
        print("production_authority_effect: False")
        print("report:",resolve(root,a.output_json))
        return 0

    actual_files=sorted(parity_root.glob("*.jsonl.gz"))
    actual_symbols={p.name:p for p in actual_files}
    missing=sorted(set(expected_symbols)-set(actual_symbols))
    extra=sorted(set(actual_symbols)-set(expected_symbols))
    comparisons=[]
    total_expected=0;total_actual=0;mismatch_symbols=[]
    for name in sorted(set(expected_symbols)&set(actual_symbols)):
        cmp=compare_symbol_files(expected_symbols[name],actual_symbols[name])
        cmp["file"]=name
        comparisons.append(cmp)
        total_expected+=cmp["expected_rows"];total_actual+=cmp["actual_rows"]
        if not cmp["equal"]:mismatch_symbols.append(name[:-9])

    exact=(
        not missing and not extra and not mismatch_symbols and
        total_expected==EXPECTED_ROWS and total_actual==EXPECTED_ROWS
    )

    # M77.19.8.7.10.4.2.1:
    # Derive coverage from the regenerated matrix itself. The prior version read
    # coverage_summary from the 8.4.3 report using one assumed JSON shape even
    # though the regenerated matrix already matched certified Development rows
    # exactly. Matrix-derived coverage is authoritative here.
    coverage_row_count,coverage_summary=_coverage_from_materialized_matrix(actual_files)
    if coverage_row_count!=total_actual:
        raise ParityError(
            f"coverage row-count mismatch: coverage={coverage_row_count} actual={total_actual}"
        )
    required_coverage_ok=all(
        int(rec["present"])==EXPECTED_ROWS and int(rec["missing"])==0
        for rec in coverage_summary
    )

    certified=bool(exact and required_coverage_ok)
    status="READY" if certified else "BLOCKED_DEVELOPMENT_REPLAY_PARITY_MISMATCH"
    report={
        "version":VERSION,"status":status,
        "call_graph_authority_sha256":sha256_file(cg_p),
        "development_backfill_script_sha256":sha256_file(script),
        "exact_main_cli_invocation_contract_certified":certified,
        "development_parity_execution_performed":True,
        "development_parity_certified":certified,
        "expected_symbol_file_count":len(expected_symbols),
        "actual_symbol_file_count":len(actual_symbols),
        "expected_row_count":total_expected,
        "actual_row_count":total_actual,
        "missing_symbol_files":missing,
        "extra_symbol_files":extra,
        "mismatch_symbol_count":len(mismatch_symbols),
        "mismatch_symbols":mismatch_symbols,
        "required_feature_coverage_zero_missing":required_coverage_ok,
        "required_feature_coverage_source":"REGENERATED_MATRIX_DIRECT_SCAN",
        "required_feature_coverage_summary":coverage_summary,
        "required_feature_ids":list(REQUIRED_FEATURE_IDS),
        "feature_formula_reimplementation_performed":False,
        "semantic_equivalent_rewrite_performed":False,
        "validation_feature_matrix_materialized":False,
        "validation_targets_opened":False,
        "validation_outcomes_opened":False,
        "validation_scoring_performed":False,
        "final_holdout_opened":False,
        "production_authority_effect":False,
        "parity_output_retained":bool(a.keep_parity_output),
        "parity_output_root":str(parity_root) if a.keep_parity_output else None,
        "next_step":(
            "BUILD_M77_19_8_7_10_5_EXACT_MAIN_REUSE_VALIDATION_FEATURE_MATRIX_MATERIALIZATION"
            if certified else
            "REVIEW_M77_19_8_7_10_4_2_DEVELOPMENT_PARITY_MISMATCH"
        ),
    }
    atomic_json(resolve(root,a.output_json),report)
    if not a.keep_parity_output:shutil.rmtree(tmp_base,ignore_errors=True)

    print("=== M77.19.8.7.10.4.2 EXACT MAIN DEVELOPMENT REPLAY PARITY HARNESS ===")
    print("status:",status)
    print("development_backfill_script_sha256:",sha256_file(script))
    print("expected_symbol_file_count:",len(expected_symbols))
    print("actual_symbol_file_count:",len(actual_symbols))
    print("expected_row_count:",total_expected)
    print("actual_row_count:",total_actual)
    print("missing_symbol_file_count:",len(missing))
    print("extra_symbol_file_count:",len(extra))
    print("mismatch_symbol_count:",len(mismatch_symbols))
    for rec in coverage_summary:
        print(f"{rec['feature_id']}: present={rec['present']} missing={rec['missing']} coverage_pct={rec['coverage_pct']}")
    print("required_feature_coverage_source: REGENERATED_MATRIX_DIRECT_SCAN")
    print("required_feature_coverage_zero_missing:",required_coverage_ok)
    print("exact_main_cli_invocation_contract_certified:",certified)
    print("development_parity_execution_performed: True")
    print("development_parity_certified:",certified)
    print("feature_formula_reimplementation_performed: False")
    print("semantic_equivalent_rewrite_performed: False")
    print("validation_feature_matrix_materialized: False")
    print("validation_targets_opened: False")
    print("validation_outcomes_opened: False")
    print("validation_scoring_performed: False")
    print("final_holdout_opened: False")
    print("production_authority_effect: False")
    print("next_step:",report["next_step"])
    print("report:",resolve(root,a.output_json))
    return 0

if __name__=="__main__":raise SystemExit(main())
