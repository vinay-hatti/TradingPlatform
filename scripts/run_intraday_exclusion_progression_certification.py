#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text
from trading_ai.database.session import SessionLocal
from intraday_market_session import market_session_info

ROOT = Path(__file__).resolve().parents[1]
SHADOW_LATEST = ROOT / "reports/market_ingestion/intraday_active_universe_shadow/latest.json"
CERT_DIR = ROOT / "reports/market_ingestion/intraday_exclusion_progression"
CERT_LATEST = CERT_DIR / "latest.json"
CERT_HISTORY = CERT_DIR / "history.jsonl"

VERSION = "INTRADAY-EXCLUSION-PROGRESSION-CERTIFICATION-1.1.1"

DOWNSTREAM_TABLES = (
    "institutional_option_strategy_candidates",
    "institutional_option_contract_recommendations",
    "institutional_option_strategy_valuations",
    "institutional_option_decision_snapshots",
    "institutional_option_execution_recommendations",
    "institutional_option_handoffs",
)

TERMINAL_OPPORTUNITY_STATES = {
    "RETIRED", "CLOSED", "SUPERSEDED", "REJECTED", "EXPIRED",
}

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

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

def table_exists(session, table: str) -> bool:
    return bool(session.execute(text(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name=:t"
    ), {"t": table}).scalar())

def columns(session, table: str) -> set[str]:
    return set(session.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=:t"
    ), {"t": table}).scalars())

def opportunity_rows(session) -> list[dict[str, Any]]:
    table = "institutional_option_opportunities"
    if not table_exists(session, table):
        return []
    c = columns(session, table)
    select = ["opportunity_id", "symbol"]
    state_col = next((x for x in ("state", "status", "lifecycle_state", "disposition") if x in c), None)
    updated_col = next((x for x in ("updated_at", "created_at", "snapshot_timestamp") if x in c), None)
    if state_col:
        select.append(f'"{state_col}" AS lifecycle_state')
    else:
        select.append("NULL::text AS lifecycle_state")
    if updated_col:
        select.append(f'"{updated_col}" AS lifecycle_timestamp')
    else:
        select.append("NULL::text AS lifecycle_timestamp")
    q = text(f"SELECT {','.join(select)} FROM {table} WHERE symbol IS NOT NULL")
    return [dict(x) for x in session.execute(q).mappings()]

def opportunity_map(session) -> tuple[dict[str, str], dict[str, dict[str, Any]]]:
    oid_to_symbol: dict[str, str] = {}
    per_symbol: dict[str, dict[str, Any]] = {}
    for r in opportunity_rows(session):
        sym = normalize_symbol(r.get("symbol"))
        oid = str(r.get("opportunity_id") or "")
        state = str(r.get("lifecycle_state") or "").upper()
        ts = r.get("lifecycle_timestamp")
        if oid:
            oid_to_symbol[oid] = sym
        item = per_symbol.setdefault(sym, {
            "opportunity_count": 0,
            "nonterminal_opportunity_count": 0,
            "states": set(),
            "latest_opportunity_timestamp": None,
        })
        item["opportunity_count"] += 1
        if state not in TERMINAL_OPPORTUNITY_STATES:
            item["nonterminal_opportunity_count"] += 1
        if state:
            item["states"].add(state)
        if ts is not None:
            st = str(ts)
            if item["latest_opportunity_timestamp"] is None or st > item["latest_opportunity_timestamp"]:
                item["latest_opportunity_timestamp"] = st
    for item in per_symbol.values():
        item["states"] = sorted(item["states"])
    return oid_to_symbol, per_symbol

def stage_counts(session, oid_to_symbol: dict[str, str]) -> tuple[dict[str, dict[str, int]], dict[str, str]]:
    by_symbol: dict[str, dict[str, int]] = defaultdict(dict)
    availability: dict[str, str] = {}
    for table in DOWNSTREAM_TABLES:
        if not table_exists(session, table):
            availability[table] = "MISSING"
            continue
        c = columns(session, table)
        availability[table] = "AVAILABLE"
        stage_key = table.replace("institutional_option_", "")
        counts: dict[str, int] = defaultdict(int)
        try:
            if "symbol" in c:
                for r in session.execute(text(
                    f'SELECT symbol, count(*) AS n FROM "{table}" '
                    "WHERE symbol IS NOT NULL GROUP BY symbol"
                )).mappings():
                    counts[normalize_symbol(r["symbol"])] += int(r["n"])
            elif "opportunity_id" in c:
                for r in session.execute(text(
                    f'SELECT opportunity_id, count(*) AS n FROM "{table}" '
                    "WHERE opportunity_id IS NOT NULL GROUP BY opportunity_id"
                )).mappings():
                    sym = oid_to_symbol.get(str(r["opportunity_id"]))
                    if sym:
                        counts[sym] += int(r["n"])
            else:
                availability[table] = "UNUSABLE_NO_SYMBOL_OR_OPPORTUNITY_ID"
                continue
        except Exception:
            session.rollback()
            availability[table] = "QUERY_FAILED"
            continue
        for sym, n in counts.items():
            by_symbol[sym][stage_key] = n
    return dict(by_symbol), availability

def authoritative_safety_symbols(session) -> tuple[set[str], set[str]]:
    positions, orders = set(), set()
    try:
        for x in session.execute(text("""
          SELECT DISTINCT symbol FROM broker_current_positions
          WHERE active IS TRUE AND COALESCE(signed_quantity,0) <> 0 AND closed_at IS NULL
        """)).scalars():
            if x: positions.add(normalize_symbol(x))
    except Exception:
        session.rollback()
    try:
        for x in session.execute(text("""
          SELECT DISTINCT symbol FROM portfolio_positions
          WHERE COALESCE(quantity,0) <> 0
            AND UPPER(COALESCE(status,'')) NOT IN
            ('CLOSED','EXITED','CANCELLED','CANCELED','REJECTED','EXPIRED','SUPERSEDED','FLAT')
        """)).scalars():
            if x: positions.add(normalize_symbol(x))
    except Exception:
        session.rollback()
    try:
        for x in session.execute(text("""
          SELECT DISTINCT symbol FROM broker_orders
          WHERE symbol IS NOT NULL AND COALESCE(remaining_quantity,0) > 0
            AND UPPER(COALESCE(status,'')) NOT IN
            ('FILLED','CLOSED','CANCELLED','CANCELED','REJECTED','EXPIRED','SUPERSEDED')
        """)).scalars():
            if x: orders.add(normalize_symbol(x))
    except Exception:
        session.rollback()
    try:
        for x in session.execute(text("""
          SELECT DISTINCT symbol FROM execution_intents
          WHERE symbol IS NOT NULL AND terminal_at IS NULL
            AND UPPER(COALESCE(state,'')) NOT IN
            ('FILLED','CLOSED','CANCELLED','CANCELED','REJECTED','EXPIRED','SUPERSEDED')
        """)).scalars():
            if x: orders.add(normalize_symbol(x))
    except Exception:
        session.rollback()
    return positions, orders

def current_snapshot() -> dict[str, Any]:
    shadow = load_json(SHADOW_LATEST)
    if shadow.get("version") not in {"INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3","INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3.1"}:
        raise SystemExit("Latest active-universe shadow is not policy 1.3.x")
    if shadow.get("mode") != "SHADOW_INTRADAY_DECISION":
        raise SystemExit("Latest active-universe shadow is not an intraday decision snapshot")

    excluded = {normalize_symbol(x) for x in shadow.get("proposed_excluded_symbols") or []}
    active = {normalize_symbol(x) for x in shadow.get("proposed_active_symbols") or []}

    with SessionLocal() as session:
        oid_map, opp = opportunity_map(session)
        stages, availability = stage_counts(session, oid_map)
        positions, orders = authoritative_safety_symbols(session)

    evidence = {}
    for sym in sorted(excluded | active):
        evidence[sym] = {
            "excluded": sym in excluded,
            "opportunity": opp.get(sym, {
                "opportunity_count": 0,
                "nonterminal_opportunity_count": 0,
                "states": [],
                "latest_opportunity_timestamp": None,
            }),
            "stages": stages.get(sym, {}),
            "open_position_now": sym in positions,
            "working_order_now": sym in orders,
        }

    generated_at=utcnow()
    session_info=market_session_info(shadow.get("generated_at") or generated_at)
    return {
        "version": VERSION,
        "status": "READY" if session_info["market_session"] else "DIAGNOSTIC",
        "mode": "PROSPECTIVE_EXCLUSION_BASELINE",
        "generated_at": generated_at,
        **session_info,
        "certification_eligible": session_info["market_session"],
        "source_shadow_generated_at": shadow.get("generated_at"),
        "source_stock_scanner_run_id": shadow.get("stock_scanner_run_id"),
        "canonical_symbols": shadow.get("canonical_symbols"),
        "active_symbols": len(active),
        "excluded_symbols": len(excluded),
        "excluded_symbol_list": sorted(excluded),
        "stage_table_availability": availability,
        "evidence": evidence,
        "production_effect": False,
    }

def previous_snapshot() -> dict[str, Any] | None:
    if not CERT_HISTORY.exists():
        return None
    rows = []
    for line in CERT_HISTORY.read_text().splitlines():
        try:
            x = json.loads(line)
            if x.get("mode") == "PROSPECTIVE_EXCLUSION_BASELINE" and x.get("certification_eligible", x.get("market_session", True)):
                rows.append(x)
        except Exception:
            pass
    return rows[-1] if rows else None

ACTIONABLE_STATES = {"READY_FOR_EXECUTION"}
SOFT_STATES = {"VALIDATED", "CONTRACTS_OPTIMIZED"}
NOISE_STAGE_KEYS = {"strategy_candidates", "contract_recommendations", "strategy_valuations"}
ACTIONABLE_STAGE_KEYS = {"decision_snapshots", "execution_recommendations", "handoffs"}

def compare(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    prior_excluded=set(previous.get("excluded_symbol_list") or [])
    prev_ev=previous.get("evidence") or {}; cur_ev=current.get("evidence") or {}
    details=[]; safety=set(); actionable=set(); soft=set(); noise=set(); dynamic_success=set()
    for sym in sorted(prior_excluded):
        p=prev_ev.get(sym) or {}; c=cur_ev.get(sym) or {}; cls=[]; reasons=[]
        currently_excluded=bool(c.get("excluded", False))
        dynamically_admitted=not currently_excluded
        if not p.get("open_position_now") and c.get("open_position_now"):
            if dynamically_admitted:
                cls.append("DYNAMIC_ADMISSION_SUCCESS"); reasons.append("ADMITTED_BEFORE_OPEN_POSITION")
            else:
                cls.append("SAFETY_MISS"); reasons.append("BECAME_OPEN_POSITION"); safety.add(sym)
        if not p.get("working_order_now") and c.get("working_order_now"):
            if dynamically_admitted:
                cls.append("DYNAMIC_ADMISSION_SUCCESS"); reasons.append("ADMITTED_BEFORE_WORKING_ORDER")
            else:
                cls.append("SAFETY_MISS"); reasons.append("BECAME_WORKING_ORDER"); safety.add(sym)
        po=p.get("opportunity") or {}; co=c.get("opportunity") or {}
        prev_states=set(po.get("states") or []); curr_states=set(co.get("states") or [])
        entered=sorted(curr_states-prev_states)
        ae=sorted(set(entered)&ACTIONABLE_STATES); se=sorted(set(entered)&SOFT_STATES)
        if ae:
            if dynamically_admitted:
                cls.append("DYNAMIC_ADMISSION_SUCCESS"); reasons.append("ADMITTED_BEFORE_ACTIONABLE_STATE:"+",".join(ae))
            else:
                cls.append("ACTIONABLE_MISS"); reasons.append("ENTERED_ACTIONABLE_STATE:"+",".join(ae)); actionable.add(sym)
        elif se:
            cls.append("SOFT_PROGRESSION"); reasons.append("ENTERED_SOFT_STATE:"+",".join(se)); soft.add(sym)
        if int(co.get("nonterminal_opportunity_count") or 0)>int(po.get("nonterminal_opportunity_count") or 0):
            reasons.append("NEW_NONTERMINAL_OPPORTUNITY")
            if not ae and not se and sym not in safety:
                cls.append("SOFT_PROGRESSION"); soft.add(sym)
        ps=p.get("stages") or {}; cs=c.get("stages") or {}; delta={}
        for stage in sorted(set(ps)|set(cs)):
            before=int(ps.get(stage) or 0); after=int(cs.get(stage) or 0)
            if after>before: delta[stage]=after-before
        ad={k:v for k,v in delta.items() if k in ACTIONABLE_STAGE_KEYS}
        nd={k:v for k,v in delta.items() if k in NOISE_STAGE_KEYS}
        if ad and not (prev_states&ACTIONABLE_STATES):
            if dynamically_admitted:
                cls.append("DYNAMIC_ADMISSION_SUCCESS"); reasons.append("ADMITTED_BEFORE_ACTIONABLE_STAGE:"+",".join(sorted(ad)))
            else:
                cls.append("ACTIONABLE_MISS"); reasons.append("NEW_ACTIONABLE_STAGE:"+",".join(sorted(ad))); actionable.add(sym)
        if delta and not cls:
            cls.append("NOISE"); reasons.append("RECOMPUTATION_ONLY"); noise.add(sym)
        if "DYNAMIC_ADMISSION_SUCCESS" in cls:
            dynamic_success.add(sym)
        if cls or reasons:
            severity=("SAFETY_MISS" if "SAFETY_MISS" in cls else "ACTIONABLE_MISS" if "ACTIONABLE_MISS" in cls else "DYNAMIC_ADMISSION_SUCCESS" if "DYNAMIC_ADMISSION_SUCCESS" in cls else "SOFT_PROGRESSION" if "SOFT_PROGRESSION" in cls else "NOISE")
            details.append({"symbol":sym,"severity":severity,"classifications":sorted(set(cls)),"reasons":reasons,
              "entered_states":entered,"previous_opportunity_states":sorted(prev_states),"current_opportunity_states":sorted(curr_states),
              "stage_delta":delta,"actionable_stage_delta":ad,"noise_stage_delta":nd})
    fail=sorted(safety|actionable)
    return {"previous_shadow_generated_at":previous.get("source_shadow_generated_at"),
      "current_shadow_generated_at":current.get("source_shadow_generated_at"),"prior_excluded_symbols_examined":len(prior_excluded),
      "safety_miss_count":len(safety),"safety_miss_symbols":sorted(safety),
      "actionable_miss_count":len(actionable),"actionable_miss_symbols":sorted(actionable),
      "soft_progression_count":len(soft),"soft_progression_symbols":sorted(soft),
      "recomputation_noise_count":len(noise),"recomputation_noise_symbols":sorted(noise),
      "dynamic_admission_success_count":len(dynamic_success),"dynamic_admission_success_symbols":sorted(dynamic_success),
      "certification_fail_count":len(fail),"certification_fail_symbols":fail,"details":details,
      "gate":"PASS" if not fail else "FAIL"}

def persist(snapshot: dict[str, Any]) -> dict[str, Any]:
    CERT_DIR.mkdir(parents=True, exist_ok=True)
    previous = previous_snapshot()
    if not snapshot.get("certification_eligible", True):
        snapshot["prospective_comparison"] = {
            "gate":"NON_MARKET_SESSION_DIAGNOSTIC",
            "prior_excluded_symbols_examined":0,
            "safety_miss_count":0,
            "actionable_miss_count":0,
            "soft_progression_count":0,
            "recomputation_noise_count":0,
            "dynamic_admission_success_count":0,
            "certification_fail_count":0,
            "certification_fail_symbols":[],
        }
    elif previous:
        snapshot["prospective_comparison"] = compare(previous, snapshot)
    else:
        snapshot["prospective_comparison"] = {
            "gate": "BASELINE_ONLY",
            "prior_excluded_symbols_examined": 0,
            "safety_miss_count": 0, "actionable_miss_count": 0, "soft_progression_count": 0, "recomputation_noise_count": 0, "certification_fail_count": 0, "certification_fail_symbols": [],
        }

    snapshot["policy_sha256"] = hashlib.sha256(
        json.dumps({
            "version": VERSION,
            "shadow_policy": "INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3",
            "downstream_tables": DOWNSTREAM_TABLES,
        }, sort_keys=True).encode()
    ).hexdigest()

    CERT_LATEST.write_text(json.dumps(snapshot, indent=2, default=str) + "\n")
    with CERT_HISTORY.open("a") as f:
        f.write(json.dumps(snapshot, default=str) + "\n")
    return snapshot

def eod_check() -> dict[str, Any]:
    shadow=load_json(SHADOW_LATEST)
    generated_at=utcnow()
    info=market_session_info(shadow.get("generated_at") or generated_at)
    non_session=not info["market_session"]
    ready=shadow.get("mode")=="SHADOW_EOD_FULL_UNIVERSE_AUTHORITY" and bool(shadow.get("eod_authority_ready")) and not non_session
    out={
        "version":VERSION,"generated_at":generated_at,"mode":"EOD_RESEARCH_AUTHORITY_CHECK",
        **info,"certification_eligible":not non_session,
        "source_shadow_version":shadow.get("version"),"source_shadow_mode":shadow.get("mode"),
        "eod_authority_ready":bool(shadow.get("eod_authority_ready")) if not non_session else False,
        "research_authority_eligible":bool(shadow.get("research_authority_eligible")) if not non_session else False,
        "reported_option_symbol_coverage":shadow.get("reported_option_symbol_coverage"),
        "canonical_symbols":shadow.get("canonical_symbols"),
        "gate":"NON_MARKET_SESSION_DIAGNOSTIC" if non_session else ("PASS" if ready else "FAIL"),
        "production_effect":False,
    }
    CERT_DIR.mkdir(parents=True,exist_ok=True)
    with CERT_HISTORY.open("a") as f:
        f.write(json.dumps(out,default=str)+"\n")
    CERT_LATEST.write_text(json.dumps(out,indent=2,default=str)+"\n")
    return out

def preflight() -> dict[str, Any]:
    return {
        "version": VERSION,
        "status": "READY",
        "mode": "PREFLIGHT",
        "required_shadow_policy": "INTRADAY-ACTIVE-UNIVERSE-SHADOW-1.3.x",
        "downstream_tables": list(DOWNSTREAM_TABLES),
        "certification_rule": "MARKET_SESSION_ONLY; DYNAMIC_ADMISSION_IS_SUCCESS; FAIL_CLOSED_ON_STILL_EXCLUDED_ACTIONABLE_OR_SAFETY_PROGRESSION",
        "production_effect": False,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("preflight", "cycle", "eod"))
    args = ap.parse_args()
    if args.mode == "preflight":
        out = preflight()
    elif args.mode == "eod":
        out = eod_check()
    else:
        out = persist(current_snapshot())
    print(json.dumps(out, indent=2, default=str))

if __name__ == "__main__":
    main()
