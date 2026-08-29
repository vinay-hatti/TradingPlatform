#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import statistics
from pathlib import Path
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/m77/m77_19_1_historical_reconstructibility_audit.json"
OUT = ROOT / "reports/m77/m77_19_1_multi_cadence_historical_reconstructibility_audit.json"

def write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def safe_text(path):
    try:
        return path.read_text(errors="ignore")
    except Exception:
        return ""

def discover(patterns):
    seen = set()
    out = []
    for pattern in patterns:
        for p in ROOT.glob(pattern):
            if p.is_file() and str(p) not in seen:
                seen.add(str(p))
                out.append(p)
    return sorted(out)

def analyze_runner(path):
    txt = safe_text(path)
    low = txt.lower()
    start_arg = bool(re.search(r'["\\\']--(?:start|start-date|from|from-date)["\\\']', txt, re.I))
    end_arg = bool(re.search(r'["\\\']--(?:end|end-date|through|through-date)["\\\']', txt, re.I))
    asof_arg = bool(re.search(r'["\\\']--(?:as-of|as_of)["\\\']', txt, re.I))
    return {
        "path": str(path.relative_to(ROOT)),
        "start_arg": start_arg,
        "end_arg": end_arg,
        "as_of_arg": asof_arg,
        "explicit_range_capable": start_arg and (end_arg or asof_arg),
        "mentions_point_in_time": any(k in low for k in ("point_in_time", "walk_forward", "as_of", "pit")),
        "mentions_replay_table": "historical_underlying_replay_prediction" in low,
    }

def load_json(rel):
    p = ROOT / rel
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}

def main():
    cfg = json.loads(CFG.read_text())
    runners = {
        k: [analyze_runner(p) for p in discover(v)]
        for k, v in cfg["runner_patterns"].items()
    }

    dm = load_json("reports/m77/m77_9_daily_model_replay_manifest.json")
    wm = load_json("reports/m77/m77_2_multiyear_frozen_champion_manifest.json")
    mm = load_json("reports/m77/m77_10_monthly_model_replay_manifest.json")

    daily_ids = [dm["replay_run_id"]] if dm.get("replay_run_id") else []
    weekly_ids = list(wm.get("replay_run_ids") or [])
    monthly_ids = [mm["replay_run_id"]] if mm.get("replay_run_id") else []

    with SessionLocal() as s:
        cohorts = {}
        for name, ids in (("daily", daily_ids), ("weekly", weekly_ids), ("monthly", monthly_ids)):
            if not ids:
                cohorts[name] = []
                continue
            rows = s.execute(text(
                "SELECT DISTINCT symbol "
                "FROM historical_underlying_replay_prediction "
                "WHERE replay_run_id = ANY(:ids) ORDER BY symbol"
            ), {"ids": ids}).scalars().all()
            cohorts[name] = [str(x) for x in rows]

        original = cohorts["daily"]
        common = set(original)
        if cohorts["weekly"]:
            common &= set(cohorts["weekly"])
        if cohorts["monthly"]:
            common &= set(cohorts["monthly"])

        coverage_rows = []
        if original:
            rows = s.execute(text(
                "SELECT symbol, count(*) AS rows, min(date) AS first_date, max(date) AS last_date "
                "FROM price_history WHERE symbol = ANY(:symbols) GROUP BY symbol"
            ), {"symbols": original}).mappings().all()
            coverage_rows = [{
                "symbol": str(r["symbol"]),
                "rows": int(r["rows"] or 0),
                "first_date": str(r["first_date"])[:10] if r["first_date"] else None,
                "last_date": str(r["last_date"])[:10] if r["last_date"] else None,
            } for r in rows]

    desired_start = cfg["target_history"]["desired_start"]
    desired_end = cfg["target_history"]["desired_end"]
    by_symbol = {r["symbol"]: r for r in coverage_rows}
    full = []
    starts = []
    rowcounts = []
    for sym in original:
        r = by_symbol.get(sym)
        if not r:
            continue
        if r["first_date"]:
            starts.append(r["first_date"])
        rowcounts.append(r["rows"])
        if r["first_date"] <= desired_start and r["last_date"] >= desired_end:
            full.append(sym)

    summary = {
        "original_daily_cohort_symbols": len(original),
        "weekly_symbols": len(cohorts["weekly"]),
        "monthly_symbols": len(cohorts["monthly"]),
        "daily_weekly_monthly_common_symbols": len(common),
        "symbols_with_any_price_history": len(coverage_rows),
        "symbols_covering_full_desired_range": len(full),
        "full_range_pct_of_original": round(100.0 * len(full) / len(original), 3) if original else 0.0,
        "earliest_price_start_across_original": min(starts) if starts else None,
        "median_price_rows": statistics.median(rowcounts) if rowcounts else None,
        "full_range_symbol_sample": full[:25],
    }

    def range_capable(kind):
        return any(r["explicit_range_capable"] for r in runners[kind])

    gates = {
        "original_cross_sectional_universe_recoverable": len(original) >= 590 and len(common) >= 580,
        "material_long_history_price_coverage_for_original_universe": (
            len(full) >= int(0.90 * len(original)) if original else False
        ),
        "weekly_replay_runner_historical_range_capable": range_capable("weekly"),
        "daily_replay_runner_historical_range_capable": range_capable("daily"),
        "monthly_replay_runner_historical_range_capable": range_capable("monthly"),
        "pit_regime_runner_historical_range_capable": range_capable("pit"),
        "all_replay_computation_point_in_time_certified": False,
        "proxy_only_substitution_rejected": True,
        "no_fabricated_pit_regimes": True,
    }

    blockers = []
    if not gates["original_cross_sectional_universe_recoverable"]:
        blockers.append("ORIGINAL_CROSS_SECTIONAL_UNIVERSE_NOT_RECOVERABLE")
    if not gates["material_long_history_price_coverage_for_original_universe"]:
        blockers.append("INSUFFICIENT_23_YEAR_PRICE_HISTORY_FOR_ORIGINAL_CROSS_SECTIONAL_UNIVERSE")
    gate_key_by_kind = {
        "weekly": "weekly_replay_runner_historical_range_capable",
        "daily": "daily_replay_runner_historical_range_capable",
        "monthly": "monthly_replay_runner_historical_range_capable",
        "pit": "pit_regime_runner_historical_range_capable",
    }
    for kind, gate_key in gate_key_by_kind.items():
        if not gates[gate_key]:
            blockers.append(kind.upper() + "_HISTORICAL_RANGE_RUNNER_NOT_DEMONSTRATED")
    blockers.append("POINT_IN_TIME_REPLAY_SEMANTICS_REQUIRE_DEEP_CODE_AUDIT")

    authorized = all(gates.values())

    out = {
        "version": cfg["version"],
        "status": "READY",
        "mode": "READ_ONLY_RECONSTRUCTIBILITY_AUDIT",
        "historical_universe_and_price_coverage": summary,
        "runner_discovery": runners,
        "gates": gates,
        "exact_long_history_reconstruction_authorized": authorized,
        "blockers": blockers,
        "interpretation": {
            "three_proxy_authority_is_exact_replication": False,
            "reason": "M77.11/M77.12 are cross-sectional studies over roughly 600 symbols; SPY/QQQ_LINEAGE/IWM-only evidence would answer a different research question."
        },
        "next_step": (
            "BUILD_M77_19_2_DEEP_REPLAY_PIT_RECONSTRUCTIBILITY_AUDIT"
            if not authorized else
            "BUILD_ISOLATED_LONG_HISTORY_REPLAY_AUTHORITIES"
        ),
        "database_writes": False,
        "production_authority_effect": False,
    }
    write_json_atomic(OUT, out)
    print(json.dumps({
        "version": out["version"],
        "status": "READY",
        "historical_universe_and_price_coverage": summary,
        "gates": gates,
        "exact_long_history_reconstruction_authorized": authorized,
        "blockers": blockers,
        "next_step": out["next_step"],
        "production_authority_effect": False,
    }, indent=2))

if __name__ == "__main__":
    main()
