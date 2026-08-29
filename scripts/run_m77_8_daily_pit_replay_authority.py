#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import inspect as pyinspect
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text

from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.regime import (
    HistoricalRegimeAuthorityService,
    REGIME_AUTHORITY_VERSION,
)

VERSION = "M77.8-DAILY-PIT-REPLAY-AUTHORITY-1.0"
MODE = "READ_ONLY_DAILY_PIT_REPLAY_AUTHORITY"
DAILY_HORIZONS = (5, 10, 20, 40, 60)
MIN_WARMUP_SESSIONS = 252
DEFAULT_M77_7 = Path("reports/m77/m77_7_multi_cadence_replay_coverage_feasibility.json")
DEFAULT_M77_3 = Path("reports/m77/m77_3_historical_regime_authority.json")
DEFAULT_UNIVERSE = Path("data/universe/us_listed_equities_etfs.csv")
DEFAULT_OUTPUT = Path("reports/m77/m77_8_daily_pit_replay_authority.json")
DEFAULT_SNAPSHOTS = Path("reports/m77/m77_8_daily_pit_regime_snapshots.json")
NUMERIC_FIELDS = (
    "spy_close", "spy_sma50", "spy_sma200", "spy_return20_pct",
    "spy_realized_vol20_pct", "vol20_percentile_252", "breadth_above_50d_pct",
)
EXACT_FIELDS = (
    "regime", "trend_state", "volatility_state", "breadth_state",
    "breadth_eligible_symbols", "evidence_quality", "unavailable_reasons",
)


def normalize_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"FAIL_CLOSED: required artifact missing: {path}")
    return json.loads(path.read_text())


def read_canonical_symbols(path: Path) -> list[str]:
    if not path.exists():
        raise SystemExit(f"FAIL_CLOSED: canonical universe missing: {path}")
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("FAIL_CLOSED: canonical universe is empty")
    col = next((x for x in ("symbol", "ticker", "Symbol", "Ticker") if x in rows[0]), None)
    if col is None:
        raise SystemExit("FAIL_CLOSED: canonical universe symbol column not found")
    return sorted({str(r.get(col) or "").strip().upper() for r in rows if str(r.get(col) or "").strip()})


def validate_m77_7(d: dict) -> None:
    gov = d.get("governance") or {}
    feas = d.get("feasibility") or {}
    if d.get("status") != "READY":
        raise SystemExit("FAIL_CLOSED: M77.7 feasibility artifact is not READY")
    if gov.get("production_authority_effect") is not False or gov.get("database_writes") is not False:
        raise SystemExit("FAIL_CLOSED: M77.7 governance is not research-only/read-only")
    if feas.get("daily_replay_bar_coverage_feasible") is not True:
        raise SystemExit("FAIL_CLOSED: M77.7 did not certify daily bar coverage as feasible")


def verify_polygon_adjustment_semantics() -> dict:
    # This is a source-provenance gate, not a network call. The production provider
    # must explicitly request adjusted Polygon aggregates for both historical and
    # grouped-daily paths. If source inspection becomes unavailable, fail closed.
    from trading_ai.market.providers.polygon import PolygonHistoricalProvider

    try:
        source = pyinspect.getsource(PolygonHistoricalProvider)
        source_file = Path(pyinspect.getsourcefile(PolygonHistoricalProvider) or "")
    except (OSError, TypeError) as exc:
        raise SystemExit(f"FAIL_CLOSED: cannot inspect Polygon provider source: {exc}")

    adjusted_true_count = source.replace(" ", "").count("adjusted=True")
    fetch_history_present = "def fetch_history" in source
    grouped_present = "def fetch_grouped_daily" in source
    passed = adjusted_true_count >= 2 and fetch_history_present and grouped_present
    if not passed:
        raise SystemExit(
            "FAIL_CLOSED: adjusted-price provenance gate failed; Polygon provider must "
            "explicitly request adjusted=True for historical and grouped daily aggregates"
        )
    return {
        "provider": "POLYGON",
        "source_file": str(source_file),
        "adjusted_true_occurrences": adjusted_true_count,
        "historical_fetch_present": fetch_history_present,
        "grouped_daily_present": grouped_present,
        "stored_price_history_semantic": "POLYGON_ADJUSTED_AGGREGATES",
        "gate": "PASSED",
    }


def discover_price_history(session) -> dict:
    insp = inspect(session.get_bind())
    if "price_history" not in set(insp.get_table_names()):
        raise SystemExit("FAIL_CLOSED: price_history table not found")
    cols = {c["name"] for c in insp.get_columns("price_history")}
    required = {"symbol", "date", "close"}
    if not required.issubset(cols):
        raise SystemExit(f"FAIL_CLOSED: price_history missing required columns: {sorted(required - cols)}")
    return {"table": "price_history", "columns": sorted(cols), "date_col": "date", "price_col": "close"}


def build_session_calendar(session) -> list[date]:
    rows = session.execute(text("SELECT DISTINCT date FROM price_history WHERE symbol='SPY' ORDER BY date")).scalars().all()
    calendar = [normalize_date(x) for x in rows]
    if len(calendar) < MIN_WARMUP_SESSIONS + max(DAILY_HORIZONS):
        raise SystemExit("FAIL_CLOSED: SPY history too short for daily PIT warmup + outcomes")
    return calendar


def compare_snapshot(current: dict, frozen: dict, tolerance: float = 1e-9) -> list[str]:
    mismatches: list[str] = []
    for field in EXACT_FIELDS:
        a, b = current.get(field), frozen.get(field)
        if field == "unavailable_reasons":
            a, b = list(a or []), list(b or [])
        if a != b:
            mismatches.append(field)
    for field in NUMERIC_FIELDS:
        a, b = current.get(field), frozen.get(field)
        if a is None or b is None:
            if a != b:
                mismatches.append(field)
            continue
        if abs(float(a) - float(b)) > tolerance:
            mismatches.append(field)
    return mismatches


def main() -> None:
    ap = argparse.ArgumentParser(description="M77.8 additive daily point-in-time replay authority foundation")
    ap.add_argument("--m77-7", default=str(DEFAULT_M77_7))
    ap.add_argument("--m77-3", default=str(DEFAULT_M77_3))
    ap.add_argument("--universe", default=str(DEFAULT_UNIVERSE))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--snapshots-output", default=str(DEFAULT_SNAPSHOTS))
    args = ap.parse_args()

    m77_7_path = Path(args.m77_7)
    m77_3_path = Path(args.m77_3)
    universe_path = Path(args.universe)
    output = Path(args.output)
    snapshots_output = Path(args.snapshots_output)

    m77_7 = read_json(m77_7_path)
    validate_m77_7(m77_7)
    frozen_weekly = read_json(m77_3_path)
    symbols = read_canonical_symbols(universe_path)
    price_provenance = verify_polygon_adjustment_semantics()

    if frozen_weekly.get("regime_authority_version") != REGIME_AUTHORITY_VERSION:
        raise SystemExit(
            "FAIL_CLOSED: frozen M77.3 regime authority version does not match installed regime service"
        )

    with SessionLocal() as session:
        price_info = discover_price_history(session)
        calendar = build_session_calendar(session)
        # Daily observation authority starts after a full 252-session warmup.
        regime_dates = calendar[MIN_WARMUP_SESSIONS:]
        replay_dates = calendar[MIN_WARMUP_SESSIONS: -max(DAILY_HORIZONS)]
        service = HistoricalRegimeAuthorityService(session)
        authority = service.build_authority(regime_dates)

    if len(authority) != len(regime_dates):
        raise SystemExit("FAIL_CLOSED: daily regime authority did not materialize every requested date")

    daily_snapshots = [authority[d].as_dict() for d in regime_dates]
    unknown_dates = [str(x["as_of"]) for x in daily_snapshots if x.get("regime") == "UNKNOWN"]
    partial_dates = [str(x["as_of"]) for x in daily_snapshots if x.get("evidence_quality") != "FULL"]

    frozen_by_date = {
        str(x.get("as_of"))[:10]: x
        for x in (frozen_weekly.get("snapshots") or [])
        if x.get("as_of")
    }
    parity_checked = 0
    parity_mismatches = []
    for d in regime_dates:
        key = str(d)
        if key not in frozen_by_date:
            continue
        parity_checked += 1
        current = authority[d].as_dict()
        frozen = frozen_by_date[key]
        fields = compare_snapshot(current, frozen)
        if fields:
            parity_mismatches.append({"as_of": key, "fields": fields})

    frozen_dates = set(frozen_by_date)
    authority_dates = {str(d) for d in regime_dates}
    comparable_frozen_dates = frozen_dates.intersection(authority_dates)
    parity_complete = parity_checked == len(comparable_frozen_dates)
    parity_pass = parity_complete and not parity_mismatches and parity_checked > 0
    if not parity_pass:
        raise SystemExit(
            "FAIL_CLOSED: M77.8 daily regime reconstruction does not exactly reproduce frozen M77.3 weekly snapshots"
        )

    cal_index = {d: i for i, d in enumerate(calendar)}
    horizon_counts = {
        str(h): sum(1 for d in replay_dates if cal_index[d] + h < len(calendar))
        for h in DAILY_HORIZONS
    }
    regime_counts = Counter(x["regime"] for x in daily_snapshots)
    quality_counts = Counter(x["evidence_quality"] for x in daily_snapshots)

    daily_ready = (
        price_provenance["gate"] == "PASSED"
        and parity_pass
        and not unknown_dates
        and not partial_dates
        and len(replay_dates) >= 250
    )
    status = "READY" if daily_ready else "DEGRADED"

    snapshot_payload = {
        "version": VERSION,
        "regime_authority_version": REGIME_AUTHORITY_VERSION,
        "cadence": "DAILY",
        "governance": {
            "research_only": True,
            "database_read_only": True,
            "database_writes": False,
            "production_authority_effect": False,
            "existing_weekly_m77_mutation": False,
        },
        "snapshots": daily_snapshots,
    }
    snapshots_output.parent.mkdir(parents=True, exist_ok=True)
    snapshots_output.write_text(json.dumps(snapshot_payload, default=str, indent=2) + "\n")

    result = {
        "version": VERSION,
        "status": status,
        "governance": {
            "mode": MODE,
            "research_only": True,
            "database_read_only": True,
            "database_writes": False,
            "database_migrations": False,
            "production_source_replacements": False,
            "production_authority_effect": False,
            "production_ingestion_change": False,
            "production_stock_intelligence_change": False,
            "production_decision_change": False,
            "production_execution_change": False,
            "production_portfolio_change": False,
            "existing_weekly_m77_mutation": False,
        },
        "lineage": {
            "m77_7": str(m77_7_path),
            "m77_7_sha256": sha256_file(m77_7_path),
            "m77_3_frozen_weekly_authority": str(m77_3_path),
            "m77_3_sha256": sha256_file(m77_3_path),
            "m77_3_regime_authority_version": REGIME_AUTHORITY_VERSION,
            "canonical_universe": str(universe_path),
            "canonical_universe_sha256": sha256_file(universe_path),
        },
        "price_adjustment_provenance": price_provenance,
        "source": {
            "canonical_symbols": len(symbols),
            "price_history": price_info,
            "session_calendar_symbol": "SPY",
            "session_calendar_first": str(calendar[0]),
            "session_calendar_last": str(calendar[-1]),
            "session_calendar_sessions": len(calendar),
        },
        "daily_contract": {
            "cadence": "EVERY_STORED_US_MARKET_SESSION",
            "warmup_sessions": MIN_WARMUP_SESSIONS,
            "outcome_horizons_sessions": list(DAILY_HORIZONS),
            "regime_authority_dates": len(regime_dates),
            "first_regime_date": str(regime_dates[0]),
            "last_regime_date": str(regime_dates[-1]),
            "outcome_eligible_observation_dates": len(replay_dates),
            "first_replay_date": str(replay_dates[0]),
            "last_replay_date": str(replay_dates[-1]),
            "eligible_observation_counts_by_horizon": horizon_counts,
        },
        "regime_authority": {
            "daily_point_in_time_regime_authority": daily_ready,
            "snapshot_count": len(daily_snapshots),
            "regime_counts": dict(sorted(regime_counts.items())),
            "evidence_quality_counts": dict(sorted(quality_counts.items())),
            "unknown_dates": unknown_dates,
            "partial_dates": partial_dates,
            "snapshots_artifact": str(snapshots_output),
        },
        "frozen_weekly_parity": {
            "frozen_snapshot_count": len(frozen_by_date),
            "comparable_frozen_snapshot_count": len(comparable_frozen_dates),
            "checked": parity_checked,
            "mismatch_count": len(parity_mismatches),
            "mismatches": parity_mismatches[:25],
            "status": "PASSED" if parity_pass else "FAILED",
        },
        "acceptance": {
            "m77_7_daily_bar_coverage_feasible": True,
            "polygon_adjusted_price_semantics_verified": price_provenance["gate"] == "PASSED",
            "daily_pit_regime_materialized": len(authority) == len(regime_dates),
            "frozen_weekly_regime_parity": parity_pass,
            "daily_regime_unknown_zero": len(unknown_dates) == 0,
            "daily_regime_partial_zero": len(partial_dates) == 0,
            "daily_pit_replay_authority_ready": daily_ready,
            "multi_cadence_confluence_ready": False,
        },
        "next_step": (
            "BUILD_DAILY_MODEL_REPLAY_AND_WALK_FORWARD_CERTIFICATION"
            if daily_ready
            else "REMEDIATE_DAILY_PIT_AUTHORITY_GAPS"
        ),
        "production_authority_effect": False,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "status": status,
        "version": VERSION,
        "output": str(output),
        "snapshots_output": str(snapshots_output),
        "daily_contract": result["daily_contract"],
        "regime_authority": result["regime_authority"],
        "frozen_weekly_parity": result["frozen_weekly_parity"],
        "price_adjustment_provenance": price_provenance,
        "acceptance": result["acceptance"],
        "next_step": result["next_step"],
        "production_authority_effect": False,
    }, indent=2))


if __name__ == "__main__":
    main()
