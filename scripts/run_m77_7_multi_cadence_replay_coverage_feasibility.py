#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any

from sqlalchemy import inspect, text

from trading_ai.database.session import SessionLocal


VERSION = "M77.7-MULTI-CADENCE-REPLAY-COVERAGE-FEASIBILITY-1.0"
MODE = "READ_ONLY_MULTI_CADENCE_REPLAY_FEASIBILITY"

DEFAULT_OUTPUT = Path(
    "reports/m77/m77_7_multi_cadence_replay_coverage_feasibility.json"
)
DEFAULT_UNIVERSE = Path("data/universe/us_listed_equities_etfs.csv")
DEFAULT_M77_3 = Path("reports/m77/m77_3_conditional_edge_attribution.json")

# Proposed research horizons. These are NOT production model horizons.
DAILY_HORIZONS = (5, 10, 20, 40, 60)
WEEKLY_REFERENCE_HORIZONS = (20, 40, 60)
MONTHLY_HORIZONS = (60, 120, 180, 252)

# Conservative warmup for historical PIT feature construction.
MIN_WARMUP_SESSIONS = 252

# Feasibility gates only.
READY_COVERAGE_PCT = 98.0
PARTIAL_COVERAGE_PCT = 90.0
MIN_DAILY_ELIGIBLE_OBSERVATIONS = 250
MIN_MONTHLY_ELIGIBLE_OBSERVATIONS = 12


def normalize_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v)[:10])


def discover_price_history(session):
    insp = inspect(session.get_bind())
    tables = set(insp.get_table_names())
    if "price_history" not in tables:
        raise RuntimeError("price_history table not found")

    cols = {c["name"] for c in insp.get_columns("price_history")}
    date_col = (
        "date"
        if "date" in cols
        else ("timestamp" if "timestamp" in cols else None)
    )
    if date_col is None:
        raise RuntimeError(
            "price_history has no recognized date/timestamp column"
        )
    if "symbol" not in cols:
        raise RuntimeError("price_history has no symbol column")

    price_candidates = [
        x for x in ("adjusted_close", "adj_close", "close") if x in cols
    ]
    return {
        "table": "price_history",
        "date_col": date_col,
        "columns": sorted(cols),
        "price_candidates": price_candidates,
        "has_volume": "volume" in cols,
    }


def read_canonical_symbols(path: Path):
    if not path.exists():
        raise RuntimeError(f"canonical universe file missing: {path}")

    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return []

    candidates = ("symbol", "ticker", "Symbol", "Ticker")
    sym_col = next((c for c in candidates if c in rows[0]), None)
    if sym_col is None:
        raise RuntimeError(
            f"cannot identify symbol column in canonical universe: "
            f"{sorted(rows[0].keys())}"
        )

    return sorted(
        {
            str(r[sym_col]).strip().upper()
            for r in rows
            if str(r.get(sym_col) or "").strip()
        }
    )


def load_symbol_dates(session, info, symbols):
    date_col = info["date_col"]

    # Read only dates, not OHLCV payloads.
    rows = session.execute(
        text(
            f"""
            SELECT symbol, {date_col} AS session_date
            FROM price_history
            WHERE symbol = ANY(:symbols)
            ORDER BY symbol, {date_col}
            """
        ),
        {"symbols": symbols},
    ).all()

    out = defaultdict(list)
    for sym, dt in rows:
        d = normalize_date(dt)
        if not out[str(sym)] or out[str(sym)][-1] != d:
            out[str(sym)].append(d)
    return out


def monthly_endpoints(session_calendar):
    by_month = {}
    for d in session_calendar:
        by_month[(d.year, d.month)] = d
    return [by_month[k] for k in sorted(by_month)]


def eligible_count(symbol_dates, calendar, horizon, cadence):
    """
    Conservative availability estimate:
      * requires MIN_WARMUP_SESSIONS source sessions before observation;
      * requires future outcome session at horizon;
      * observation must exist in symbol history.

    This does NOT run StockIntelligenceService. It estimates whether the stored
    historical bars are sufficient to attempt the replay.
    """
    if not symbol_dates:
        return 0

    cal_index = {d: i for i, d in enumerate(calendar)}
    sym_set = set(symbol_dates)

    if cadence == "DAILY":
        obs_dates = [
            d
            for d in calendar
            if d in sym_set
        ]
    elif cadence == "MONTHLY":
        obs_dates = [
            d
            for d in monthly_endpoints(calendar)
            if d in sym_set
        ]
    else:
        raise ValueError(cadence)

    count = 0
    for d in obs_dates:
        i = cal_index[d]
        if i < MIN_WARMUP_SESSIONS:
            continue
        if i + horizon >= len(calendar):
            continue
        target = calendar[i + horizon]
        if target not in sym_set:
            continue
        count += 1
    return count


def symbol_coverage(symbol_dates, calendar):
    if not symbol_dates:
        return {
            "first_date": None,
            "last_date": None,
            "stored_sessions": 0,
            "calendar_sessions_in_span": 0,
            "coverage_pct": 0.0,
            "internal_missing_sessions": 0,
        }

    first, last = symbol_dates[0], symbol_dates[-1]
    expected = [d for d in calendar if first <= d <= last]
    present = set(symbol_dates)
    missing = sum(1 for d in expected if d not in present)
    coverage = (
        100.0 * len(present.intersection(expected)) / len(expected)
        if expected
        else 0.0
    )
    return {
        "first_date": str(first),
        "last_date": str(last),
        "stored_sessions": len(symbol_dates),
        "calendar_sessions_in_span": len(expected),
        "coverage_pct": coverage,
        "internal_missing_sessions": missing,
    }


def disposition(coverage_pct, daily_n, monthly_n):
    if (
        coverage_pct >= READY_COVERAGE_PCT
        and daily_n >= MIN_DAILY_ELIGIBLE_OBSERVATIONS
        and monthly_n >= MIN_MONTHLY_ELIGIBLE_OBSERVATIONS
    ):
        return "READY_DAILY_AND_MONTHLY_RESEARCH"
    if (
        coverage_pct >= PARTIAL_COVERAGE_PCT
        and daily_n > 0
    ):
        return "PARTIAL_REPLAY_RESEARCH"
    return "INSUFFICIENT_REPLAY_COVERAGE"


def m77_3_context(path: Path):
    if not path.exists():
        return {
            "available": False,
            "daily_point_in_time_regime_authority": False,
            "reason": "M77.3 artifact not found",
        }

    d = json.loads(path.read_text())
    auth = d.get("historical_regime_authority") or {}
    snapshots = auth.get("snapshots") or []
    dates = sorted(
        {
            str(x.get("as_of"))[:10]
            for x in snapshots
            if x.get("as_of")
        }
    )
    return {
        "available": True,
        "artifact_version": d.get("version"),
        "snapshot_dates": len(dates),
        "first_snapshot": dates[0] if dates else None,
        "last_snapshot": dates[-1] if dates else None,
        "daily_point_in_time_regime_authority": False,
        "assessment": (
            "Existing M77.3 regime snapshots are tied to the weekly replay "
            "observation dates. Daily replay requires additive daily PIT regime "
            "reconstruction; weekly snapshots must not be forward-filled as "
            "daily authority."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--universe", default=str(DEFAULT_UNIVERSE))
    ap.add_argument("--m77-3", default=str(DEFAULT_M77_3))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = ap.parse_args()

    universe_path = Path(args.universe)
    m77_3_path = Path(args.m77_3)
    output = Path(args.output)

    symbols = read_canonical_symbols(universe_path)
    if not symbols:
        raise SystemExit("canonical universe contains no symbols")

    with SessionLocal() as session:
        info = discover_price_history(session)

        # SPY is used only as the observed US market-session calendar.
        spy_rows = session.execute(
            text(
                f"""
                SELECT DISTINCT {info["date_col"]}
                FROM price_history
                WHERE symbol='SPY'
                ORDER BY {info["date_col"]}
                """
            )
        ).scalars().all()
        calendar = [normalize_date(x) for x in spy_rows]

        if len(calendar) < MIN_WARMUP_SESSIONS + max(MONTHLY_HORIZONS):
            raise SystemExit(
                "FAIL_CLOSED: SPY session calendar is too short for "
                "the proposed warmup + monthly outcome horizon"
            )

        dates_by_symbol = load_symbol_dates(
            session, info, symbols
        )

    monthly_obs_dates = monthly_endpoints(calendar)

    per_symbol = []
    for sym in symbols:
        dates = dates_by_symbol.get(sym, [])
        cov = symbol_coverage(dates, calendar)

        daily_by_h = {
            str(h): eligible_count(dates, calendar, h, "DAILY")
            for h in DAILY_HORIZONS
        }
        monthly_by_h = {
            str(h): eligible_count(dates, calendar, h, "MONTHLY")
            for h in MONTHLY_HORIZONS
        }

        daily_min = min(daily_by_h.values()) if daily_by_h else 0
        monthly_min = min(monthly_by_h.values()) if monthly_by_h else 0

        per_symbol.append(
            {
                "symbol": sym,
                **cov,
                "eligible_daily_observations_by_horizon": daily_by_h,
                "eligible_monthly_observations_by_horizon": monthly_by_h,
                "minimum_daily_eligible_observations": daily_min,
                "minimum_monthly_eligible_observations": monthly_min,
                "disposition": disposition(
                    cov["coverage_pct"],
                    daily_min,
                    monthly_min,
                ),
            }
        )

    dispositions = Counter(x["disposition"] for x in per_symbol)
    coverages = [x["coverage_pct"] for x in per_symbol]
    daily_minima = [
        x["minimum_daily_eligible_observations"] for x in per_symbol
    ]
    monthly_minima = [
        x["minimum_monthly_eligible_observations"] for x in per_symbol
    ]

    daily_ready = sum(
        x["minimum_daily_eligible_observations"]
        >= MIN_DAILY_ELIGIBLE_OBSERVATIONS
        and x["coverage_pct"] >= READY_COVERAGE_PCT
        for x in per_symbol
    )
    monthly_ready = sum(
        x["minimum_monthly_eligible_observations"]
        >= MIN_MONTHLY_ELIGIBLE_OBSERVATIONS
        and x["coverage_pct"] >= READY_COVERAGE_PCT
        for x in per_symbol
    )

    gaps = []
    context = m77_3_context(m77_3_path)
    if not context["daily_point_in_time_regime_authority"]:
        gaps.append(
            {
                "severity": "REQUIRED_BEFORE_DAILY_CERTIFICATION",
                "gap": "DAILY_POINT_IN_TIME_REGIME_AUTHORITY_NOT_MATERIALIZED",
                "remediation": (
                    "Reconstruct PIT regime context for every daily replay date "
                    "from historical source data. Do not forward-fill weekly "
                    "M77.3 snapshots."
                ),
            }
        )

    if "adjusted_close" not in info["columns"] and "adj_close" not in info["columns"]:
        gaps.append(
            {
                "severity": "VERIFY",
                "gap": "ADJUSTED_PRICE_COLUMN_NOT_IDENTIFIED",
                "remediation": (
                    "Verify whether stored OHLC prices are already split/dividend "
                    "adjusted before comparing long-horizon historical outcomes."
                ),
            }
        )

    gaps.extend(
        [
            {
                "severity": "KNOWN_RESEARCH_LIMITATION",
                "gap": "CURRENT_UNIVERSE_SURVIVORSHIP_BIAS",
                "remediation": (
                    "Daily/monthly replay can proceed as current-universe research, "
                    "but cannot claim survivorship-bias-free market-wide inference."
                ),
            },
            {
                "severity": "REQUIRED_BEFORE_MULTI_CADENCE_MODEL",
                "gap": "CADENCE_CONFLUENCE_NOT_YET_CERTIFIED",
                "remediation": (
                    "Validate daily and monthly authorities independently before "
                    "testing Daily × Weekly × Monthly agreement/conflict."
                ),
            },
        ]
    )

    daily_feasible = daily_ready >= int(0.90 * len(symbols))
    monthly_feasible = monthly_ready >= int(0.90 * len(symbols))

    result = {
        "version": VERSION,
        "status": "READY",
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
        "source": {
            "canonical_universe": str(universe_path),
            "canonical_symbols": len(symbols),
            "price_history": info,
            "session_calendar_symbol": "SPY",
            "session_calendar_first": str(calendar[0]),
            "session_calendar_last": str(calendar[-1]),
            "session_calendar_sessions": len(calendar),
            "monthly_observation_endpoints": len(monthly_obs_dates),
        },
        "proposed_research_contract": {
            "daily": {
                "observation_cadence": "EVERY_STORED_US_MARKET_SESSION",
                "warmup_sessions": MIN_WARMUP_SESSIONS,
                "outcome_horizons_sessions": list(DAILY_HORIZONS),
            },
            "weekly": {
                "status": "PRESERVE_EXISTING_FROZEN_M77_BASELINE",
                "outcome_horizons_sessions": list(WEEKLY_REFERENCE_HORIZONS),
                "mutation": False,
            },
            "monthly": {
                "observation_cadence": "LAST_STORED_US_MARKET_SESSION_OF_MONTH",
                "warmup_sessions": MIN_WARMUP_SESSIONS,
                "outcome_horizons_sessions": list(MONTHLY_HORIZONS),
            },
        },
        "coverage_summary": {
            "symbols": len(per_symbol),
            "median_symbol_coverage_pct": median(coverages) if coverages else None,
            "median_minimum_daily_eligible_observations": (
                median(daily_minima) if daily_minima else None
            ),
            "median_minimum_monthly_eligible_observations": (
                median(monthly_minima) if monthly_minima else None
            ),
            "daily_ready_symbols": daily_ready,
            "monthly_ready_symbols": monthly_ready,
            "daily_ready_pct": 100.0 * daily_ready / len(symbols),
            "monthly_ready_pct": 100.0 * monthly_ready / len(symbols),
            "dispositions": dict(sorted(dispositions.items())),
        },
        "context_feasibility": context,
        "gaps": gaps,
        "feasibility": {
            "daily_replay_bar_coverage_feasible": daily_feasible,
            "monthly_replay_bar_coverage_feasible": monthly_feasible,
            "daily_replay_certification_ready": (
                daily_feasible
                and context["daily_point_in_time_regime_authority"]
            ),
            "monthly_replay_certification_ready": monthly_feasible,
            "multi_cadence_confluence_ready": False,
            "recommended_next_step": (
                "BUILD_ADDITIVE_DAILY_PIT_REPLAY_AUTHORITY"
                if daily_feasible
                else "REMEDIATE_DAILY_BAR_COVERAGE_FIRST"
            ),
        },
        "per_symbol": per_symbol,
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")

    print(
        json.dumps(
            {
                "status": result["status"],
                "version": VERSION,
                "output": str(output),
                "canonical_symbols": len(symbols),
                "calendar_sessions": len(calendar),
                "coverage_summary": result["coverage_summary"],
                "feasibility": result["feasibility"],
                "production_authority_effect": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
