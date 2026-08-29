#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from pathlib import Path
from statistics import mean

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.stock_intelligence.service import StockIntelligenceService
from trading_ai.stock_intelligence.publication_service import StockIntelligencePublicationService

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/m77/m77_19_6_isolated_replay_engine_parity.json"
OUT = ROOT / "reports/m77/m77_19_6_isolated_replay_engine_parity_certification.json"

def write_json_atomic(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def load_json(rel):
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"M77.19.6 blocked: missing {rel}")
    return json.loads(p.read_text())

def normalized_path(root: Path, symbol: str) -> Path:
    return root / f"{symbol.replace('/','_')}_daily.csv"

def load_symbol_rows(root: Path, symbol: str) -> list[dict]:
    p = normalized_path(root, symbol)
    if not p.exists():
        raise FileNotFoundError(p)
    out = []
    with p.open(newline="") as f:
        for r in csv.DictReader(f):
            try:
                out.append({
                    "date": date.fromisoformat(r["date"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"] or 0),
                })
            except Exception:
                continue
    out.sort(key=lambda x: x["date"])
    return out

def continuity(rows):
    starts = [0]
    for i in range(1, len(rows)):
        p, c = rows[i-1], rows[i]
        gap = (c["date"] - p["date"]).days
        ratio = c["close"] / p["close"] if p["close"] else 1
        if gap > 45 or ratio > 4 or ratio < .25:
            starts.append(i)
    idx = starts[-1]
    return rows[idx]["date"], rows[idx:], len(starts)-1

def engine_rows(rows):
    return [{**r, "date": r["date"].isoformat()} for r in rows]

def timeframes(rows):
    d = engine_rows(rows)
    return {
        "1d": d,
        "1w": StockIntelligencePublicationService._aggregate(d, "week"),
        "1mo": StockIntelligencePublicationService._aggregate(d, "month"),
    }

def cadence_select(dates, cadence):
    if cadence == "DAILY":
        return sorted(dates)
    if cadence == "WEEKLY":
        last = {d.isocalendar()[:2]: d for d in dates}
        return sorted(last.values())
    if cadence == "MONTHLY":
        last = {(d.year, d.month): d for d in dates}
        return sorted(last.values())
    raise ValueError(cadence)

def isolated_profile(service, rows, as_of, session_set, warmup=300, history_rows=750):
    _, segment, _ = continuity(rows)
    valid = [r for r in segment if r["date"] in session_set and r["date"].weekday() < 5]
    if len(valid) < warmup:
        return None
    eligible_from = valid[warmup-1]["date"]
    if as_of < eligible_from:
        return None
    index = {r["date"]: i for i, r in enumerate(valid)}
    if as_of not in index:
        return None
    pos = index[as_of]
    history = valid[max(0, pos-(history_rows-1)):pos+1]
    profile = service.analyze(
        None,
        timeframes(history),
        snapshot_timestamp=f"{as_of.isoformat()}T20:00:00+00:00",
        external_context={},
        symbol_override=None,
    )
    return profile

def call_profile(service, symbol, rows, as_of, session_set, warmup, history_rows):
    """
    Preserve original service call semantics. Some installed StockIntelligenceService
    versions accept analyze(symbol, timeframes, ...), while newer compatible versions
    may expose symbol_override. Try the canonical historical signature first.
    """
    _, segment, _ = continuity(rows)
    valid = [r for r in segment if r["date"] in session_set and r["date"].weekday() < 5]
    if len(valid) < warmup:
        return None
    eligible_from = valid[warmup-1]["date"]
    if as_of < eligible_from:
        return None
    index = {r["date"]: i for i, r in enumerate(valid)}
    if as_of not in index:
        return None
    pos = index[as_of]
    history = valid[max(0, pos-(history_rows-1)):pos+1]
    tf = timeframes(history)
    try:
        return service.analyze(
            symbol,
            tf,
            snapshot_timestamp=f"{as_of.isoformat()}T20:00:00+00:00",
            external_context={},
        )
    except TypeError:
        return service.analyze(
            tf,
            snapshot_timestamp=f"{as_of.isoformat()}T20:00:00+00:00",
            external_context={},
            symbol_override=symbol,
        )

def stored_rows(session, cadence, manifests):
    if cadence == "DAILY":
        rid = manifests["daily"]["replay_run_id"]
        return session.execute(text("""
            SELECT replay_run_id,as_of,symbol,direction,overall_score,confidence,state_hash
            FROM historical_underlying_replay_prediction
            WHERE replay_run_id=:rid
            ORDER BY symbol,as_of
        """), {"rid": rid}).mappings().all()
    if cadence == "MONTHLY":
        rid = manifests["monthly"]["replay_run_id"]
        return session.execute(text("""
            SELECT replay_run_id,as_of,symbol,direction,overall_score,confidence,state_hash
            FROM historical_underlying_replay_prediction
            WHERE replay_run_id=:rid
            ORDER BY symbol,as_of
        """), {"rid": rid}).mappings().all()
    ids = list(manifests["weekly"].get("replay_run_ids") or [])
    return session.execute(text("""
        SELECT replay_run_id,as_of,symbol,direction,overall_score,confidence,state_hash
        FROM historical_underlying_replay_prediction
        WHERE replay_run_id = ANY(:ids)
        ORDER BY symbol,as_of
    """), {"ids": ids}).mappings().all()

def deterministic_sample(rows, n_symbols, n_dates):
    by = defaultdict(list)
    for r in rows:
        by[str(r["symbol"])].append(dict(r))
    symbols = sorted(by)
    if not symbols:
        return []
    # Spread symbols deterministically across the alphabetically sorted frozen cohort.
    if len(symbols) <= n_symbols:
        chosen = symbols
    else:
        idxs = sorted(set(round(i*(len(symbols)-1)/(n_symbols-1)) for i in range(n_symbols)))
        chosen = [symbols[i] for i in idxs]
    out = []
    for sym in chosen:
        rs = sorted(by[sym], key=lambda x: str(x["as_of"]))
        if not rs:
            continue
        if len(rs) <= n_dates:
            picks = rs
        else:
            idxs = sorted(set(round(i*(len(rs)-1)/(n_dates-1)) for i in range(n_dates)))
            picks = [rs[i] for i in idxs]
        out.extend(picks)
    return out

def compare_profile(profile, stored):
    scores = getattr(profile, "scores", None)
    score = float(getattr(scores, "overall", 0.0) if scores else 0.0)
    confidence = float(getattr(profile, "confidence", 0.0))
    direction = str(getattr(profile, "direction", ""))
    state_hash = getattr(profile, "state_hash", None)
    return {
        "direction_match": direction == str(stored["direction"]),
        "score_abs_error": abs(score - float(stored["overall_score"] or 0.0)),
        "confidence_abs_error": abs(confidence - float(stored["confidence"] or 0.0)),
        "state_hash_match": state_hash == stored["state_hash"],
        "isolated": {
            "direction": direction,
            "overall_score": score,
            "confidence": confidence,
            "state_hash": state_hash,
        },
        "stored": {
            "direction": stored["direction"],
            "overall_score": float(stored["overall_score"] or 0.0),
            "confidence": float(stored["confidence"] or 0.0),
            "state_hash": stored["state_hash"],
        },
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "certify"))
    args = ap.parse_args()
    cfg = json.loads(CFG.read_text())

    source_cert = load_json(cfg["source_authority"]["certification"])
    if not source_cert.get("certified_for_m77_19_6_reconstruction"):
        raise SystemExit("M77.19.6 blocked: M77.19.5 source authority not certified")

    manifests = {
        k: load_json(v) for k, v in cfg["frozen_manifests"].items()
    }
    root = ROOT / cfg["source_authority"]["root"]

    with SessionLocal() as session:
        spy_dates = [
            x["date"] for x in load_symbol_rows(root, "SPY")
        ]
        session_set = set(spy_dates)

        counts = {}
        stored_by_cadence = {}
        for cadence in ("DAILY", "MONTHLY", "WEEKLY"):
            rows = stored_rows(session, cadence, manifests)
            stored_by_cadence[cadence] = rows
            counts[cadence] = len(rows)

        if args.mode == "preflight":
            print(json.dumps({
                "version": cfg["version"],
                "status": "READY",
                "m77_19_5_certified": True,
                "stored_prediction_counts": counts,
                "source_root": str(root),
                "parity_policy": cfg["parity_policy"],
                "database_writes": False,
                "production_authority_effect": False,
            }, indent=2))
            return

        svc = StockIntelligenceService()
        policy = cfg["parity_policy"]
        cadence_results = {}

        for cadence in ("DAILY", "MONTHLY", "WEEKLY"):
            sample = deterministic_sample(
                stored_by_cadence[cadence],
                policy["symbols"],
                policy["observations_per_cadence"],
            )
            evidence = []
            errors = []
            cache = {}
            for stored in sample:
                sym = str(stored["symbol"])
                as_of = stored["as_of"]
                if not isinstance(as_of, date):
                    as_of = date.fromisoformat(str(as_of)[:10])
                try:
                    rows = cache.get(sym)
                    if rows is None:
                        rows = load_symbol_rows(root, sym)
                        cache[sym] = rows
                    p1 = call_profile(
                        svc, sym, rows, as_of, session_set,
                        policy["authority_warmup_rows"],
                        policy["history_window_rows"],
                    )
                    p2 = call_profile(
                        svc, sym, rows, as_of, session_set,
                        policy["authority_warmup_rows"],
                        policy["history_window_rows"],
                    )
                    if p1 is None or p2 is None:
                        errors.append({"symbol": sym, "as_of": str(as_of), "error": "NOT_ELIGIBLE"})
                        continue
                    c1 = compare_profile(p1, stored)
                    c2 = compare_profile(p2, stored)
                    c1["symbol"] = sym
                    c1["as_of"] = str(as_of)
                    c1["deterministic_repeat"] = c1["isolated"] == c2["isolated"]
                    evidence.append(c1)
                except Exception as exc:
                    errors.append({
                        "symbol": sym,
                        "as_of": str(as_of),
                        "error": type(exc).__name__,
                        "message": str(exc)[:1000],
                    })

            n = len(evidence)
            direction_pct = (
                100.0 * sum(x["direction_match"] for x in evidence) / n
                if n else 0.0
            )
            state_pct = (
                100.0 * sum(x["state_hash_match"] for x in evidence) / n
                if n else 0.0
            )
            repeat_pct = (
                100.0 * sum(x["deterministic_repeat"] for x in evidence) / n
                if n else 0.0
            )
            max_score = max((x["score_abs_error"] for x in evidence), default=None)
            max_conf = max((x["confidence_abs_error"] for x in evidence), default=None)
            gates = {
                "minimum_comparisons": n >= policy["minimum_comparisons_per_cadence"],
                "direction_exact": direction_pct >= policy["direction_exact_required_pct"],
                "score_exact": max_score is not None and max_score <= policy["overall_score_max_abs_error"],
                "confidence_exact": max_conf is not None and max_conf <= policy["confidence_max_abs_error"],
                "state_hash_exact": (
                    state_pct == 100.0 if policy["state_hash_exact_required"] else True
                ),
                "deterministic_repeat": (
                    repeat_pct == 100.0 if policy["deterministic_repeat_required"] else True
                ),
            }
            cadence_results[cadence] = {
                "sample_requested": len(sample),
                "comparisons": n,
                "errors": errors,
                "direction_match_pct": direction_pct,
                "state_hash_match_pct": state_pct,
                "deterministic_repeat_pct": repeat_pct,
                "max_score_abs_error": max_score,
                "max_confidence_abs_error": max_conf,
                "gates": gates,
                "evidence": evidence,
                "pass": all(gates.values()),
            }

    certified = all(x["pass"] for x in cadence_results.values())
    result = {
        "version": cfg["version"],
        "status": "READY",
        "source_authority_certified": True,
        "cadence_results": cadence_results,
        "isolated_replay_engine_parity_certified": certified,
        "full_23_year_reconstruction_authorized": certified,
        "interpretation": (
            "Exact parity against frozen replay outputs demonstrated; long-history reconstruction may proceed."
            if certified else
            "Exact parity not demonstrated. Do not run the 23-year reconstruction until differences are resolved."
        ),
        "next_step": (
            "BUILD_M77_19_6_1_FULL_LONG_HISTORY_RECONSTRUCTION"
            if certified else
            "FORENSIC_REVIEW_M77_19_6_PARITY_DIFFERENCES"
        ),
        "database_writes": False,
        "production_authority_effect": False,
    }
    write_json_atomic(OUT, result)
    print(json.dumps({
        "version": result["version"],
        "status": "READY",
        "isolated_replay_engine_parity_certified": certified,
        "full_23_year_reconstruction_authorized": certified,
        "cadence_summary": {
            k: {
                "comparisons": v["comparisons"],
                "direction_match_pct": v["direction_match_pct"],
                "state_hash_match_pct": v["state_hash_match_pct"],
                "max_score_abs_error": v["max_score_abs_error"],
                "max_confidence_abs_error": v["max_confidence_abs_error"],
                "deterministic_repeat_pct": v["deterministic_repeat_pct"],
                "pass": v["pass"],
                "error_count": len(v["errors"]),
            }
            for k, v in cadence_results.items()
        },
        "next_step": result["next_step"],
        "production_authority_effect": False,
    }, indent=2))

if __name__ == "__main__":
    main()
