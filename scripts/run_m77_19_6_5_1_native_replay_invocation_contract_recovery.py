#!/usr/bin/env python3
"""
M77.19.6.5.1 — Native Replay Invocation Contract Recovery

Purpose
-------
M77.19.6.5 proved that heuristic function ranking is not an acceptable way to
execute certified replay semantics:

* DAILY/MONTHLY incorrectly selected build_adapter_contract(cfg, source_analysis),
  which is a contract builder, not a prediction executor.
* WEEKLY selected the genuine isolated_profile(...) function but failed to
  reconstruct native service / rows / session_set wiring.

M77.19.6.5.1 therefore performs source-native invocation-contract recovery.

It does NOT execute parity and does NOT authorize long-history reconstruction.
It parses the installed certified sources and captures:

* exact source SHA-256;
* all functions/classes/imports;
* call sites of target replay functions;
* call argument expressions;
* enclosing function source;
* assignments and constructors feeding those arguments;
* relevant argparse/config wiring;
* native main/orchestration call chain;
* source markers for M77.19.4.1 certified DAILY/MONTHLY/PIT adapters;
* source markers for M77.19.6 / M77.2 WEEKLY isolated_profile execution.

The resulting report is the binding input for M77.19.6.5.2.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

VERSION = "M77.19.6.5.1-NATIVE-REPLAY-INVOCATION-CONTRACT-RECOVERY-1.0"

TARGET_SOURCE_HINTS = {
    "DAILY_MONTHLY": (
        "run_m77_19_4_1",
        "run_m77_19_3_isolated_daily_monthly_pit_harness",
    ),
    "WEEKLY": (
        "run_m77_19_6_isolated_replay_engine_parity",
        "run_m77_2",
        "weekly",
    ),
}

TARGET_CALL_NAMES = {
    "DAILY_MONTHLY": {
        "isolated_profile",
        "build_daily",
        "build_monthly",
        "daily_adapter",
        "monthly_adapter",
        "replay_daily",
        "replay_monthly",
        "compute_daily",
        "compute_monthly",
        "build_adapter_contract",
    },
    "WEEKLY": {
        "isolated_profile",
    },
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_segment(text: str, node: ast.AST) -> str:
    try:
        return ast.get_source_segment(text, node) or ""
    except Exception:
        return ""


def call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        parts = []
        cur: ast.AST = node.func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def function_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
    args = (
        list(node.args.posonlyargs)
        + list(node.args.args)
        + list(node.args.kwonlyargs)
    )
    return {
        "name": node.name,
        "line": node.lineno,
        "args": [a.arg for a in args],
        "vararg": node.args.vararg.arg if node.args.vararg else None,
        "kwarg": node.args.kwarg.arg if node.args.kwarg else None,
    }


def class_signature(node: ast.ClassDef) -> dict[str, Any]:
    return {
        "name": node.name,
        "line": node.lineno,
        "bases": [ast.unparse(x) for x in node.bases],
        "methods": [
            function_signature(x)
            for x in node.body
            if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
        ],
    }


def import_record(node: ast.Import | ast.ImportFrom) -> dict[str, Any]:
    if isinstance(node, ast.Import):
        return {
            "type": "import",
            "module": None,
            "names": [
                {"name": x.name, "asname": x.asname} for x in node.names
            ],
            "line": node.lineno,
        }
    return {
        "type": "from",
        "module": node.module,
        "names": [
            {"name": x.name, "asname": x.asname} for x in node.names
        ],
        "line": node.lineno,
    }


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    out = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            out[child] = parent
    return out


def enclosing_function(
    node: ast.AST,
    parents: Mapping[ast.AST, ast.AST],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
    return None


def assignment_target_names(node: ast.AST) -> list[str]:
    out = []
    if isinstance(node, ast.Name):
        out.append(node.id)
    elif isinstance(node, (ast.Tuple, ast.List)):
        for item in node.elts:
            out.extend(assignment_target_names(item))
    elif isinstance(node, ast.Attribute):
        try:
            out.append(ast.unparse(node))
        except Exception:
            pass
    return out


def assignments_in_function(
    text: str,
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, Any]]:
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign):
            targets = []
            for t in node.targets:
                targets.extend(assignment_target_names(t))
            out.append(
                {
                    "line": node.lineno,
                    "targets": targets,
                    "expression": source_segment(text, node.value),
                }
            )
        elif isinstance(node, ast.AnnAssign):
            out.append(
                {
                    "line": node.lineno,
                    "targets": assignment_target_names(node.target),
                    "expression": source_segment(text, node.value)
                    if node.value
                    else None,
                }
            )
    return sorted(out, key=lambda x: x["line"])


def calls_in_function(
    text: str,
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[dict[str, Any]]:
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            out.append(
                {
                    "line": node.lineno,
                    "call": call_name(node),
                    "args": [source_segment(text, x) for x in node.args],
                    "kwargs": {
                        kw.arg or "**": source_segment(text, kw.value)
                        for kw in node.keywords
                    },
                    "expression": source_segment(text, node),
                }
            )
    return sorted(out, key=lambda x: x["line"])


def classify_path(path: Path) -> list[str]:
    low = str(path).lower()
    roles = []
    for role, hints in TARGET_SOURCE_HINTS.items():
        if any(h.lower() in low for h in hints):
            roles.append(role)
    return roles


def discover_sources(root: Path) -> list[Path]:
    out = []
    for base in (root / "scripts", root / "src", root / "research"):
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if classify_path(path):
                out.append(path)
    return sorted(set(out))


def analyze_source(root: Path, path: Path) -> dict[str, Any]:
    text = path.read_text(errors="replace")
    tree = ast.parse(text)
    parents = parent_map(tree)

    functions = [
        function_signature(x)
        for x in tree.body
        if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    classes = [
        class_signature(x)
        for x in tree.body
        if isinstance(x, ast.ClassDef)
    ]

    imports = [
        import_record(x)
        for x in tree.body
        if isinstance(x, (ast.Import, ast.ImportFrom))
    ]

    calls = []

    roles = classify_path(path)
    target_names = set()
    for role in roles:
        target_names |= TARGET_CALL_NAMES[role]

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        name = call_name(node)
        leaf = name.split(".")[-1]

        if leaf not in target_names:
            continue

        enclosing = enclosing_function(node, parents)

        record = {
            "line": node.lineno,
            "call": name,
            "args": [source_segment(text, x) for x in node.args],
            "kwargs": {
                kw.arg or "**": source_segment(text, kw.value)
                for kw in node.keywords
            },
            "expression": source_segment(text, node),
            "enclosing_function": enclosing.name if enclosing else None,
            "enclosing_function_line": enclosing.lineno if enclosing else None,
        }

        if enclosing:
            record["enclosing_function_source"] = source_segment(
                text, enclosing
            )
            record["assignments_in_enclosing_function"] = assignments_in_function(
                text, enclosing
            )
            record["calls_in_enclosing_function"] = calls_in_function(
                text, enclosing
            )

        calls.append(record)

    semantic_markers = []

    marker_tokens = (
        "adapter_certified_for_isolated_historical_replay",
        "future_mutation",
        "history_rows",
        "session_set",
        "warmup",
        "external_context",
        "StockIntelligence",
        "service =",
        "isolated_profile",
        "daily",
        "monthly",
        "weekly",
    )

    for lineno, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(token.lower() in low for token in marker_tokens):
            semantic_markers.append(
                {
                    "line": lineno,
                    "text": line.strip()[:800],
                }
            )

    return {
        "path": str(path.relative_to(root)),
        "roles": roles,
        "sha256": sha256_text(text),
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "target_call_sites": calls,
        "semantic_markers": semantic_markers[:1000],
    }


def native_contract_summary(
    analyses: list[Mapping[str, Any]],
) -> dict[str, Any]:
    summary = {
        "DAILY_MONTHLY": {
            "source_files": [],
            "target_call_sites": [],
            "certified_native_contract_resolved": False,
            "blockers": [],
        },
        "WEEKLY": {
            "source_files": [],
            "target_call_sites": [],
            "certified_native_contract_resolved": False,
            "blockers": [],
        },
    }

    for analysis in analyses:
        for role in analysis["roles"]:
            summary[role]["source_files"].append(
                {
                    "path": analysis["path"],
                    "sha256": analysis["sha256"],
                }
            )
            summary[role]["target_call_sites"].extend(
                [
                    {
                        "path": analysis["path"],
                        **call,
                    }
                    for call in analysis["target_call_sites"]
                ]
            )

    # Resolve only when source-native call-site evidence exists.
    dm_calls = summary["DAILY_MONTHLY"]["target_call_sites"]
    weekly_calls = summary["WEEKLY"]["target_call_sites"]

    # build_adapter_contract is explicitly NOT execution authority.
    dm_execution_calls = [
        x
        for x in dm_calls
        if x["call"].split(".")[-1] != "build_adapter_contract"
    ]

    summary["DAILY_MONTHLY"]["certified_native_contract_resolved"] = bool(
        dm_execution_calls
    )

    if not dm_execution_calls:
        summary["DAILY_MONTHLY"]["blockers"].append(
            "DAILY_MONTHLY_EXECUTION_CALL_SITE_NOT_YET_RESOLVED"
        )

    weekly_native = [
        x
        for x in weekly_calls
        if x["call"].split(".")[-1] == "isolated_profile"
        and x.get("enclosing_function_source")
    ]

    summary["WEEKLY"]["certified_native_contract_resolved"] = bool(
        weekly_native
    )

    if not weekly_native:
        summary["WEEKLY"]["blockers"].append(
            "WEEKLY_ISOLATED_PROFILE_NATIVE_CALL_SITE_NOT_RESOLVED"
        )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument(
        "--prior-report",
        default="reports/m77_19_6_5_controlled_adapter_execution_parity_certification.json",
    )
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_5_1_native_replay_invocation_contract_recovery.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    prior_path = root / args.prior_report

    if not prior_path.exists():
        raise SystemExit("FAIL CLOSED: M77.19.6.5 report missing")

    prior = json.loads(prior_path.read_text())

    if (
        prior.get("next_step")
        != "RESOLVE_M77_19_6_5_CONTROLLED_EXECUTION_BLOCKERS"
    ):
        raise SystemExit(
            "FAIL CLOSED: prior report does not request controlled execution blocker resolution"
        )

    if prior.get("full_23_year_reconstruction_authorized") is True:
        raise SystemExit("FAIL CLOSED: unexpected prior 23-year authorization")

    sources = discover_sources(root)
    analyses = []

    for path in sources:
        try:
            analyses.append(analyze_source(root, path))
        except Exception as exc:
            analyses.append(
                {
                    "path": str(path.relative_to(root)),
                    "roles": classify_path(path),
                    "analysis_error": f"{type(exc).__name__}: {exc}",
                }
            )

    good = [x for x in analyses if "analysis_error" not in x]
    summary = native_contract_summary(good)

    blockers = []
    for role in ("DAILY_MONTHLY", "WEEKLY"):
        blockers.extend(summary[role]["blockers"])

    ready = not blockers

    report = {
        "version": VERSION,
        "prior_report": str(prior_path),
        "governance": {
            "research_only": True,
            "production_database_access_required": False,
            "production_database_writes": False,
            "parity_thresholds_relaxed": False,
            "heuristic_adapter_execution_allowed": False,
            "build_adapter_contract_is_execution_authority": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "source_analyses": analyses,
        "native_contract_summary": summary,
        "native_invocation_contract_ready": ready,
        "controlled_exact_input_parity_certified": False,
        "blockers": sorted(set(blockers)),
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": (
            "BUILD_M77_19_6_5_2_NATIVE_CONTROLLED_EXECUTION_AND_PARITY_CERTIFICATION"
            if ready
            else "RESOLVE_M77_19_6_5_1_NATIVE_CONTRACT_BLOCKERS"
        ),
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print("=== M77.19.6.5.1 NATIVE REPLAY INVOCATION CONTRACT RECOVERY ===")
    print("heuristic_adapter_execution_allowed: False")
    print("build_adapter_contract_is_execution_authority: False")

    for role in ("DAILY_MONTHLY", "WEEKLY"):
        r = summary[role]
        print(
            role,
            {
                "source_files": len(r["source_files"]),
                "target_call_sites": len(r["target_call_sites"]),
                "certified_native_contract_resolved": r[
                    "certified_native_contract_resolved"
                ],
                "blockers": r["blockers"],
            },
        )

    print("native_invocation_contract_ready:", ready)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")

    if blockers:
        print("blockers:")
        for blocker in sorted(set(blockers)):
            print(" -", blocker)

    print("next_step:", report["next_step"])
    print("report:", output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
