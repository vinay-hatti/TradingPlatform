#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import contextlib
import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

VERSION = "M77.19.6.3-CONTROLLED-EXACT-INPUT-PARITY-REPLAY-1.0"

SCORE_EPSILON = 1e-9
CONFIDENCE_EPSILON = 1e-9
DIRECTION_REQUIRED_PCT = 100.0
SEMANTIC_HASH_REQUIRED_PCT = 100.0
DETERMINISTIC_REPEAT_REQUIRED_PCT = 100.0
CADENCES = ("DAILY", "WEEKLY", "MONTHLY")

RUN_METADATA_KEYS = {
    "id", "run_id", "replay_run_id", "snapshot_id", "state_id",
    "publication_id", "request_id", "trace_id", "correlation_id",
    "generated_at", "created_at", "updated_at", "published_at",
    "snapshot_timestamp", "computed_at", "calculated_at", "ingested_at",
    "uuid", "nonce",
}


def semantic_projection(value: Any) -> Any:
    if isinstance(value, Mapping):
        result = {}
        for key, item in value.items():
            lk = str(key).lower()
            if (
                lk in RUN_METADATA_KEYS
                or lk.endswith("_uuid")
                or lk.endswith("_run_id")
                or lk.endswith("_snapshot_id")
                or lk.endswith("_generated_at")
                or lk.endswith("_created_at")
            ):
                continue
            result[str(key)] = semantic_projection(item)
        return result
    if isinstance(value, (list, tuple)):
        return [semantic_projection(x) for x in value]
    return value


def semantic_hash(value: Any) -> str:
    payload = json.dumps(
        semantic_projection(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def require_m77_19_6_2_authority(root: Path, explicit: str | None):
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(root / "reports" / "m77_19_6_2_exact_input_context_hash_parity.json")

    for path in candidates:
        if not path.exists():
            continue
        doc = load_json(path)

        if doc.get("controlled_exact_parity_replay_authorized") is not True:
            raise SystemExit(
                "FAIL CLOSED: M77.19.6.2 did not authorize controlled exact parity replay"
            )

        if doc.get("full_23_year_reconstruction_authorized") is True:
            raise SystemExit(
                "FAIL CLOSED: unexpected full 23-year reconstruction authorization"
            )

        return path, doc

    raise SystemExit("FAIL CLOSED: M77.19.6.2 authority report not found")


@contextlib.contextmanager
def readonly_session():
    from trading_ai.database.session import SessionLocal
    from sqlalchemy import text

    session = SessionLocal()
    try:
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
        session.rollback()
    finally:
        session.close()


def database_inventory() -> dict[str, Any]:
    from sqlalchemy import text

    result = {
        "available": False,
        "candidate_schemas": [],
        "errors": [],
    }

    try:
        with readonly_session() as session:
            tables = session.execute(
                text(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name
                    """
                )
            ).all()

            for schema, table in tables:
                full_name = f"{schema}.{table}"
                low = full_name.lower()

                if not any(
                    token in low
                    for token in (
                        "price_history",
                        "stock_intelligence",
                        "replay",
                        "m77",
                        "regime",
                    )
                ):
                    continue

                columns = session.execute(
                    text(
                        """
                        SELECT column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = :schema
                          AND table_name = :table
                        ORDER BY ordinal_position
                        """
                    ),
                    {"schema": schema, "table": table},
                ).all()

                result["candidate_schemas"].append(
                    {
                        "table": full_name,
                        "columns": [
                            {"name": col[0], "type": col[1]} for col in columns
                        ],
                    }
                )

            result["available"] = True

    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")

    return result


def classify_candidate_tables(inventory: Mapping[str, Any]) -> dict[str, list[str]]:
    result = {
        "price_history": [],
        "replay": [],
        "context": [],
    }

    for item in inventory.get("candidate_schemas", []):
        table = item["table"]
        low = table.lower()
        columns = {x["name"].lower() for x in item["columns"]}

        if "price_history" in low:
            result["price_history"].append(table)

        if any(token in low for token in ("replay", "stock_intelligence", "m77")):
            result["replay"].append(table)

        if (
            "regime" in low
            or "external_context" in columns
            or "historical_regime" in columns
        ):
            result["context"].append(table)

    return {k: sorted(set(v)) for k, v in result.items()}


def discover_project_files(root: Path) -> dict[str, list[str]]:
    sources = []
    artifacts = []

    bases = [
        root / "scripts",
        root / "src",
        root / "reports",
        root / "research",
        root / "research_data",
        root / "artifacts",
    ]

    for base in bases:
        if not base.exists():
            continue

        for path in base.rglob("*"):
            if not path.is_file():
                continue

            rel = str(path.relative_to(root))
            low = rel.lower()

            if path.suffix == ".py" and any(
                token in low
                for token in ("m77", "replay", "stock_intelligence")
            ):
                sources.append(rel)

            if path.suffix.lower() in {".json", ".jsonl"} and any(
                token in low for token in ("77_19_6", "parity")
            ):
                artifacts.append(rel)

    return {
        "sources": sorted(set(sources))[:1000],
        "artifacts": sorted(set(artifacts))[:1000],
    }


def inspect_source_semantics(root: Path, source_files: list[str]) -> dict[str, Any]:
    compute_calls = []
    context_markers = []
    output_markers = []

    for rel in source_files:
        path = root / rel

        try:
            text = path.read_text(errors="replace")
            tree = ast.parse(text)
        except Exception:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            else:
                name = ""

            if any(
                token in name.lower()
                for token in ("replay", "compute", "evaluate", "score", "build")
            ):
                compute_calls.append(
                    {
                        "file": rel,
                        "line": getattr(node, "lineno", None),
                        "call": name,
                    }
                )

        for lineno, line in enumerate(text.splitlines(), 1):
            low = line.lower()

            if any(
                token in low
                for token in (
                    "external_context",
                    "market_regime",
                    "historical_regime",
                )
            ):
                context_markers.append(
                    {"file": rel, "line": lineno, "text": line.strip()[:500]}
                )

            if any(
                token in low
                for token in ("state_hash", "overall_score", "confidence")
            ):
                output_markers.append(
                    {"file": rel, "line": lineno, "text": line.strip()[:500]}
                )

    return {
        "compute_calls": compute_calls[:300],
        "context_markers": context_markers[:300],
        "output_markers": output_markers[:300],
    }


def extract_actual_scalar_comparisons(
    root: Path,
    artifacts: list[str],
) -> list[dict[str, Any]]:
    rows = []

    def walk(value: Any, source: str):
        if isinstance(value, Mapping):
            keys = set(value.keys())

            direction_fields = {
                "stored_direction",
                "isolated_direction",
                "stored_confidence",
                "isolated_confidence",
            }

            score_fields_present = (
                {"stored_score", "isolated_score"}.issubset(keys)
                or {"stored_overall_score", "isolated_overall_score"}.issubset(keys)
            )

            if direction_fields.issubset(keys) and score_fields_present:
                rows.append({"source": source, **dict(value)})

            for item in value.values():
                walk(item, source)

        elif isinstance(value, list):
            for item in value:
                walk(item, source)

    for rel in artifacts:
        path = root / rel
        try:
            if path.suffix.lower() == ".json":
                doc = load_json(path)
            else:
                doc = [
                    json.loads(line)
                    for line in path.read_text().splitlines()
                    if line.strip()
                ]
            walk(doc, rel)
        except Exception:
            continue

    return rows


def normalize_cadence(value: Any) -> str:
    cadence = str(value or "").upper()
    aliases = {
        "1D": "DAILY",
        "D": "DAILY",
        "1W": "WEEKLY",
        "W": "WEEKLY",
        "1MO": "MONTHLY",
        "1M": "MONTHLY",
        "M": "MONTHLY",
    }
    return aliases.get(cadence, cadence)


def evaluate_actual_comparisons(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    grouped = defaultdict(list)

    for row in rows:
        cadence = normalize_cadence(row.get("cadence") or row.get("timeframe"))
        if cadence in CADENCES:
            grouped[cadence].append(row)

    result = {}
    all_pass = True

    for cadence in CADENCES:
        evidence = grouped[cadence]

        if not evidence:
            result[cadence] = {
                "evidence_count": 0,
                "pass": False,
                "reason": "NO_CONTROLLED_ACTUAL_SCALAR_COMPARISONS",
            }
            all_pass = False
            continue

        score_errors = []
        confidence_errors = []
        direction_matches = []
        semantic_hash_matches = []
        repeat_matches = []

        for row in evidence:
            stored_score = row.get(
                "stored_score",
                row.get("stored_overall_score"),
            )
            isolated_score = row.get(
                "isolated_score",
                row.get("isolated_overall_score"),
            )

            score_errors.append(
                abs(float(stored_score) - float(isolated_score))
            )

            confidence_errors.append(
                abs(
                    float(row["stored_confidence"])
                    - float(row["isolated_confidence"])
                )
            )

            direction_matches.append(
                str(row["stored_direction"]) == str(row["isolated_direction"])
            )

            if (
                row.get("stored_state") is not None
                and row.get("isolated_state") is not None
            ):
                semantic_hash_matches.append(
                    semantic_hash(row["stored_state"])
                    == semantic_hash(row["isolated_state"])
                )

            if "deterministic_repeat" in row:
                repeat_matches.append(bool(row["deterministic_repeat"]))

        direction_pct = 100.0 * sum(direction_matches) / len(direction_matches)

        semantic_hash_pct = (
            100.0 * sum(semantic_hash_matches) / len(semantic_hash_matches)
            if semantic_hash_matches
            else None
        )

        deterministic_repeat_pct = (
            100.0 * sum(repeat_matches) / len(repeat_matches)
            if repeat_matches
            else None
        )

        passed = (
            max(score_errors) <= SCORE_EPSILON
            and max(confidence_errors) <= CONFIDENCE_EPSILON
            and direction_pct == DIRECTION_REQUIRED_PCT
            and semantic_hash_pct == SEMANTIC_HASH_REQUIRED_PCT
            and deterministic_repeat_pct == DETERMINISTIC_REPEAT_REQUIRED_PCT
        )

        result[cadence] = {
            "evidence_count": len(evidence),
            "max_score_abs_error": max(score_errors),
            "max_confidence_abs_error": max(confidence_errors),
            "direction_match_pct": direction_pct,
            "semantic_hash_match_pct": semantic_hash_pct,
            "deterministic_repeat_pct": deterministic_repeat_pct,
            "pass": passed,
        }

        all_pass = all_pass and passed

    return {
        "cadences": result,
        "strict_parity_certified": all_pass,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--m77-19-6-2-report")
    parser.add_argument(
        "--output",
        default="reports/m77_19_6_3_controlled_exact_input_parity_replay.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()

    authority_path, _ = require_m77_19_6_2_authority(
        root,
        args.m77_19_6_2_report,
    )

    inventory = database_inventory()
    candidate_tables = classify_candidate_tables(inventory)
    discovered = discover_project_files(root)
    source_semantics = inspect_source_semantics(root, discovered["sources"])

    actual_rows = extract_actual_scalar_comparisons(
        root,
        discovered["artifacts"],
    )
    evidence = evaluate_actual_comparisons(actual_rows)

    blockers = []

    if not inventory["available"]:
        blockers.append("READ_ONLY_DATABASE_AUTHORITY_UNAVAILABLE")

    if not candidate_tables["price_history"]:
        blockers.append("PRODUCTION_PRICE_HISTORY_NOT_DISCOVERED")

    if not candidate_tables["replay"]:
        blockers.append("FROZEN_REPLAY_AUTHORITY_NOT_DISCOVERED")

    if (
        not candidate_tables["context"]
        and not source_semantics["context_markers"]
    ):
        blockers.append("FROZEN_CONTEXT_AUTHORITY_NOT_DISCOVERED")

    if not source_semantics["compute_calls"]:
        blockers.append("REPLAY_COMPUTE_ENTRYPOINT_NOT_DISCOVERED")

    if not evidence["strict_parity_certified"]:
        blockers.append("CONTROLLED_EXACT_INPUT_REPLAY_NOT_YET_CERTIFIED")

    certified = not blockers and evidence["strict_parity_certified"]

    report = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "m77_19_6_2_authority_report": str(authority_path),
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY",
            "production_writes": False,
            "parity_thresholds_relaxed": False,
            "score_epsilon": SCORE_EPSILON,
            "confidence_epsilon": CONFIDENCE_EPSILON,
            "direction_required_pct": DIRECTION_REQUIRED_PCT,
            "semantic_hash_required_pct": SEMANTIC_HASH_REQUIRED_PCT,
            "deterministic_repeat_required_pct": DETERMINISTIC_REPEAT_REQUIRED_PCT,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "database_inventory": inventory,
        "candidate_tables": candidate_tables,
        "source_semantics": source_semantics,
        "actual_comparison_evidence": evidence,
        "controlled_exact_input_parity_certified": certified,
        "blockers": sorted(set(blockers)),
        "full_23_year_reconstruction_authorized": False,
        "production_authority_effect": False,
        "next_step": (
            "AUTHORIZE_LONG_HISTORY_RECONSTRUCTION_DESIGN"
            if certified
            else "BUILD_EXACT_FROZEN_INPUT_CONTEXT_REPLAY_ADAPTER"
        ),
    }

    output = root / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print("=== M77.19.6.3 CONTROLLED EXACT-INPUT PARITY REPLAY ===")
    print("M77.19.6.2 authority: ACCEPTED")
    print("database_mode: READ_ONLY")
    print("parity_thresholds_relaxed: False")
    print("controlled_exact_input_parity_certified:", certified)
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
