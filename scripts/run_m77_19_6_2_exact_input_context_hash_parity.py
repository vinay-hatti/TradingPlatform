#!/usr/bin/env python3
"""
M77.19.6.2 — Exact Input, Context & Hash Semantics Parity

Research-only, fail-closed parity decomposition.

Objectives
----------
1. Preserve the strict M77.19.6 parity thresholds; never relax them.
2. Reproduce sampled frozen observations with production price_history inputs
   wherever exact source inputs are recoverable.
3. Inventory and recover frozen external-context semantics where available.
4. Decompose state_hash inputs and distinguish semantic fields from
   run/snapshot metadata.
5. Emit causal-attribution evidence and keep the 23-year reconstruction
   blocked unless exact semantic replay parity is actually demonstrated.

This script is intentionally additive.  It imports no production database
engine singleton and performs no writes.  Database access uses SessionLocal
and a transaction declared READ ONLY.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import dataclasses
import datetime as dt
import hashlib
import inspect
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

VERSION = "M77.19.6.2-EXACT-INPUT-CONTEXT-HASH-PARITY-1.0"
STRICT_SCORE_EPSILON = 1e-9
STRICT_CONFIDENCE_EPSILON = 1e-9
STRICT_DIRECTION_MATCH_PCT = 100.0
STRICT_SEMANTIC_HASH_MATCH_PCT = 100.0

RUN_METADATA_KEYS = {
    "id", "run_id", "replay_run_id", "snapshot_id", "state_id",
    "publication_id", "request_id", "trace_id", "correlation_id",
    "generated_at", "created_at", "updated_at", "published_at",
    "snapshot_timestamp", "computed_at", "calculated_at", "ingested_at",
    "uuid", "nonce",
}
SEMANTIC_ID_ALLOWLIST = {
    "symbol", "timeframe", "cadence", "direction", "primary_category",
    "historical_regime", "regime", "score_band",
}
HASH_FIELD_HINTS = ("state_hash", "hash", "sha256", "digest")
CONTEXT_HINTS = (
    "external_context", "market_alignment", "market_regime", "regime",
    "dealer", "liquidity", "institutional", "participation", "breadth",
    "sentiment", "volatility", "sector", "macro", "trend",
)
REPLAY_HINTS = ("m77", "replay", "stock_intelligence", "cadence")


def _jsonable(v: Any) -> Any:
    if dataclasses.is_dataclass(v):
        return _jsonable(dataclasses.asdict(v))
    if isinstance(v, Mapping):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(x) for x in v]
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
    return v


def _canonical_json(v: Any) -> str:
    return json.dumps(_jsonable(v), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def semantic_projection(v: Any) -> Any:
    """Remove clearly run-specific metadata recursively, retaining model semantics."""
    if isinstance(v, Mapping):
        out = {}
        for k, x in v.items():
            key = str(k)
            lk = key.lower()
            if lk in RUN_METADATA_KEYS and lk not in SEMANTIC_ID_ALLOWLIST:
                continue
            if lk.endswith("_uuid"):
                continue
            if lk.endswith("_run_id") or lk.endswith("_snapshot_id"):
                continue
            if lk.endswith("_generated_at") or lk.endswith("_created_at"):
                continue
            out[key] = semantic_projection(x)
        return out
    if isinstance(v, (list, tuple)):
        return [semantic_projection(x) for x in v]
    return _jsonable(v)


def semantic_hash(v: Any) -> str:
    return hashlib.sha256(_canonical_json(semantic_projection(v)).encode("utf-8")).hexdigest()


def flatten(v: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(v, Mapping):
        for k, x in v.items():
            p = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten(x, p))
    elif isinstance(v, (list, tuple)):
        for i, x in enumerate(v):
            out.update(flatten(x, f"{prefix}[{i}]"))
    else:
        out[prefix] = _jsonable(v)
    return out


def diff_flat(a: Any, b: Any) -> dict[str, Any]:
    fa, fb = flatten(a), flatten(b)
    keys = sorted(set(fa) | set(fb))
    diffs = []
    metadata_only = True
    for k in keys:
        av, bv = fa.get(k, "<MISSING>"), fb.get(k, "<MISSING>")
        if av != bv:
            leaf = re.split(r"[.\[]", k)[-1].rstrip("]").lower()
            is_meta = (
                leaf in RUN_METADATA_KEYS
                or leaf.endswith("_uuid")
                or leaf.endswith("_run_id")
                or leaf.endswith("_snapshot_id")
                or leaf.endswith("_generated_at")
                or leaf.endswith("_created_at")
            )
            metadata_only = metadata_only and is_meta
            diffs.append({"path": k, "a": av, "b": bv, "run_metadata_like": is_meta})
    return {
        "different_field_count": len(diffs),
        "metadata_only": metadata_only if diffs else True,
        "differences": diffs[:200],
        "truncated": len(diffs) > 200,
    }


def discover_project_files(project_root: Path) -> dict[str, list[str]]:
    buckets = {"forensic_reports": [], "parity_reports": [], "source_files": [], "research_files": []}
    search_roots = [
        project_root / "reports",
        project_root / "research",
        project_root / "research_data",
        project_root / "artifacts",
        project_root / "config" / "m77",
        project_root / "scripts",
        project_root / "src",
    ]
    for base in search_roots:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if not p.is_file():
                continue
            low = p.name.lower()
            rel = str(p.relative_to(project_root))
            if "77_19_6_1" in low or "m77.19.6.1" in low or ("parity" in low and "forensic" in low):
                buckets["forensic_reports"].append(rel)
            if "77_19_6" in low or ("parity" in low and p.suffix.lower() in {".json", ".jsonl", ".csv"}):
                buckets["parity_reports"].append(rel)
            if p.suffix == ".py" and any(h in low for h in REPLAY_HINTS):
                buckets["source_files"].append(rel)
            if "m77_19_5" in str(p).lower() or "original_cohort_long_history" in str(p).lower():
                buckets["research_files"].append(rel)
    for k in buckets:
        buckets[k] = sorted(set(buckets[k]))[:500]
    return buckets


def parse_json_candidates(project_root: Path, rels: Sequence[str]) -> list[tuple[str, Any]]:
    out = []
    for rel in rels:
        p = project_root / rel
        if p.suffix.lower() not in {".json", ".jsonl"}:
            continue
        try:
            if p.suffix.lower() == ".json":
                out.append((rel, json.loads(p.read_text())))
            else:
                rows = [json.loads(line) for line in p.read_text().splitlines() if line.strip()]
                out.append((rel, rows))
        except Exception:
            continue
    return out


def recursively_find_records(v: Any, required: set[str]) -> list[dict[str, Any]]:
    found = []
    if isinstance(v, Mapping):
        keys = {str(k) for k in v}
        if required.issubset(keys):
            found.append(dict(v))
        for x in v.values():
            found.extend(recursively_find_records(x, required))
    elif isinstance(v, list):
        for x in v:
            found.extend(recursively_find_records(x, required))
    return found


def analyze_hash_semantics(project_root: Path, source_files: Sequence[str], json_docs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    source_markers = []
    hash_builders = []
    for rel in source_files:
        p = project_root / rel
        try:
            text = p.read_text(errors="replace")
            tree = ast.parse(text)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if any(h in name.lower() for h in HASH_FIELD_HINTS):
                    try:
                        snippet = ast.get_source_segment(text, node) or name
                    except Exception:
                        snippet = name
                    hash_builders.append({"file": rel, "line": getattr(node, "lineno", None), "call": snippet[:1000]})
        for i, line in enumerate(text.splitlines(), 1):
            if "state_hash" in line or "sha256" in line or "snapshot_timestamp" in line or "uuid" in line.lower():
                source_markers.append({"file": rel, "line": i, "text": line.strip()[:500]})

    raw_hash_records = []
    for rel, doc in json_docs:
        recs = recursively_find_records(doc, {"state_hash"})
        for r in recs[:200]:
            raw_hash_records.append({
                "file": rel,
                "state_hash": r.get("state_hash"),
                "semantic_hash": semantic_hash(r),
                "run_metadata_fields_present": sorted(
                    k for k in r if str(k).lower() in RUN_METADATA_KEYS
                ),
            })

    return {
        "source_hash_call_count": len(hash_builders),
        "source_hash_calls": hash_builders[:100],
        "semantic_markers_count": len(source_markers),
        "semantic_markers": source_markers[:200],
        "raw_hash_record_count": len(raw_hash_records),
        "raw_hash_records": raw_hash_records[:200],
        "canonical_semantic_hash_contract": {
            "algorithm": "SHA256(canonical JSON of semantic projection)",
            "excluded_fields": sorted(RUN_METADATA_KEYS),
            "strict_match_required_pct": STRICT_SEMANTIC_HASH_MATCH_PCT,
            "status": "DIAGNOSTIC_ONLY_UNTIL_FROZEN_HASH_PAYLOAD_IS_PROVEN",
        },
    }


def analyze_external_context(project_root: Path, source_files: Sequence[str], json_docs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    markers = []
    for rel in source_files:
        p = project_root / rel
        try:
            text = p.read_text(errors="replace")
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            ll = line.lower()
            if any(h in ll for h in CONTEXT_HINTS):
                markers.append({"file": rel, "line": i, "text": line.strip()[:500]})

    recovered_paths = Counter()
    example_values = {}
    for rel, doc in json_docs:
        flat = flatten(doc)
        for path, val in flat.items():
            lp = path.lower()
            if any(h in lp for h in CONTEXT_HINTS):
                recovered_paths[path] += 1
                example_values.setdefault(path, val)

    return {
        "source_context_marker_count": len(markers),
        "source_context_markers": markers[:300],
        "recovered_context_path_count": len(recovered_paths),
        "recovered_context_paths": [
            {"path": p, "occurrences": n, "example": example_values.get(p)}
            for p, n in recovered_paths.most_common(200)
        ],
        "empty_context_is_certified_equivalent": False,
    }


@contextlib.contextmanager
def readonly_session():
    # Required project-safe import pattern.
    from trading_ai.database.session import SessionLocal
    session = SessionLocal()
    try:
        bind = session.get_bind()
        # PostgreSQL transaction-level guard; if unsupported, the SQL itself fails closed.
        session.execute(__import__("sqlalchemy").text("SET TRANSACTION READ ONLY"))
        yield session
        session.rollback()
    finally:
        session.close()


def inspect_db_readonly() -> dict[str, Any]:
    """
    Inspect schema and parity-authority candidates without writes.

    We deliberately use information_schema rather than assuming table names.
    """
    from sqlalchemy import text
    result: dict[str, Any] = {"available": False, "tables": [], "candidate_tables": [], "errors": []}
    try:
        with readonly_session() as session:
            rows = session.execute(text("""
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog','information_schema')
                ORDER BY table_schema, table_name
            """)).all()
            result["available"] = True
            tables = [f"{r[0]}.{r[1]}" for r in rows]
            result["tables"] = tables
            candidates = [
                t for t in tables
                if any(h in t.lower() for h in ("price_history", "stock_intelligence", "replay", "m77", "regime"))
            ]
            result["candidate_tables"] = candidates

            schemas = []
            for t in candidates[:50]:
                schema, table = t.split(".", 1)
                cols = session.execute(text("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema=:s AND table_name=:t
                    ORDER BY ordinal_position
                """), {"s": schema, "t": table}).all()
                schemas.append({
                    "table": t,
                    "columns": [{"name": c[0], "type": c[1]} for c in cols],
                })
            result["candidate_schemas"] = schemas
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    return result


def infer_exact_input_authority(db: Mapping[str, Any]) -> dict[str, Any]:
    tables = db.get("candidate_schemas") or []
    price = []
    replay = []
    context = []
    for item in tables:
        name = item["table"].lower()
        cols = {c["name"].lower() for c in item["columns"]}
        if "price_history" in name:
            price.append(item)
        if "replay" in name or "stock_intelligence" in name or "m77" in name:
            replay.append(item)
        if "regime" in name or any(h in cols for h in ("market_regime", "external_context", "historical_regime")):
            context.append(item)
    return {
        "production_price_history_candidates": [x["table"] for x in price],
        "frozen_replay_candidates": [x["table"] for x in replay],
        "context_authority_candidates": [x["table"] for x in context],
        "exact_input_replay_ready": bool(price and replay),
        "context_recovery_ready": bool(context),
    }


def classify(report: Mapping[str, Any]) -> tuple[str, list[str], bool]:
    blockers = []
    exact = report["exact_input_authority"]
    hash_info = report["hash_semantics"]
    ctx = report["external_context"]

    if not report["database"]["available"]:
        blockers.append("READ_ONLY_DATABASE_AUTHORITY_UNAVAILABLE")
    if not exact["exact_input_replay_ready"]:
        blockers.append("EXACT_PRODUCTION_INPUT_AND_FROZEN_REPLAY_AUTHORITY_NOT_BOTH_DISCOVERED")
    if not exact["context_recovery_ready"]:
        blockers.append("FROZEN_EXTERNAL_CONTEXT_AUTHORITY_NOT_DISCOVERED")
    if hash_info["source_hash_call_count"] == 0 and hash_info["semantic_markers_count"] == 0:
        blockers.append("STATE_HASH_CONSTRUCTION_SEMANTICS_NOT_LOCATED")
    if ctx["source_context_marker_count"] == 0:
        blockers.append("EXTERNAL_CONTEXT_SOURCE_DEPENDENCY_NOT_LOCATED")

    # This phase may only authorize the *next controlled parity replay*.
    # It never authorizes 23-year reconstruction by discovery alone.
    controlled_replay_ready = not blockers
    status = "READY_FOR_CONTROLLED_EXACT_PARITY_REPLAY" if controlled_replay_ready else "BLOCKED_FORENSIC_EVIDENCE_INCOMPLETE"
    return status, blockers, controlled_replay_ready


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-root", default=".")
    ap.add_argument("--output", default="reports/m77_19_6_2_exact_input_context_hash_parity.json")
    ap.add_argument("--skip-db", action="store_true", help="Filesystem/source-only diagnostic; remains blocked.")
    args = ap.parse_args()

    root = Path(args.project_root).resolve()
    discovered = discover_project_files(root)
    docs = parse_json_candidates(root, discovered["forensic_reports"] + discovered["parity_reports"])
    db = {"available": False, "tables": [], "candidate_tables": [], "candidate_schemas": [],
          "errors": ["SKIPPED_BY_OPERATOR"]} if args.skip_db else inspect_db_readonly()

    report = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "ANALYZING",
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY",
            "production_writes": False,
            "parity_thresholds_relaxed": False,
            "score_epsilon": STRICT_SCORE_EPSILON,
            "confidence_epsilon": STRICT_CONFIDENCE_EPSILON,
            "direction_match_required_pct": STRICT_DIRECTION_MATCH_PCT,
            "semantic_hash_match_required_pct": STRICT_SEMANTIC_HASH_MATCH_PCT,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "discovered": discovered,
        "database": db,
    }
    report["exact_input_authority"] = infer_exact_input_authority(db)
    report["hash_semantics"] = analyze_hash_semantics(root, discovered["source_files"], docs)
    report["external_context"] = analyze_external_context(root, discovered["source_files"], docs)

    status, blockers, controlled = classify(report)
    report["status"] = status
    report["blockers"] = blockers
    report["controlled_exact_parity_replay_authorized"] = controlled
    report["full_23_year_reconstruction_authorized"] = False
    report["production_authority_effect"] = False
    report["next_step"] = (
        "RUN_CONTROLLED_EXACT_INPUT_CONTEXT_PARITY_REPLAY"
        if controlled else
        "RESOLVE_M77_19_6_2_FORENSIC_BLOCKERS"
    )

    out = root / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    print("=== M77.19.6.2 EXACT INPUT / CONTEXT / HASH SEMANTICS PARITY ===")
    print("status:", report["status"])
    print("database_mode: READ_ONLY")
    print("parity_thresholds_relaxed: False")
    print("controlled_exact_parity_replay_authorized:", controlled)
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    if blockers:
        print("blockers:")
        for b in blockers:
            print(" -", b)
    print("report:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
