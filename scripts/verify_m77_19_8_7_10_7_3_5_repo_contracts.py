#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, json
from pathlib import Path
class AuditError(RuntimeError): pass
def load_json(p):
    with Path(p).open("r",encoding="utf-8") as f:return json.load(f)
def resolve(root,p):
    p=Path(p);return p if p.is_absolute() else root/p
def function_signature_from_ast(path,name):
    tree=ast.parse(Path(path).read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name:
            return [a.arg for a in n.args.args]
    return None
def class_methods_from_ast(path,name):
    tree=ast.parse(Path(path).read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n,ast.ClassDef) and n.name==name:
            return [x.name for x in n.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))]
    return []
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--project-root",default="/Users/vinay.hatti/TradingPlatform");a=ap.parse_args();root=Path(a.project_root).resolve()
    p85=resolve(root,"reports/m77_19_8_5_structured_feature_field_whitelist_development_target_matrix_authority.json")
    p86=resolve(root,"reports/m77_19_8_6_structured_feature_materialization_development_model_training_preregistration_gate.json")
    p106=resolve(root,"reports/m77_19_8_7_10_6_frozen_development_preprocessor_validation_target_materialization_authority.json")
    p25=resolve(root,"reports/m77_19_8_7_10_7_2_5_combined_mf1_mf2_exact_invocation_authority.json")
    mf1=resolve(root,"scripts/run_m77_19_8_7_development_only_structured_training_matrix_walk_forward_model_family_evaluation.py")
    mf2=resolve(root,"scripts/run_m77_19_8_7_8_mf2_only_development_walk_forward_completion_checkpoint_reuse.py")
    runtime=resolve(root,"src/trading_ai/research/m77/m77_19_8_7_4_certified_solvers.py")
    for p in (p85,p86,p106,p25,mf1,mf2,runtime):
        if not p.exists():raise AuditError(f"required repo contract missing: {p}")
    a85=load_json(p85);a86=load_json(p86);a106=load_json(p106);a25=load_json(p25)
    hs=(a85.get("target_matrix") or {}).get("horizon_summary")
    if a85.get("status")!="READY" or not isinstance(hs,dict) or set(hs)!={"5","10","20"}:raise AuditError("8.5 schema mismatch")
    if a86.get("status")!="READY" or not isinstance(a86.get("structured_columns"),list) or not a86["structured_columns"]:raise AuditError("8.6 schema mismatch")
    summary=a106.get("target_horizon_summary")
    if a106.get("status")!="READY" or not isinstance(summary,list) or sorted(x.get("horizon") for x in summary)!=[5,10,20]:raise AuditError("10.6 schema mismatch")
    if a106.get("validation_targets_materialized") is not True:raise AuditError("10.6 targets not materialized")
    if a25.get("status")!="READY" or a25.get("combined_exact_invocation_authority_certified") is not True:raise AuditError("10.7.2.5 invalid")
    sig=function_signature_from_ast(mf1,"evaluate_mf1");expected=["train_rows","test_rows","feature_cols","target_key","grid","ml","progress_prefix"]
    if sig!=expected:raise AuditError(f"evaluate_mf1 signature mismatch: {sig}")
    for fn in ("require_ml","flatten_base_features","build_structured"):
        if function_signature_from_ast(mf1,fn) is None:raise AuditError(f"MF1 helper missing: {fn}")
    methods=class_methods_from_ast(mf2,"FoldPreprocessor")
    if "fit" not in methods or "transform" not in methods:raise AuditError(f"FoldPreprocessor mismatch: {methods}")
    rmethods=class_methods_from_ast(runtime,"CertifiedMonotonicGAM")
    if "fit" not in rmethods or "predict_proba" not in rmethods:raise AuditError(f"runtime mismatch: {rmethods}")
    print("=== M77.19.8.7.10.7.3.5 REPO CONTRACT AUDIT ===")
    print("status: READY")
    print("8.5_target_schema: target_matrix.horizon_summary")
    print("8.6_structured_column_count:",len(a86["structured_columns"]))
    print("10.6_target_schema: target_horizon_summary list")
    print("10.6_validation_matured_counts:",{x["horizon"]:x["matured"] for x in summary})
    print("MF1_evaluate_mf1_signature:",sig)
    print("MF2_FoldPreprocessor_methods:",methods)
    print("MF2_runtime_methods:",rmethods)
    return 0
if __name__=="__main__":raise SystemExit(main())
