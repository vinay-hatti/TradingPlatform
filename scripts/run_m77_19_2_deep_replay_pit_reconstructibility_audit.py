#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/m77/m77_19_2_deep_replay_pit_reconstructibility_audit.json"
OUT = ROOT / "reports/m77/m77_19_2_deep_replay_pit_reconstructibility_audit.json"

def write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def safe_text(path):
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""

def parse_python(path):
    txt = safe_text(path)
    try:
        tree = ast.parse(txt)
    except Exception:
        tree = None
    return txt, tree

def imported_modules(tree):
    mods = []
    if tree is None:
        return mods
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.extend(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            mods.append(n.module or "")
    return sorted(set(mods))

def argparse_options(txt):
    return sorted(set(re.findall(r'add_argument\(\s*["\'](--[^"\']+)["\']', txt)))

def sql_fragments(txt):
    # Extract likely SQL snippets and classify date bounding / write behavior.
    frags = re.findall(r'(?is)(SELECT|INSERT|UPDATE|DELETE)\s+.{0,700}', txt)
    # regex above only captures operation due group; use simpler line-oriented capture
    lines = []
    for line in txt.splitlines():
        low = line.lower()
        if any(k in low for k in ("select ", "insert ", "update ", "delete ", "where ", "as_of", "date <=", "date >=", "timestamp <=")):
            lines.append(line.strip())
    return lines[:200]

def analyze(path):
    txt, tree = parse_python(path)
    low = txt.lower()
    opts = argparse_options(txt)

    # Date/range controls.
    has_start = any(x in opts for x in ("--start", "--start-date", "--from", "--from-date"))
    has_end = any(x in opts for x in ("--end", "--end-date", "--through", "--through-date"))
    has_asof = any(x in opts for x in ("--as-of", "--as_of"))
    explicit_range = has_start and (has_end or has_asof)

    # PIT semantics markers.
    asof_markers = [
        "as_of <=", "<= as_of", "date <=", "<= daily", "snapshot_timestamp <=",
        "published_at <=", "effective_at <=", "point_in_time", "walk_forward",
        "latest", "historical"
    ]
    future_markers = [
        "shift(-", "lead(", "future_", "next_", "forward_return", "target_hit",
        "max_favorable", "max_adverse"
    ]
    write_markers = [
        ".add(", ".add_all(", ".merge(", ".delete(", ".execute(insert",
        ".execute(update", ".execute(delete", "insert into", "update ", "delete from"
    ]
    production_markers = [
        "current_stock_intelligence", "current_institutional_options",
        "portfolio_", "execution_", "production"
    ]
    hist_namespace_markers = [
        "historical_underlying_replay", "historical_", "replay_run_id"
    ]

    # Function-level evidence.
    functions = []
    if tree is not None:
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                src = ast.get_source_segment(txt, n) or ""
                sl = src.lower()
                functions.append({
                    "name": n.name,
                    "mentions_as_of": "as_of" in sl or "point_in_time" in sl or "walk_forward" in sl,
                    "mentions_future_token": any(k in sl for k in future_markers),
                    "mentions_write": any(k in sl for k in write_markers),
                    "mentions_historical_namespace": any(k in sl for k in hist_namespace_markers),
                })

    return {
        "path": str(path.relative_to(ROOT)),
        "exists": path.exists(),
        "imports": imported_modules(tree),
        "argparse_options": opts,
        "has_start_arg": has_start,
        "has_end_arg": has_end,
        "has_as_of_arg": has_asof,
        "explicit_historical_range_parameterization": explicit_range,
        "mentions_point_in_time_semantics": any(k in low for k in asof_markers),
        "mentions_future_sensitive_tokens": any(k in low for k in future_markers),
        "mentions_database_write_tokens": any(k in low for k in write_markers),
        "mentions_production_namespaces": any(k in low for k in production_markers),
        "mentions_historical_namespace": any(k in low for k in hist_namespace_markers),
        "functions": functions,
        "sql_evidence": sql_fragments(txt),
    }

def main():
    cfg = json.loads(CFG.read_text())
    analyses = {}
    for key, rel in cfg["required_sources"].items():
        p = ROOT / rel
        analyses[key] = analyze(p) if p.exists() else {"path": rel, "exists": False}

    # Fail-closed semantic gates.
    weekly = analyses["weekly_runner"]
    pit = analyses["pit_runner"]
    daily = analyses["daily_runner"]
    monthly = analyses["monthly_runner"]

    gates = {
        "weekly_historical_range_parameterized":
            bool(weekly.get("explicit_historical_range_parameterization")),
        "monthly_historical_range_parameterized":
            bool(monthly.get("explicit_historical_range_parameterization")),
        "daily_historical_range_parameterized":
            bool(daily.get("explicit_historical_range_parameterization")),
        "pit_historical_range_parameterized":
            bool(pit.get("explicit_historical_range_parameterization")),
        "daily_mentions_point_in_time_semantics":
            bool(daily.get("mentions_point_in_time_semantics")),
        "pit_mentions_point_in_time_semantics":
            bool(pit.get("mentions_point_in_time_semantics")),
        "daily_uses_historical_namespace":
            bool(daily.get("mentions_historical_namespace")),
        "pit_uses_historical_namespace":
            bool(pit.get("mentions_historical_namespace")),
        "daily_static_no_obvious_production_write":
            not (daily.get("mentions_database_write_tokens") and daily.get("mentions_production_namespaces")),
        "pit_static_no_obvious_production_write":
            not (pit.get("mentions_database_write_tokens") and pit.get("mentions_production_namespaces")),
        "point_in_time_correctness_fully_certified":
            False
    }

    blockers = []
    if not gates["daily_historical_range_parameterized"]:
        blockers.append("DAILY_RUNNER_NEEDS_HISTORICAL_DATE_PARAMETERIZATION")
    if not gates["monthly_historical_range_parameterized"]:
        blockers.append("MONTHLY_RUNNER_NEEDS_HISTORICAL_DATE_PARAMETERIZATION")
    if not gates["pit_historical_range_parameterized"]:
        blockers.append("PIT_RUNNER_NEEDS_HISTORICAL_DATE_PARAMETERIZATION")
    if not gates["daily_mentions_point_in_time_semantics"]:
        blockers.append("DAILY_RUNNER_POINT_IN_TIME_SEMANTICS_NOT_DEMONSTRATED")
    if not gates["pit_mentions_point_in_time_semantics"]:
        blockers.append("PIT_RUNNER_POINT_IN_TIME_SEMANTICS_NOT_DEMONSTRATED")
    if not gates["daily_static_no_obvious_production_write"]:
        blockers.append("DAILY_RUNNER_PRODUCTION_WRITE_RISK_REQUIRES_ISOLATION")
    if not gates["pit_static_no_obvious_production_write"]:
        blockers.append("PIT_RUNNER_PRODUCTION_WRITE_RISK_REQUIRES_ISOLATION")
    blockers.append("POINT_IN_TIME_CORRECTNESS_REQUIRES_CONTROLLED_ISOLATED_REPLAY_CERTIFICATION")

    # We do not authorize reconstruction until controlled isolated replay proves PIT correctness.
    authorized = False

    next_step = "BUILD_M77_19_3_ISOLATED_DAILY_MONTHLY_PIT_HISTORICAL_REPLAY_HARNESS"
    if (
        not gates["daily_historical_range_parameterized"]
        or not gates["monthly_historical_range_parameterized"]
        or not gates["pit_historical_range_parameterized"]
    ):
        next_step = "BUILD_M77_19_3_DATE_PARAMETERIZED_ISOLATED_DAILY_MONTHLY_PIT_HARNESS"

    out = {
        "version": cfg["version"],
        "status": "READY",
        "mode": "READ_ONLY_DEEP_STATIC_SEMANTIC_AUDIT",
        "source_analysis": analyses,
        "gates": gates,
        "exact_long_history_reconstruction_authorized": authorized,
        "blockers": blockers,
        "required_isolation_contract": {
            "read_only_source_prices": True,
            "separate_research_namespace": True,
            "no_production_table_mutation": True,
            "date_parameterized_daily_replay": True,
            "date_parameterized_monthly_replay": True,
            "date_parameterized_pit_regime_reconstruction": True,
            "walk_forward_as_of_enforcement": True,
            "future_leakage_tests_required": True,
            "deterministic_replay_identity_required": True
        },
        "next_step": next_step,
        "database_writes": False,
        "production_authority_effect": False
    }

    write_json_atomic(OUT, out)
    print(json.dumps({
        "version": out["version"],
        "status": out["status"],
        "gates": gates,
        "exact_long_history_reconstruction_authorized": authorized,
        "blockers": blockers,
        "next_step": next_step,
        "production_authority_effect": False
    }, indent=2))

if __name__ == "__main__":
    main()
