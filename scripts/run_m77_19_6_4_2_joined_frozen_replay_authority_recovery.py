#!/usr/bin/env python3
"""
M77.19.6.4.2 — Joined Frozen Replay Authority Recovery

Corrects M77.19.6.4.1 by using the actual frozen replay relational authority:

  historical_underlying_replay_prediction
      JOIN historical_underlying_replay_run
        ON replay_run_id

Prediction supplies:
  symbol, as_of, direction, overall_score, confidence, state_hash,
  profile_json, lineage_json

Run supplies:
  cadence, replay_mode, champion_mode, start_date, end_date,
  authority_version and run metadata.

This package:
  * uses exact DB column names discovered in the installed schema;
  * recognizes `as_of` explicitly;
  * derives cadence only through the authoritative replay-run join;
  * rejects unrelated filesystem-history fallbacks;
  * materializes 48 exact frozen bundles per cadence if available;
  * reads production price_history READ ONLY;
  * preserves profile_json and lineage_json as frozen replay context/provenance.

No production mutations. No threshold relaxation. No 23-year authorization.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "M77.19.6.4.2-JOINED-FROZEN-REPLAY-AUTHORITY-RECOVERY-1.0"
CADENCES = ("DAILY", "WEEKLY", "MONTHLY")
DEFAULT_SAMPLE_PER_CADENCE = 48


def jsonable(v: Any) -> Any:
    if isinstance(v, Mapping):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, float):
        if math.isnan(v): return "NaN"
        if math.isinf(v): return "Infinity" if v > 0 else "-Infinity"
    return v


def canonical_json(v: Any) -> str:
    return json.dumps(jsonable(v), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(v: Any) -> str:
    return hashlib.sha256(canonical_json(v).encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def require_prior(root: Path, explicit: str | None) -> tuple[Path, dict[str, Any]]:
    candidates = [Path(explicit)] if explicit else []
    candidates.append(
        root / "reports" / "m77_19_6_4_1_replay_authority_resolution_adapter_recovery.json"
    )

    for path in candidates:
        if not path.exists():
            continue
        doc = load_json(path)

        if doc.get("full_23_year_reconstruction_authorized") is True:
            raise SystemExit("FAIL CLOSED: unexpected 23-year authorization")

        if doc.get("production_authority_effect") is True:
            raise SystemExit("FAIL CLOSED: unexpected production authority effect")

        if doc.get("next_step") != "RESOLVE_M77_19_6_4_1_AUTHORITY_BLOCKERS":
            raise SystemExit("FAIL CLOSED: prior report does not request authority blocker resolution")

        return path, doc

    raise SystemExit("FAIL CLOSED: M77.19.6.4.1 report not found")


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


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def table_exists(session, schema: str, table: str) -> bool:
    from sqlalchemy import text
    return bool(
        session.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema=:schema AND table_name=:table
                )
                """
            ),
            {"schema": schema, "table": table},
        ).scalar_one()
    )


def columns_for(session, schema: str, table: str) -> list[str]:
    from sqlalchemy import text
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


def require_columns(actual: Sequence[str], required: Sequence[str], label: str) -> None:
    missing = [c for c in required if c not in actual]
    if missing:
        raise SystemExit(f"FAIL CLOSED: {label} missing required columns: {missing}")


def normalize_cadence(value: Any) -> str | None:
    s = str(value or "").strip().upper()
    aliases = {
        "DAILY": "DAILY", "1D": "DAILY", "D": "DAILY",
        "WEEKLY": "WEEKLY", "1W": "WEEKLY", "W": "WEEKLY",
        "MONTHLY": "MONTHLY", "1MO": "MONTHLY", "1M": "MONTHLY", "M": "MONTHLY",
    }
    return aliases.get(s)


def parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def fetch_joined_sample(session, cadence: str, limit: int) -> list[dict[str, Any]]:
    from sqlalchemy import text

    aliases = {
        "DAILY": ("DAILY", "1d", "D"),
        "WEEKLY": ("WEEKLY", "1w", "W"),
        "MONTHLY": ("MONTHLY", "1mo", "1m", "M"),
    }[cadence]

    params = {"limit": limit}
    cadence_clauses = []
    for i, alias in enumerate(aliases):
        key = f"c{i}"
        params[key] = alias
        cadence_clauses.append(f"LOWER(CAST(r.cadence AS TEXT)) = LOWER(:{key})")

    sql = text(
        f"""
        SELECT
            p.prediction_id,
            p.replay_run_id,
            p.symbol,
            p.as_of,
            p.direction,
            p.primary_category,
            p.overall_score,
            p.confidence,
            p.state_hash,
            p.profile_json,
            p.lineage_json,
            p.created_at AS prediction_created_at,

            r.replay_mode,
            r.champion_mode,
            r.start_date AS run_start_date,
            r.end_date AS run_end_date,
            r.cadence,
            r.status AS run_status,
            r.authority_version,
            r.started_at AS run_started_at,
            r.completed_at AS run_completed_at,
            r.prediction_count AS run_prediction_count,
            r.failure_count AS run_failure_count,
            r.metadata_json AS run_metadata_json

        FROM public.historical_underlying_replay_prediction p
        JOIN public.historical_underlying_replay_run r
          ON r.replay_run_id = p.replay_run_id

        WHERE ({" OR ".join(cadence_clauses)})
          AND UPPER(CAST(r.status AS TEXT)) = 'READY'

        ORDER BY
            p.as_of ASC,
            p.symbol ASC,
            p.prediction_id ASC

        LIMIT :limit
        """
    )

    return [dict(r) for r in session.execute(sql, params).mappings().all()]


def cadence_inventory(session) -> list[dict[str, Any]]:
    from sqlalchemy import text
    rows = session.execute(
        text(
            """
            SELECT
                r.cadence,
                r.status,
                COUNT(*) AS prediction_rows,
                COUNT(DISTINCT p.replay_run_id) AS replay_runs,
                MIN(p.as_of) AS first_as_of,
                MAX(p.as_of) AS last_as_of,
                COUNT(DISTINCT p.symbol) AS symbols
            FROM public.historical_underlying_replay_prediction p
            JOIN public.historical_underlying_replay_run r
              ON r.replay_run_id = p.replay_run_id
            GROUP BY r.cadence, r.status
            ORDER BY r.cadence, r.status
            """
        )
    ).mappings().all()
    return [jsonable(dict(r)) for r in rows]


def find_price_history_profile(session) -> dict[str, Any] | None:
    from sqlalchemy import text

    rows = session.execute(
        text(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog','information_schema')
              AND LOWER(table_name) LIKE '%price_history%'
            ORDER BY table_schema, table_name
            """
        )
    ).all()

    candidates = []
    for schema, table in rows:
        cols = columns_for(session, schema, table)
        lower = {c.lower(): c for c in cols}

        symbol = lower.get("symbol") or lower.get("ticker")
        date_col = (
            lower.get("date")
            or lower.get("session_date")
            or lower.get("price_date")
            or lower.get("bar_date")
            or lower.get("as_of")
        )

        ohlcv_hits = sum(
            key in lower for key in ("open", "high", "low", "close", "volume")
        )

        if symbol and date_col:
            candidates.append(
                (
                    ohlcv_hits,
                    {
                        "schema": schema,
                        "table": table,
                        "columns": cols,
                        "symbol_column": symbol,
                        "date_column": date_col,
                    },
                )
            )

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def fetch_price_window(
    session,
    profile: Mapping[str, Any],
    symbol: str,
    as_of: Any,
    bars: int = 300,
) -> list[dict[str, Any]]:
    from sqlalchemy import text

    lower = {c.lower(): c for c in profile["columns"]}
    wanted_names = {
        profile["symbol_column"].lower(),
        profile["date_column"].lower(),
        "open", "high", "low", "close", "volume",
        "adjusted_close", "adj_close", "vwap",
    }
    selected = [c for c in profile["columns"] if c.lower() in wanted_names]

    qt = f"{qident(profile['schema'])}.{qident(profile['table'])}"

    sql = text(
        f"""
        SELECT {", ".join(qident(c) for c in selected)}
        FROM {qt}
        WHERE {qident(profile["symbol_column"])} = :symbol
          AND {qident(profile["date_column"])} <= :as_of
        ORDER BY {qident(profile["date_column"])} DESC
        LIMIT :bars
        """
    )

    rows = session.execute(
        sql,
        {"symbol": symbol, "as_of": as_of, "bars": bars},
    ).mappings().all()

    return [dict(r) for r in reversed(rows)]


def build_bundle(
    session,
    cadence: str,
    row: Mapping[str, Any],
    price_profile: Mapping[str, Any],
) -> dict[str, Any]:
    prices = fetch_price_window(
        session,
        price_profile,
        symbol=row["symbol"],
        as_of=row["as_of"],
        bars=300,
    )

    profile_json = parse_jsonish(row.get("profile_json"))
    lineage_json = parse_jsonish(row.get("lineage_json"))
    run_metadata_json = parse_jsonish(row.get("run_metadata_json"))

    bundle = {
        "adapter_version": VERSION,
        "authority_contract": "JOINED_HISTORICAL_UNDERLYING_REPLAY_PREDICTION_TO_RUN",
        "cadence": cadence,
        "prediction_identity": {
            "prediction_id": jsonable(row.get("prediction_id")),
            "replay_run_id": jsonable(row.get("replay_run_id")),
            "symbol": jsonable(row.get("symbol")),
            "as_of": jsonable(row.get("as_of")),
        },
        "frozen_output": {
            "direction": jsonable(row.get("direction")),
            "primary_category": jsonable(row.get("primary_category")),
            "overall_score": jsonable(row.get("overall_score")),
            "confidence": jsonable(row.get("confidence")),
            "state_hash": jsonable(row.get("state_hash")),
        },
        "frozen_profile": jsonable(profile_json),
        "frozen_lineage": jsonable(lineage_json),
        "frozen_run_context": {
            "replay_mode": jsonable(row.get("replay_mode")),
            "champion_mode": jsonable(row.get("champion_mode")),
            "run_start_date": jsonable(row.get("run_start_date")),
            "run_end_date": jsonable(row.get("run_end_date")),
            "cadence": jsonable(row.get("cadence")),
            "run_status": jsonable(row.get("run_status")),
            "authority_version": jsonable(row.get("authority_version")),
            "run_started_at": jsonable(row.get("run_started_at")),
            "run_completed_at": jsonable(row.get("run_completed_at")),
            "run_prediction_count": jsonable(row.get("run_prediction_count")),
            "run_failure_count": jsonable(row.get("run_failure_count")),
            "run_metadata_json": jsonable(run_metadata_json),
        },
        "prediction_created_at": jsonable(row.get("prediction_created_at")),
        "price_history": jsonable(prices),
        "price_row_count": len(prices),
    }

    bundle["price_history_sha256"] = sha256_json(bundle["price_history"])
    bundle["frozen_profile_sha256"] = sha256_json(bundle["frozen_profile"])
    bundle["frozen_lineage_sha256"] = sha256_json(bundle["frozen_lineage"])
    bundle["frozen_run_context_sha256"] = sha256_json(bundle["frozen_run_context"])

    bundle["bundle_semantic_sha256"] = sha256_json(
        {
            "cadence": bundle["cadence"],
            "prediction_identity": bundle["prediction_identity"],
            "frozen_output": bundle["frozen_output"],
            "frozen_profile": bundle["frozen_profile"],
            "frozen_lineage": bundle["frozen_lineage"],
            "frozen_run_context": bundle["frozen_run_context"],
            "price_history": bundle["price_history"],
        }
    )

    return bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--m77-19-6-4-1-report")
    parser.add_argument("--sample-per-cadence", type=int, default=DEFAULT_SAMPLE_PER_CADENCE)
    parser.add_argument(
        "--output-root",
        default="research_data/m77_19_6_4_2/exact_frozen_input_context_bundles",
    )
    parser.add_argument(
        "--report",
        default="reports/m77_19_6_4_2_joined_frozen_replay_authority_recovery.json",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    prior_path, _ = require_prior(root, args.m77_19_6_4_1_report)

    output_root = root / args.output_root
    output_root.mkdir(parents=True, exist_ok=True)

    report = {
        "version": VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "prior_report": str(prior_path),
        "governance": {
            "research_only": True,
            "database_mode": "READ_ONLY",
            "production_database_writes": False,
            "filesystem_research_artifacts_only": True,
            "generic_filesystem_fallback_allowed": False,
            "parity_thresholds_relaxed": False,
            "controlled_exact_input_parity_certified": False,
            "full_23_year_reconstruction_authorized": False,
            "production_authority_effect": False,
        },
        "authority_contract": {
            "prediction_table": "public.historical_underlying_replay_prediction",
            "run_table": "public.historical_underlying_replay_run",
            "join_key": "replay_run_id",
            "prediction_date_column": "as_of",
            "cadence_source": "historical_underlying_replay_run.cadence",
        },
        "sample_per_cadence_requested": args.sample_per_cadence,
        "cadences": {},
        "blockers": [],
    }

    with readonly_session() as session:
        if not table_exists(session, "public", "historical_underlying_replay_prediction"):
            raise SystemExit("FAIL CLOSED: historical_underlying_replay_prediction missing")

        if not table_exists(session, "public", "historical_underlying_replay_run"):
            raise SystemExit("FAIL CLOSED: historical_underlying_replay_run missing")

        prediction_cols = columns_for(
            session, "public", "historical_underlying_replay_prediction"
        )
        run_cols = columns_for(
            session, "public", "historical_underlying_replay_run"
        )

        require_columns(
            prediction_cols,
            (
                "prediction_id",
                "replay_run_id",
                "symbol",
                "as_of",
                "direction",
                "primary_category",
                "overall_score",
                "confidence",
                "state_hash",
                "profile_json",
                "lineage_json",
            ),
            "historical_underlying_replay_prediction",
        )

        require_columns(
            run_cols,
            (
                "replay_run_id",
                "replay_mode",
                "champion_mode",
                "start_date",
                "end_date",
                "cadence",
                "status",
                "authority_version",
                "prediction_count",
                "failure_count",
                "metadata_json",
            ),
            "historical_underlying_replay_run",
        )

        report["cadence_inventory"] = cadence_inventory(session)

        price_profile = find_price_history_profile(session)
        report["selected_price_history_table"] = (
            f"{price_profile['schema']}.{price_profile['table']}"
            if price_profile
            else None
        )

        if price_profile is None:
            report["blockers"].append("PRICE_HISTORY_AUTHORITY_NOT_DISCOVERED")

        for cadence in CADENCES:
            rows = fetch_joined_sample(
                session,
                cadence=cadence,
                limit=args.sample_per_cadence,
            )

            cadence_dir = output_root / cadence.lower()
            cadence_dir.mkdir(parents=True, exist_ok=True)

            written = 0
            with_price = 0
            with_profile = 0
            with_lineage = 0

            for index, row in enumerate(rows, 1):
                if price_profile is None:
                    break

                bundle = build_bundle(
                    session=session,
                    cadence=cadence,
                    row=row,
                    price_profile=price_profile,
                )

                safe_symbol = re.sub(
                    r"[^A-Za-z0-9._-]+",
                    "_",
                    str(bundle["prediction_identity"]["symbol"]),
                )
                safe_date = re.sub(
                    r"[^A-Za-z0-9._-]+",
                    "_",
                    str(bundle["prediction_identity"]["as_of"]),
                )

                path = cadence_dir / f"{index:03d}_{safe_symbol}_{safe_date}.json"
                path.write_text(
                    json.dumps(bundle, indent=2, sort_keys=True, default=str) + "\n"
                )

                written += 1
                with_price += bundle["price_row_count"] > 0
                with_profile += bundle["frozen_profile"] is not None
                with_lineage += bundle["frozen_lineage"] is not None

            report["cadences"][cadence] = {
                "authority_source_type": "DATABASE_JOINED_FROZEN_REPLAY_AUTHORITY",
                "authority_source": (
                    "public.historical_underlying_replay_prediction "
                    "JOIN public.historical_underlying_replay_run USING (replay_run_id)"
                ),
                "rows_recovered": len(rows),
                "bundles_written": written,
                "bundles_with_price_history": with_price,
                "bundles_with_frozen_profile": with_profile,
                "bundles_with_frozen_lineage": with_lineage,
            }

            if len(rows) < args.sample_per_cadence:
                report["blockers"].append(
                    f"{cadence}_JOINED_REPLAY_ROWS_BELOW_{args.sample_per_cadence}"
                )

            if written < args.sample_per_cadence:
                report["blockers"].append(
                    f"{cadence}_EXACT_BUNDLE_COUNT_BELOW_{args.sample_per_cadence}"
                )

            if written and with_price < written:
                report["blockers"].append(
                    f"{cadence}_PRICE_HISTORY_INCOMPLETE"
                )

            if written and with_profile < written:
                report["blockers"].append(
                    f"{cadence}_FROZEN_PROFILE_INCOMPLETE"
                )

            if written and with_lineage < written:
                report["blockers"].append(
                    f"{cadence}_FROZEN_LINEAGE_INCOMPLETE"
                )

    ready = not report["blockers"]

    report["exact_frozen_input_context_adapter_ready"] = ready
    report["controlled_exact_input_parity_certified"] = False
    report["full_23_year_reconstruction_authorized"] = False
    report["production_authority_effect"] = False

    report["next_step"] = (
        "BUILD_M77_19_6_5_CONTROLLED_ADAPTER_EXECUTION_AND_PARITY_CERTIFICATION"
        if ready
        else "RESOLVE_M77_19_6_4_2_JOINED_AUTHORITY_BLOCKERS"
    )

    report_path = root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str) + "\n"
    )

    print("=== M77.19.6.4.2 JOINED FROZEN REPLAY AUTHORITY RECOVERY ===")
    print("database_mode: READ_ONLY")
    print("generic_filesystem_fallback_allowed: False")
    print("parity_thresholds_relaxed: False")
    print("authority_contract: prediction JOIN run ON replay_run_id")

    for cadence in CADENCES:
        print(cadence, report["cadences"][cadence])

    print("exact_frozen_input_context_adapter_ready:", ready)
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
