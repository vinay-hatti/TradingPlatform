#!/usr/bin/env python3
"""
M77.19.6.5.1.1 — Imported Native Contract Resolution

Corrective source-resolution pass for M77.19.6.5.1.

DAILY/MONTHLY:
  Follow the certified import:
    trading_ai.historical_underlying_replay.m77_19_4_isolated_adapters
  and capture the actual implementation of:
    snapshot
    daily_dates
    monthly_dates

WEEKLY:
  Recover the real orchestration in
    scripts/run_m77_19_6_isolated_replay_engine_parity.py
  by capturing:
    StockIntelligenceService()
    session_set construction
    call_profile(...)
    isolated_profile(...)
    call_profile implementation body
    enclosing main-loop call sites

This stage performs NO replay execution and NO database access.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

VERSION = "M77.19.6.5.1.1-IMPORTED-NATIVE-CONTRACT-RESOLUTION-1.0"

DM_MODULE_REL = "src/trading_ai/historical_underlying_replay/m77_19_4_isolated_adapters.py"
WEEKLY_REL = "scripts/run_m77_19_6_isolated_replay_engine_parity.py"

DM_REQUIRED_FUNCTIONS = ("snapshot", "daily_dates", "monthly_dates")
WEEKLY_REQUIRED_FUNCTIONS = ("isolated_profile", "call_profile", "main")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_segment(text: str, node: ast.AST) -> str:
    return ast.get_source_segment(text, node) or ""


def function_nodes(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def function_contract(text: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, Any]:
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
        "source": source_segment(text, node),
    }


def call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        try:
            return ast.unparse(node.func)
        except Exception:
            return node.func.attr
    return ""


def calls_named(text: str, tree: ast.Module, names: set[str]) -> list[dict[str, Any]]:
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node)
        leaf = name.split(".")[-1]
        if leaf not in names:
            continue
        out.append(
            {
                "line": node.lineno,
                "call": name,
                "args": [source_segment(text, x) for x in node.args],
                "kwargs": {
                    kw.arg or "**": source_segment(text, kw.value)
                    for kw in node.keywords
                },
                "expression": source_segment(text, node),
            }
        )
    return sorted(out, key=lambda x: x["line"])


def assignments_matching(text: str, tree: ast.Module, needles: tuple[str, ...]) -> list[dict[str, Any]]:
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            expr = source_segment(text, node.value)
            targets = [source_segment(text, t) for t in node.targets]
            joined = " ".join(targets + [expr]).lower()
            if any(n.lower() in joined for n in needles):
                out.append(
                    {
                        "line": node.lineno,
                        "targets": targets,
                        "expression": expr,
                    }
                )
        elif isinstance(node, ast.AnnAssign):
            expr = source_segment(text, node.value) if node.value else ""
            target = source_segment(text, node.target)
            joined = f"{target} {expr}".lower()
            if any(n.lower() in joined for n in needles):
                out.append(
                    {
                        "line": node.lineno,
                        "targets": [target],
                        "expression": expr,
                    }
                )
    return sorted(out, key=lambda x: x["line"])


def import_records(tree: ast.Module) -> list[dict[str, Any]]:
    out = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            out.append(
                {
                    "line": node.lineno,
                    "type": "import",
                    "module": None,
                    "names": [
                        {"name": n.name, "asname": n.asname} for n in node.names
                    ],
                }
            )
        elif isinstance(node, ast.ImportFrom):
            out.append(
                {
                    "line": node.lineno,
                    "type": "from",
                    "module": node.module,
                    "names": [
                        {"name": n.name, "asname": n.asname} for n in node.names
                    ],
                }
            )
    return out


def analyze_dm(root: Path) -> dict[str, Any]:
    path = root / DM_MODULE_REL
    if not path.exists():
        return {
            "resolved": False,
            "path": DM_MODULE_REL,
            "blockers": ["CERTIFIED_DAILY_MONTHLY_ADAPTER_MODULE_MISSING"],
        }

    text = path.read_text(errors="replace")
    tree = ast.parse(text)
    fns = function_nodes(tree)

    missing = [name for name in DM_REQUIRED_FUNCTIONS if name not in fns]

    contracts = {
        name: function_contract(text, fns[name])
        for name in DM_REQUIRED_FUNCTIONS
        if name in fns
    }

    calls = calls_named(
        text,
        tree,
        set(DM_REQUIRED_FUNCTIONS)
        | {
            "_aggregate",
            "StockIntelligenceService",
            "compute",
            "build",
            "profile",
        },
    )

    markers = []
    for lineno, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if any(
            token in low
            for token in (
                "history",
                "future",
                "as_of",
                "external_context",
                "stockintelligence",
                "_aggregate",
                "snapshot",
            )
        ):
            markers.append({"line": lineno, "text": line.strip()[:1000]})

    return {
        "resolved": not missing,
        "path": DM_MODULE_REL,
        "sha256": sha256_text(text),
        "imports": import_records(tree),
        "required_function_contracts": contracts,
        "native_calls": calls,
        "semantic_markers": markers[:1000],
        "blockers": (
            [f"MISSING_CERTIFIED_FUNCTION:{x}" for x in missing]
            if missing
            else []
        ),
    }


def analyze_weekly(root: Path) -> dict[str, Any]:
    path = root / WEEKLY_REL
    if not path.exists():
        return {
            "resolved": False,
            "path": WEEKLY_REL,
            "blockers": ["WEEKLY_PARITY_RUNNER_MISSING"],
        }

    text = path.read_text(errors="replace")
    tree = ast.parse(text)
    fns = function_nodes(tree)

    missing = [name for name in WEEKLY_REQUIRED_FUNCTIONS if name not in fns]

    contracts = {
        name: function_contract(text, fns[name])
        for name in WEEKLY_REQUIRED_FUNCTIONS
        if name in fns
    }

    native_calls = calls_named(
        text,
        tree,
        {
            "isolated_profile",
            "call_profile",
            "StockIntelligenceService",
            "StockIntelligencePublicationService",
            "_aggregate",
            "set",
        },
    )

    assignments = assignments_matching(
        text,
        tree,
        (
            "session_set",
            "spy_dates",
            "svc",
            "service",
            "rows",
            "warmup",
            "history_rows",
            "policy",
        ),
    )

    call_profile_calls = [
        x for x in native_calls
        if x["call"].split(".")[-1] == "call_profile"
    ]

    service_ctor = [
        x for x in native_calls
        if x["call"].split(".")[-1] == "StockIntelligenceService"
    ]

    session_assignments = [
        x for x in assignments
        if any("session_set" in t for t in x["targets"])
    ]

    resolved = (
        not missing
        and bool(call_profile_calls)
        and bool(service_ctor)
        and bool(session_assignments)
    )

    blockers = []
    if missing:
        blockers.extend(f"MISSING_WEEKLY_FUNCTION:{x}" for x in missing)
    if not call_profile_calls:
        blockers.append("CALL_PROFILE_NATIVE_CALL_SITE_NOT_FOUND")
    if not service_ctor:
        blockers.append("STOCK_INTELLIGENCE_SERVICE_CONSTRUCTION_NOT_FOUND")
    if not session_assignments:
        blockers.append("SESSION_SET_CONSTRUCTION_NOT_FOUND")

    return {
        "resolved": resolved,
        "path": WEEKLY_REL,
        "sha256": sha256_text(text),
        "imports": import_records(tree),
        "required_function_contracts": contracts,
        "native_calls": native_calls,
        "native_assignments": assignments,
        "call_profile_call_sites": call_profile_calls,
        "service_construction_call_sites": service_ctor,
        "session_set_assignments": session_assignments,
        "blockers": blockers,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument(
        "--prior-report",
        default="reports/m77_19_6_5_1_native_replay_invocation_contract_recovery.json",
    )
    ap.add_argument(
        "--output",
        default="reports/m77_19_6_5_1_1_imported_native_contract_resolution.json",
    )
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    prior_path = root / args.prior_report

    if not prior_path.exists():
        raise SystemExit("FAIL CLOSED: M77.19.6.5.1 report missing")

    prior = json.loads(prior_path.read_text())

    if (
        prior.get("next_step")
        != "RESOLVE_M77_19_6_5_1_NATIVE_CONTRACT_BLOCKERS"
    ):
        raise SystemExit(
            "FAIL CLOSED: prior report does not request native contract blocker resolution"
        )

    if prior.get("full_23_year_reconstruction_authorized") is True:
        raise SystemExit("FAIL CLOSED: unexpected prior 23-year authorization")

    dm = analyze_dm(root)
    weekly = analyze_weekly(root)

    blockers = list(dm["blockers"]) + list(weekly["blockers"])
    ready = dm["resolved"] and weekly["resolved"] and not blockers

    report = {
        "version": VERSION,
        "prior_report": str(prior_path),
        "governance": {
            "research_only": True,
            "database_access": False,
            "replay_execution": False,
            "heuristic_adapter_execution_allowed": False,
            "parity_thresholds_relaxed": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "daily_monthly_native_contract": dm,
        "weekly_native_contract": weekly,
        "native_invocation_contract_ready": ready,
        "controlled_exact_input_parity_certified": False,
        "blockers": sorted(set(blockers)),
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": (
            "BUILD_M77_19_6_5_2_NATIVE_CONTROLLED_EXECUTION_AND_PARITY_CERTIFICATION"
            if ready
            else "RESOLVE_M77_19_6_5_1_1_IMPORTED_NATIVE_CONTRACT_BLOCKERS"
        ),
    }

    out = root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print("=== M77.19.6.5.1.1 IMPORTED NATIVE CONTRACT RESOLUTION ===")
    print(
        "DAILY_MONTHLY",
        {
            "resolved": dm["resolved"],
            "path": dm["path"],
            "functions": sorted(dm.get("required_function_contracts", {}).keys()),
            "blockers": dm["blockers"],
        },
    )
    print(
        "WEEKLY",
        {
            "resolved": weekly["resolved"],
            "path": weekly["path"],
            "call_profile_call_sites": len(weekly.get("call_profile_call_sites", [])),
            "service_construction_call_sites": len(
                weekly.get("service_construction_call_sites", [])
            ),
            "session_set_assignments": len(
                weekly.get("session_set_assignments", [])
            ),
            "blockers": weekly["blockers"],
        },
    )
    print("native_invocation_contract_ready:", ready)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")

    if blockers:
        print("blockers:")
        for b in sorted(set(blockers)):
            print(" -", b)

    print("next_step:", report["next_step"])
    print("report:", out)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
