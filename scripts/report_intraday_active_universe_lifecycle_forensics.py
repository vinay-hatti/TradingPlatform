#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "reports/market_ingestion/intraday_active_universe_shadow/history.jsonl"
VERSION = "INTRADAY-ACTIVE-UNIVERSE-LIFECYCLE-FORENSICS-1.0"
POLICY = "INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3.x"

DIRECT_POLICY_REASONS = {
    "STOCK_INTELLIGENCE_HIGH_SCORE",
    "STOCK_INTELLIGENCE_DISCOVERY_COMBINATION",
    "MULTI_DOMAIN_DISCOVERY_COMBINATION",
}
SAFETY_REASONS = {"OPEN_POSITION", "WORKING_ORDER_OR_EXECUTION"}
MANDATORY_REASONS = {"MANDATORY_CORE_ETF_REFERENCE", "MANDATORY_INDEX_REFERENCE"}
NON_QUALIFYING_CONTEXT_REASONS = {
    "ELIGIBILITY_HYSTERESIS",
    "EXISTING_INSTITUTIONAL_OPPORTUNITY_CONTEXT",
    "INSTITUTIONAL_VOLUME_ANOMALY",
    "STRUCTURAL_BREAKOUT_BREAKDOWN",
    "EVENT_RELEVANCE",
    "OPEX_DEALER_RELEVANCE",
    "MISPRICING_RELEVANCE",
}

QUALIFYING_REASONS = DIRECT_POLICY_REASONS | SAFETY_REASONS | MANDATORY_REASONS


def parse_day(value: str) -> date:
    return date.fromisoformat(value)


def load_history(path: Path = HISTORY) -> list[dict]:
    out: list[dict] = []
    if not path.exists():
        return out
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception as exc:
            raise RuntimeError(f"Invalid JSON in {path} line {line_no}: {exc}") from exc
        if row.get("mode") != "SHADOW_INTRADAY_DECISION":
            continue
        if not row.get("market_session", True):
            continue
        if not row.get("market_date"):
            continue
        out.append(row)
    out.sort(key=lambda x: str(x.get("generated_at") or ""))
    return out


def reason_set(snapshot: dict, symbol: str) -> set[str]:
    raw = (snapshot.get("inclusion_reasons") or {}).get(symbol) or []
    return {str(x) for x in raw}


def independently_qualified(reasons: set[str]) -> bool:
    return bool(reasons & QUALIFYING_REASONS)


def classify_membership(reasons: set[str]) -> str:
    if reasons & SAFETY_REASONS:
        return "SAFETY_INCLUDED"
    if reasons & MANDATORY_REASONS:
        return "MANDATORY_REFERENCE"
    if reasons & DIRECT_POLICY_REASONS:
        return "CURRENT_POLICY_QUALIFIED"
    if "ELIGIBILITY_HYSTERESIS" in reasons:
        return "HYSTERESIS_ONLY"
    return "UNEXPLAINED_ACTIVE"


def active_symbols(snapshot: dict) -> set[str]:
    return {str(x).upper() for x in snapshot.get("proposed_active_symbols") or []}


def analyze_snapshots(snapshots: Iterable[dict], start: date, end: date) -> dict:
    all_rows = list(snapshots)
    scoped = [x for x in all_rows if start <= parse_day(str(x["market_date"])) <= end]
    by_day: dict[str, list[dict]] = defaultdict(list)
    for row in scoped:
        by_day[str(row["market_date"])].append(row)
    for rows in by_day.values():
        rows.sort(key=lambda x: str(x.get("generated_at") or ""))

    # Track consecutive observations with no independent current qualifier.
    no_direct_streak: Counter[str] = Counter()
    max_no_direct_streak: Counter[str] = Counter()
    sticky_events: list[dict] = []
    observation_rows: list[dict] = []

    previous_active: set[str] = set()
    previous_day: str | None = None

    for row in scoped:
        day = str(row["market_date"])
        active = active_symbols(row)
        classes = Counter()
        current_qualified: set[str] = set()
        hysteresis_only: set[str] = set()
        unexplained: set[str] = set()
        safety: set[str] = set()
        mandatory: set[str] = set()

        for sym in active:
            reasons = reason_set(row, sym)
            cls = classify_membership(reasons)
            classes[cls] += 1
            if independently_qualified(reasons):
                current_qualified.add(sym)
                no_direct_streak[sym] = 0
            else:
                no_direct_streak[sym] += 1
                max_no_direct_streak[sym] = max(max_no_direct_streak[sym], no_direct_streak[sym])
                if no_direct_streak[sym] > 2:
                    sticky_events.append({
                        "symbol": sym,
                        "market_date": day,
                        "generated_at": row.get("generated_at"),
                        "consecutive_observations_without_independent_qualification": no_direct_streak[sym],
                        "reasons": sorted(reasons),
                    })
            if cls == "HYSTERESIS_ONLY": hysteresis_only.add(sym)
            if cls == "UNEXPLAINED_ACTIVE": unexplained.add(sym)
            if cls == "SAFETY_INCLUDED": safety.add(sym)
            if cls == "MANDATORY_REFERENCE": mandatory.add(sym)

        # Reset streaks for symbols that are no longer active: de-admission occurred.
        for sym in set(no_direct_streak) - active:
            no_direct_streak[sym] = 0

        cross_session = previous_day is not None and day != previous_day
        carried = active & previous_active if previous_active else set()
        carried_without_current = carried - current_qualified if cross_session else set()
        newly_active = active - previous_active if previous_active else set(active)
        deactivated = previous_active - active if previous_active else set()

        observation_rows.append({
            "market_date": day,
            "generated_at": row.get("generated_at"),
            "active_total": len(active),
            "current_policy_qualified": classes["CURRENT_POLICY_QUALIFIED"],
            "safety_included": classes["SAFETY_INCLUDED"],
            "mandatory_reference": classes["MANDATORY_REFERENCE"],
            "hysteresis_only": classes["HYSTERESIS_ONLY"],
            "unexplained_active": classes["UNEXPLAINED_ACTIVE"],
            "newly_active": len(newly_active),
            "deactivated": len(deactivated),
            "cross_session_transition": cross_session,
            "carried_from_previous_snapshot": len(carried),
            "carried_without_current_qualification": len(carried_without_current),
            "carried_without_current_qualification_symbols": sorted(carried_without_current),
        })
        previous_active = active
        previous_day = day

    daily: list[dict] = []
    dates = sorted(by_day)
    for idx, day in enumerate(dates):
        rows = by_day[day]
        first, last = rows[0], rows[-1]
        first_active, last_active = active_symbols(first), active_symbols(last)
        prev_last_active: set[str] = set()
        if idx > 0:
            prev_last_active = active_symbols(by_day[dates[idx - 1]][-1])
        first_current = {s for s in first_active if independently_qualified(reason_set(first, s))}
        last_current = {s for s in last_active if independently_qualified(reason_set(last, s))}
        first_hyst = {s for s in first_active if classify_membership(reason_set(first, s)) == "HYSTERESIS_ONLY"}
        last_hyst = {s for s in last_active if classify_membership(reason_set(last, s)) == "HYSTERESIS_ONLY"}
        carry = first_active & prev_last_active
        carry_without = carry - first_current
        daily.append({
            "market_date": day,
            "observation_count": len(rows),
            "initial_active": len(first_active),
            "final_active": len(last_active),
            "initial_independently_qualified": len(first_current),
            "final_independently_qualified": len(last_current),
            "initial_hysteresis_only": len(first_hyst),
            "final_hysteresis_only": len(last_hyst),
            "previous_session_final_active": len(prev_last_active) if idx > 0 else None,
            "carried_from_previous_session": len(carry) if idx > 0 else None,
            "carried_without_current_qualification": len(carry_without) if idx > 0 else None,
            "carried_without_current_qualification_symbols": sorted(carry_without) if idx > 0 else [],
            "new_since_previous_session_final": len(first_active - prev_last_active) if idx > 0 else None,
            "dropped_since_previous_session_final": len(prev_last_active - first_active) if idx > 0 else None,
        })

    offenders = sorted(
        ((sym, streak) for sym, streak in max_no_direct_streak.items() if streak > 2),
        key=lambda x: (-x[1], x[0]),
    )
    cross_session_unqualified = sum(int(x.get("carried_without_current_qualification") or 0) for x in daily)
    max_active = max((x["active_total"] for x in observation_rows), default=0)
    min_active = min((x["active_total"] for x in observation_rows), default=0)
    monotonic_non_decreasing = all(
        observation_rows[i]["active_total"] >= observation_rows[i - 1]["active_total"]
        for i in range(1, len(observation_rows))
    ) if observation_rows else False

    fail_reasons: list[str] = []
    if offenders:
        fail_reasons.append("HYSTERESIS_RETENTION_EXCEEDS_TWO_OBSERVATIONS_WITHOUT_INDEPENDENT_REQUALIFICATION")
    if cross_session_unqualified:
        fail_reasons.append("CROSS_SESSION_CARRY_FORWARD_WITHOUT_CURRENT_QUALIFICATION")
    if any(x["unexplained_active"] for x in observation_rows):
        fail_reasons.append("UNEXPLAINED_ACTIVE_MEMBERSHIP")

    gate = "FAIL" if fail_reasons else "PASS"
    return {
        "version": VERSION,
        "mode": "READ_ONLY_ACTIVE_UNIVERSE_LIFECYCLE_FORENSICS",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "policy": {"name": POLICY, "frozen": True, "production_effect": False, "threshold_change": False},
        "observation_count": len(observation_rows),
        "market_session_count": len(daily),
        "active_count_min": min_active,
        "active_count_max": max_active,
        "active_count_monotonic_non_decreasing": monotonic_non_decreasing,
        "cross_session_carried_without_current_qualification_total": cross_session_unqualified,
        "sticky_symbol_count": len(offenders),
        "sticky_symbols": [
            {"symbol": sym, "max_consecutive_observations_without_independent_qualification": streak}
            for sym, streak in offenders
        ],
        "daily": daily,
        "observations": observation_rows,
        "sticky_events": sticky_events,
        "forensic_gate": gate,
        "fail_reasons": fail_reasons,
        "interpretation": (
            "PASS means active membership is explainable by current policy/safety/mandatory reasons or bounded hysteresis. "
            "FAIL means retention outlives the intended two-observation hysteresis window, crosses sessions without current qualification, "
            "or contains unexplained active membership."
        ),
    }


def print_report(result: dict) -> None:
    print("=== INTRADAY ACTIVE-UNIVERSE LIFECYCLE FORENSICS ===")
    print(
        f"range={result['start_date']}..{result['end_date']} sessions={result['market_session_count']} "
        f"observations={result['observation_count']} active_min={result['active_count_min']} "
        f"active_max={result['active_count_max']} monotonic={result['active_count_monotonic_non_decreasing']} "
        f"gate={result['forensic_gate']}"
    )
    print(
        f"sticky_symbols={result['sticky_symbol_count']} "
        f"cross_session_unqualified_carry={result['cross_session_carried_without_current_qualification_total']}"
    )
    if result["fail_reasons"]:
        print("fail_reasons=" + ",".join(result["fail_reasons"]))
    print("\n=== DAILY LIFECYCLE ===")
    for row in result["daily"]:
        print(
            f"{row['market_date']} obs={row['observation_count']} active={row['initial_active']}->{row['final_active']} "
            f"independent={row['initial_independently_qualified']}->{row['final_independently_qualified']} "
            f"hysteresis_only={row['initial_hysteresis_only']}->{row['final_hysteresis_only']} "
            f"prior_final={row['previous_session_final_active']} carry={row['carried_from_previous_session']} "
            f"carry_without_current={row['carried_without_current_qualification']} "
            f"new={row['new_since_previous_session_final']} dropped={row['dropped_since_previous_session_final']}"
        )
    if result["sticky_symbols"]:
        print("\n=== STICKY HYSTERESIS OFFENDERS ===")
        for row in result["sticky_symbols"][:50]:
            print(
                f"{row['symbol']} max_no_current_qualifier_observations="
                f"{row['max_consecutive_observations_without_independent_qualification']}"
            )


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--history", type=Path, default=HISTORY)
    p.add_argument("--json-output", type=Path)
    args = p.parse_args()
    start, end = parse_day(args.start_date), parse_day(args.end_date)
    if end < start:
        raise SystemExit("--end-date must be >= --start-date")
    snapshots = load_history(args.history)
    if not snapshots:
        raise SystemExit(f"No eligible intraday shadow history found at {args.history}")
    result = analyze_snapshots(snapshots, start, end)
    print_report(result)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"\njson_output={args.json_output}")


if __name__ == "__main__":
    main()
