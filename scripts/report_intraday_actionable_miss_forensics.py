#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CERT_HISTORY = ROOT / "reports/market_ingestion/intraday_exclusion_progression/history.jsonl"
SHADOW_HISTORY = ROOT / "reports/market_ingestion/intraday_active_universe_shadow/history.jsonl"
VERSION = "INTRADAY-ACTIONABLE-MISS-FORENSICS-1.0"

POLICY_HIGH_SCORE = 70.0
POLICY_DISCOVERY_SCORE = 60.0

DIRECT_SIGNAL_NAMES = {
    "INSTITUTIONAL_VOLUME_ANOMALY",
    "STRUCTURAL_BREAKOUT_BREAKDOWN",
    "EVENT_RELEVANCE",
    "OPEX_DEALER_RELEVANCE",
    "MISPRICING_RELEVANCE",
}


def normalize_symbol(value: Any) -> str:
    s = str(value or "").strip().upper()
    return {
        "BF-B": "BF.B",
        "BRK-B": "BRK.B",
        "I:SPX": "SPX",
        "I:NDX": "NDX",
        "I:RTY": "RUT",
        "RTY": "RUT",
    }.get(s, s)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Required history artifact does not exist: {path}")
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception as exc:
            raise SystemExit(f"Invalid JSONL at {path}:{lineno}: {exc}") from exc
    return rows


def payload_reasons(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    out: set[str] = set()
    volume = payload.get("institutional_volume") or {}
    breakout = payload.get("breakout") or {}
    event = payload.get("event_intelligence") or payload.get("event") or {}
    opex = payload.get("opex_intelligence") or payload.get("opex") or {}
    mispricing = payload.get("option_mispricing") or payload.get("mispricing") or {}

    volume_signal = str(volume.get("signal") or "").upper()
    volume_regime = str(volume.get("regime") or "").upper()
    if volume_signal in {
        "SELLING_ABSORPTION", "BUYING_ABSORPTION", "BREAKOUT_EXPANSION",
        "BREAKDOWN_EXPANSION", "ACCUMULATION_CONFIRMED", "DISTRIBUTION_CONFIRMED",
    } or volume_regime == "CLIMACTIC":
        out.add("INSTITUTIONAL_VOLUME_ANOMALY")

    breakout_state = str(breakout.get("state") or "").upper()
    if breakout_state in {
        "BREAKOUT_WATCH", "BREAKOUT_CONFIRMED", "BREAKOUT_CONTINUATION",
        "BREAKDOWN_WATCH", "BREAKDOWN_CONFIRMED", "FAILED_BREAKOUT",
    }:
        out.add("STRUCTURAL_BREAKOUT_BREAKDOWN")

    event_state = str(event.get("status") or event.get("state") or event.get("classification") or "").upper()
    if event_state and event_state not in {"NONE", "NEUTRAL", "UNAVAILABLE", "NO_EVENT", "INACTIVE"}:
        out.add("EVENT_RELEVANCE")

    opex_state = str(opex.get("status") or opex.get("state") or opex.get("classification") or "").upper()
    if opex_state and opex_state not in {"NONE", "NEUTRAL", "UNAVAILABLE", "INACTIVE"}:
        out.add("OPEX_DEALER_RELEVANCE")

    mis_state = str(mispricing.get("status") or mispricing.get("state") or mispricing.get("classification") or "").upper()
    if mis_state in {"UNDERPRICED", "MISPRICED", "ACTIONABLE", "HIGH_CONVICTION", "RELATIVE_VALUE"}:
        out.add("MISPRICING_RELEVANCE")
    return out


@dataclass(frozen=True)
class Qualification:
    score: float | None
    evidence: tuple[str, ...]
    qualifies: bool
    route: str | None
    distances: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "evidence_domains": list(self.evidence),
            "evidence_domain_count": len(self.evidence),
            "qualifies_under_frozen_policy_1_3": self.qualifies,
            "qualification_route": self.route,
            "distance_to_threshold": self.distances,
        }


def qualify(score: Any, payload: Any) -> Qualification:
    try:
        value = float(score) if score is not None else None
    except (TypeError, ValueError):
        value = None
    evidence = tuple(sorted(payload_reasons(payload)))
    n = len(evidence)
    route: str | None = None
    qualifies = False
    if value is not None:
        if value >= POLICY_HIGH_SCORE:
            qualifies, route = True, "STOCK_INTELLIGENCE_HIGH_SCORE"
        elif value >= POLICY_DISCOVERY_SCORE and n >= 1:
            qualifies, route = True, "STOCK_INTELLIGENCE_DISCOVERY_COMBINATION"
        elif value < POLICY_DISCOVERY_SCORE and n >= 2:
            qualifies, route = True, "MULTI_DOMAIN_DISCOVERY_COMBINATION"
    distances = {
        "high_score_points_below_70": None if value is None else round(max(0.0, POLICY_HIGH_SCORE - value), 6),
        "discovery_score_points_below_60": None if value is None else round(max(0.0, POLICY_DISCOVERY_SCORE - value), 6),
        "discovery_evidence_domains_missing": max(0, 1 - n),
        "multi_domain_evidence_domains_missing": max(0, 2 - n),
    }
    return Qualification(value, evidence, qualifies, route, distances)


def candidate_rows_by_run(run_ids: set[str]) -> tuple[dict[tuple[str, str], dict[str, Any]], list[str]]:
    from sqlalchemy import text
    from trading_ai.database.session import SessionLocal

    out: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[str] = []
    if not run_ids:
        return out, errors
    try:
        with SessionLocal() as session:
            for run_id in sorted(run_ids):
                try:
                    rows = session.execute(text("""
                        SELECT symbol, score, payload_json
                        FROM stock_scanner_candidates
                        WHERE scanner_run_id=:run_id
                    """), {"run_id": run_id}).mappings()
                    for row in rows:
                        sym = normalize_symbol(row.get("symbol"))
                        out[(run_id, sym)] = {
                            "score": row.get("score"),
                            "payload_json": row.get("payload_json") if isinstance(row.get("payload_json"), dict) else {},
                        }
                except Exception as exc:
                    session.rollback()
                    errors.append(f"scanner_run={run_id}: {type(exc).__name__}: {exc}")
    except Exception as exc:
        errors.append(f"database_connection: {type(exc).__name__}: {exc}")
    return out, errors


def day_in_range(value: Any, start: date, end: date) -> bool:
    try:
        d = date.fromisoformat(str(value))
        return start <= d <= end
    except Exception:
        return False


def actionable_occurrences(cert_rows: list[dict[str, Any]], start: date, end: date, symbols: set[str] | None) -> list[dict[str, Any]]:
    out = []
    for row in cert_rows:
        if row.get("mode") != "PROSPECTIVE_EXCLUSION_BASELINE":
            continue
        if not row.get("certification_eligible", row.get("market_session", False)):
            continue
        if not day_in_range(row.get("market_date"), start, end):
            continue
        comp = row.get("prospective_comparison") or {}
        for detail in comp.get("details") or []:
            classes = set(detail.get("classifications") or [])
            if detail.get("severity") != "ACTIONABLE_MISS" and "ACTIONABLE_MISS" not in classes:
                continue
            sym = normalize_symbol(detail.get("symbol"))
            if symbols and sym not in symbols:
                continue
            out.append({"row": row, "detail": detail, "symbol": sym})
    return out


def shadow_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(x.get("generated_at")): x
        for x in rows
        if x.get("mode") == "SHADOW_INTRADAY_DECISION" and x.get("generated_at")
    }


def shadow_candidate(
    shadow: dict[str, Any] | None,
    symbol: str,
    candidates: dict[tuple[str, str], dict[str, Any]],
) -> tuple[Qualification | None, dict[str, Any]]:
    if not shadow:
        return None, {"status": "MISSING_SHADOW_SNAPSHOT"}
    run_id = str(shadow.get("stock_scanner_run_id") or "")
    row = candidates.get((run_id, symbol))
    if row is None:
        return None, {"status": "MISSING_SCANNER_CANDIDATE", "scanner_run_id": run_id or None}
    q = qualify(row.get("score"), row.get("payload_json"))
    return q, {"status": "AVAILABLE", "scanner_run_id": run_id, **q.as_dict()}


def classify_occurrence(prev_q: Qualification | None, cur_q: Qualification | None) -> tuple[str, bool | None, str]:
    if prev_q is None or cur_q is None:
        return "UNRESOLVED_EVIDENCE", None, "Historical scanner evidence is incomplete; fail closed and do not infer causality."
    if prev_q.qualifies:
        return (
            "INITIAL_ADMISSION_BLIND_SPOT",
            True,
            "The symbol satisfied a direct frozen Policy 1.3 admission route at the prior decision but remained excluded.",
        )
    if cur_q.qualifies:
        return (
            "DYNAMIC_ADMISSION_BLIND_SPOT",
            True,
            "The symbol did not qualify at the prior decision, later satisfied a direct frozen Policy 1.3 route, and was still excluded when actionability was observed.",
        )
    return (
        "LEGITIMATE_LATE_EMERGENCE",
        False,
        "Neither the prior nor current scanner snapshot satisfied a direct frozen Policy 1.3 admission route; actionability emerged without a prospectively qualifying policy signal.",
    )


def build_report(start: date, end: date, symbols: set[str] | None = None) -> dict[str, Any]:
    cert_rows = load_jsonl(CERT_HISTORY)
    shadows = load_jsonl(SHADOW_HISTORY)
    sidx = shadow_index(shadows)
    occurrences = actionable_occurrences(cert_rows, start, end, symbols)

    run_ids: set[str] = set()
    for item in occurrences:
        comp = item["row"].get("prospective_comparison") or {}
        for ts in (comp.get("previous_shadow_generated_at"), comp.get("current_shadow_generated_at")):
            shadow = sidx.get(str(ts))
            if shadow and shadow.get("stock_scanner_run_id"):
                run_ids.add(str(shadow["stock_scanner_run_id"]))
    candidates, db_errors = candidate_rows_by_run(run_ids)

    results: list[dict[str, Any]] = []
    classification_counts: Counter[str] = Counter()
    per_symbol: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for item in occurrences:
        row, detail, sym = item["row"], item["detail"], item["symbol"]
        comp = row.get("prospective_comparison") or {}
        prev_ts = str(comp.get("previous_shadow_generated_at") or "")
        cur_ts = str(comp.get("current_shadow_generated_at") or "")
        prev_shadow = sidx.get(prev_ts)
        cur_shadow = sidx.get(cur_ts)
        prev_q, prev_evidence = shadow_candidate(prev_shadow, sym, candidates)
        cur_q, cur_evidence = shadow_candidate(cur_shadow, sym, candidates)
        classification, knowable, rationale = classify_occurrence(prev_q, cur_q)
        classification_counts[classification] += 1
        per_symbol[sym][classification] += 1

        current_evidence = (row.get("evidence") or {}).get(sym) or {}
        opportunity = current_evidence.get("opportunity") or {}
        prev_active = bool(prev_shadow and sym in set(prev_shadow.get("proposed_active_symbols") or []))
        cur_active = bool(cur_shadow and sym in set(cur_shadow.get("proposed_active_symbols") or []))
        prior_exclusion_reason = (
            "QUALIFIED_BUT_EXCLUDED_INCONSISTENCY" if prev_q and prev_q.qualifies
            else "NO_DIRECT_POLICY_QUALIFIER_AT_PRIOR_DECISION" if prev_q is not None
            else "UNRESOLVED_PRIOR_SCANNER_EVIDENCE"
        )

        results.append({
            "symbol": sym,
            "market_date": row.get("market_date"),
            "observation_timestamp": row.get("generated_at"),
            "trigger_window_start": prev_ts or None,
            "trigger_window_end": cur_ts or None,
            "actionability_trigger_first_observed_at": row.get("generated_at"),
            "latest_opportunity_timestamp": opportunity.get("latest_opportunity_timestamp"),
            "actionability_reasons": detail.get("reasons") or [],
            "entered_states": detail.get("entered_states") or [],
            "actionable_stage_delta": detail.get("actionable_stage_delta") or {},
            "prior_shadow_active": prev_active,
            "current_shadow_active": cur_active,
            "prior_exclusion_reason": prior_exclusion_reason,
            "prior_selection_evidence": prev_evidence,
            "current_selection_evidence": cur_evidence,
            "prospectively_knowable": knowable,
            "classification": classification,
            "classification_rationale": rationale,
        })

    recurring = []
    total_by_symbol = Counter(x["symbol"] for x in results)
    for sym, n in total_by_symbol.most_common():
        recurring.append({
            "symbol": sym,
            "actionable_occurrences": n,
            "classifications": dict(sorted(per_symbol[sym].items())),
        })

    unresolved = classification_counts.get("UNRESOLVED_EVIDENCE", 0)
    return {
        "version": VERSION,
        "mode": "READ_ONLY_HISTORICAL_PROSPECTIVE_FORENSICS",
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "symbol_filter": sorted(symbols) if symbols else None,
        "policy": {
            "name": "INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3.x",
            "frozen": True,
            "high_score_threshold": POLICY_HIGH_SCORE,
            "discovery_score_threshold": POLICY_DISCOVERY_SCORE,
            "production_effect": False,
            "threshold_change": False,
        },
        "actionable_occurrence_count": len(results),
        "unique_actionable_symbols": len(total_by_symbol),
        "classification_counts": dict(sorted(classification_counts.items())),
        "recurring_symbols": recurring,
        "database_errors": db_errors,
        "forensic_gate": "INCOMPLETE" if unresolved or db_errors else "READY",
        "occurrences": results,
    }


def print_human(report: dict[str, Any]) -> None:
    print("=== INTRADAY ACTIONABLE-MISS FORENSICS ===")
    print(f"range={report['start_date']}..{report['end_date']} occurrences={report['actionable_occurrence_count']} unique={report['unique_actionable_symbols']} gate={report['forensic_gate']}")
    counts = report.get("classification_counts") or {}
    print("classification_counts=" + ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))
    print("\n=== RECURRING SYMBOLS ===")
    for row in report.get("recurring_symbols") or []:
        print(f"{row['symbol']} occurrences={row['actionable_occurrences']} classifications={row['classifications']}")
    print("\n=== OCCURRENCES ===")
    for row in report.get("occurrences") or []:
        prev = row.get("prior_selection_evidence") or {}
        cur = row.get("current_selection_evidence") or {}
        print(
            f"{row['observation_timestamp'][:19]} {row['symbol']} classification={row['classification']} "
            f"knowable={row['prospectively_knowable']} prior_score={prev.get('score')} prior_evidence={prev.get('evidence_domain_count')} "
            f"current_score={cur.get('score')} current_evidence={cur.get('evidence_domain_count')}"
        )
        print("  trigger=" + ";".join(row.get("actionability_reasons") or []))
        print("  prior_distance=" + json.dumps(prev.get("distance_to_threshold"), sort_keys=True))
        print("  current_distance=" + json.dumps(cur.get("distance_to_threshold"), sort_keys=True))
    if report.get("database_errors"):
        print("\n=== DATABASE ERRORS (FORENSICS INCOMPLETE) ===")
        for err in report["database_errors"]:
            print("  " + err)


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only forensic decomposition of intraday actionable misses.")
    ap.add_argument("--start-date", required=True, type=date.fromisoformat)
    ap.add_argument("--end-date", required=True, type=date.fromisoformat)
    ap.add_argument("--symbols", help="Optional comma-separated symbol filter")
    ap.add_argument("--json-output", type=Path, help="Optional JSON report path")
    args = ap.parse_args()
    if args.end_date < args.start_date:
        raise SystemExit("--end-date must be >= --start-date")
    symbols = {normalize_symbol(x) for x in args.symbols.split(",") if x.strip()} if args.symbols else None
    report = build_report(args.start_date, args.end_date, symbols)
    print_human(report)
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2, default=str) + "\n")
        print(f"\njson_output={args.json_output}")


if __name__ == "__main__":
    main()
