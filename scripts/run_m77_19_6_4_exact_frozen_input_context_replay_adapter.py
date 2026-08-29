#!/usr/bin/env python3
"""
M77.19.6.4 — Exact Frozen Input & Context Replay Adapter

Purpose
-------
Build a controlled, research-only adapter bundle for exact overlap-period parity
replay using:
  * frozen production price_history rows,
  * frozen replay observation identities,
  * recoverable frozen context/regime authority,
  * frozen cadence/as-of semantics.

This package does not modify production code and does not authorize the
23-year reconstruction.  Database access is transaction READ ONLY.

The adapter emits filesystem JSON bundles under research_data/m77_19_6_4.
These bundles are research artifacts only and are intended to become the exact
inputs for M77.19.6.5 controlled execution/certification.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "M77.19.6.4-EXACT-FROZEN-INPUT-CONTEXT-REPLAY-ADAPTER-1.0"
CADENCES = ("DAILY", "WEEKLY", "MONTHLY")
DEFAULT_SAMPLE_PER_CADENCE = 48


def jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def require_authority(root: Path, explicit: str | None) -> tuple[Path, dict[str, Any]]:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(root / "reports" / "m77_19_6_3_controlled_exact_input_parity_replay.json")

    for path in candidates:
        if not path.exists():
            continue
        doc = load_json(path)

        if doc.get("full_23_year_reconstruction_authorized") is True:
            raise SystemExit("FAIL CLOSED: unexpected full 23-year authorization")

        if doc.get("production_authority_effect") is True:
            raise SystemExit("FAIL CLOSED: unexpected production authority effect")

        if doc.get("next_step") != "BUILD_EXACT_FROZEN_INPUT_CONTEXT_REPLAY_ADAPTER":
            raise SystemExit(
                "FAIL CLOSED: M77.19.6.3 does not request exact frozen-input/context adapter"
            )

        return path, doc

    raise SystemExit("FAIL CLOSED: M77.19.6.3 authority report not found")


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


def quote_ident(name: str) -> str:
    # identifiers come only from information_schema, but still quote defensively
    return '"' + name.replace('"', '""') + '"'


def split_table(full_name: str) -> tuple[str, str]:
    if "." not in full_name:
        return "public", full_name
    return tuple(full_name.split(".", 1))


def inspect_columns(session, full_name: str) -> list[str]:
    from sqlalchemy import text

    schema, table = split_table(full_name)
    rows = session.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema=:schema AND table_name=:table
            ORDER BY ordinal_position
            """
        ),
        {"schema": schema, "table": table},
    ).all()
    return [r[0] for r in rows]


def discover_tables(session) -> dict[str, list[str]]:
    from sqlalchemy import text

    rows = session.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog','information_schema')
            ORDER BY table_schema, table_name
            """
        )
    ).all()

    result = {
        "price_history": [],
        "replay": [],
        "context": [],
    }

    for schema, table in rows:
        full = f"{schema}.{table}"
        low = full.lower()
        cols = {c.lower() for c in inspect_columns(session, full)}

        if "price_history" in low:
            result["price_history"].append(full)

        if any(token in low for token in ("replay", "stock_intelligence", "m77")):
            result["replay"].append(full)

        if (
            "regime" in low
            or "external_context" in cols
            or "historical_regime" in cols
            or "market_regime" in cols
        ):
            result["context"].append(full)

    return {k: sorted(set(v)) for k, v in result.items()}


def detect_column(columns: Sequence[str], candidates: Sequence[str]) -> str | None:
    low = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in low:
            return low[candidate.lower()]
    return None


def table_profile(session, full_name: str) -> dict[str, Any]:
    columns = inspect_columns(session, full_name)

    return {
        "table": full_name,
        "columns": columns,
        "symbol_column": detect_column(columns, ("symbol", "ticker")),
        "date_column": detect_column(
            columns,
            (
                "as_of_date",
                "replay_date",
                "date",
                "session_date",
                "price_date",
                "snapshot_date",
                "bar_date",
            ),
        ),
        "timestamp_column": detect_column(
            columns,
            (
                "snapshot_timestamp",
                "as_of_timestamp",
                "created_at",
                "generated_at",
                "timestamp",
            ),
        ),
        "cadence_column": detect_column(
            columns,
            ("cadence", "timeframe", "interval"),
        ),
        "direction_column": detect_column(
            columns,
            ("direction", "trend_direction", "stock_direction"),
        ),
        "score_column": detect_column(
            columns,
            ("overall_score", "score", "stock_score"),
        ),
        "confidence_column": detect_column(
            columns,
            ("confidence", "confidence_score"),
        ),
        "state_hash_column": detect_column(
            columns,
            ("state_hash", "profile_hash"),
        ),
        "external_context_column": detect_column(
            columns,
            ("external_context", "context_json", "context"),
        ),
        "historical_regime_column": detect_column(
            columns,
            ("historical_regime", "market_regime", "regime"),
        ),
    }


def choose_replay_tables(profiles: Sequence[Mapping[str, Any]]) -> dict[str, str | None]:
    selected = {c: None for c in CADENCES}

    for profile in profiles:
        table = profile["table"]
        low = table.lower()

        for cadence, hints in {
            "DAILY": ("daily", "1d", "m77_9"),
            "WEEKLY": ("weekly", "1w", "m77_2"),
            "MONTHLY": ("monthly", "1mo", "m77_10"),
        }.items():
            if selected[cadence] is None and any(h in low for h in hints):
                selected[cadence] = table

    # Fallback: a unified table with a cadence/timeframe column.
    unified = next(
        (p["table"] for p in profiles if p.get("cadence_column")),
        None,
    )
    for cadence in CADENCES:
        if selected[cadence] is None:
            selected[cadence] = unified

    return selected


def fetch_replay_sample(
    session,
    profile: Mapping[str, Any],
    cadence: str,
    limit: int,
) -> list[dict[str, Any]]:
    from sqlalchemy import text

    symbol_col = profile.get("symbol_column")
    date_col = profile.get("date_column")
    direction_col = profile.get("direction_column")
    score_col = profile.get("score_column")
    confidence_col = profile.get("confidence_column")
    cadence_col = profile.get("cadence_column")

    required = [symbol_col, date_col, direction_col, score_col, confidence_col]
    if any(x is None for x in required):
        return []

    schema, table = split_table(profile["table"])
    qtable = f"{quote_ident(schema)}.{quote_ident(table)}"

    selected_cols = list(dict.fromkeys(
        [x for x in (
            symbol_col,
            date_col,
            direction_col,
            score_col,
            confidence_col,
            profile.get("state_hash_column"),
            profile.get("external_context_column"),
            profile.get("historical_regime_column"),
            profile.get("timestamp_column"),
            cadence_col,
        ) if x]
    ))

    select_sql = ", ".join(quote_ident(c) for c in selected_cols)
    where = ""
    params = {"limit": limit}

    if cadence_col:
        values = {
            "DAILY": ("DAILY", "1d", "D"),
            "WEEKLY": ("WEEKLY", "1w", "W"),
            "MONTHLY": ("MONTHLY", "1mo", "1m", "M"),
        }[cadence]
        clauses = []
        for i, value in enumerate(values):
            key = f"c{i}"
            clauses.append(f"LOWER(CAST({quote_ident(cadence_col)} AS TEXT)) = LOWER(:{key})")
            params[key] = value
        where = "WHERE (" + " OR ".join(clauses) + ")"

    sql = text(
        f"""
        SELECT {select_sql}
        FROM {qtable}
        {where}
        ORDER BY {quote_ident(date_col)} ASC, {quote_ident(symbol_col)} ASC
        LIMIT :limit
        """
    )

    rows = session.execute(sql, params).mappings().all()
    return [dict(r) for r in rows]


def find_price_profile(
    profiles: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    scored = []
    for p in profiles:
        columns = {c.lower() for c in p["columns"]}
        score = sum(x in columns for x in ("open", "high", "low", "close", "volume"))
        if p.get("symbol_column"):
            score += 2
        if p.get("date_column"):
            score += 2
        scored.append((score, p))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def fetch_price_window(
    session,
    profile: Mapping[str, Any],
    symbol: str,
    as_of: Any,
    bars: int = 300,
) -> list[dict[str, Any]]:
    from sqlalchemy import text

    symbol_col = profile.get("symbol_column")
    date_col = profile.get("date_column")

    if not symbol_col or not date_col:
        return []

    columns = profile["columns"]
    needed = [
        c for c in columns
        if c.lower() in {
            symbol_col.lower(),
            date_col.lower(),
            "open",
            "high",
            "low",
            "close",
            "volume",
            "adjusted_close",
            "vwap",
        }
    ]

    schema, table = split_table(profile["table"])
    qtable = f"{quote_ident(schema)}.{quote_ident(table)}"

    sql = text(
        f"""
        SELECT {", ".join(quote_ident(c) for c in needed)}
        FROM {qtable}
        WHERE {quote_ident(symbol_col)} = :symbol
          AND {quote_ident(date_col)} <= :as_of
        ORDER BY {quote_ident(date_col)} DESC
        LIMIT :bars
        """
    )

    rows = session.execute(
        sql,
        {"symbol": symbol, "as_of": as_of, "bars": bars},
    ).mappings().all()

    return [dict(r) for r in reversed(rows)]


def build_bundle_for_observation(
    session,
    cadence: str,
    replay_profile: Mapping[str, Any],
    replay_row: Mapping[str, Any],
    price_profile: Mapping[str, Any],
) -> dict[str, Any]:
    symbol_col = replay_profile["symbol_column"]
    date_col = replay_profile["date_column"]

    symbol = replay_row[symbol_col]
    as_of = replay_row[date_col]

    price_rows = fetch_price_window(
        session,
        price_profile,
        symbol=symbol,
        as_of=as_of,
        bars=300,
    )

    frozen_output = {
        "direction": replay_row.get(replay_profile["direction_column"]),
        "overall_score": replay_row.get(replay_profile["score_column"]),
        "confidence": replay_row.get(replay_profile["confidence_column"]),
        "state_hash": (
            replay_row.get(replay_profile["state_hash_column"])
            if replay_profile.get("state_hash_column")
            else None
        ),
    }

    context = {
        "external_context": (
            replay_row.get(replay_profile["external_context_column"])
            if replay_profile.get("external_context_column")
            else None
        ),
        "historical_regime": (
            replay_row.get(replay_profile["historical_regime_column"])
            if replay_profile.get("historical_regime_column")
            else None
        ),
        "snapshot_timestamp": (
            replay_row.get(replay_profile["timestamp_column"])
            if replay_profile.get("timestamp_column")
            else None
        ),
    }

    bundle = {
        "adapter_version": VERSION,
        "cadence": cadence,
        "symbol": symbol,
        "as_of": jsonable(as_of),
        "frozen_output": jsonable(frozen_output),
        "frozen_context": jsonable(context),
        "price_history": jsonable(price_rows),
        "price_row_count": len(price_rows),
    }

    bundle["price_history_sha256"] = sha256_json(bundle["price_history"])
    bundle["context_sha256"] = sha256_json(bundle["frozen_context"])
    bundle["bundle_semantic_sha256"] = sha256_json(
        {
            "cadence": bundle["cadence"],
            "symbol": bundle["symbol"],
            "as_of": bundle["as_of"],
            "frozen_output": bundle["frozen_output"],
            "frozen_context": bundle["frozen_context"],
            "price_history": bundle["price_history"],
        }
    )

    return bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--m77-19-6-3-report")
    parser.add_argument("--sample-per-cadence", type=int, default=DEFAULT_SAMPLE_PER_CADENCE)
    parser.add_argument(
        "--output-root",
        default="research_data/m77_19_6_4/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--report",
        default="reports/m77_19_6_4_exact_frozen_input_context_replay_adapter.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    authority_path, _ = require_authority(root, args.m77_19_6_3_report)

    output_root = root / args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    report = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "m77_19_6_3_authority_report": str(authority_path),
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY",
            "production_database_writes": False,
            "filesystem_research_artifacts_only": True,
            "parity_thresholds_relaxed": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "sample_per_cadence_requested": args.sample_per_cadence,
        "cadences": {},
        "blockers": [],
    }

    with readonly_session() as session:
        tables = discover_tables(session)

        replay_profiles = [
            table_profile(session, t) for t in tables["replay"]
        ]
        price_profiles = [
            table_profile(session, t) for t in tables["price_history"]
        ]

        selected_replay = choose_replay_tables(replay_profiles)
        price_profile = find_price_profile(price_profiles)

        report["discovered_tables"] = tables
        report["selected_replay_tables"] = selected_replay
        report["selected_price_history_table"] = (
            price_profile["table"] if price_profile else None
        )

        if price_profile is None:
            report["blockers"].append("NO_USABLE_PRICE_HISTORY_TABLE_DISCOVERED")

        profile_by_table = {p["table"]: p for p in replay_profiles}

        for cadence in CADENCES:
            cadence_report = {
                "selected_replay_table": selected_replay[cadence],
                "sample_rows_found": 0,
                "bundles_written": 0,
                "bundles_with_price_history": 0,
                "bundles_with_external_context": 0,
                "bundles_with_historical_regime": 0,
                "bundle_files": [],
            }

            table = selected_replay[cadence]

            if table is None:
                report["blockers"].append(
                    f"{cadence}_FROZEN_REPLAY_TABLE_NOT_DISCOVERED"
                )
                report["cadences"][cadence] = cadence_report
                continue

            profile = profile_by_table[table]
            rows = fetch_replay_sample(
                session,
                profile,
                cadence,
                args.sample_per_cadence,
            )

            cadence_report["sample_rows_found"] = len(rows)

            if not rows:
                report["blockers"].append(
                    f"{cadence}_FROZEN_REPLAY_SAMPLE_NOT_RECOVERED"
                )
                report["cadences"][cadence] = cadence_report
                continue

            if price_profile is None:
                report["cadences"][cadence] = cadence_report
                continue

            cadence_dir = output_root / cadence.lower()
            cadence_dir.mkdir(parents=True, exist_ok=True)

            for index, row in enumerate(rows, 1):
                bundle = build_bundle_for_observation(
                    session,
                    cadence,
                    profile,
                    row,
                    price_profile,
                )

                safe_symbol = re.sub(r"[^A-Za-z0-9._-]+", "_", str(bundle["symbol"]))
                safe_date = re.sub(r"[^A-Za-z0-9._-]+", "_", str(bundle["as_of"]))
                filename = (
                    f"{index:03d}_{safe_symbol}_{safe_date}.json"
                )

                path = cadence_dir / filename
                path.write_text(
                    json.dumps(bundle, indent=2, sort_keys=True, default=str) + "\n"
                )

                cadence_report["bundles_written"] += 1
                cadence_report["bundle_files"].append(
                    str(path.relative_to(root))
                )

                if bundle["price_row_count"] > 0:
                    cadence_report["bundles_with_price_history"] += 1

                if bundle["frozen_context"]["external_context"] is not None:
                    cadence_report["bundles_with_external_context"] += 1

                if bundle["frozen_context"]["historical_regime"] is not None:
                    cadence_report["bundles_with_historical_regime"] += 1

            report["cadences"][cadence] = cadence_report

    for cadence in CADENCES:
        c = report["cadences"].get(cadence, {})
        if c.get("bundles_written", 0) != args.sample_per_cadence:
            report["blockers"].append(
                f"{cadence}_EXACT_BUNDLE_COUNT_BELOW_{args.sample_per_cadence}"
            )
        if c.get("bundles_with_price_history", 0) != c.get("bundles_written", 0):
            report["blockers"].append(
                f"{cadence}_PRICE_HISTORY_INCOMPLETE"
            )

    adapter_ready = not report["blockers"]

    report["exact_frozen_input_context_adapter_ready"] = adapter_ready
    report["controlled_exact_input_parity_certified"] = False
    report["full_23_year_reconstruction_authorized"] = False
    report["production_authority_effect"] = False
    report["next_step"] = (
        "BUILD_M77_19_6_5_CONTROLLED_ADAPTER_EXECUTION_AND_PARITY_CERTIFICATION"
        if adapter_ready
        else "RESOLVE_M77_19_6_4_ADAPTER_BLOCKERS"
    )

    report_path = root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print("=== M77.19.6.4 EXACT FROZEN INPUT & CONTEXT REPLAY ADAPTER ===")
    print("database_mode: READ_ONLY")
    print("filesystem_research_artifacts_only: True")
    print("parity_thresholds_relaxed: False")

    for cadence in CADENCES:
        c = report["cadences"].get(cadence, {})
        print(
            cadence,
            {
                "sample_rows_found": c.get("sample_rows_found", 0),
                "bundles_written": c.get("bundles_written", 0),
                "bundles_with_price_history": c.get("bundles_with_price_history", 0),
                "bundles_with_external_context": c.get("bundles_with_external_context", 0),
                "bundles_with_historical_regime": c.get("bundles_with_historical_regime", 0),
            },
        )

    print("exact_frozen_input_context_adapter_ready:", adapter_ready)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")

    if report["blockers"]:
        print("blockers:")
        for blocker in sorted(set(report["blockers"])):
            print(" -", blocker)

    print("next_step:", report["next_step"])
    print("report:", report_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
