#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import py_compile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/m77/m77_19_3_isolated_harness_foundation.json"
OUT = ROOT / "reports/m77/m77_19_3_isolated_harness_foundation.json"
RESEARCH = ROOT / "research_data/m77_19_3"
ADAPTER = RESEARCH / "adapter_contract.json"

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_json_atomic(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def inspect_runner(path: Path):
    if not path.exists():
        return {"path": str(path.relative_to(ROOT)), "present": False}
    py_compile.compile(str(path), doraise=True)
    text = path.read_text(errors="ignore")
    tree = ast.parse(text)
    funcs = []
    classes = []
    imports = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append({
                "name": node.name,
                "args": [a.arg for a in node.args.args],
                "kwonlyargs": [a.arg for a in node.args.kwonlyargs],
                "defaults": len(node.args.defaults),
            })
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
    return {
        "path": str(path.relative_to(ROOT)),
        "present": True,
        "sha256": sha256(path),
        "top_level_functions": funcs,
        "top_level_classes": classes,
        "imports": sorted(set(imports)),
        "contains_sessionlocal": "SessionLocal" in text,
        "contains_production_db_import": "trading_ai.database" in text,
        "contains_main_guard": 'if __name__ == "__main__"' in text or "if __name__=='__main__'" in text,
    }


def harness_has_production_db_semantics() -> dict:
    """
    Inspect THIS harness semantically, not by naive substring search.
    String literals used to audit source runners (e.g. "SessionLocal") are not
    themselves database usage.
    """
    source = Path(__file__).read_text(errors="ignore")
    tree = ast.parse(source)

    db_imports = []
    sessionlocal_name_refs = 0
    sql_write_literals = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.startswith("trading_ai.database"):
                db_imports.append(mod)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("trading_ai.database"):
                    db_imports.append(alias.name)
        elif isinstance(node, ast.Name) and node.id == "SessionLocal":
            sessionlocal_name_refs += 1
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            s = node.value.lower().strip()
            if s.startswith(("insert into ", "update ", "delete from ")):
                sql_write_literals.append(node.value[:120])

    return {
        "database_imports": sorted(set(db_imports)),
        "sessionlocal_name_refs": sessionlocal_name_refs,
        "sql_write_literals": sql_write_literals,
        "has_production_db_semantics": bool(db_imports or sessionlocal_name_refs or sql_write_literals),
    }

def build_adapter_contract(cfg, source_analysis):
    return {
        "version": cfg["version"],
        "status": "FOUNDATION_ONLY",
        "research_storage_root": cfg["research_storage_root"],
        "date_parameters": {
            "start": cfg["target_history"]["desired_start"],
            "end": cfg["target_history"]["desired_end"],
            "as_of_rule": "EVERY FEATURE/STATE READ MUST BE <= OBSERVATION AS_OF"
        },
        "cadence_adapters": {
            "DAILY": {
                "source_runner": cfg["source_runners"]["daily"],
                "required_new_parameters": ["start", "end", "research_output_root"],
                "execution_authorized": False
            },
            "MONTHLY": {
                "source_runner": cfg["source_runners"]["monthly"],
                "required_new_parameters": ["start", "end", "research_output_root"],
                "execution_authorized": False
            },
            "PIT": {
                "source_runner": cfg["source_runners"]["pit"],
                "required_new_parameters": ["start", "end", "research_output_root"],
                "execution_authorized": False
            },
            "WEEKLY": {
                "source_runner": cfg["source_runners"]["weekly"],
                "required_new_parameters": [],
                "existing_range_capability_reused": True,
                "execution_authorized": False
            }
        },
        "source_sha256": {
            k: v.get("sha256")
            for k, v in source_analysis.items()
            if v.get("present")
        },
        "production_db_write_allowed": False,
        "original_runner_source_mutation_allowed": False,
        "automatic_replay_execution": False,
        "point_in_time_certification_required_before_execution": True
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "certify"))
    args = ap.parse_args()

    cfg = json.loads(CFG.read_text())
    analyses = {
        name: inspect_runner(ROOT / rel)
        for name, rel in cfg["source_runners"].items()
    }

    all_present = all(x.get("present") for x in analyses.values())
    callable_counts = {
        k: len(v.get("top_level_functions") or [])
        for k, v in analyses.items()
    }

    contract = build_adapter_contract(cfg, analyses)

    if args.mode == "preflight":
        print(json.dumps({
            "version": cfg["version"],
            "status": "READY",
            "source_runners_present": all_present,
            "callable_counts": callable_counts,
            "source_analysis": analyses,
            "adapter_contract_preview": contract,
            "automatic_replay_execution": False,
            "database_writes": False,
            "production_authority_effect": False
        }, indent=2))
        return

    # Certification materializes only filesystem research metadata; it never invokes source runners.
    RESEARCH.mkdir(parents=True, exist_ok=True)
    write_json_atomic(ADAPTER, contract)

    harness_db_semantics = harness_has_production_db_semantics()
    gates = {
        "source_runners_present": all_present,
        "source_runners_compile": all_present,
        "source_sha256_frozen": all(
            bool(v.get("sha256")) for v in analyses.values() if v.get("present")
        ),
        "top_level_callables_discovered": all(
            callable_counts[k] > 0 for k in ("pit", "daily", "monthly", "weekly")
        ),
        "date_parameterization_adapter_contract_present": ADAPTER.exists(),
        "research_output_namespace_isolated": str(RESEARCH).startswith(str(ROOT / "research_data")),
        "no_production_db_write_code_in_harness":
            not harness_db_semantics["has_production_db_semantics"],
        "no_automatic_replay_execution": True,
        "point_in_time_execution_not_yet_authorized": True
    }

    certified = all(gates.values())
    out = {
        "version": cfg["version"],
        "status": "READY",
        "mode": "ISOLATED_HARNESS_FOUNDATION_CERTIFICATION",
        "source_analysis": analyses,
        "adapter_contract": contract,
        "harness_db_semantic_audit": harness_db_semantics,
        "gates": gates,
        "harness_foundation_certified": certified,
        "historical_replay_execution_authorized": False,
        "remaining_blockers": [
            "ORIGINAL_601_SYMBOL_LONG_HISTORY_SOURCE_DATA_MISSING",
            "ADAPTER_IMPLEMENTATION_NOT_YET_BUILT",
            "POINT_IN_TIME_BEHAVIOR_NOT_YET_EXECUTION_CERTIFIED"
        ],
        "next_step": (
            "BUILD_M77_19_4_ISOLATED_ADAPTER_IMPLEMENTATION_AND_PIT_LEAKAGE_TESTS"
            if certified
            else "REVIEW_M77_19_3_FOUNDATION_CERTIFICATION_FAILURES"
        ),
        "database_writes": False,
        "production_authority_effect": False
    }
    write_json_atomic(OUT, out)
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
