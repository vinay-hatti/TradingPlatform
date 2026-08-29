#!/usr/bin/env python3
import json
from pathlib import Path
p=Path("reports/m77/m77_18_1_semantic_replication_backlog_refinement.json")
if not p.exists(): raise SystemExit("Run M77.18.1 first")
x=json.loads(p.read_text())
print("=== M77.18.1 SEMANTIC REPLICATION BACKLOG REFINEMENT ===")
print("status:",x["status"])
print("source_audit_summary:",x["source_audit_summary"])
print("long_history_authority:",x["long_history_authority"])
print("p0_frozen_replication_families:",x["p0_frozen_replication_families"])
print("p1_review_families:",x["p1_review_families"])
print("next_step:",x["next_step"])
print("production_authority_effect:",x["production_authority_effect"])
print("\n--- FALSE-POSITIVE EXCLUSIONS ---")
for e in x["false_positive_exclusions"]: print(e)
print("\n--- FAMILY DETAIL ---")
for f in x["families"]:
    print(f'\n{f["family_id"]} {f["name"]}')
    print(" priority:",f["priority"])
    print(" files_found:",f["files_found"],"missing:",len(f["files_missing"]))
    print(" empirical:",f["empirical_file_count"],"runtime/structural:",f["runtime_or_structural_file_count"])
    print(" frozen_hypothesis_recoverable:",f["frozen_hypothesis_recoverable"])
    print(" recommended_action:",f["recommended_action"])
    if f["files_missing"]:
        print(" missing_files:",f["files_missing"])
    for z in f["files"]:
        print("  ",z["path"],"type=",z["semantic_type"])
        if z["python_constants"]: print("    constants=",z["python_constants"])
        if z["json_semantics"]: print("    json=",z["json_semantics"])
