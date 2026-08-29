#!/usr/bin/env python3
"""
M77.19.6.4.1 — Replay Authority Resolution & Adapter Recovery

Corrects M77.19.6.4 table-selection semantics.

M77.19.6.4 incorrectly allowed a run-level table such as
historical_underlying_replay_run to serve as the replay-observation source.
This patch resolves replay authorities semantically using:
  * required observation columns,
  * row counts,
  * cadence/timeframe fields where available,
  * source-name hints only as a secondary signal,
  * filesystem frozen replay artifacts as a governed fallback.

Database remains READ ONLY.  Production behavior is unchanged.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

VERSION = "M77.19.6.4.1-REPLAY-AUTHORITY-RESOLUTION-ADAPTER-RECOVERY-1.0"
CADENCES = ("DAILY", "WEEKLY", "MONTHLY")
DEFAULT_SAMPLE_PER_CADENCE = 48

OBSERVATION_FIELD_GROUPS = {
    "symbol": ("symbol", "ticker"),
    "date": ("as_of_date", "replay_date", "date", "session_date", "snapshot_date", "bar_date"),
    "direction": ("direction", "trend_direction", "stock_direction"),
    "score": ("overall_score", "score", "stock_score"),
    "confidence": ("confidence", "confidence_score"),
}
OPTIONAL_FIELDS = {
    "cadence": ("cadence", "timeframe", "interval"),
    "state_hash": ("state_hash", "profile_hash"),
    "external_context": ("external_context", "context_json", "context"),
    "historical_regime": ("historical_regime", "market_regime", "regime"),
    "timestamp": ("snapshot_timestamp", "as_of_timestamp", "generated_at", "created_at", "timestamp"),
}


def jsonable(v: Any) -> Any:
    if isinstance(v, Mapping):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    if isinstance(v, (dt.date, dt.datetime)):
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


def require_prior(root: Path, explicit: str | None):
    candidates = [Path(explicit)] if explicit else []
    candidates.append(root / "reports" / "m77_19_6_4_exact_frozen_input_context_replay_adapter.json")
    for p in candidates:
        if not p.exists():
            continue
        d = load_json(p)
        if d.get("full_23_year_reconstruction_authorized") is True:
            raise SystemExit("FAIL CLOSED: unexpected 23-year authorization")
        if d.get("next_step") != "RESOLVE_M77_19_6_4_ADAPTER_BLOCKERS":
            raise SystemExit("FAIL CLOSED: prior report does not request adapter blocker resolution")
        return p, d
    raise SystemExit("FAIL CLOSED: M77.19.6.4 blocker report not found")


@contextlib.contextmanager
def readonly_session():
    from trading_ai.database.session import SessionLocal
    from sqlalchemy import text
    s = SessionLocal()
    try:
        s.execute(text("SET TRANSACTION READ ONLY"))
        yield s
        s.rollback()
    finally:
        s.close()


def qident(s: str) -> str:
    return '"' + s.replace('"', '""') + '"'


def split_table(full: str):
    return tuple(full.split(".", 1)) if "." in full else ("public", full)


def columns_for(session, full: str) -> list[str]:
    from sqlalchemy import text
    schema, table = split_table(full)
    rows = session.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema=:s AND table_name=:t
        ORDER BY ordinal_position
    """), {"s": schema, "t": table}).all()
    return [r[0] for r in rows]


def detect(cols: Sequence[str], candidates: Sequence[str]) -> str | None:
    m = {c.lower(): c for c in cols}
    for x in candidates:
        if x.lower() in m:
            return m[x.lower()]
    return None


def profile_table(session, full: str) -> dict[str, Any]:
    from sqlalchemy import text
    cols = columns_for(session, full)
    schema, table = split_table(full)
    qt = f"{qident(schema)}.{qident(table)}"
    try:
        count = int(session.execute(text(f"SELECT COUNT(*) FROM {qt}")).scalar_one())
    except Exception:
        count = -1

    fields = {}
    for role, candidates in {**OBSERVATION_FIELD_GROUPS, **OPTIONAL_FIELDS}.items():
        fields[role] = detect(cols, candidates)

    required_hits = sum(fields[k] is not None for k in OBSERVATION_FIELD_GROUPS)
    observation_capable = required_hits == len(OBSERVATION_FIELD_GROUPS)

    low = full.lower()
    run_level_penalty = 0
    if low.endswith("_run") or "replay_run" in low:
        run_level_penalty = 1000
    if "authority" in low and not observation_capable:
        run_level_penalty += 500

    name_bonus = 0
    if "prediction" in low: name_bonus += 100
    if "comparison" in low: name_bonus += 40
    if "cadence_state" in low or "cadence_states" in low: name_bonus += 80
    if "stock_intelligence" in low: name_bonus += 50

    semantic_score = (
        required_hits * 100
        + (30 if fields["cadence"] else 0)
        + (10 if fields["state_hash"] else 0)
        + (10 if fields["historical_regime"] else 0)
        + (5 if fields["external_context"] else 0)
        + name_bonus
        - run_level_penalty
    )

    return {
        "table": full,
        "columns": cols,
        "row_count": count,
        "fields": fields,
        "required_observation_fields_found": required_hits,
        "observation_capable": observation_capable,
        "semantic_score": semantic_score,
        "run_level_penalty": run_level_penalty,
    }


def all_candidate_tables(session) -> list[str]:
    from sqlalchemy import text
    rows = session.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog','information_schema')
        ORDER BY table_schema, table_name
    """)).all()
    out = []
    for schema, table in rows:
        full = f"{schema}.{table}"
        low = full.lower()
        if any(x in low for x in ("replay", "stock_intelligence", "m77", "cadence")):
            out.append(full)
    return out


def normalize_cadence(v: Any) -> str | None:
    s = str(v or "").strip().upper()
    aliases = {
        "DAILY": "DAILY", "1D": "DAILY", "D": "DAILY",
        "WEEKLY": "WEEKLY", "1W": "WEEKLY", "W": "WEEKLY",
        "MONTHLY": "MONTHLY", "1MO": "MONTHLY", "1M": "MONTHLY", "M": "MONTHLY",
    }
    return aliases.get(s)


def cadence_name_bonus(table: str, cadence: str) -> int:
    low = table.lower()
    hints = {
        "DAILY": ("daily", "1d", "m77_9"),
        "WEEKLY": ("weekly", "1w", "m77_2"),
        "MONTHLY": ("monthly", "1mo", "m77_10"),
    }[cadence]
    return 100 if any(h in low for h in hints) else 0


def cadence_counts(session, p: Mapping[str, Any]) -> dict[str, int]:
    from sqlalchemy import text
    col = p["fields"].get("cadence")
    if not col:
        return {}
    schema, table = split_table(p["table"])
    qt = f"{qident(schema)}.{qident(table)}"
    try:
        rows = session.execute(text(
            f"SELECT CAST({qident(col)} AS TEXT), COUNT(*) FROM {qt} GROUP BY 1"
        )).all()
    except Exception:
        return {}
    out = {}
    for value, count in rows:
        c = normalize_cadence(value)
        if c:
            out[c] = out.get(c, 0) + int(count)
    return out


def choose_db_authority(session, profiles: Sequence[Mapping[str, Any]], cadence: str):
    ranked = []
    for p in profiles:
        if not p["observation_capable"] or p["row_count"] <= 0:
            continue
        counts = cadence_counts(session, p)
        cadence_evidence = counts.get(cadence, 0)
        has_explicit_cadence = bool(p["fields"].get("cadence"))
        eligible = cadence_evidence > 0 or not has_explicit_cadence
        if not eligible:
            continue
        score = p["semantic_score"] + cadence_name_bonus(p["table"], cadence)
        if cadence_evidence > 0:
            score += min(200, cadence_evidence // 1000)
        ranked.append((score, cadence_evidence, p))
    ranked.sort(key=lambda x: (x[0], x[1], x[2]["row_count"]), reverse=True)
    return ranked[0][2] if ranked else None


def fetch_db_rows(session, p: Mapping[str, Any], cadence: str, limit: int):
    from sqlalchemy import text
    f = p["fields"]
    schema, table = split_table(p["table"])
    qt = f"{qident(schema)}.{qident(table)}"
    selected = []
    for role in ("symbol","date","direction","score","confidence","state_hash",
                 "external_context","historical_regime","timestamp","cadence"):
        c = f.get(role)
        if c and c not in selected:
            selected.append(c)

    where = ""
    params = {"lim": limit}
    if f.get("cadence"):
        aliases = {
            "DAILY": ("DAILY","1d","D"),
            "WEEKLY": ("WEEKLY","1w","W"),
            "MONTHLY": ("MONTHLY","1mo","1m","M"),
        }[cadence]
        clauses = []
        for i, val in enumerate(aliases):
            params[f"c{i}"] = val
            clauses.append(f"LOWER(CAST({qident(f['cadence'])} AS TEXT))=LOWER(:c{i})")
        where = "WHERE (" + " OR ".join(clauses) + ")"

    sql = text(f"""
        SELECT {", ".join(qident(c) for c in selected)}
        FROM {qt}
        {where}
        ORDER BY {qident(f["date"])} ASC, {qident(f["symbol"])} ASC
        LIMIT :lim
    """)
    return [dict(r) for r in session.execute(sql, params).mappings().all()]


def discover_filesystem_authorities(root: Path) -> list[Path]:
    out = []
    bases = [root/"reports", root/"research", root/"research_data", root/"artifacts"]
    for base in bases:
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".json",".jsonl",".csv"}:
                low = str(p).lower()
                if any(x in low for x in ("m77", "replay", "cadence", "stock_intelligence")):
                    out.append(p)
    return sorted(set(out))


def flatten_records(v: Any) -> list[dict[str, Any]]:
    out = []
    if isinstance(v, Mapping):
        keys = {str(k).lower() for k in v}
        has_symbol = any(x in keys for x in OBSERVATION_FIELD_GROUPS["symbol"])
        has_date = any(x in keys for x in OBSERVATION_FIELD_GROUPS["date"])
        has_direction = any(x in keys for x in OBSERVATION_FIELD_GROUPS["direction"])
        has_score = any(x in keys for x in OBSERVATION_FIELD_GROUPS["score"])
        has_conf = any(x in keys for x in OBSERVATION_FIELD_GROUPS["confidence"])
        if all((has_symbol,has_date,has_direction,has_score,has_conf)):
            out.append(dict(v))
        for x in v.values():
            out.extend(flatten_records(x))
    elif isinstance(v, list):
        for x in v:
            out.extend(flatten_records(x))
    return out


def load_file_records(path: Path) -> list[dict[str, Any]]:
    try:
        if path.suffix.lower() == ".json":
            return flatten_records(json.loads(path.read_text()))
        if path.suffix.lower() == ".jsonl":
            rows = []
            for line in path.read_text().splitlines():
                if line.strip():
                    rows.extend(flatten_records(json.loads(line)))
            return rows
        if path.suffix.lower() == ".csv":
            return [dict(r) for r in csv.DictReader(path.open())]
    except Exception:
        return []
    return []


def record_role(record: Mapping[str, Any], role: str):
    low = {str(k).lower(): k for k in record}
    candidates = (OBSERVATION_FIELD_GROUPS | OPTIONAL_FIELDS)[role]
    for c in candidates:
        if c.lower() in low:
            return record[low[c.lower()]]
    return None


def choose_file_rows(root: Path, cadence: str, limit: int):
    candidates = []
    for path in discover_filesystem_authorities(root):
        rows = load_file_records(path)
        if not rows:
            continue
        filtered = []
        for r in rows:
            c = normalize_cadence(record_role(r, "cadence"))
            low = str(path).lower()
            name_match = cadence_name_bonus(low, cadence) > 0
            if c == cadence or (c is None and name_match):
                filtered.append(r)
        if filtered:
            candidates.append((len(filtered), path, filtered))
    candidates.sort(key=lambda x: x[0], reverse=True)
    if not candidates:
        return None, []
    _, path, rows = candidates[0]
    return path, rows[:limit]


def normalize_observation(record: Mapping[str, Any], cadence: str) -> dict[str, Any]:
    return {
        "cadence": cadence,
        "symbol": record_role(record, "symbol"),
        "as_of": jsonable(record_role(record, "date")),
        "frozen_output": {
            "direction": jsonable(record_role(record, "direction")),
            "overall_score": jsonable(record_role(record, "score")),
            "confidence": jsonable(record_role(record, "confidence")),
            "state_hash": jsonable(record_role(record, "state_hash")),
        },
        "frozen_context": {
            "external_context": jsonable(record_role(record, "external_context")),
            "historical_regime": jsonable(record_role(record, "historical_regime")),
            "snapshot_timestamp": jsonable(record_role(record, "timestamp")),
        },
    }


def find_price_profile(session):
    candidates = []
    from sqlalchemy import text
    rows = session.execute(text("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog','information_schema')
          AND LOWER(table_name) LIKE '%price_history%'
        ORDER BY 1,2
    """)).all()
    for s,t in rows:
        full=f"{s}.{t}"
        cols=columns_for(session,full)
        symbol=detect(cols,("symbol","ticker"))
        date=detect(cols,("date","session_date","price_date","bar_date"))
        hits=sum(x in {c.lower() for c in cols} for x in ("open","high","low","close","volume"))
        if symbol and date:
            candidates.append((hits,full,cols,symbol,date))
    candidates.sort(reverse=True)
    return candidates[0] if candidates else None


def fetch_price_window(session, price_profile, symbol, as_of, bars=300):
    from sqlalchemy import text
    _, full, cols, symbol_col, date_col = price_profile
    schema,table=split_table(full)
    qt=f"{qident(schema)}.{qident(table)}"
    wanted=[c for c in cols if c.lower() in {symbol_col.lower(),date_col.lower(),"open","high","low","close","volume","adjusted_close","vwap"}]
    rows=session.execute(text(f"""
        SELECT {", ".join(qident(c) for c in wanted)}
        FROM {qt}
        WHERE {qident(symbol_col)}=:symbol
          AND {qident(date_col)}<=:as_of
        ORDER BY {qident(date_col)} DESC
        LIMIT :bars
    """),{"symbol":symbol,"as_of":as_of,"bars":bars}).mappings().all()
    return [dict(r) for r in reversed(rows)]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--project-root",default=".")
    ap.add_argument("--m77-19-6-4-report")
    ap.add_argument("--sample-per-cadence",type=int,default=DEFAULT_SAMPLE_PER_CADENCE)
    ap.add_argument("--output-root",default="research_data/m77_19_6_4_1/exact_frozen_input_context_bundles")
    ap.add_argument("--report",default="reports/m77_19_6_4_1_replay_authority_resolution_adapter_recovery.json")
    a=ap.parse_args()

    root=Path(a.project_root).resolve()
    prior_path,_=require_prior(root,a.m77_19_6_4_report)
    outroot=root/a.output_root
    outroot.mkdir(parents=True,exist_ok=True)

    report={
        "version":VERSION,
        "generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),
        "prior_report":str(prior_path),
        "governance":{
            "research_only":True,
            "database_mode":"READ_ONLY",
            "production_database_writes":False,
            "filesystem_research_artifacts_only":True,
            "parity_thresholds_relaxed":False,
            "controlled_exact_input_parity_certified":False,
            "full_23_year_reconstruction_authorized":False,
            "production_authority_effect":False,
        },
        "cadences":{},
        "blockers":[],
    }

    with readonly_session() as session:
        profiles=[profile_table(session,t) for t in all_candidate_tables(session)]
        report["replay_authority_profiles"]=profiles
        price_profile=find_price_profile(session)
        report["selected_price_history_table"]=price_profile[1] if price_profile else None
        if not price_profile:
            report["blockers"].append("PRICE_HISTORY_AUTHORITY_NOT_DISCOVERED")

        for cadence in CADENCES:
            dbp=choose_db_authority(session,profiles,cadence)
            source_type=None; source=None; rows=[]
            if dbp:
                rows=fetch_db_rows(session,dbp,cadence,a.sample_per_cadence)
                if rows:
                    source_type="DATABASE"; source=dbp["table"]

            if len(rows)<a.sample_per_cadence:
                fp,frows=choose_file_rows(root,cadence,a.sample_per_cadence)
                if len(frows)>len(rows):
                    source_type="FILESYSTEM_FROZEN_ARTIFACT"; source=str(fp.relative_to(root)); rows=frows

            cdir=outroot/cadence.lower()
            cdir.mkdir(parents=True,exist_ok=True)
            written=0; with_price=0; with_ctx=0; with_regime=0

            for i,row in enumerate(rows[:a.sample_per_cadence],1):
                obs=normalize_observation(row,cadence)
                prices=[]
                if price_profile and obs["symbol"] is not None and obs["as_of"] is not None:
                    prices=fetch_price_window(session,price_profile,obs["symbol"],obs["as_of"],300)
                bundle={
                    "adapter_version":VERSION,
                    "authority_source_type":source_type,
                    "authority_source":source,
                    **obs,
                    "price_history":jsonable(prices),
                    "price_row_count":len(prices),
                }
                bundle["price_history_sha256"]=sha256_json(bundle["price_history"])
                bundle["context_sha256"]=sha256_json(bundle["frozen_context"])
                bundle["bundle_semantic_sha256"]=sha256_json({
                    "cadence":bundle["cadence"],"symbol":bundle["symbol"],"as_of":bundle["as_of"],
                    "frozen_output":bundle["frozen_output"],"frozen_context":bundle["frozen_context"],
                    "price_history":bundle["price_history"],
                })
                safe_symbol=re.sub(r"[^A-Za-z0-9._-]+","_",str(bundle["symbol"]))
                safe_date=re.sub(r"[^A-Za-z0-9._-]+","_",str(bundle["as_of"]))
                path=cdir/f"{i:03d}_{safe_symbol}_{safe_date}.json"
                path.write_text(json.dumps(bundle,indent=2,sort_keys=True,default=str)+"\n")
                written+=1
                with_price += bool(prices)
                with_ctx += bundle["frozen_context"]["external_context"] is not None
                with_regime += bundle["frozen_context"]["historical_regime"] is not None

            report["cadences"][cadence]={
                "authority_source_type":source_type,
                "authority_source":source,
                "rows_recovered":len(rows),
                "bundles_written":written,
                "bundles_with_price_history":with_price,
                "bundles_with_external_context":with_ctx,
                "bundles_with_historical_regime":with_regime,
            }
            if written<a.sample_per_cadence:
                report["blockers"].append(f"{cadence}_EXACT_BUNDLE_COUNT_BELOW_{a.sample_per_cadence}")
            if written and with_price<written:
                report["blockers"].append(f"{cadence}_PRICE_HISTORY_INCOMPLETE")

    ready=not report["blockers"]
    report["exact_frozen_input_context_adapter_ready"]=ready
    report["controlled_exact_input_parity_certified"]=False
    report["full_23_year_reconstruction_authorized"]=False
    report["production_authority_effect"]=False
    report["next_step"]="BUILD_M77_19_6_5_CONTROLLED_ADAPTER_EXECUTION_AND_PARITY_CERTIFICATION" if ready else "RESOLVE_M77_19_6_4_1_AUTHORITY_BLOCKERS"

    rp=root/a.report
    rp.parent.mkdir(parents=True,exist_ok=True)
    rp.write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")

    print("=== M77.19.6.4.1 REPLAY AUTHORITY RESOLUTION & ADAPTER RECOVERY ===")
    print("database_mode: READ_ONLY")
    print("parity_thresholds_relaxed: False")
    for c in CADENCES:
        print(c, report["cadences"][c])
    print("exact_frozen_input_context_adapter_ready:",ready)
    print("controlled_exact_input_parity_certified: False")
    print("full_23_year_reconstruction_authorized: False")
    print("production_authority_effect: False")
    if report["blockers"]:
        print("blockers:")
        for b in sorted(set(report["blockers"])): print(" -",b)
    print("next_step:",report["next_step"])
    print("report:",rp)

if __name__=="__main__":
    main()
