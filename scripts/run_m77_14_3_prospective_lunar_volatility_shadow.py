#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.historical_underlying_replay.astronomical_cycles import features

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "reports/m77/m77_14_3_lunar_forward_shadow"
LATEST = DIR / "latest.json"
HISTORY = DIR / "history.jsonl"

VERSION = "M77.14.3.1-PROSPECTIVE-LUNAR-VOLATILITY-SHADOW-1.0"

TARGET = "NDX"
FALLBACK = "QQQ"
HORIZON = 10
HYPOTHESIS = "FIRST_QUARTER_WINDOW"
OUTCOME = "ABSOLUTE_RETURN"
EXPECTED_DIRECTION = "SUPPRESSED_10D_ABSOLUTE_MOVE"

# Frozen historical reference from M77.14.2.
HISTORICAL_EVENT_MEAN = 0.022805432403945603
HISTORICAL_COMPLEMENT_MEAN = 0.03030143129180395
HISTORICAL_INCREMENTAL = -0.007495998887858346

MIN_COMPLETED_EPISODES_FOR_REVIEW = 12
LAUNCH_PARTIAL_EPISODE_ID = "FIRST_QUARTER_WINDOW:2026-08-19"

def utcnow():
    return datetime.now(timezone.utc).isoformat()

def resolve_symbol(session):
    for sym in (TARGET, FALLBACK, "I:" + TARGET):
        if session.execute(
            text("SELECT 1 FROM price_history WHERE symbol=:s LIMIT 1"),
            {"s": sym},
        ).scalar():
            return sym
    return None

def latest_price_rows(session, symbol):
    return [
        (r[0], float(r[1]))
        for r in session.execute(
            text(
                "SELECT date,close FROM price_history "
                "WHERE symbol=:s AND close IS NOT NULL ORDER BY date"
            ),
            {"s": symbol},
        )
    ]

def load_history():
    if not HISTORY.exists():
        return []
    out = []
    for line in HISTORY.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out

def episode_id_for(session_date: date):
    # Deterministic cluster id: contiguous event sessions map to the same first-quarter episode.
    # Walk backward until prior day no longer satisfies the frozen event window.
    d = session_date
    while True:
        prev = date.fromordinal(d.toordinal() - 1)
        if not features(prev).get(HYPOTHESIS):
            break
        d = prev
    return f"{HYPOTHESIS}:{d.isoformat()}"

def current_regime(session_date):
    p = ROOT / "reports/m77/m77_8_daily_pit_regime_snapshots.json"
    if not p.exists():
        return None
    x = json.loads(p.read_text())
    rows = x if isinstance(x, list) else x.get("snapshots") or x.get("rows") or []
    for r in reversed(rows):
        if str(r.get("as_of"))[:10] == session_date.isoformat():
            return r.get("regime")
    return None

def capture():
    DIR.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as session:
        symbol = resolve_symbol(session)
        if not symbol:
            raise SystemExit("NDX/QQQ price history unavailable")
        rows = latest_price_rows(session, symbol)

    if not rows:
        raise SystemExit("No price history available")

    session_date, close = rows[-1]
    feat = features(session_date)
    event_active = bool(feat.get(HYPOTHESIS))
    eid = episode_id_for(session_date) if event_active else None

    history = load_history()
    duplicate = any(
        x.get("mode") == "CAPTURE"
        and x.get("session_date") == session_date.isoformat()
        and x.get("hypothesis") == HYPOTHESIS
        for x in history
    )

    out = {
        "version": VERSION,
        "status": "READY",
        "mode": "CAPTURE",
        "generated_at": utcnow(),
        "session_date": session_date.isoformat(),
        "target": TARGET,
        "price_symbol": symbol,
        "hypothesis": HYPOTHESIS,
        "event_active": event_active,
         "episode_id": eid,
        "episode_eligibility": (
            "PARTIAL_LAUNCH_EPISODE"
            if eid == LAUNCH_PARTIAL_EPISODE_ID
            else ("CERTIFICATION_ELIGIBLE" if event_active else None)
        ),
        "counts_toward_review_gate": bool(event_active and eid != LAUNCH_PARTIAL_EPISODE_ID),
        "entry_close": close if event_active else None,
        "horizon_sessions": HORIZON,
        "outcome": OUTCOME,
        "prediction": EXPECTED_DIRECTION if event_active else None,
        "historical_reference": {
            "event_mean": HISTORICAL_EVENT_MEAN,
            "complement_mean": HISTORICAL_COMPLEMENT_MEAN,
            "incremental": HISTORICAL_INCREMENTAL,
        },
        "pit_regime": current_regime(session_date),
        "lunar_phase_angle_deg": feat.get("lunar_phase_angle_deg"),
        "lunar_illumination": feat.get("lunar_illumination"),
        "idempotent_duplicate": duplicate,
        "production_authority_effect": False,
        "production_model_or_weight_change": False,
    }

    LATEST.write_text(json.dumps(out, indent=2) + "\n")
    if not duplicate:
        with HISTORY.open("a") as f:
            f.write(json.dumps(out) + "\n")
    return out

def mature():
    DIR.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as session:
        symbol = resolve_symbol(session)
        if not symbol:
            raise SystemExit("NDX/QQQ price history unavailable")
        rows = latest_price_rows(session, symbol)

    index_by_date = {d: i for i, (d, _) in enumerate(rows)}
    close_by_date = {d: c for d, c in rows}
    history = load_history()

    captures = [
        x for x in history
        if x.get("mode") == "CAPTURE"
        and x.get("event_active")
        and x.get("episode_id")
    ]
    completed_episode_ids = {
        x.get("episode_id")
        for x in history
        if x.get("mode") == "MATURED"
    }

    matured = []
    waiting = 0

    # One primary evaluation per episode: earliest captured session in cluster.
    earliest = {}
    for x in captures:
        eid = x["episode_id"]
        if eid not in earliest or x["session_date"] < earliest[eid]["session_date"]:
            earliest[eid] = x

    for eid, x in sorted(earliest.items()):
        if eid in completed_episode_ids:
            continue
        d = date.fromisoformat(x["session_date"])
        if d not in index_by_date:
            waiting += 1
            continue
        i = index_by_date[d]
        j = i + HORIZON
        if j >= len(rows):
            waiting += 1
            continue
        exit_date, exit_close = rows[j]
        realized_abs = abs(exit_close / float(x["entry_close"]) - 1.0)
        record = {
            "version": VERSION,
            "status": "READY",
            "mode": "MATURED",
            "generated_at": utcnow(),
            "episode_id": eid,
             "entry_session": x["session_date"],
            "exit_session": exit_date.isoformat(),
            "episode_eligibility": x.get("episode_eligibility", "CERTIFICATION_ELIGIBLE"),
            "counts_toward_review_gate": bool(x.get("counts_toward_review_gate", True)),
            "entry_close": x["entry_close"],
            "exit_close": exit_close,
            "realized_10d_absolute_return": realized_abs,
            "historical_event_mean": HISTORICAL_EVENT_MEAN,
            "historical_complement_mean": HISTORICAL_COMPLEMENT_MEAN,
            "suppression_vs_historical_complement": realized_abs < HISTORICAL_COMPLEMENT_MEAN,
            "pit_regime_at_entry": x.get("pit_regime"),
            "production_authority_effect": False,
        }
        matured.append(record)

    if matured:
        with HISTORY.open("a") as f:
            for r in matured:
                f.write(json.dumps(r) + "\n")
        LATEST.write_text(json.dumps(matured[-1], indent=2) + "\n")

    all_history = load_history()
    completed = [x for x in all_history if x.get("mode") == "MATURED"]
    eligible_completed = [x for x in completed if x.get("counts_toward_review_gate", True)]
    diagnostic_completed = [x for x in completed if not x.get("counts_toward_review_gate", True)]
    avg = None
    if eligible_completed:
        avg = sum(x["realized_10d_absolute_return"] for x in eligible_completed) / len(eligible_completed)

    summary = {
        "version": VERSION,
        "status": "READY",
        "mode": "MATURITY_SUMMARY",
        "generated_at": utcnow(),
        "matured_now": len(matured),
        "waiting_episode_count": waiting,
         "completed_episode_count": len(completed),
        "certification_eligible_completed_episode_count": len(eligible_completed),
        "diagnostic_completed_episode_count": len(diagnostic_completed),
        "prospective_mean_absolute_return": avg,
        "historical_event_mean": HISTORICAL_EVENT_MEAN,
        "historical_complement_mean": HISTORICAL_COMPLEMENT_MEAN,
         "minimum_completed_episodes_for_review": MIN_COMPLETED_EPISODES_FOR_REVIEW,
        "partial_launch_episode_excluded_from_gate": LAUNCH_PARTIAL_EPISODE_ID,
        "review_eligible": len(eligible_completed) >= MIN_COMPLETED_EPISODES_FOR_REVIEW,
        "production_authority_effect": False,
    }
    return summary

def preflight():
    with SessionLocal() as session:
        symbol = resolve_symbol(session)
    return {
        "version": VERSION,
        "status": "READY",
        "mode": "PREFLIGHT",
        "frozen_hypothesis": {
            "target": TARGET,
            "price_symbol": symbol,
            "hypothesis": HYPOTHESIS,
            "horizon_sessions": HORIZON,
            "outcome": OUTCOME,
            "prediction": EXPECTED_DIRECTION,
        },
        "minimum_completed_episodes_for_review": MIN_COMPLETED_EPISODES_FOR_REVIEW,
        "governance": {
            "research_only": True,
            "automatic_promotion": False,
            "production_authority_effect": False,
            "production_model_or_weight_change": False,
            "neighboring_search": False,
        },
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "capture", "mature", "cycle"))
    args = ap.parse_args()

    if args.mode == "preflight":
        out = preflight()
    elif args.mode == "capture":
        out = capture()
    elif args.mode == "mature":
        out = mature()
    else:
        c = capture()
        m = mature()
        out = {"capture": c, "maturity": m}

    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
