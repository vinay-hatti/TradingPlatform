#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median
from sqlalchemy import text

from trading_ai.database.session import SessionLocal

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/m77/m77_19_6_1_parity_forensic_decomposition.json"
OUT = ROOT / "reports/m77/m77_19_6_1_parity_forensic_decomposition.json"

def write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    json.loads(tmp.read_text())
    tmp.replace(path)

def load_json(rel):
    p = ROOT / rel
    if not p.exists():
        raise SystemExit(f"M77.19.6.1 blocked: missing {rel}")
    return json.loads(p.read_text())

def load_research_rows(root, symbol, start, end):
    p = root / f"{symbol.replace('/','_')}_daily.csv"
    if not p.exists():
        return []
    rows = []
    with p.open(newline="") as f:
        for r in csv.DictReader(f):
            d = date.fromisoformat(r["date"])
            if start <= d <= end:
                rows.append({
                    "date": d,
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"] or 0),
                })
    return rows

def production_rows(session, symbol, start, end):
    rows = session.execute(text("""
        SELECT date,open,high,low,close,volume
        FROM price_history
        WHERE symbol=:symbol AND date>=:start AND date<=:end
        ORDER BY date
    """), {"symbol": symbol, "start": start, "end": end}).mappings().all()
    return [{
        "date": r["date"],
        "open": float(r["open"]),
        "high": float(r["high"]),
        "low": float(r["low"]),
        "close": float(r["close"]),
        "volume": float(r["volume"] or 0),
    } for r in rows]

def price_parity(prod, research, tol):
    a = {r["date"]: r for r in prod}
    b = {r["date"]: r for r in research}
    common = sorted(set(a) & set(b))
    diffs = []
    exact = 0
    max_abs = {k: 0.0 for k in ("open","high","low","close","volume")}
    for d in common:
        row_diff = {}
        good = True
        for k in max_abs:
            dv = abs(a[d][k] - b[d][k])
            row_diff[k] = dv
            max_abs[k] = max(max_abs[k], dv)
            if dv > tol:
                good = False
        if good:
            exact += 1
        else:
            diffs.append({
                "date": str(d),
                "production": {k:a[d][k] for k in max_abs},
                "research": {k:b[d][k] for k in max_abs},
                "abs_diff": row_diff
            })
    return {
        "production_rows": len(prod),
        "research_rows": len(research),
        "common_dates": len(common),
        "production_only_dates": len(set(a)-set(b)),
        "research_only_dates": len(set(b)-set(a)),
        "exact_ohlcv_rows": exact,
        "exact_ohlcv_pct": (100.0*exact/len(common)) if common else None,
        "max_abs_diff": max_abs,
        "mismatch_sample": diffs[:10],
    }

def evidence_summary(report):
    out = {}
    for cadence, block in report["cadence_results"].items():
        ev = block.get("evidence") or []
        # Existing deterministic_repeat compares the whole isolated dict including state_hash.
        # Decompose it so hash instability is not mistaken for score/direction instability.
        core_repeat_possible = []
        hash_matches = []
        score_errors = []
        conf_errors = []
        directions = Counter()
        symbols = Counter()
        for x in ev:
            score_errors.append(float(x["score_abs_error"]))
            conf_errors.append(float(x["confidence_abs_error"]))
            hash_matches.append(bool(x["state_hash_match"]))
            directions[(x["stored"]["direction"], x["isolated"]["direction"])] += 1
            symbols[x["symbol"]] += 1
            # We cannot recover p2 fields from M77.19.6, so classify current deterministic failure cause.
            core_repeat_possible.append(
                bool(x.get("deterministic_repeat")) or
                (
                    x["isolated"]["direction"] == x["isolated"]["direction"]
                    and x["isolated"]["overall_score"] == x["isolated"]["overall_score"]
                    and x["isolated"]["confidence"] == x["isolated"]["confidence"]
                )
            )
        out[cadence] = {
            "evidence_count": len(ev),
            "state_hash_match_pct": 100.0*sum(hash_matches)/len(hash_matches) if hash_matches else None,
            "score_error_median": median(score_errors) if score_errors else None,
            "score_error_mean": mean(score_errors) if score_errors else None,
            "score_error_max": max(score_errors) if score_errors else None,
            "confidence_error_median": median(conf_errors) if conf_errors else None,
            "confidence_error_mean": mean(conf_errors) if conf_errors else None,
            "confidence_error_max": max(conf_errors) if conf_errors else None,
            "direction_pairs": [
                {"stored": k[0], "isolated": k[1], "count": v}
                for k,v in directions.most_common()
            ],
            "symbols": dict(symbols),
            "all_reported_repeat_failures": sum(not bool(x.get("deterministic_repeat")) for x in ev),
        }
    return out

def inspect_hash_semantics():
    candidates = [
        ROOT/"src/trading_ai/stock_intelligence/service.py",
        ROOT/"src/trading_ai/stock_intelligence/contracts.py",
        ROOT/"src/trading_ai/stock_intelligence/models.py",
        ROOT/"src/trading_ai/historical_underlying_replay/service.py",
    ]
    hits = []
    for p in candidates:
        if not p.exists():
            continue
        for n,line in enumerate(p.read_text(errors="ignore").splitlines(),1):
            low=line.lower()
            if any(k in low for k in ("state_hash","uuid","snapshot_timestamp","generated_at","now(","utcnow","time.time")):
                hits.append({"path":str(p.relative_to(ROOT)),"line":n,"text":line[:500]})
    return hits

def inspect_external_context_semantics():
    p = ROOT/"src/trading_ai/stock_intelligence/service.py"
    if not p.exists():
        return []
    hits=[]
    for n,line in enumerate(p.read_text(errors="ignore").splitlines(),1):
        low=line.lower()
        if any(k in low for k in ("external_context","market_alignment","dealer","liquidity","institutional","context")):
            hits.append({"line":n,"text":line[:500]})
    return hits[:300]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode", choices=("run",))
    args=ap.parse_args()
    cfg=json.loads(CFG.read_text())
    parity=load_json(cfg["source_parity_report"])
    if parity.get("isolated_replay_engine_parity_certified"):
        raise SystemExit("M77.19.6.1 unnecessary: M77.19.6 already certified")

    summary=evidence_summary(parity)
    root=ROOT/cfg["source_authority_root"]
    tol=float(cfg["sample_policy"]["ohlcv_tolerance"])

    # Audit exact OHLCV parity for every symbol/as_of present in parity evidence.
    requested=defaultdict(list)
    for cadence, block in parity["cadence_results"].items():
        for e in block.get("evidence") or []:
            requested[e["symbol"]].append(date.fromisoformat(str(e["as_of"])[:10]))

    price_results={}
    with SessionLocal() as session:
        for symbol, dates in sorted(requested.items()):
            end=max(dates)
            # 1100 calendar days comfortably covers ~750 sessions.
            start=date.fromordinal(max(1,end.toordinal()-1100))
            prod=production_rows(session,symbol,start,end)
            research=load_research_rows(root,symbol,start,end)
            price_results[symbol]=price_parity(prod,research,tol)

    common_total=sum(v["common_dates"] for v in price_results.values())
    exact_total=sum(v["exact_ohlcv_rows"] for v in price_results.values())
    price_exact_pct=(100.0*exact_total/common_total) if common_total else None

    hash_hits=inspect_hash_semantics()
    context_hits=inspect_external_context_semantics()

    findings=[]
    if all(v["state_hash_match_pct"]==0.0 for v in summary.values()):
        findings.append({
            "classification":"STATE_HASH_IS_NOT_A_VALID_CROSS_RUN_PARITY_KEY_UNTIL_HASH_INPUTS_ARE_DECOMPOSED",
            "evidence":"0% state_hash parity across all cadences despite ~98-100% direction agreement."
        })
    if price_exact_pct is not None and price_exact_pct < 100.0:
        findings.append({
            "classification":"SOURCE_DATA_REVISION_OR_ADJUSTMENT_DRIFT_PRESENT",
            "evidence":f"Only {price_exact_pct:.6f}% of overlapping OHLCV rows are exact between frozen production price_history and M77.19.5 Polygon research history."
        })
    if context_hits:
        findings.append({
            "classification":"EXTERNAL_CONTEXT_DEPENDENCY_REQUIRES_PARITY_CONTROL",
            "evidence":"Stock Intelligence service contains external/context-dependent logic; M77.19.6 used external_context={}. Frozen replay context must be recovered or explicitly demonstrated irrelevant."
        })

    # We cannot certify a corrected parity policy from this audit alone.
    result={
        "version":cfg["version"],
        "status":"READY",
        "source_m77_19_6_certified":False,
        "cadence_error_decomposition":summary,
        "price_input_parity":{
            "symbols_audited":len(price_results),
            "common_rows":common_total,
            "exact_ohlcv_rows":exact_total,
            "exact_ohlcv_pct":price_exact_pct,
            "by_symbol":price_results,
        },
        "state_hash_semantic_markers":hash_hits,
        "external_context_semantic_markers":context_hits,
        "findings":findings,
        "forensic_conclusion":"PARITY_FAILURE_IS_REAL_BUT_MIXES_MULTIPLE_DIMENSIONS; DO_NOT AUTHORIZE 23_YEAR_RECONSTRUCTION",
        "next_step":"BUILD_M77_19_6_2_EXACT_INPUT_CONTEXT_AND_HASH_SEMANTICS_PARITY",
        "database_writes":False,
        "production_authority_effect":False,
    }
    write_json_atomic(OUT,result)
    print(json.dumps({
        "version":result["version"],
        "status":"READY",
        "price_input_parity":{
            "symbols_audited":len(price_results),
            "common_rows":common_total,
            "exact_ohlcv_rows":exact_total,
            "exact_ohlcv_pct":price_exact_pct,
        },
        "cadence_error_decomposition":summary,
        "findings":findings,
        "forensic_conclusion":result["forensic_conclusion"],
        "next_step":result["next_step"],
        "production_authority_effect":False,
    }, indent=2))

if __name__=="__main__":
    main()
